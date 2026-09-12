"""GEO 원고 자동 수정 웹앱.

탭 구성:
- 원고 리스트: 원고 학습 현황 + 새 초안 일괄 자동 수정 + 다운로드
- 스타일 가이드: 카테고리별 규칙 검토/수정 + 메모로 규칙 직접 추가
- 심의문구 가이드: 상품 선택 -> 최신 최종본에서 심의문구 추출 + 복사
"""
import io
import zipfile
from collections import defaultdict

import streamlit as st

from src import compliance, config, docx_text, drive_client, highlighter, pattern_learning, reviser, sheets_client

st.set_page_config(page_title="GEO 원고 자동 수정", page_icon="✏️", layout="wide")


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
    "product_list": None,
    "compliance_result": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


tab_manuscripts, tab_style_guide, tab_compliance = st.tabs(["원고 리스트", "스타일 가이드", "심의문구 가이드"])


# ══════════════════════════════════════════════════════════════════════
# 탭 1: 원고 리스트 (학습 현황 + 일괄 자동 수정 + 다운로드)
# ══════════════════════════════════════════════════════════════════════
with tab_manuscripts:
    st.header("원고 학습 현황")
    st.caption("드라이브 전체를 스캔해서, 아직 반영하지 않은 초안→최종본 수정 이력만 골라 누적 학습합니다.")

    _learning_state = pattern_learning.load_learning_state()
    _rule_count = len((st.session_state.style_guide or {}).get("rules", []))
    st.write(
        f"현재까지 누적 학습된 원고 쌍: **{len(_learning_state.get('processed_pairs', []))}건**, "
        f"스타일 가이드 규칙: **{_rule_count}개**"
    )

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
    st.header("이번 달 새 초안 일괄 자동 수정")

    rules = (st.session_state.style_guide or {}).get("rules", [])

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
                    st.warning("먼저 위에서 스타일 가이드를 준비하세요 (학습 반영, 또는 스타일 가이드 탭에서 직접 추가).")
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
                            revisions, revise_error = reviser.revise_paragraphs(
                                st.session_state.style_guide, paragraphs
                            )
                            result_bytes, changed_any, comment_count = highlighter.build_highlighted_docx(
                                target_bytes, revisions
                            )
                        if revise_error:
                            st.error(f"'{target_file['name']}' 처리 중 문제가 발생했습니다: {revise_error}")
                        changed_count = sum(1 for r in revisions if r["changed"])
                        results.append(
                            {
                                "name": target_file["name"],
                                "bytes": result_bytes,
                                "total": len(paragraphs),
                                "changed": changed_count,
                                "comments": comment_count,
                                "error": revise_error,
                            }
                        )
                        progress.progress((i + 1) / len(selected_targets))
                    st.session_state.batch_results = results
                    st.success(f"{len(results)}건 처리 완료했습니다.")

    st.divider()
    st.header("다운로드")

    if not st.session_state.batch_results:
        st.caption("위에서 자동 수정을 실행하면 여기에 결과가 표시됩니다.")
    else:
        for r in st.session_state.batch_results:
            status = " ⚠️ 자동 수정 실패 (원본 그대로)" if r.get("error") else ""
            st.write(
                f"- **{r['name']}** : 총 {r['total']}개 문단 중 {r['changed']}개 수정 "
                f"(전부 근거 코멘트 포함), Word 코멘트 총 {r['comments']}건{status}"
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


# ══════════════════════════════════════════════════════════════════════
# 탭 2: 스타일 가이드
# ══════════════════════════════════════════════════════════════════════
with tab_style_guide:
    rules = (st.session_state.style_guide or {}).get("rules", [])

    st.header("규칙 직접 추가")
    st.caption("자동 학습 외에, 팀에서 알고 있는 규칙을 메모 형태로 바로 추가할 수 있어요.")
    existing_categories = sorted({r.get("category", "기타") for r in rules}) or ["기타"]
    with st.form("add_rule_form", clear_on_submit=True):
        new_rule_text = st.text_area("추가할 규칙 (메모)", placeholder="예: 상품명 뒤에는 항상 '(사후관리형)'을 붙인다")
        col_a, col_b = st.columns([2, 1])
        with col_a:
            category_choice = st.selectbox("카테고리", existing_categories + ["+ 새 카테고리"])
        with col_b:
            new_category_name = st.text_input("새 카테고리명 (선택 시)")
        submitted = st.form_submit_button("규칙 추가")
        if submitted:
            if not new_rule_text.strip():
                st.warning("규칙 내용을 입력해주세요.")
            else:
                final_category = (
                    new_category_name.strip() if category_choice == "+ 새 카테고리" and new_category_name.strip()
                    else category_choice
                )
                rules.append(
                    {
                        "category": final_category or "기타",
                        "rule": new_rule_text.strip(),
                        "example_before": "",
                        "example_after": "(직접 추가한 규칙)",
                    }
                )
                st.session_state.style_guide = {"rules": rules}
                pattern_learning.save_style_guide_cache(st.session_state.style_guide)
                st.success("규칙을 추가했습니다.")
                st.rerun()

    st.divider()
    st.header("전체 스타일 가이드")

    if not rules:
        st.info("아직 학습된 규칙이 없습니다. '원고 리스트' 탭에서 먼저 학습을 반영하거나, 위에서 직접 추가해주세요.")
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


# ══════════════════════════════════════════════════════════════════════
# 탭 3: 심의문구 가이드
# ══════════════════════════════════════════════════════════════════════
with tab_compliance:
    st.header("심의문구 가이드")
    st.caption("상품을 선택하면, 해당 상품의 가장 최근 최종본 원고에서 심의문구만 뽑아 보여줍니다.")

    if st.button("상품 목록 불러오기/새로고침"):
        try:
            st.session_state.product_list = sheets_client.read_product_list()
        except Exception as exc:  # noqa: BLE001
            st.error(f"상품 목록 시트를 읽지 못했습니다: {exc}")
            st.session_state.product_list = []

    if not st.session_state.product_list:
        st.info("먼저 위 버튼으로 상품 목록을 불러와주세요.")
    else:
        product = st.selectbox("상품 선택", st.session_state.product_list, key="compliance_product")

        if st.button("심의문구 조회", type="primary"):
            with st.spinner(f"'{product}' 관련 최신 최종본을 찾는 중..."):
                try:
                    matched_file, compliance_text = compliance.get_compliance_text_for_product(product)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"조회 중 문제가 발생했습니다: {exc}")
                    matched_file, compliance_text = None, None
            st.session_state.compliance_result = {
                "product": product,
                "file": matched_file,
                "text": compliance_text,
            }

        result = st.session_state.compliance_result
        if result and result["product"] == product:
            if not result["file"]:
                st.warning("이 상품과 관련된 최종본 원고를 찾지 못했습니다.")
            elif not result["text"]:
                st.warning(
                    f"'{result['file']['name']}' 파일은 찾았지만, 이 안에서 심의문구(‘준법감시인 심사필’로 "
                    "시작하는 문단)를 찾지 못했습니다."
                )
            else:
                st.write(f"출처 원고: **{result['file']['name']}**")
                st.code(result["text"], language=None)
                st.caption("우측 상단 복사 아이콘을 누르면 바로 복사돼요. 문서 안 심의번호는 [숫자]로 표시했으니, 실제 심의 번호로 바꿔서 사용하세요.")
