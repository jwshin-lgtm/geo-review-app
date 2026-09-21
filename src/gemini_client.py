"""Gemini API 래퍼. JSON 구조화 출력을 강제하고, 실패 시 재시도한다."""
from __future__ import annotations

import json
import time

from google import genai
from google.genai import types

from . import config

_clients_by_key_index: dict[int, genai.Client] = {}
# 여러 API 키를 등록했을 때, 마지막으로 성공했던(또는 아직 한도가 안 찬) 키부터
# 시작하도록 기억해둔다 - 매번 이미 소진된 첫 번째 키부터 다시 시도하며 시간을 버리지 않기 위함.
_current_key_index = 0

# 일시적 과부하 에러 - 몇 초 기다렸다가 다시 시도하면 대부분 해결됨
_TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "overloaded")

# 사용량 한도(429/RESOURCE_EXHAUSTED) 초과는 "일시적"이 아니라 그 날의 요청 가능
# 횟수를 이미 다 쓴 것이므로, 재시도해봤자 같은 실패가 반복되며 남은 한도만 더 깎아먹는다.
# 즉시 포기하고 위로 명확히 알려야 한다.
_QUOTA_MARKERS = ("429", "RESOURCE_EXHAUSTED", "quota")


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _TRANSIENT_MARKERS)


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _QUOTA_MARKERS)


class GeminiQuotaExceededError(RuntimeError):
    """Gemini API 사용량 한도(일일 요청 수 등)를 초과했을 때 발생. 재시도로 해결되지 않는다."""


def _get_client_by_index(index: int) -> genai.Client:
    if index not in _clients_by_key_index:
        _clients_by_key_index[index] = genai.Client(api_key=config.GEMINI_API_KEYS[index])
    return _clients_by_key_index[index]


def _call_once(
    client: genai.Client,
    generation_config: types.GenerateContentConfig,
    user_content: str,
    max_retries: int,
):
    """키 하나로 호출하고, 일시적 에러(503 등)만 재시도한다.

    한도 초과(429/RESOURCE_EXHAUSTED)는 이 키로는 더 재시도해도 소용없으므로
    즉시 GeminiQuotaExceededError를 던져 호출측이 다음 키로 넘어가게 한다.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_content,
                config=generation_config,
            )
        except Exception as exc:  # noqa: BLE001 - API 호출 자체의 실패 원인을 그대로 보존
            if _is_quota_error(exc):
                raise GeminiQuotaExceededError(
                    f"Gemini API 사용량 한도를 초과했습니다: {exc}"
                ) from exc
            last_error = exc
            if _is_transient_error(exc) and attempt < max_retries:
                time.sleep(2 ** (attempt + 1))
            continue

        finish_reason = None
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason

        if not response.text:
            last_error = RuntimeError(
                f"Gemini가 빈 응답을 반환했습니다 (finish_reason={finish_reason}). "
                "문서가 너무 길어 출력이 잘렸을 수 있습니다."
            )
            continue

        try:
            return json.loads(response.text)
        except json.JSONDecodeError as exc:
            last_error = RuntimeError(
                f"Gemini 응답을 JSON으로 파싱하지 못했습니다 (finish_reason={finish_reason}): {exc}"
            )
            continue

    raise RuntimeError(f"Gemini 호출 실패: {last_error}")


def generate_json(
    system_instruction: str,
    user_content: str,
    response_schema: dict | None = None,
    max_retries: int = 3,
    max_output_tokens: int = 32768,
):
    """Gemini에 JSON 응답을 요청하고 파싱해서 반환한다.

    response_schema는 Gemini의 responseSchema 형식(dict)을 그대로 전달한다.
    실패하면 max_retries만큼 재시도하고, 그래도 실패하면 실제 원인이 담긴 예외를 던진다
    (호출측에서 원인을 화면에 보여줄 수 있도록 원인을 뭉개지 않는다).
    503처럼 일시적인 과부하 에러는 재시도 사이에 점점 길게(2초, 4초, 8초...) 기다렸다가
    다시 시도한다 - 곧바로 재시도하면 여전히 붐비는 상태일 확률이 높기 때문.

    GEMINI_API_KEYS에 키가 여러 개 등록되어 있으면(팀원별로 무료 키를 나눠 등록한
    경우), 현재 키가 사용량 한도를 초과했을 때 자동으로 다음 키로 넘어가서 계속
    시도한다. 등록된 키가 모두 한도를 초과해야 최종적으로 실패한다.
    """
    global _current_key_index

    keys = config.GEMINI_API_KEYS
    if not keys:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다. secrets.toml을 확인하세요.")

    generation_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=response_schema,
        max_output_tokens=max_output_tokens,
    )

    last_error: Exception | None = None
    for offset in range(len(keys)):
        key_index = (_current_key_index + offset) % len(keys)
        client = _get_client_by_index(key_index)
        try:
            result = _call_once(client, generation_config, user_content, max_retries)
        except GeminiQuotaExceededError as exc:
            last_error = exc
            continue
        _current_key_index = key_index
        return result

    raise GeminiQuotaExceededError(
        f"등록된 API 키 {len(keys)}개가 모두 사용량 한도를 초과했습니다: {last_error}"
    )
