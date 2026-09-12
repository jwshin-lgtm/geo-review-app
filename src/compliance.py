"""심의문구 가이드: 상품명으로 가장 최신 최종 원고를 찾아 심의문구만 추출한다."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from . import config, drive_client
from .docx_text import extract_paragraphs

_ANCHOR_RE = re.compile(config.COMPLIANCE_ANCHOR_PATTERN)
_NUMBER_IN_ANCHOR_RE = re.compile(r"(제\s*)[0-9][0-9\-]*(\s*호)")


def extract_compliance_text(paragraphs: list[str]) -> str | None:
    """'준법감시인 심사필'로 시작하는 문단부터 문서 끝까지를 심의문구로 간주해 추출한다.

    심의번호(숫자)는 매번 바뀌므로 [숫자]로 치환해서 반환한다.
    """
    start_idx = None
    for i, text in enumerate(paragraphs):
        if _ANCHOR_RE.search(text):
            start_idx = i
            break
    if start_idx is None:
        return None

    block = [p for p in paragraphs[start_idx:] if p.strip()]
    joined = "\n".join(block)
    return _NUMBER_IN_ANCHOR_RE.sub(r"\1[숫자]\2", joined)


def _name_similarity(product_name: str, filename: str) -> float:
    if product_name.lower() in filename.lower():
        return 1.0
    return SequenceMatcher(None, product_name.lower(), filename.lower()).ratio()


def find_latest_final_for_product(
    product_name: str,
    root_folder_id: str = config.DRIVE_FOLDER_ID,
    min_similarity: float = 0.3,
) -> dict | None:
    """모든 월의 '최종' 폴더를 훑어서, 상품명과 가장 관련 있어 보이면서
    가장 최근에 수정된 최종본 파일 하나를 찾는다."""
    month_folders = drive_client.list_subfolders(root_folder_id)

    best_file: dict | None = None
    best_score = -1.0

    for month_folder in month_folders:
        final_folder = drive_client.find_subfolder_by_candidates(
            month_folder["id"], config.FINAL_FOLDER_NAME_CANDIDATES
        )
        if not final_folder:
            continue

        for f in drive_client.list_docx_files(final_folder["id"]):
            score = _name_similarity(product_name, f["name"])
            if score < min_similarity:
                continue
            # 유사도가 더 높거나, 유사도가 같은데 더 최근(modifiedTime)이면 갱신
            if best_file is None or score > best_score or (
                score == best_score and f.get("modifiedTime", "") > best_file.get("modifiedTime", "")
            ):
                best_file = f
                best_score = score

    return best_file


def get_compliance_text_for_product(product_name: str) -> tuple[dict | None, str | None]:
    """상품명 -> (매칭된 파일 정보, 심의문구 텍스트) 반환. 못 찾으면 (None, None)."""
    matched_file = find_latest_final_for_product(product_name)
    if not matched_file:
        return None, None

    docx_bytes = drive_client.download_docx_bytes(matched_file["id"], matched_file["mimeType"])
    paragraphs = extract_paragraphs(docx_bytes)
    compliance_text = extract_compliance_text(paragraphs)
    return matched_file, compliance_text
