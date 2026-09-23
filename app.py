"""GEO 원고 자동 수정 웹앱.

탭 구성:
- 원고 리스트: 원고 학습 현황 + 새 초안 일괄 자동 수정 + 다운로드
- 스타일 가이드: 카테고리별 규칙 검토/수정 + 메모로 규칙 직접 추가
- 심의문구 가이드: 상품 선택 -> 최신 최종본에서 심의문구 추출 + 복사
"""
import io
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

from src import (
    compliance,
    config,
    docx_text,
    drive_client,
    feedback,
    highlighter,
    pattern_learning,
    reviser,
    sheets_client,
    theme,
    word_comments,
)

st.set_page_config(page_title="GEO원고, 알아서 다듬어드려요", page_icon="✏️", layout="wide")
theme.inject()


def _save_style_guide_safely(style_guide: dict) -> bool:
    """스타일 가이드를 드라이브에 저장한다. 실패해도 화면 세션에는 그대로 남지만,
    드라이브 저장이 안 되면 새로고침/재배포 시 이번 수정이 사라지므로 반드시
    화면에 명확히 알려야 한다 (수기로 추가한 규칙이 조용히 사라지는 것을 방지)."""
    try:
        pattern_learning.save_style_guide_cache(style_guide)
        return True
    except Exception as exc:  # noqa: BLE001
        st.error(
            f"규칙을 구글 드라이브에 저장하지 못했어요: {exc}\n\n"
            "이 화면에는 반영됐지만, 드라이브에 저장이 안 되면 나중에 사라질 수 있어요. "
            "서비스 계정이 드라이브 폴더에 '편집자'로 공유되어 있는지 확인해주세요."
        )
        return False


def _check_password() -> bool:
    """APP_PASSWORD 시크릿이 설정되어 있으면, 맞는 비밀번호를 입력해야 앱을 쓸 수 있게 한다."""
    if not config.APP_PASSWORD:
        return True  # 비밀번호 미설정 (로컬 개발 등) - 잠금 건너뜀

    if st.session_state.get("authenticated"):
        return True

    st.title("GEO원고, 알아서 다듬어드려요")
    st.info("우리 팀만 쓰는 도구예요. 비밀번호를 입력해주세요.")
    password = st.text_input("비밀번호", type="password")
    if st.button("들어가기"):
        if password == config.APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 맞지 않아요. 다시 확인해주세요.")
    return False


if not _check_password():
    st.stop()

st.title("GEO원고, 알아서 다듬어드려요")

for key, default in {
    "month_folders": None,
    "style_guide": pattern_learning.load_cached_style_guide(),
    "batch_results": None,
    "product_list": None,
    "compliance_result": None,
    "feedback_candidates": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


tab_manuscripts, tab_style_guide, tab_compliance = st.tabs(["원고 리스트", "스타일 가이드", "심의문구 가이드"])


# ══════════════════════════════════════════════════════════════════════
# 탭 1: 원고 리스트 (학습 현황 + 일괄 자동 수정 + 다운로드)
# ══════════════════════════════════════════════════════════════════════
with tab_manuscripts:
    with st.container(border=True):
        st.header("원고 학습 현황")
        st.caption("드라이브를 쭉 살펴보고, 아직 안 배운 수정 이력만 콕 집어서 학습해요.")

        _learning_state = pattern_learning.load_learning_state()
        _rule_count = len((st.session_state.style_guide or {}).get("rules", []))
        st.write(
            f"지금까지 익힌 최종 원고는 **{len(_learning_state.get('processed_pairs', []))}건**, "
            f"정리된 규칙은 **{_rule_count}개**예요."
        )

        if st.button("새 원고 있는지 확인하기", type="primary"):
            with st.spinner("드라이브를 살펴보는 중이에요. 원고가 많으면 조금 걸릴 수 있어요..."):
                try:
                    result = pattern_learning.scan_and_accumulate_learning()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"학습 중 문제가 생겼어요: {exc}")
                    result = None
            if result is not None:
                st.session_state.style_guide = result["style_guide"]
                if result["new_pairs"] > 0:
                    st.success(
                        f"새 원고 {result['new_pairs']}건, 방금 배웠어요. "
                        f"(누적 예시 {result['total_examples']}건, 규칙 {len(result['style_guide'].get('rules', []))}개)"
                    )
                else:
                    st.info("새로 배울 원고가 없어요. 이미 최신이에요.")
                if result["skipped_months"]:
                    st.caption(f"초안·최종본 폴더를 못 찾아서 건너뛴 달: {', '.join(result['skipped_months'])}")
                _learning_state = pattern_learning.load_learning_state()

        _learned_month_labels = pattern_learning.sorted_month_labels(_learning_state.get("learned_months", []))
        if _learned_month_labels:
            st.caption(
                f"여기까지 배웠어요: {', '.join(_learned_month_labels)} "
                f"(가장 최근은 **{_learned_month_labels[-1]}**)"
            )
        else:
            st.caption("아직 배운 달이 없어요.")

    st.write("")

    with st.container(border=True):
        st.header("새 초안 한 번에 수정하기")

        rules = (st.session_state.style_guide or {}).get("rules", [])

        if st.button("월별 폴더 불러오기"):
            try:
                st.session_state.month_folders = drive_client.list_subfolders(config.DRIVE_FOLDER_ID)
            except Exception as exc:  # noqa: BLE001
                st.error(f"드라이브 폴더를 못 불러왔어요: {exc}")
                st.session_state.month_folders = []

        if not st.session_state.month_folders:
            st.info("위 버튼을 눌러서 폴더부터 불러와주세요.")
        else:
            month_names = [f["name"] for f in st.session_state.month_folders]
            target_month = st.selectbox("어느 달 초안을 고칠까요?", month_names, key="target_month")
            target_month_folder = next(f for f in st.session_state.month_folders if f["name"] == target_month)
            target_draft_folder = drive_client.find_subfolder_by_candidates(
                target_month_folder["id"], config.DRAFT_FOLDER_NAME_CANDIDATES
            )

            if not target_draft_folder:
                st.warning("'초안' 폴더를 못 찾았어요.")
            else:
                target_files = drive_client.list_docx_files(target_draft_folder["id"])
                target_names = st.multiselect(
                    "고칠 초안을 골라주세요 (여러 개도 OK)",
                    [f["name"] for f in target_files],
                    key="target_files",
                )
                selected_targets = [f for f in target_files if f["name"] in target_names]

                if st.button("선택한 초안 한 번에 수정하기", type="primary"):
                    if not rules:
                        st.warning("먼저 스타일 가이드부터 준비해주세요 (학습을 반영하거나, 스타일 가이드 탭에서 직접 추가할 수 있어요).")
                    elif not selected_targets:
                        st.warning("고칠 파일을 하나 이상 골라주세요.")
                    else:
                        def _process_file(target_file: dict) -> dict:
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
                            changed_count = sum(1 for r in revisions if r["changed"])
                            return {
                                "name": target_file["name"],
                                "bytes": result_bytes,
                                "total": len(paragraphs),
                                "changed": changed_count,
                                "comments": comment_count,
                                "error": revise_error,
                            }

                        progress = st.progress(0.0)
                        results_by_name = {}
                        with st.spinner(f"원고 {len(selected_targets)}건을 동시에 읽고 고치는 중이에요..."):
                            # 파일마다 순서대로 처리하면 파일 수만큼 대기 시간이 그대로 쌓이므로,
                            # 여러 파일을 동시에 처리해서 전체 소요 시간을 줄인다.
                            with ThreadPoolExecutor(max_workers=min(4, len(selected_targets))) as executor:
                                futures = {
                                    executor.submit(_process_file, target_file): target_file
                                    for target_file in selected_targets
                                }
                                done_count = 0
                                for future in as_completed(futures):
                                    target_file = futures[future]
                                    try:
                                        results_by_name[target_file["name"]] = future.result()
                                    except Exception as exc:  # noqa: BLE001
                                        st.error(f"'{target_file['name']}'을 고치다가 문제가 생겼어요: {exc}")
                                    done_count += 1
                                    progress.progress(done_count / len(selected_targets))

                        results = [
                            results_by_name[target_file["name"]]
                            for target_file in selected_targets
                            if target_file["name"] in results_by_name
                        ]
                        for r in results:
                            if r["error"]:
                                st.error(f"'{r['name']}'을 고치다가 문제가 생겼어요: {r['error']}")
                        st.session_state.batch_results = results
                        st.success(f"{len(results)}건, 다 고쳤어요.")

    st.write("")

    with st.container(border=True):
        st.header("다운로드")

        if not st.session_state.batch_results:
            st.caption("위에서 자동 수정을 실행하면 결과가 여기 쌓여요.")
        else:
            for r in st.session_state.batch_results:
                status = " ⚠️ 자동 수정에 실패해서 원본 그대로예요" if r.get("error") else ""
                st.write(
                    f"- **{r['name']}** : 총 {r['total']}개 문단 중 {r['changed']}개 고쳤어요 "
                    f"(고친 이유는 전부 코멘트로 남겼어요), Word 코멘트 총 {r['comments']}건{status}"
                )

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in st.session_state.batch_results:
                    zf.writestr(f"[수정본] {r['name']}", r["bytes"])

            st.download_button(
                "수정본 전체 한 번에 받기 (zip)",
                data=zip_buffer.getvalue(),
                file_name="수정본_모음.zip",
                mime="application/zip",
            )

            if len(st.session_state.batch_results) == 1:
                only = st.session_state.batch_results[0]
                st.download_button(
                    "수정본 받기 (.docx)",
                    data=only["bytes"],
                    file_name=f"[수정본] {only['name']}",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )


# ══════════════════════════════════════════════════════════════════════
# 탭 2: 스타일 가이드
# ══════════════════════════════════════════════════════════════════════
with tab_style_guide:
    rules = (st.session_state.style_guide or {}).get("rules", [])

    with st.container(border=True):
        st.header("피드백 히스토리 추가")
        st.caption("피드백 사항을 자유롭게 작성하면, 맥락을 파악해서 스타일 가이드에 추가할 내용을 제안해드려요.")
        feedback_text = st.text_area(
            "피드백 내용",
            placeholder="예: 이번 원고에서 상품명을 축약형으로 쓰지 말아 달라는 의견이 있었어요. 앞으로는 항상 정식 명칭을 쓰기로 했어요.",
            key="feedback_text_input",
        )
        if st.button("피드백 분석하기", type="primary"):
            if not feedback_text.strip():
                st.warning("피드백 내용을 먼저 적어주세요.")
            else:
                try:
                    feedback.append_feedback(feedback_text.strip())
                except Exception as exc:  # noqa: BLE001
                    st.error(f"피드백 기록을 드라이브에 저장하지 못했어요: {exc}")
                with st.spinner("피드백 맥락을 분석하는 중이에요..."):
                    try:
                        candidates = feedback.analyze_feedback(feedback_text.strip(), st.session_state.style_guide)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"분석 중 문제가 생겼어요: {exc}")
                        candidates = []
                st.session_state.feedback_candidates = candidates
                if not candidates:
                    st.info("이 피드백에서는 새로 반영할 규칙을 찾지 못했어요. (그래도 기록에는 남겨뒀어요)")

        feedback_log = feedback.load_feedback_log()
        if feedback_log:
            with st.expander(f"지난 피드백 기록 ({len(feedback_log)}건)", expanded=False):
                for entry in reversed(feedback_log[-20:]):
                    st.write(f"- {entry['timestamp']} : {entry['text']}")

    st.write("")

    with st.container(border=True):
        st.header("중간과정 원고 살펴보기")
        st.caption("최종본은 아니어도, 검토 코멘트(Word 메모)가 달린 원고를 올리면 그 코멘트들을 분석해서 스타일 가이드 후보를 뽑아드려요.")
        uploaded_file = st.file_uploader("코멘트가 달린 .docx 파일 업로드", type=["docx"], key="comment_doc_upload")
        if uploaded_file is not None and st.button("코멘트 분석하기", type="primary"):
            doc_bytes = uploaded_file.read()
            uploaded_doc = docx_text.load_document(doc_bytes)
            doc_comments = word_comments.extract_comments(uploaded_doc)
            if not doc_comments:
                st.info("이 문서에서 Word 코멘트를 찾지 못했어요.")
            else:
                combined_text = "\n\n".join(
                    f"[원문] {c['anchored_text']}\n[코멘트] {c['comment']}" for c in doc_comments
                )
                try:
                    feedback.append_feedback(
                        f"(업로드 문서 코멘트 {len(doc_comments)}건 - {uploaded_file.name})\n{combined_text}"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"피드백 기록을 드라이브에 저장하지 못했어요: {exc}")
                with st.spinner(f"코멘트 {len(doc_comments)}건을 분석하는 중이에요..."):
                    try:
                        candidates = feedback.analyze_feedback(combined_text, st.session_state.style_guide)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"분석 중 문제가 생겼어요: {exc}")
                        candidates = []
                st.session_state.feedback_candidates = candidates
                st.success(f"코멘트 {len(doc_comments)}건을 확인했어요.")
                if not candidates:
                    st.info("반영할 만한 규칙을 찾지 못했어요.")

    st.write("")

    if st.session_state.feedback_candidates:
        with st.container(border=True):
            st.write("**반영할 만한 규칙 후보 - 원하는 것만 골라서 추가하세요**")
            selected_candidates = []
            for i, candidate in enumerate(st.session_state.feedback_candidates):
                checked = st.checkbox(
                    f"[{candidate.get('category', '기타')}] {candidate.get('rule', '')}",
                    value=True,
                    key=f"fb_candidate_{i}",
                    help=candidate.get("rationale", ""),
                )
                if checked:
                    selected_candidates.append(candidate)

            if st.button("선택한 규칙 스타일 가이드에 추가"):
                updated_rules = (st.session_state.style_guide or {}).get("rules", [])
                for candidate in selected_candidates:
                    updated_rules.append(
                        {
                            "category": candidate.get("category", "기타"),
                            "rule": candidate.get("rule", ""),
                            "example_before": candidate.get("example_before", ""),
                            "example_after": candidate.get("example_after", ""),
                        }
                    )
                st.session_state.style_guide = {"rules": updated_rules}
                if _save_style_guide_safely(st.session_state.style_guide):
                    st.success(f"{len(selected_candidates)}개 규칙을 추가했어요.")
                st.session_state.feedback_candidates = None
                st.rerun()

    st.write("")

    with st.container(border=True):
        with st.expander("규칙 직접 추가하기", expanded=False):
            st.caption("자동으로 배운 것 말고도, 팀이 이미 알고 있는 규칙을 메모로 바로 추가할 수 있어요.")
            existing_categories = sorted({r.get("category", "기타") for r in rules}) or ["기타"]
            with st.form("add_rule_form", clear_on_submit=True):
                new_rule_text = st.text_area("어떤 규칙을 추가할까요?", placeholder="예: 상품명 뒤에는 항상 '(사후관리형)'을 붙여요")
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    category_choice = st.selectbox("카테고리", existing_categories + ["+ 새 카테고리"])
                with col_b:
                    new_category_name = st.text_input("새 카테고리 이름 (선택했을 때만)")
                submitted = st.form_submit_button("규칙 추가하기")
                if submitted:
                    if not new_rule_text.strip():
                        st.warning("규칙 내용을 먼저 적어주세요.")
                    else:
                        final_category = (
                            new_category_name.strip()
                            if category_choice == "+ 새 카테고리" and new_category_name.strip()
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
                        if _save_style_guide_safely(st.session_state.style_guide):
                            st.success("규칙을 추가했어요.")
                        st.rerun()

    st.write("")

    with st.container(border=True):
        with st.expander("전체 규칙 보기", expanded=False):
            if not rules:
                st.info("아직 규칙이 없어요. '원고 리스트' 탭에서 학습을 반영하거나, 위에서 직접 추가해보세요.")
            else:
                search_query = st.text_input(
                    "규칙 검색", placeholder="규칙 내용이나 카테고리로 검색해보세요", key="rule_search_query"
                ).strip()

                if search_query:
                    matched = [
                        r
                        for r in rules
                        if search_query.lower() in r.get("rule", "").lower()
                        or search_query.lower() in r.get("category", "").lower()
                    ]
                    st.caption(f"검색 결과 {len(matched)}건 (검색 중에는 조회만 가능해요. 수정하려면 검색어를 지워주세요.)")
                    for r in matched:
                        st.markdown(theme.badge_html(r.get("category", "기타"), 0), unsafe_allow_html=True)
                        st.write(r.get("rule", ""))
                        if r.get("example_before") or r.get("example_after"):
                            st.caption(f"예시: {r.get('example_before', '')} -> {r.get('example_after', '')}")
                        st.write("")
                else:
                    st.caption("카테고리별로 접어뒀어요. 펼쳐서 확인하고 고친 다음, 아래 저장 버튼을 눌러주세요.")
                    grouped = defaultdict(list)
                    for rule in rules:
                        grouped[rule.get("category", "기타")].append(rule)

                    pending_by_category = {}
                    for i, (category, items) in enumerate(grouped.items()):
                        rows = [
                            {
                                "rule": r.get("rule", ""),
                                "example_before": r.get("example_before", ""),
                                "example_after": r.get("example_after", ""),
                            }
                            for r in items
                        ]
                        st.markdown(theme.badge_html(category, i), unsafe_allow_html=True)
                        with st.expander(f"{len(rows)}개 규칙 보기", expanded=False):
                            edited_rows = st.data_editor(
                                rows,
                                num_rows="dynamic",
                                use_container_width=True,
                                key=f"style_cat_{category}",
                            )
                            pending_by_category[category] = edited_rows

                    if st.button("저장하기"):
                        new_rules = []
                        for category, edited_rows in pending_by_category.items():
                            for row in edited_rows:
                                if (row.get("rule") or "").strip():
                                    new_rules.append({"category": category, **row})
                        st.session_state.style_guide = {"rules": new_rules}
                        if _save_style_guide_safely(st.session_state.style_guide):
                            st.success("저장했어요.")


# ══════════════════════════════════════════════════════════════════════
# 탭 3: 심의문구 가이드
# ══════════════════════════════════════════════════════════════════════
with tab_compliance:
    with st.container(border=True):
        st.header("심의문구 가이드")
        st.caption("상품을 고르면, 가장 최근 최종본에서 심의문구만 쏙 뽑아 보여드려요.")

        if st.button("상품 목록 불러오기"):
            try:
                st.session_state.product_list = sheets_client.read_product_list()
            except Exception as exc:  # noqa: BLE001
                st.error(f"상품 목록을 못 불러왔어요: {exc}")
                st.session_state.product_list = []

        if not st.session_state.product_list:
            st.info("위 버튼을 눌러서 상품 목록부터 불러와주세요.")
        else:
            product = st.selectbox("어떤 상품인가요?", st.session_state.product_list, key="compliance_product")

            if st.button("심의문구 찾기", type="primary"):
                with st.spinner(f"'{product}' 관련 최신 원고를 찾는 중이에요..."):
                    try:
                        matched_file, compliance_text = compliance.get_compliance_text_for_product(product)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"찾는 중에 문제가 생겼어요: {exc}")
                        matched_file, compliance_text = None, None
                st.session_state.compliance_result = {
                    "product": product,
                    "file": matched_file,
                    "text": compliance_text,
                }

            result = st.session_state.compliance_result
            if result and result["product"] == product:
                if not result["file"]:
                    st.warning("이 상품과 관련된 최종본을 못 찾았어요.")
                elif not result["text"]:
                    st.warning(
                        f"'{result['file']['name']}' 파일은 찾았는데, 그 안에서 심의문구는 못 찾았어요 "
                        "('준법감시인 심사필'로 시작하는 문단이 없어요)."
                    )
                else:
                    st.write(f"여기서 가져왔어요: **{result['file']['name']}**")
                    st.code(result["text"], language=None, height=500, wrap_lines=True)
                    st.caption("우측 상단 복사 아이콘 누르면 바로 복사돼요. 심의번호는 [숫자]로 표시해뒀으니, 실제 번호로 바꿔서 써주세요.")
