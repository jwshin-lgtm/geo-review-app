"""과거 (초안, 최종본) 쌍에서 수정 패턴을 뽑아 '스타일 가이드'로 요약한다 (Stage A).

한 번 학습하고 끝나는 게 아니라, 이미 반영한 초안/최종본 쌍(signature)을
data/learning_state.json에 기록해두고, 다음에 실행할 때는 '새로 생기거나
바뀐 쌍'만 골라서 기존 누적 예시에 추가한 뒤 스타일 가이드를 다시 요약한다.
"""
from __future__ import annotations

import json
import os

from . import config, diff_utils, drive_client, gemini_client
from .diff_utils import EditExample, align_paragraphs
from .docx_text import extract_paragraphs

MAX_EXAMPLES_FOR_PROMPT = 80
LEARNING_STATE_PATH = "data/learning_state.json"

STYLE_GUIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "rule": {"type": "string"},
                    "example_before": {"type": "string"},
                    "example_after": {"type": "string"},
                },
                "required": ["category", "rule", "example_before", "example_after"],
            },
        }
    },
    "required": ["rules"],
}

SYSTEM_INSTRUCTION = """당신은 광고 원고 교정 패턴을 분석하는 전문 에디터입니다.
아래는 과거 여러 달치 '초안 문단 -> 최종본 문단' 실제 수정 사례입니다.
이 사례들에서 반복적으로 관찰되는 수정 원칙을 최대 20개로 요약하세요.

규칙:
- 반드시 제공된 사례에서 실제로 근거를 찾을 수 있는 규칙만 포함한다. 추측이나 일반론 금지.
- 각 규칙은 구체적이고 실행 가능한 문장으로 작성한다.
  예: "브랜드명은 항상 전체 명칭으로 표기한다", "단정적 어미(~됩니다)를 완곡한 어미(~될 수 있습니다)로 순화한다"
- 각 규칙에는 근거가 된 실제 예시에서 뽑은 before/after를 하나씩 첨부한다.
- 사례가 부족하거나 우연한 변형으로 보이면 규칙으로 만들지 않는다.
- 각 규칙에 category를 하나 붙인다. 아래 중 가장 맞는 것을 고르고, 다 안 맞으면
  사례 내용에 맞는 짧은 카테고리명을 새로 만든다:
  "톤앤매너", "용어/표기", "사실관계·정확성", "법적고지·컴플라이언스", "구조·포맷", "SEO최적화", "기타"
"""


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

    # 예시가 너무 많으면 최근 것 위주로 샘플링 (프롬프트 길이/비용 관리)
    sampled = examples[-MAX_EXAMPLES_FOR_PROMPT:]
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


def load_learning_state(path: str = LEARNING_STATE_PATH) -> dict:
    if not os.path.exists(path):
        return {"processed_pairs": [], "examples": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_learning_state(state: dict, path: str = LEARNING_STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _pair_signature(draft_file: dict, final_file: dict) -> str:
    # final 파일이 재수정되면 modifiedTime이 바뀌므로 다시 학습 대상이 된다.
    return f"{draft_file['id']}::{final_file['id']}::{final_file.get('modifiedTime', '')}"


def scan_and_accumulate_learning(root_folder_id: str = config.DRIVE_FOLDER_ID) -> dict:
    """드라이브 전체를 스캔해서, 아직 반영하지 않은 초안/최종본 쌍만 골라 학습에 누적한다.

    반환: {"new_pairs": int, "skipped_months": list[str], "total_examples": int,
           "style_guide": dict}
    """
    state = load_learning_state()
    processed = set(state.get("processed_pairs", []))
    examples: list[EditExample] = [
        EditExample(before=e["before"], after=e["after"]) for e in state.get("examples", [])
    ]

    month_folders = drive_client.list_subfolders(root_folder_id)
    new_pair_count = 0
    skipped_months: list[str] = []

    for month_folder in month_folders:
        draft_folder = drive_client.find_subfolder_by_candidates(
            month_folder["id"], config.DRAFT_FOLDER_NAME_CANDIDATES
        )
        final_folder = drive_client.find_subfolder_by_candidates(
            month_folder["id"], config.FINAL_FOLDER_NAME_CANDIDATES
        )
        if not draft_folder or not final_folder:
            skipped_months.append(month_folder["name"])
            continue

        draft_files = drive_client.list_docx_files(draft_folder["id"])
        final_files = drive_client.list_docx_files(final_folder["id"])
        matched = diff_utils.match_files_by_name(draft_files, final_files)

        for draft_file, final_file in matched:
            signature = _pair_signature(draft_file, final_file)
            if signature in processed:
                continue

            draft_bytes = drive_client.download_docx_bytes(draft_file["id"], draft_file["mimeType"])
            final_bytes = drive_client.download_docx_bytes(final_file["id"], final_file["mimeType"])
            new_examples = build_edit_examples([(draft_bytes, final_bytes)])
            examples.extend(new_examples)
            processed.add(signature)
            new_pair_count += 1

    style_guide = load_cached_style_guide() or {"rules": []}
    if new_pair_count > 0:
        style_guide = summarize_style_guide(examples)
        save_style_guide_cache(style_guide)
        save_learning_state(
            {
                "processed_pairs": sorted(processed),
                "examples": [{"before": e.before, "after": e.after} for e in examples],
            }
        )

    return {
        "new_pairs": new_pair_count,
        "skipped_months": skipped_months,
        "total_examples": len(examples),
        "style_guide": style_guide,
    }
