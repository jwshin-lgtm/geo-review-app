"""GEO 원고 자동 수정 웹앱 - 1차 MVP.

흐름: ① 학습용 월 선택 → ② 초안/최종본 쌍 확인 → ③ 스타일 가이드 생성/검토
     → ④ 이번 달 새 초안 선택 → ⑤ 자동 수정 실행 → ⑥ 다운로드
"""
import streamlit as st

from src import config, diff_utils, drive_client, docx_text, pattern_learning, reviser, highlighter

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
    "learning_pairs": {},  # {month_name: {"draft": bytes|None, "final": bytes|None}}
    "style_guide": pattern_learning.load_cached_style_guide(),
    "target_bytes": None,
    "target_filename": None,
    "revision_result": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _load_month_folders():
    try:
        st.session_state.month_folders = drive_client.list_subfolders(config.DRIVE_FOLDER_ID)
    except Exception as exc:  # noqa: BLE001
        st.error(f"드라이브 폴더를 읽지 못했습니다: {exc}")
        st.session_state.month_folders = []


st.header("① 학습에 쓸 과거 월 선택")
st.caption("과거 초안 → 최종본 수정 이력을 분석해서 수정 패턴을 학습합니다.")

if st.button("드라이브에서 월별 폴더 불러오기"):
    _load_month_folders()

if st.session_state.month_folders:
    month_names = [f["name"] for f in st.session_state.month_folders]
    selected_months = st.multiselect("학습에 사용할 월", month_names)

    for month_name in selected_months:
        month_folder = next(f for f in st.session_state.month_folders if f["name"] == month_name)
        with st.expander(f"{month_name} - 초안/최종본 파일 선택", expanded=True):
            draft_folder = drive_client.find_subfolder_by_candidates(
                month_folder["id"], config.DRAFT_FOLDER_NAME_CANDIDATES
            )
            final_folder = drive_client.find_subfolder_by_candidates(
                month_folder["id"], config.FINAL_FOLDER_NAME_CANDIDATES
            )

            pair_state = st.session_state.learning_pairs.setdefault(
                month_name, {"draft_files": [], "final_files": []}
            )

            col1, col2 = st.columns(2)
            with col1:
                if draft_folder:
                    draft_files = drive_client.list_docx_files(draft_folder["id"])
                    draft_names = st.multiselect(
                        "초안 파일 (여러 개 선택 가능)",
                        [f["name"] for f in draft_files],
                        key=f"draft_{month_name}",
                    )
                    pair_state["draft_files"] = [f for f in draft_files if f["name"] in draft_names]
                else:
                    st.warning("'초안' 폴더를 찾지 못했습니다.")
            with col2:
                if final_folder:
                    final_files = drive_client.list_docx_files(final_folder["id"])
                    final_names = st.multiselect(
                        "최종본 파일 (여러 개 선택 가능)",
                        [f["name"] for f in final_files],
                        key=f"final_{month_name}",
                    )
                    pair_state["final_files"] = [f for f in final_files if f["name"] in final_names]
                else:
                    st.warning("'최종본' 폴더를 찾지 못했습니다.")

st.divider()
st.subheader("선택된 학습 파일")

_any_selected = False
for month_name, pair in st.session_state.learning_pairs.items():
    draft_files = pair.get("draft_files", [])
    final_files = pair.get("final_files", [])
    if not draft_files and not final_files:
        continue
    _any_selected = True
    st.markdown(f"**{month_name}**")
    matched = diff_utils.match_files_by_name(draft_files, final_files)
    for draft_file, final_file in matched:
        st.write(f"- (초안) {draft_file['name']}  ↔  (최종) {final_file['name']}")
    matched_ids = {f["id"] for pair_ in matched for f in pair_}
    for f in draft_files + final_files:
        if f["id"] not in matched_ids:
            st.write(f"- (짝 없음, 학습에서 제외) {f['name']}")

if not _any_selected:
    st.caption("아직 선택된 파일이 없습니다. 위에서 월을 펼쳐서 초안/최종본 파일을 선택해주세요.")

st.divider()
st.header("② 스타일 가이드 생성")

if st.button("선택한 월들로 학습 시작"):
    pairs_bytes = []
    for month_name, pair in st.session_state.learning_pairs.items():
        matched = diff_utils.match_files_by_name(
            pair.get("draft_files", []), pair.get("final_files", [])
        )
        for draft_file, final_file in matched:
            draft_bytes = drive_client.download_docx_bytes(draft_file["id"], draft_file["mimeType"])
            final_bytes = drive_client.download_docx_bytes(final_file["id"], final_file["mimeType"])
            pairs_bytes.append((draft_bytes, final_bytes))

    if not pairs_bytes:
        st.warning("학습할 초안/최종본 쌍이 없습니다. ①에서 월을 선택하고 파일을 확인하세요.")
    else:
        with st.spinner("과거 수정 이력을 분석하는 중..."):
            examples = pattern_learning.build_edit_examples(pairs_bytes)
            style_guide = pattern_learning.summarize_style_guide(examples)
            pattern_learning.save_style_guide_cache(style_guide)
            st.session_state.style_guide = style_guide
        st.success(f"스타일 가이드 {len(style_guide.get('rules', []))}개 규칙을 생성했습니다.")

if st.session_state.style_guide:
    st.caption("아래 규칙을 검토하고, 필요하면 직접 수정/삭제하세요. 여기 내용이 다음 자동 수정에 그대로 반영됩니다.")
    edited_rules = st.data_editor(
        st.session_state.style_guide.get("rules", []),
        num_rows="dynamic",
        use_container_width=True,
        key="style_guide_editor",
    )
    if st.button("이 규칙으로 저장"):
        st.session_state.style_guide = {"rules": edited_rules}
        pattern_learning.save_style_guide_cache(st.session_state.style_guide)
        st.success("저장했습니다.")

st.divider()
st.header("③ 이번 달 새 초안 자동 수정")

if not st.session_state.month_folders:
    st.info("먼저 ①에서 '드라이브에서 월별 폴더 불러오기'를 눌러주세요.")
else:
    month_names = [f["name"] for f in st.session_state.month_folders]
    target_month = st.selectbox("수정할 초안이 있는 월", month_names, key="target_month")
    target_month_folder = next(f for f in st.session_state.month_folders if f["name"] == target_month)
    target_draft_folder = drive_client.find_subfolder_by_candidates(
        target_month_folder["id"], config.DRAFT_FOLDER_NAME_CANDIDATES
    )

    if target_draft_folder:
        target_files = drive_client.list_docx_files(target_draft_folder["id"])
        target_name = st.selectbox("수정할 초안 파일", [f["name"] for f in target_files], key="target_file")
        target_file = next((f for f in target_files if f["name"] == target_name), None)

        if st.button("자동 수정 실행", type="primary"):
            if not st.session_state.style_guide or not st.session_state.style_guide.get("rules"):
                st.warning("먼저 ②에서 스타일 가이드를 생성하세요.")
            else:
                with st.spinner("초안을 분석하고 수정하는 중..."):
                    target_bytes = drive_client.download_docx_bytes(target_file["id"], target_file["mimeType"])
                    paragraphs = docx_text.extract_paragraphs(target_bytes)
                    revisions = reviser.revise_paragraphs(st.session_state.style_guide, paragraphs)
                    result_bytes, changed_any = highlighter.build_highlighted_docx(target_bytes, revisions)

                st.session_state.revision_result = result_bytes
                st.session_state.target_filename = target_name
                changed_count = sum(1 for r in revisions if r["changed"])
                if changed_any:
                    st.success(f"총 {len(paragraphs)}개 문단 중 {changed_count}개 문단을 수정했습니다.")
                else:
                    st.info("스타일 가이드 기준으로 수정할 부분을 찾지 못했습니다 (원본과 동일).")
    else:
        st.warning("'초안' 폴더를 찾지 못했습니다.")

if st.session_state.revision_result:
    st.divider()
    st.header("④ 다운로드")
    out_name = f"[수정본] {st.session_state.target_filename}"
    st.download_button(
        "수정된 원고 다운로드 (.docx)",
        data=st.session_state.revision_result,
        file_name=out_name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
