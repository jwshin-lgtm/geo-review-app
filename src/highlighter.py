"""원본 docx를 열어, 바뀐 문단의 run만 교체하고 변경분에 하이라이트를 입힌다."""
from __future__ import annotations

import io

from docx.enum.text import WD_COLOR_INDEX

from . import diff_utils, word_comments
from .docx_text import load_document

RunFormat = dict


def get_run_format(run) -> RunFormat:
    if run is None:
        return {}
    color = run.font.color
    return {
        "bold": run.bold,
        "italic": run.italic,
        "underline": run.underline,
        "font_name": run.font.name,
        "font_size": run.font.size,
        "color_rgb": color.rgb if color and color.type is not None else None,
    }


def apply_run_format(run, fmt: RunFormat) -> None:
    run.bold = fmt.get("bold")
    run.italic = fmt.get("italic")
    run.underline = fmt.get("underline")
    if fmt.get("font_name"):
        run.font.name = fmt["font_name"]
    if fmt.get("font_size"):
        run.font.size = fmt["font_size"]
    if fmt.get("color_rgb") is not None:
        run.font.color.rgb = fmt["color_rgb"]


def build_run_map(paragraph) -> list[tuple[int, int, object]]:
    """[(start_offset, end_offset, run), ...] - run.text 길이 누적 기준."""
    run_map = []
    offset = 0
    for run in paragraph.runs:
        length = len(run.text)
        run_map.append((offset, offset + length, run))
        offset += length
    return run_map


def _run_at(run_map: list[tuple[int, int, object]], pos: int):
    for start, end, run in run_map:
        if start <= pos < end:
            return start, end, run
    if run_map:
        return run_map[-1]
    return None


def slice_by_original_runs(text_segment: str, start_pos: int, run_map: list[tuple[int, int, object]]):
    """text_segment(원문 그대로의 구간)를, 걸쳐있는 원본 run 경계에 맞춰 (부분텍스트, run) 리스트로 쪼갠다."""
    segments = []
    pos = start_pos
    idx = 0
    n = len(text_segment)
    while idx < n:
        found = _run_at(run_map, pos)
        if found is None:
            segments.append((text_segment[idx:], None))
            break
        run_start, run_end, run = found
        take = min(run_end - pos, n - idx)
        take = max(take, 1)
        segments.append((text_segment[idx : idx + take], run))
        idx += take
        pos += take
    return segments


def clear_runs(paragraph) -> None:
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)


def apply_highlighted_revision(doc, para_index: int, revised_text: str) -> bool:
    """paragraph를 수정된 텍스트로 교체하고, 바뀐/추가된 부분만 하이라이트한다.

    반환값: 실제로 내용이 바뀌었는지 여부.
    """
    paragraph = doc.paragraphs[para_index]
    original_text = paragraph.text
    if original_text == revised_text:
        return False

    run_map = build_run_map(paragraph)
    base_run = paragraph.runs[0] if paragraph.runs else None
    base_fmt = get_run_format(base_run)

    old_tokens, new_tokens, opcodes = diff_utils.word_diff_opcodes(original_text, revised_text)

    clear_runs(paragraph)

    orig_pos = 0
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            segment_text = "".join(old_tokens[i1:i2])
            for sub_text, run in slice_by_original_runs(segment_text, orig_pos, run_map):
                new_run = paragraph.add_run(sub_text)
                apply_run_format(new_run, get_run_format(run) if run else base_fmt)
            orig_pos += len(segment_text)
        else:
            if tag in ("replace", "insert"):
                segment_text = "".join(new_tokens[j1:j2])
                if segment_text:
                    new_run = paragraph.add_run(segment_text)
                    apply_run_format(new_run, base_fmt)
                    new_run.font.highlight_color = WD_COLOR_INDEX.BRIGHT_GREEN
            if tag in ("replace", "delete"):
                orig_pos += len("".join(old_tokens[i1:i2]))

    return True


def build_highlighted_docx(original_docx_bytes: bytes, revisions: list[dict]) -> tuple[bytes, bool, int]:
    """revisions: reviser.revise_paragraphs()의 결과.

    확신 있는 수정은 원문에 반영 후 초록 하이라이트를 입히고, 그 근거(reason)를
    Word 코멘트로도 반드시 남긴다. 애매해서 확신이 없는 부분은 원문은 그대로 두고
    검토의견(suggestion)만 Word 코멘트로 남긴다. 이 둘은 항상 세트로 붙어야
    "누가 실행해도 같은 수준의 결과"가 보장된다 - reviser._validate()가 changed=true인데
    reason이 빈 경우를 실패로 처리하므로, 여기서는 있는 그대로 반영만 한다.

    반환: (수정된 docx bytes, 실제 텍스트 변경 여부, 코멘트 개수)
    """
    doc = load_document(original_docx_bytes)
    changed_any = False
    comment_count = 0

    for rev in revisions:
        note_text = None

        if rev.get("changed"):
            original_text = doc.paragraphs[rev["index"]].text  # 하이라이트 적용 전에 원문을 미리 보존
            changed = apply_highlighted_revision(doc, rev["index"], rev["revised_text"])
            changed_any = changed_any or changed
            reason = (rev.get("reason") or "").strip()
            if reason:
                note_text = f"[자동 수정]\n원문: {original_text}\n사유: {reason}"
        else:
            suggestion = (rev.get("suggestion") or "").strip()
            if suggestion:
                note_text = f"[검토의견] {suggestion}"

        if note_text:
            word_comments.add_comment_to_paragraph(doc, doc.paragraphs[rev["index"]], note_text)
            comment_count += 1

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue(), changed_any, comment_count
