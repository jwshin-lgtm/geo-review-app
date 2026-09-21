"""매일 한 번, 사람이 사이트에 접속하지 않아도 자동으로 학습을 시도하는 스크립트.

GitHub Actions 스케줄(.github/workflows/daily_learn.yml)에서 이 스크립트를
실행한다. 학습 결과(스타일 가이드/진행 상태)는 로컬이 아니라 구글 드라이브에
저장되므로(drive_storage.py), 여기서 갱신해두면 Streamlit 앱에 접속했을 때
바로 최신 상태로 보인다. 무료 API 사용량 한도 때문에 오늘 실패해도, 이 스크립트가
내일 다시 자동으로 시도한다.
"""
import sys

from src import pattern_learning


def main() -> int:
    try:
        result = pattern_learning.scan_and_accumulate_learning()
    except Exception as exc:  # noqa: BLE001 - 실패 원인을 Actions 로그에 그대로 남긴다
        print(f"학습 실패: {exc}")
        return 1

    print(
        f"새 원고 {result['new_pairs']}건 학습, "
        f"누적 예시 {result['total_examples']}건, "
        f"규칙 {len(result['style_guide'].get('rules', []))}개"
    )
    if result["skipped_months"]:
        print(f"건너뛴 달: {', '.join(result['skipped_months'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
