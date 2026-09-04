"""스타일 가이드를 참고해 새 초안 문단을 최소한으로 수정한다 (Stage B)."""
from __future__ import annotations

import json

from . import gemini_client

REVISION_SCHEMA = {
    "type": "object",
    "properties": {
        "revisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "revised_text": {"type": "string"},
                    "changed": {"type": "boolean"},
                },
                "required": ["index", "revised_text", "changed"],
            },
        }
    },
    "required": ["revisions"],
}

SYSTEM_INSTRUCTION = """당신은 GEO 블로그 원고 편집 보조입니다.
아래 '수정 스타일 가이드'는 과거 담당자/광고주가 반복해온 실제 수정 원칙입니다.
이번 초안에 이 가이드를 참고하여 최소한의 수정만 가하세요.

철칙:
1. 원문의 의미, 사실관계, 문단 개수, 문단 순서를 절대 바꾸지 않는다.
2. 스타일 가이드에서 명확한 근거를 찾을 수 있는 수정만 적용한다. 근거 없는 창작적 재작성은 금지한다.
3. 대부분의 문단은 그대로 두어도 된다. 바꿀 명확한 이유가 없으면 바꾸지 않는다.
4. 문장을 통째로 새로 쓰지 말고, 단어나 구 단위로 다듬는 정도로 그친다.
5. 출력은 입력과 반드시 같은 개수, 같은 순서의 항목을 포함해야 한다.
   changed가 false이면 revised_text는 원문(paragraphs 배열의 해당 text)과 완전히 동일해야 한다."""


class RevisionMismatchError(Exception):
    pass


def _build_user_content(style_guide: dict, paragraphs: list[str]) -> str:
    payload = {
        "style_guide": style_guide,
        "paragraphs": [{"index": i, "text": text} for i, text in enumerate(paragraphs)],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def revise_paragraphs(style_guide: dict, paragraphs: list[str]) -> list[dict]:
    """반환: [{index, revised_text, changed}, ...] (paragraphs와 같은 길이/순서 보장)

    개수/순서가 어긋나면 1회 재시도하고, 그래도 실패하면 전체를 changed=False로
    (원본 그대로) 반환한다 - 구조 훼손 방지가 최우선.
    """
    user_content = _build_user_content(style_guide, paragraphs)

    for attempt in range(2):
        try:
            result = gemini_client.generate_json(
                system_instruction=SYSTEM_INSTRUCTION,
                user_content=user_content,
                response_schema=REVISION_SCHEMA,
            )
            revisions = result["revisions"]
            _validate(revisions, paragraphs)
            return revisions
        except (RevisionMismatchError, KeyError, Exception):  # noqa: BLE001
            if attempt == 0:
                continue
            break

    # 실패: 원본 그대로 반환 (자동 수정 실패 - 검토 필요로 UI에서 표시)
    return [
        {"index": i, "revised_text": text, "changed": False}
        for i, text in enumerate(paragraphs)
    ]


def _validate(revisions: list[dict], paragraphs: list[str]) -> None:
    if len(revisions) != len(paragraphs):
        raise RevisionMismatchError("문단 개수가 일치하지 않습니다.")
    indices = [r["index"] for r in revisions]
    if indices != list(range(len(paragraphs))):
        raise RevisionMismatchError("문단 순서/인덱스가 일치하지 않습니다.")
    for r, original in zip(revisions, paragraphs):
        if not r["changed"] and r["revised_text"] != original:
            raise RevisionMismatchError("changed=false인데 텍스트가 원문과 다릅니다.")
