"""과거 (초안, 최종본) 쌍에서 수정 패턴을 뽑아 '스타일 가이드'로 요약한다 (Stage A)."""
from __future__ import annotations

import json
import os

from . import config, gemini_client
from .diff_utils import EditExample, align_paragraphs
from .docx_text import extract_paragraphs

MAX_EXAMPLES_FOR_PROMPT = 60

STYLE_GUIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string"},
                    "example_before": {"type": "string"},
                    "example_after": {"type": "string"},
                },
                "required": ["rule", "example_before", "example_after"],
            },
        }
    },
    "required": ["rules"],
}

SYSTEM_INSTRUCTION = """당신은 광고 원고 교정 패턴을 분석하는 전문 에디터입니다.
아래는 과거 여러 달치 '초안 문단 -> 최종본 문단' 실제 수정 사례입니다.
이 사례들에서 반복적으로 관찰되는 수정 원칙만 최대 12개로 요약하세요.

규칙:
- 반드시 제공된 사례에서 실제로 근거를 찾을 수 있는 규칙만 포함한다. 추측이나 일반론 금지.
- 각 규칙은 구체적이고 실행 가능한 문장으로 작성한다.
  예: "브랜드명은 항상 전체 명칭으로 표기한다", "단정적 어미(~됩니다)를 완곡한 어미(~될 수 있습니다)로 순화한다"
- 각 규칙에는 근거가 된 실제 예시에서 뽑은 before/after를 하나씩 첨부한다.
- 사례가 부족하거나 우연한 변형으로 보이면 규칙으로 만들지 않는다."""


def build_edit_examples(draft_final_pairs: list[tuple[bytes, bytes]]) -> list[EditExample]:
    """여러 달의 (초안 bytes, 최종본 bytes) 쌍에서 '바뀐 문단' 예시들을 모은다."""
    all_examples: list[EditExample] = []
    for draft_bytes, final_bytes in draft_final_pairs:
        draft_paragraphs = extract_paragraphs(draft_bytes)
        final_paragraphs = extract_paragraphs(final_bytes)
        all_examples.extend(align_paragraphs(draft_paragraphs, final_paragraphs))
    return all_examples


def summarize_style_guide(examples: list[EditExample]) -> dict:
    """수집된 예시를 Gemini로 요약해서 스타일 가이드(dict)를 만든다."""
    if not examples:
        return {"rules": []}

    sampled = examples[:MAX_EXAMPLES_FOR_PROMPT]
    user_content = json.dumps(
        [{"before": ex.before, "after": ex.after} for ex in sampled],
        ensure_ascii=False,
        indent=2,
    )
    return gemini_client.generate_json(
        system_instruction=SYSTEM_INSTRUCTION,
        user_content=user_content,
        response_schema=STYLE_GUIDE_SCHEMA,
    )


def load_cached_style_guide(path: str = config.STYLE_GUIDE_CACHE_PATH) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_style_guide_cache(style_guide: dict, path: str = config.STYLE_GUIDE_CACHE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(style_guide, f, ensure_ascii=False, indent=2)
