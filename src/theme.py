"""네이비 포인트 컬러 + 진한 원색 배지 조합의 커스텀 CSS/컬러 유틸."""
import streamlit as st

# 카테고리 배지용 - 꽉 찬 원색 + 흰 글씨. 카테고리 개수가 늘어나면 순환해서 씀.
# 크림+테라코타 팔레트와 어울리도록 전부 따뜻한 톤으로 통일 (파란/보라 계열 제외).
BADGE_COLORS = ["#B4432A", "#8A7B2E", "#6B7A3F", "#8C4A5C", "#C1862B"]


def badge_color(index: int) -> str:
    return BADGE_COLORS[index % len(BADGE_COLORS)]


def badge_html(label: str, index: int) -> str:
    color = badge_color(index)
    return (
        f'<span style="background:{color};color:#fff;padding:5px 14px;'
        f'border-radius:999px;font-size:14px;font-weight:600;'
        f'display:inline-block;margin-bottom:6px;">{label}</span>'
    )


CUSTOM_CSS = """
<style>
:root {
    --gr-primary: #C1622B;
    --gr-primary-dark: #9C4E22;
    --gr-bg-soft: #F1EAD9;
    --gr-border: #E8DFCB;
    --gr-text: #221F1B;
    --gr-text-muted: #8C8577;
    --gr-radius: 12px;
    --gr-radius-sm: 8px;
}

/* 페이지 배경(크림톤). 카드는 흰 배경으로 대비를 줌 */
[data-testid="stAppViewContainer"] {
    background-color: #F7F4EC;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF;
}

/* 전체 폭/여백 정리 */
[data-testid="stMainBlockContainer"] {
    max-width: 1000px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}

/* 제목/헤더 - 기본 크기가 너무 커서 축소 */
[data-testid="stHeading"] h1 {
    font-size: 1.6rem !important;
    color: var(--gr-text);
    font-weight: 700;
    letter-spacing: -0.02em;
}
[data-testid="stHeading"] h2 {
    font-size: 1.15rem !important;
    color: var(--gr-text);
    font-weight: 700;
    letter-spacing: -0.01em;
    margin-top: 0.4rem;
    margin-bottom: 0.2rem;
}
[data-testid="stHeading"] h3 {
    font-size: 1rem !important;
    color: var(--gr-text);
    font-weight: 700;
}

/* 캡션 */
[data-testid="stCaptionContainer"], .stCaption, small {
    color: var(--gr-text-muted) !important;
}

/* 버튼 - 기본(테두리만, secondary) */
[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button {
    border-radius: 999px;
    border: 1px solid var(--gr-primary);
    color: var(--gr-primary);
    background-color: #fff;
    font-weight: 600;
    padding: 0.5rem 1.2rem;
    transition: all 0.15s ease;
    box-shadow: none;
}
[data-testid="stButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover,
[data-testid="stDownloadButton"] button:hover {
    background-color: var(--gr-bg-soft);
    color: var(--gr-primary);
    transform: translateY(-1px);
}

/* 버튼 - primary (채움) */
[data-testid="stButton"] button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background-color: var(--gr-primary);
    border: none;
    color: #fff;
    box-shadow: 0 2px 8px rgba(193, 98, 43, 0.25);
}
[data-testid="stButton"] button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
    background-color: var(--gr-primary-dark);
    color: #fff;
}

/* 입력 요소 (텍스트/셀렉트/멀티셀렉트) */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    border-radius: var(--gr-radius-sm) !important;
    border-color: var(--gr-border) !important;
}

/* 탭 - 밑줄형(언더라인) 탭. 전체 폭 얇은 베이스라인 + 선택된 탭만 굵게+포인트컬러 밑줄 */
[data-testid="stTabs"] [role="tablist"] {
    gap: 1.6rem;
    display: flex;
    background-color: transparent;
    border: none;
    border-bottom: 1px solid var(--gr-border);
    padding: 0;
    border-radius: 0;
    margin-bottom: 1.4rem;
}
[data-testid="stTab"] {
    border-radius: 0 !important;
    font-weight: 500;
    color: var(--gr-text-muted) !important;
    padding: 0.6rem 0.1rem !important;
    margin-bottom: -1px;
    border-bottom: 2px solid transparent !important;
    transition: color 0.15s ease, border-color 0.15s ease;
}
[data-testid="stTab"]:hover {
    color: var(--gr-primary) !important;
}
[data-testid="stTab"] p {
    color: inherit !important;
}
[data-testid="stTab"][aria-selected="true"] {
    color: var(--gr-primary) !important;
    background-color: transparent !important;
    font-weight: 700;
    border-bottom: 2px solid var(--gr-primary) !important;
    box-shadow: none;
}
[data-testid="stTab"] .react-aria-SelectionIndicator {
    display: none;
}
/* BaseWeb 기본 밑줄 인디케이터가 우리 밑줄과 겹쳐 두 줄로 보이던 문제 제거 */
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}
[data-testid="stTabs"] {
    border-bottom: none !important;
}
[data-testid="stTabs"] [role="tabpanel"] {
    padding-top: 0 !important;
}

/* 알림 박스 (success/info/warning/error) - Streamlit 기본 파란색 대신 팔레트 톤으로 */
[data-testid="stAlertContainer"], [data-testid="stAlert"] {
    border-radius: var(--gr-radius-sm);
    border: 1px solid var(--gr-border);
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
    background-color: rgba(193, 98, 43, 0.08) !important;
}
[data-testid="stAlertContentInfo"] p,
[data-testid="stAlertContentInfo"] [data-testid="stIconMaterial"] {
    color: #9C4E22 !important;
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
    background-color: rgba(107, 142, 35, 0.12) !important;
}
[data-testid="stAlertContentSuccess"] p,
[data-testid="stAlertContentSuccess"] [data-testid="stIconMaterial"] {
    color: #4B6B12 !important;
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
    background-color: rgba(217, 150, 6, 0.14) !important;
}
[data-testid="stAlertContentWarning"] p,
[data-testid="stAlertContentWarning"] [data-testid="stIconMaterial"] {
    color: #8A6100 !important;
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
    background-color: rgba(190, 60, 40, 0.10) !important;
}
[data-testid="stAlertContentError"] p,
[data-testid="stAlertContentError"] [data-testid="stIconMaterial"] {
    color: #8C2E1D !important;
}

/* 카드형 컨테이너 (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: var(--gr-radius) !important;
    border-color: var(--gr-border) !important;
}

/* 익스팬더 - 제목을 소제목처럼 굵고 크게 */
[data-testid="stExpander"] {
    border-radius: var(--gr-radius-sm);
    border-color: var(--gr-border);
}
[data-testid="stExpander"] summary {
    padding: 0.9rem 1rem;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary * {
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em;
}
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {
    color: var(--gr-text) !important;
}
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    font-size: 1.3rem !important;
}

/* 코드 블록 (심의문구 표시) */
[data-testid="stCode"] {
    border-radius: var(--gr-radius-sm);
    border: 1px solid var(--gr-border);
}

/* 진행바 */
[data-testid="stProgress"] > div > div {
    border-radius: 999px;
}
[data-testid="stProgress"] > div > div > div {
    background-color: var(--gr-primary);
}

/* 구분선 여백 축소 */
hr {
    margin: 1.4rem 0;
    border-color: var(--gr-border);
}
</style>
"""


def inject() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
