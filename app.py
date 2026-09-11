"""GEO 원고 자동 수정 웹앱.

흐름: ① 드라이브 전체를 스캔해 누적 학습 → ② 스타일 가이드 검토(카테고리별)
     → ③ 이번 달 새 초안들을 한 번에 자동 수정 → ④ 일괄 다운로드
"""
import io
import zipfile
from collections import defaultdict

import streamlit as st

from src import config, docx_text, drive_client, highlighter, pattern_learning, reviser

st.set_page_config(page_title="GEO 원고 자동 수정", layout="wide")


def _check_password() -> bool:
    """APP_PASSWORD 시크릿이 설정되어 있으면, 맞는 비밀번호를 입력해야 앱을 쓸 수 있게 한다."""
    if not config.APP_PASSWORD:
        return True  # 비밀번호 미설정 (로컬 개발 등) - 잠금 건너뜀

    if st.session_state.get("authenticated"):
        return True

    st.title("GEO 원고 자동 수정")
    st.info("팀 전용 도구입니다. 비밀번호를 입력해주세요.")
    password = st.text_input("비밀번호", type="password")
    if st.button("입장"):
        if password == config.APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


if not _check_password():
    st.stop()

st.title("GEO 원고 자동 수정")

for key, default in {
    "month_folders": None,
    "style_guide": pattern_learning.load_cached_style_guide(),
    "batch_results": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── ① 학습 현황 ────────────────────────────────────────────────────────
st.header("① 원고 학습 현황")
st.caption("드라이브 전체를 스캔해서, 아직 반영하지 않은 초안→최종본 수정 이력만 골라 누적 학습합니다.")

_learning_state = pattern_learning.load_learning_state()
_rule_count = len((st.session_state.style_guide or {}).get("rules", []))
st.write(f"현재까지 누적 학습된 원고 쌍: **{len(_learning_state.get('processed_pairs', []))}건**, 스타일 가이드 규칙: **{_rule_count}개**")

if st.button("새 원고 확인하고 학습 반영", type="primary"):
    with st.spinner("드라이브 전체를 스캔하고 있습니다 (원고 수에 따라 시간이 걸릴 수 있어요)..."):
        result = pattern_learning.scan_and_accumulate_learning()
    st.session_state.style_guide = result["style_guide"]
    if result["new_pairs"] > 0:
        st.success(
            f"새 원고 쌍 {result['new_pairs']}건을 반영했습니다. "
            f"(누적 학습 예시 {result['total_examples']}건, 규칙 {len(result['style_guide'].get('rules', []))}개)"
        )
    else:
        st.info("새로 반영할 원고가 없습니다. 이미 최신 상태예요.")
    if result["skipped_months"]:
        st.caption(f"초안/최종본 폴더를 찾지 못해 건너뛴 월: {', '.join(result['skipped_months'])}")

st.divider()

# ── ② 스타일 가이드 (카테고리별 접기) ────────────────────────────────────
st.header("② 스타일 가이드")

rules = (st.session_state.style_guide or {}).get("rules", [])
if not rules:
    st.info("아직 학습된 규칙이 없습니다. ①에서 먼저 학습을 반영해주세요.")
else:
    st.caption("카테고리별로 접혀 있어요. 펼쳐서 검토/수정하시고, 다 확인했으면 아래 저장 버튼을 눌러주세요.")
    grouped = defaultdict(list)
    for rule in rules:
        grouped[rule.get("category", "기타")].append(rule)

    pending_by_category = {}
    for category, items in grouped.items():
        rows = [
            {
                "rule": r.get("rule", ""),
                "example_before": r.get("example_before", ""),
                "example_after": r.get("example_after", ""),
            }
            for r in items
        ]
        with st.expander(f"{category} ({len(rows)}개)", expanded=False):
            edited_rows = st.data_editor(
                rows,
                num_rows="dynamic",
                use_container_width=True,
                key=f"style_cat_{category}",
            )
            pending_by_category[category] = edited_rows

    if st.button("스타일 가이드 저장"):
        new_rules = []
        for category, edited_rows in pending_by_category.items():
            for row in edited_rows:
                if (row.get("rule") or "").strip():
                    new_rules.append({"category": category, **row})
        st.session_state.style_guide = {"rules": new_rules}
        pattern_learning.save_style_guide_cache(st.session_state.style_guide)
        st.success("저장했습니다.")

st.divider()

# ── ③ 초안 일괄 자동 수정 ─────────────────────────────────────────────
st.header("③ 이번 달 새 초안 일괄 자동 수정")

if st.button("드라이브에서 월별 폴더 불러오기"):
    try:
        st.session_state.month_folders = drive_client.list_subfolders(config.DRIVE_FOLDER_ID)
    except Exception as exc:  # noqa: BLE001
        st.error(f"드라이브 폴더를 읽지 못했습니다: {exc}")
        st.session_state.month_folders = []

if not st.session_state.month_folders:
    st.info("먼저 위 버튼으로 월별 폴더를 불러와주세요.")
else:
    month_names = [f["name"] for f in st.session_state.month_folders]
    target_month = st.selectbox("수정할 초안이 있는 월", month_names, key="target_month")
    target_month_folder = next(f for f in st.session_state.month_folders if f["name"] == target_month)
    target_draft_folder = drive_client.find_subfolder_by_candidates(
        target_month_folder["id"], config.DRAFT_FOLDER_NAME_CANDIDATES
    )

    if not target_draft_folder:
        st.warning("'초안' 폴더를 찾지 못했습니다.")
    else:
        target_files = drive_client.list_docx_files(target_draft_folder["id"])
        target_names = st.multiselect(
            "수정할 초안 파일 (여러 개 한 번에 선택 가능)",
            [f["name"] for f in target_files],
            key="target_files",
        )
        selected_targets = [f for f in target_files if f["name"] in target_names]

        if st.button("선택한 초안 일괄 자동 수정", type="primary"):
            if not rules:
                st.warning("먼저 ②에서 스타일 가이드를 준비하세요 (①에서 학습 반영).")
            elif not selected_targets:
                st.warning("수정할 초안 파일을 하나 이상 선택하세요.")
            else:
                results = []
                progress = st.progress(0.0)
                for i, target_file in enumerate(selected_targets):
                    with st.spinner(f"'{target_file['name']}' 분석/수정 중..."):
                        target_bytes = drive_client.download_docx_bytes(
                            target_file["id"], target_file["mimeType"]
                        )
                        paragraphs = docx_text.extract_paragraphs(target_bytes)
                        revisions = reviser.revise_paragraphs(st.session_state.style_guide, paragraphs)
                        result_bytes, changed_any, suggestion_count = highlighter.build_highlighted_docx(
                            target_bytes, revisions
                        )
                    changed_count = sum(1 for r in revisions if r["changed"])
                    results.append(
                        {
                            "name": target_file["name"],
                            "bytes": result_bytes,
                            "total": len(paragraphs),
                            "changed": changed_count,
                            "suggestions": suggestion_count,
                        }
                    )
                    progress.progress((i + 1) / len(selected_targets))
                st.session_state.batch_results = results
                st.success(f"{len(results)}건 처리 완료했습니다.")

st.divider()

# ── ④ 다운로드 ────────────────────────────────────────────────────────
st.header("④ 다운로드")

if not st.session_state.batch_results:
    st.caption("③에서 자동 수정을 실행하면 여기에 결과가 표시됩니다.")
else:
    for r in st.session_state.batch_results:
        st.write(
            f"- **{r['name']}** : 총 {r['total']}개 문단 중 {r['changed']}개 수정, "
            f"검토의견 {r['suggestions']}건"
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in st.session_state.batch_results:
            zf.writestr(f"[수정본] {r['name']}", r["bytes"])

    st.download_button(
        "전체 수정본 한번에 다운로드 (zip)",
        data=zip_buffer.getvalue(),
        file_name="수정본_모음.zip",
        mime="application/zip",
    )

    if len(st.session_state.batch_results) == 1:
        only = st.session_state.batch_results[0]
        st.download_button(
            "수정본 다운로드 (.docx)",
            data=only["bytes"],
            file_name=f"[수정본] {only['name']}",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
