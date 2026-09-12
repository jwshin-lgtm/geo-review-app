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
                    "reason": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["index", "revised_text", "changed", "reason", "suggestion"],
            },
        }
    },
    "required": ["revisions"],
}

SYSTEM_INSTRUCTION = """당신은 GEO 블로그 원고 편집 보조입니다.
아래 '수정 스타일 가이드'는 과거 담당자/광고주가 반복해온 실제 수정 원칙입니다.
이번 초안에 이 가이드를 적극적으로, 하지만 정확하게 적용하세요.

철칙:
1. 원문의 의미, 사실관계, 문단 개수, 문단 순서를 절대 바꾸지 않는다.
2. 스타일 가이드의 규칙에 해당하는 부분은 망설이지 말고 반영한다 (규칙에 맞는데도 그대로
   두는 것은 실패로 간주된다). 다만 문장을 통째로 새로 쓰지 말고 단어/구 단위로 다듬는다.
3. 스타일 가이드 규칙과 명확히 관련 없는 내용을 창작적으로 재작성하지 않는다.
4. changed=true로 고친 문단에는 반드시 reason에 "어떤 규칙 때문에 무엇을 왜 고쳤는지"를
   한 문장으로 남긴다 (예: "톤앤매너 규칙에 따라 단정적 어미를 완곡하게 순화함").
   reason이 없는 수정은 인정되지 않는다 - 절대 비워두지 않는다.
5. 규칙에 해당할 '가능성'은 있지만 확신이 서지 않는 애매한 부분은, 텍스트를 직접 고치지
   말고 revised_text는 원문 그대로 둔 채(changed=false, reason="") suggestion에 무엇을,
   왜 고치면 좋을지 한두 문장으로 구체적으로 남긴다. 확신이 없다고 그냥 넘어가지 말고
   반드시 suggestion에 검토 의견을 남긴다.
6. 고칠 것도, 의견을 남길 것도 없는 문단만 reason과 suggestion을 모두 빈 문자열("")로 둔다.
7. 출력은 입력과 반드시 같은 개수, 같은 순서의 항목을 포함해야 한다.
   changed가 false이면 revised_text는 원문(paragraphs 배열의 해당 text)과 완전히 동일해야 한다."""


class RevisionMismatchError(Exception):
    pass


def _build_user_content(style_guide: dict, paragraphs: list[str]) -> str:
    payload = {
        "style_guide": style_guide,
        "paragraphs": [{"index": i, "text": text} for i, text in enumerate(paragraphs)],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def revise_paragraphs(style_guide: dict, paragraphs: list[str]) -> tuple[list[dict], str | None]:
    """반환: (revisions, error_message)

    revisions는 [{index, revised_text, changed, reason, suggestion}, ...]
    (paragraphs와 같은 길이/순서 보장). changed=true인데 reason이 비어있는 경우도
    "일관성 없는 결과"로 간주해 재시도 대상이다 - 누가 실행해도 같은 수준(수정에는
    반드시 근거 코멘트가 남는)의 결과가 나오도록 스키마 단계에서 강제한다.
    개수/순서가 어긋나거나 호출 자체가 실패하면 1회 재시도하고, 그래도 실패하면
    전체를 changed=False(원본 그대로)로 반환하되, error_message에 실제 실패 원인을
    담아 호출측(화면)에서 "그냥 고칠 게 없었다"와 구분해서 보여줄 수 있게 한다.
    """
    user_content = _build_user_content(style_guide, paragraphs)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            result = gemini_client.generate_json(
                system_instruction=SYSTEM_INSTRUCTION,
                user_content=user_content,
                response_schema=REVISION_SCHEMA,
            )
            revisions = result["revisions"]
            _validate(revisions, paragraphs)
            return revisions, None
        except Exception as exc:  # noqa: BLE001 - 원인을 보존해 위로 전달
            last_error = exc
            continue

    fallback = [
        {"index": i, "revised_text": text, "changed": False, "reason": "", "suggestion": ""}
        for i, text in enumerate(paragraphs)
    ]
    return fallback, f"자동 수정에 실패해 원본을 그대로 반환했습니다 ({last_error})"


def _validate(revisions: list[dict], paragraphs: list[str]) -> None:
    if len(revisions) != len(paragraphs):
        raise RevisionMismatchError("문단 개수가 일치하지 않습니다.")
    indices = [r["index"] for r in revisions]
    if indices != list(range(len(paragraphs))):
        raise RevisionMismatchError("문단 순서/인덱스가 일치하지 않습니다.")
    for r, original in zip(revisions, paragraphs):
        if not r["changed"] and r["revised_text"] != original:
            raise RevisionMismatchError("changed=false인데 텍스트가 원문과 다릅니다.")
        if r["changed"] and not (r.get("reason") or "").strip():
            raise RevisionMismatchError("changed=true인데 reason(수정 근거)이 비어있습니다.")
