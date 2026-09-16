"""python-docx는 '진짜' Word 코멘트(검토 > 새 메모) 추가를 공식 지원하지 않는다.

OOXML 스펙상 코멘트는 word/comments.xml 파트 + 본문의
commentRangeStart/End + commentReference 조합으로 구성되므로, 여기서는
python-docx의 저수준 OPC/oxml API를 이용해 직접 그 구조를 만든다.
"""
from __future__ import annotations

import datetime

from docx.opc.packuri import PackURI
from docx.opc.part import XmlPart
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

_COMMENTS_PART_URI = PackURI("/word/comments.xml")
_COMMENTS_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
_COMMENTS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"


def _get_comments_part(document) -> XmlPart | None:
    document_part = document.part
    for rel in document_part.rels.values():
        if rel.reltype == _COMMENTS_REL_TYPE:
            return rel.target_part
    return None


def _get_or_create_comments_part(document) -> XmlPart:
    existing = _get_comments_part(document)
    if existing is not None:
        return existing

    document_part = document.part
    comments_element = OxmlElement("w:comments")
    comments_part = XmlPart(
        _COMMENTS_PART_URI, _COMMENTS_CONTENT_TYPE, comments_element, document_part.package
    )
    document_part.relate_to(comments_part, _COMMENTS_REL_TYPE)
    return comments_part


def _next_comment_id(comments_element) -> str:
    existing_ids = [
        int(c.get(qn("w:id"))) for c in comments_element.findall(qn("w:comment"))
    ]
    return str(max(existing_ids, default=-1) + 1)


def add_comment_to_paragraph(
    document,
    paragraph,
    text: str,
    author: str = "GEO 자동 검토",
    initials: str = "AI",
) -> None:
    """paragraph 전체를 감싸는 Word 코멘트(검토 > 메모)를 추가한다.

    원문 텍스트는 전혀 건드리지 않고, Word의 댓글창/여백에만 나타난다.
    """
    comments_part = _get_or_create_comments_part(document)
    comments_element = comments_part.element
    comment_id = _next_comment_id(comments_element)

    comment_el = OxmlElement("w:comment")
    comment_el.set(qn("w:id"), comment_id)
    comment_el.set(qn("w:author"), author)
    comment_el.set(qn("w:initials"), initials)
    comment_el.set(qn("w:date"), datetime.datetime.now().replace(microsecond=0).isoformat())

    comment_p = OxmlElement("w:p")
    comment_r = OxmlElement("w:r")
    for i, line in enumerate(text.split("\n")):
        if i > 0:
            comment_r.append(OxmlElement("w:br"))
        line_t = OxmlElement("w:t")
        line_t.set(qn("xml:space"), "preserve")
        line_t.text = line
        comment_r.append(line_t)
    comment_p.append(comment_r)
    comment_el.append(comment_p)
    comments_element.append(comment_el)

    # 본문 쪽: 문단 전체를 commentRangeStart~End로 감싸고, 끝에 참조 러닝을 붙인다.
    range_start = OxmlElement("w:commentRangeStart")
    range_start.set(qn("w:id"), comment_id)
    range_end = OxmlElement("w:commentRangeEnd")
    range_end.set(qn("w:id"), comment_id)

    ref_run = OxmlElement("w:r")
    ref_run_pr = OxmlElement("w:rPr")
    ref_style = OxmlElement("w:rStyle")
    ref_style.set(qn("w:val"), "CommentReference")
    ref_run_pr.append(ref_style)
    ref_run.append(ref_run_pr)
    ref_run.append(OxmlElement("w:commentReference"))
    ref_run.find(qn("w:commentReference")).set(qn("w:id"), comment_id)

    p = paragraph._p
    p_pr = p.find(qn("w:pPr"))
    insert_index = list(p).index(p_pr) + 1 if p_pr is not None else 0
    p.insert(insert_index, range_start)
    p.append(range_end)
    p.append(ref_run)


def _comment_texts_by_id(comments_part) -> dict[str, dict]:
    if comments_part is None:
        return {}
    texts = {}
    for comment_el in comments_part.element.findall(qn("w:comment")):
        comment_id = comment_el.get(qn("w:id"))
        author = comment_el.get(qn("w:author")) or ""
        text = "".join(t.text or "" for t in comment_el.iter(qn("w:t")))
        texts[comment_id] = {"author": author, "text": text}
    return texts


def extract_comments(document) -> list[dict]:
    """문서에 달린 Word 코멘트를, 코멘트가 달린 원문 텍스트와 함께 추출한다.

    최종본이 아니어도(리뷰 중인 원고여도) 사람이 남긴 검토 코멘트를 학습
    재료로 쓸 수 있게 하기 위한 용도. 반환: [{"anchored_text", "comment", "author"}, ...]
    """
    comments_part = _get_comments_part(document)
    comment_texts = _comment_texts_by_id(comments_part)
    if not comment_texts:
        return []

    results = []
    for paragraph in document.paragraphs:
        active_ids: set[str] = set()
        collected: dict[str, list[str]] = {}
        for el in paragraph._p.iter():
            if el.tag == qn("w:commentRangeStart"):
                comment_id = el.get(qn("w:id"))
                if comment_id in comment_texts:
                    active_ids.add(comment_id)
                    collected.setdefault(comment_id, [])
            elif el.tag == qn("w:commentRangeEnd"):
                active_ids.discard(el.get(qn("w:id")))
            elif el.tag == qn("w:t"):
                for comment_id in active_ids:
                    collected[comment_id].append(el.text or "")

        for comment_id, parts in collected.items():
            info = comment_texts[comment_id]
            if not info["text"].strip():
                continue
            results.append(
                {
                    "anchored_text": "".join(parts).strip(),
                    "comment": info["text"].strip(),
                    "author": info["author"],
                }
            )
    return results
