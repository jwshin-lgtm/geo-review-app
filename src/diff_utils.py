"""문단 단위 / 어절 단위 diff 유틸."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import NamedTuple


class EditExample(NamedTuple):
    before: str
    after: str


def align_paragraphs(old_paragraphs: list[str], new_paragraphs: list[str]) -> list[EditExample]:
    """(초안, 최종본) 문단 리스트를 정렬해서 '바뀐 문단'만 (before, after) 쌍으로 반환.

    문단이 삽입/삭제되어도 SequenceMatcher가 알아서 매칭하므로,
    학습용 예시 수집(패턴 학습)에만 쓴다 — 실제 리비전 적용 시에는 쓰지 않는다.
    """
    matcher = SequenceMatcher(None, old_paragraphs, new_paragraphs, autojunk=False)
    examples: list[EditExample] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            old_chunk = old_paragraphs[i1:i2]
            new_chunk = new_paragraphs[j1:j2]
            for before, after in zip(old_chunk, new_chunk):
                if before.strip() and after.strip() and before != after:
                    examples.append(EditExample(before=before, after=after))
    return examples


_TOKEN_RE = re.compile(r"\S+|\s+")


def tokenize_keep_seps(text: str) -> list[str]:
    """공백을 별도 토큰으로 유지한 채 어절 단위로 쪼갠다. join하면 원문과 동일해야 함."""
    return _TOKEN_RE.findall(text)


def word_diff_opcodes(old_text: str, new_text: str):
    """어절(+공백) 단위 SequenceMatcher opcodes. tag in {equal, replace, insert, delete}."""
    old_tokens = tokenize_keep_seps(old_text)
    new_tokens = tokenize_keep_seps(new_text)
    matcher = SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    return old_tokens, new_tokens, matcher.get_opcodes()
