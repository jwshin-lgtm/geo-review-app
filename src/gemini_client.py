"""Gemini API 래퍼. JSON 구조화 출력을 강제하고, 실패 시 재시도한다."""
from __future__ import annotations

import json
import re
import threading
import time

from google import genai
from google.genai import types

from . import config

_clients_by_key_index: dict[int, genai.Client] = {}
# 여러 API 키를 등록했을 때, 마지막으로 성공했던(또는 아직 한도가 안 찬) 키부터
# 시작하도록 기억해둔다 - 매번 이미 소진된 첫 번째 키부터 다시 시도하며 시간을 버리지 않기 위함.
# 배치를 병렬로 처리하면서 여러 스레드가 동시에 건드릴 수 있으므로 락으로 보호한다.
_current_key_index = 0
_key_index_lock = threading.Lock()

# 병렬 처리(여러 원고/여러 배치 동시 처리)로 한꺼번에 너무 많은 요청을 쏘면
# gemini-3.6-flash 같은 분당 요청 수가 아주 낮은(5건) 모델에서 바로 걸린다.
# 동시에 나가는 Gemini 호출 자체를 적당히 제한해서 애초에 한도에 덜 걸리게 한다.
_CONCURRENT_CALL_LIMIT = 3
_concurrency_semaphore = threading.Semaphore(_CONCURRENT_CALL_LIMIT)

# 일시적 과부하 에러 - 몇 초 기다렸다가 다시 시도하면 대부분 해결됨
_TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "overloaded")

# 429/RESOURCE_EXHAUSTED에는 두 가지 전혀 다른 상황이 섞여 있다.
# - "PerDay" 한도: 그 날의 요청 가능 횟수를 이미 다 쓴 것 -> 재시도해도 절대 안 풀린다.
#   즉시 포기하고 다음 '키'로 넘어가야 한다.
# - "PerMinute" 한도: 1분짜리 짧은 속도 제한일 뿐이라, 서버가 알려주는 시간만큼
#   잠깐 기다리면 같은 키/모델로도 금방 다시 된다. 이걸 일일 한도와 똑같이 취급해서
#   즉시 포기하면, 동시에 여러 요청을 보낼 때(병렬 처리) 오히려 더 쉽게 실패한다.
_DAILY_QUOTA_MARKERS = ("PerDay",)
_RATE_LIMIT_MARKERS = ("PerMinute",)
_QUOTA_MARKERS = ("429", "RESOURCE_EXHAUSTED", "quota")
# 분당 한도에 걸릴 때마다 같은 조합으로 여러 번 재시도하면, 그 자체로 실제 API 호출
# 횟수를 몇 배로 불려서 한도를 더 빨리 소진시킨다. 1번만 기다렸다 재시도하고, 그래도
# 안 되면 바로 다음 모델/키 조합으로 넘어가는 게 전체 호출 수를 훨씬 줄인다.
_RATE_LIMIT_MAX_RETRIES = 1

# 모델 자체가 이 키/프로젝트에서 지원 종료(404)된 경우 - 재시도해도 절대 안 되므로
# 즉시 다음 모델로 넘어간다.
_NOT_FOUND_MARKERS = ("404", "NOT_FOUND")


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _TRANSIENT_MARKERS)


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _QUOTA_MARKERS)


def _is_daily_quota_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _DAILY_QUOTA_MARKERS)


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _RATE_LIMIT_MARKERS)


def _parse_retry_delay_seconds(exc: Exception, default: float = 10.0, cap: float = 30.0) -> float:
    """에러 메시지에 담긴 'retryDelay': '5s' 같은 값을 읽어 몇 초 기다려야 하는지 구한다."""
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)", str(exc))
    if not match:
        return default
    return min(float(match.group(1)), cap)


def _is_not_found_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _NOT_FOUND_MARKERS)


class GeminiQuotaExceededError(RuntimeError):
    """Gemini API 사용량 한도(일일 요청 수 등)를 초과했을 때 발생. 재시도로 해결되지 않는다."""


class GeminiModelNotFoundError(RuntimeError):
    """이 키/프로젝트에서 해당 모델을 더 이상 지원하지 않을 때 발생. 다른 모델로 넘어가야 한다."""


def _get_client_by_index(index: int) -> genai.Client:
    if index not in _clients_by_key_index:
        _clients_by_key_index[index] = genai.Client(api_key=config.GEMINI_API_KEYS[index])
    return _clients_by_key_index[index]


def _call_once(
    client: genai.Client,
    model: str,
    generation_config: types.GenerateContentConfig,
    user_content: str,
    max_retries: int,
):
    """키 하나 + 모델 하나 조합으로 호출하고, 일시적 에러(503 등)만 재시도한다.

    하루 한도(PerDay) 초과는 이 키로는 더 재시도해도 소용없으므로 즉시
    GeminiQuotaExceededError를 던져 호출측이 다음 키로 넘어가게 한다.
    분당 한도(PerMinute) 초과는 몇 초~수십 초만 기다리면 풀리므로, 서버가 알려준
    시간만큼 기다렸다가 같은 키/모델로 다시 시도한다 (병렬로 여러 요청을 보내면
    이 분당 한도에 가장 먼저 걸리기 쉽다).
    모델 지원 종료(404/NOT_FOUND)는 이 모델로는 절대 안 되므로 즉시
    GeminiModelNotFoundError를 던져 호출측이 다음 모델로 넘어가게 한다.
    """
    last_error: Exception | None = None
    rate_limit_retries_left = _RATE_LIMIT_MAX_RETRIES
    attempt = 0
    while True:
        try:
            with _concurrency_semaphore:
                response = client.models.generate_content(
                    model=model,
                    contents=user_content,
                    config=generation_config,
                )
        except Exception as exc:  # noqa: BLE001 - API 호출 자체의 실패 원인을 그대로 보존
            if _is_quota_error(exc) and _is_daily_quota_error(exc):
                raise GeminiQuotaExceededError(
                    f"Gemini API 사용량 한도를 초과했습니다: {exc}"
                ) from exc
            if _is_quota_error(exc) and _is_rate_limit_error(exc) and rate_limit_retries_left > 0:
                # 분당 한도는 배치 전환용 attempt 예산을 쓰지 않고 별도로 재시도한다.
                rate_limit_retries_left -= 1
                last_error = exc
                time.sleep(_parse_retry_delay_seconds(exc))
                continue
            if _is_not_found_error(exc):
                raise GeminiModelNotFoundError(
                    f"모델 '{model}'을(를) 이 키에서 지원하지 않습니다: {exc}"
                ) from exc
            last_error = exc
            if _is_transient_error(exc) and attempt < max_retries:
                time.sleep(2)  # 조합(키x모델)이 여러 개 있으므로, 한 조합에서 길게 기다리지 않고 짧게만 쉬었다 넘어간다
            if attempt >= max_retries:
                break
            attempt += 1
            continue

        finish_reason = None
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason

        if not response.text:
            last_error = RuntimeError(
                f"Gemini가 빈 응답을 반환했습니다 (finish_reason={finish_reason}). "
                "문서가 너무 길어 출력이 잘렸을 수 있습니다."
            )
            if attempt >= max_retries:
                break
            attempt += 1
            continue

        try:
            return json.loads(response.text)
        except json.JSONDecodeError as exc:
            last_error = RuntimeError(
                f"Gemini 응답을 JSON으로 파싱하지 못했습니다 (finish_reason={finish_reason}): {exc}"
            )
            if attempt >= max_retries:
                break
            attempt += 1
            continue

    raise RuntimeError(f"Gemini 호출 실패: {last_error}")


def generate_json(
    system_instruction: str,
    user_content: str,
    response_schema: dict | None = None,
    max_retries: int = 1,
    max_output_tokens: int = 32768,
):
    """Gemini에 JSON 응답을 요청하고 파싱해서 반환한다.

    response_schema는 Gemini의 responseSchema 형식(dict)을 그대로 전달한다.
    한 조합(키+모델)에서 max_retries만큼만 짧게 재시도하고, 그래도 안 되면 바로
    다음 모델/키 조합으로 넘어간다 (조합이 이미 여러 개이므로, 한 조합에 오래
    매달리는 대신 조합 전환 자체를 재시도 전략으로 쓴다 - 전체 대기 시간을 줄이기 위함).

    GEMINI_API_KEYS에 키가 여러 개 등록되어 있으면(팀원별로 무료 키를 나눠 등록한
    경우), 현재 키가 사용량 한도를 초과했을 때 자동으로 다음 키로 넘어가서 계속
    시도한다. GEMINI_MODELS에 등록된 모델(기본 모델 + 대체 모델들)도 한 모델이
    지원 종료(404)되거나 계속 과부하(503)이면 자동으로 다음 모델로 넘어간다.
    키 x 모델의 모든 조합이 실패해야 최종적으로 실패한다.
    """
    global _current_key_index

    keys = config.GEMINI_API_KEYS
    if not keys:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다. secrets.toml을 확인하세요.")
    models = config.GEMINI_MODELS

    generation_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=response_schema,
        max_output_tokens=max_output_tokens,
    )

    with _key_index_lock:
        start_index = _current_key_index

    last_error: Exception | None = None
    for offset in range(len(keys)):
        key_index = (start_index + offset) % len(keys)
        client = _get_client_by_index(key_index)
        quota_exceeded_for_key = False
        for model in models:
            try:
                result = _call_once(client, model, generation_config, user_content, max_retries)
            except GeminiQuotaExceededError as exc:
                last_error = exc
                quota_exceeded_for_key = True
                break  # 한도 초과는 모델을 바꿔도 소용없다 - 바로 다음 키로
            except Exception as exc:  # noqa: BLE001 - GeminiModelNotFoundError 및 그 외 실패 모두 다음 모델로
                last_error = exc
                continue
            with _key_index_lock:
                _current_key_index = key_index
            return result
        if quota_exceeded_for_key:
            continue

    raise RuntimeError(
        f"등록된 API 키 {len(keys)}개 x 모델 {len(models)}개 조합이 모두 실패했습니다: {last_error}"
    )
