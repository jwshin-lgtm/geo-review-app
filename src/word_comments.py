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


def _get_or_create_comments_part(document) -> XmlPart:
    document_part = document.part
    for rel in document_part.rels.values():
        if rel.reltype == _COMMENTS_REL_TYPE:
            return rel.target_part

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
    comment_t = OxmlElement("w:t")
    comment_t.set(qn("xml:space"), "preserve")
    comment_t.text = text
    comment_r.append(comment_t)
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
