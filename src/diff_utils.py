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


def match_files_by_name(draft_files: list[dict], final_files: list[dict]) -> list[tuple[dict, dict]]:
    """초안 파일들과 최종본 파일들을, 파일명 유사도가 가장 높은 것끼리 짝지어준다.

    한 달에 여러 원고(topic)가 섞여 있을 때, 초안/최종본 이름이 완전히 같지는
    않아도(번호, "재심의" 등 접두/접미어 차이) 핵심 제목 부분이 겹치므로
    문자열 유사도로 충분히 매칭 가능하다. 탐욕적(greedy) 매칭이라 최적은 아니지만
    보통 한 달에 파일 수가 적어 실용적으로 문제없다.
    """
    remaining_final = list(final_files)
    pairs: list[tuple[dict, dict]] = []
    for draft in draft_files:
        if not remaining_final:
            break
        best = max(
            remaining_final,
            key=lambda f: SequenceMatcher(None, draft["name"], f["name"]).ratio(),
        )
        pairs.append((draft, best))
        remaining_final.remove(best)
    return pairs


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
