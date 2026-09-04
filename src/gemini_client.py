"""Gemini API 래퍼. JSON 구조화 출력을 강제하고, 실패 시 1회 재시도한다."""
from __future__ import annotations

import json

from google import genai
from google.genai import types

from . import config

_client: genai.Client | None = None


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
    max_retries: int = 1,
):
    """Gemini에 JSON 응답을 요청하고 파싱해서 반환한다.

    response_schema는 Gemini의 responseSchema 형식(dict)을 그대로 전달한다.
    파싱 실패 시 max_retries만큼 재시도하고, 그래도 실패하면 예외를 던진다.
    """
    client = get_client()
    generation_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=response_schema,
    )

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_content,
                config=generation_config,
            )
            return json.loads(response.text)
        except (json.JSONDecodeError, Exception) as exc:  # noqa: BLE001 - 재시도 후 상위로 전파
            last_error = exc
    raise RuntimeError(f"Gemini 응답을 JSON으로 파싱하지 못했습니다: {last_error}")
