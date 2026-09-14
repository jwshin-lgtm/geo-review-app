"""Gemini API 래퍼. JSON 구조화 출력을 강제하고, 실패 시 재시도한다."""
from __future__ import annotations

import json
import time

from google import genai
from google.genai import types

from . import config

_client: genai.Client | None = None

# 일시적 과부하/속도제한 에러 - 몇 초 기다렸다가 다시 시도하면 대부분 해결됨
_TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "overloaded")


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker in message for marker in _TRANSIENT_MARKERS)


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다. secrets.toml을 확인하세요.")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


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
    503/429처럼 일시적인 과부하 에러는 재시도 사이에 점점 길게(2초, 4초, 8초...)
    기다렸다가 다시 시도한다 - 곧바로 재시도하면 여전히 붐비는 상태일 확률이 높기 때문.
    """
    client = get_client()
    generation_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=response_schema,
        max_output_tokens=max_output_tokens,
    )

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_content,
                config=generation_config,
            )
        except Exception as exc:  # noqa: BLE001 - API 호출 자체의 실패 원인을 그대로 보존
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
