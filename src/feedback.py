"""서술형(자유형식) 피드백을 받아 맥락을 분석하고, 스타일 가이드에 반영할
규칙 후보를 뽑아준다. 원문 피드백은 히스토리로 계속 누적해서 남긴다.
"""
from __future__ import annotations

import datetime
import json

from . import drive_storage, gemini_client

FEEDBACK_LOG_FILE = "_app_data_feedback_log.json"

CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "rule": {"type": "string"},
                    "example_before": {"type": "string"},
                    "example_after": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["category", "rule", "example_before", "example_after", "rationale"],
            },
        }
    },
    "required": ["candidates"],
}

SYSTEM_INSTRUCTION = """당신은 GEO 블로그 원고 팀의 편집장입니다.
담당자가 팀장/광고주 등에게서 받은 피드백을 자유 형식(서술형)으로 남겼습니다.
이 피드백의 맥락을 파악해서, 앞으로 원고를 쓰거나 자동 수정할 때 실제로
반영해야 할 "일반화 가능한 규칙"이 있는지 검토하세요.

규칙:
- 이번 원고 하나에만 해당하는 지엽적인 지적(예: 이번 문서의 오타 하나)은 규칙으로
  만들지 않는다. "앞으로도 반복될 만한" 원칙만 후보로 만든다.
- 이미 존재하는 스타일 가이드 규칙과 사실상 같은 내용이면 새로 만들지 않는다.
- 규칙으로 만들 만한 내용이 전혀 없으면 candidates를 빈 배열로 반환한다 (억지로
  만들어내지 않는다).
- 각 후보는 category(가장 맞는 것을 고르거나 새로 만듦), rule(실행 가능한 구체적
  문장), example_before/example_after(있으면 피드백에서 유추, 없으면 빈 문자열),
  rationale(왜 이 피드백에서 이 규칙을 뽑았는지 한 문장)을 포함한다."""


def load_feedback_log() -> list[dict]:
    return drive_storage.load_json(FEEDBACK_LOG_FILE, [])


def append_feedback(text: str) -> None:
    log = load_feedback_log()
    log.append({"timestamp": datetime.datetime.now().isoformat(timespec="seconds"), "text": text})
    drive_storage.save_json(FEEDBACK_LOG_FILE, log)


def analyze_feedback(feedback_text: str, style_guide: dict) -> list[dict]:
    """피드백을 분석해서 스타일 가이드에 추가할 만한 규칙 후보 목록을 반환한다."""
    user_content = json.dumps(
        {
            "existing_rules": [
                {"category": r.get("category", ""), "rule": r.get("rule", "")}
                for r in style_guide.get("rules", [])
            ],
            "feedback": feedback_text,
        },
        ensure_ascii=False,
        indent=2,
    )
    result = gemini_client.generate_json(
        system_instruction=SYSTEM_INSTRUCTION,
        user_content=user_content,
        response_schema=CANDIDATE_SCHEMA,
    )
    return result.get("candidates", [])
