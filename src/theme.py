"""네이비 포인트 컬러 + 진한 원색 배지 조합의 커스텀 CSS/컬러 유틸."""
import streamlit as st

# 카테고리 배지용 - 꽉 찬 원색 + 흰 글씨. 카테고리 개수가 늘어나면 순환해서 씀.
BADGE_COLORS = ["#7F77DD", "#1D9E75", "#D4537E", "#378ADD", "#D85A30"]


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
    --gr-primary: #26215C;
    --gr-primary-dark: #1A1740;
    --gr-bg-soft: #F9F9FB;
    --gr-border: #E4E7EC;
    --gr-text: #1A1D29;
    --gr-text-muted: #6B7280;
    --gr-radius: 12px;
    --gr-radius-sm: 8px;
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
    box-shadow: 0 2px 8px rgba(38, 33, 92, 0.25);
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

/* 탭 - 선택된 탭은 네이비 알약, 아니면 흐린 텍스트 */
[data-testid="stTabs"] [role="tablist"] {
    gap: 0.4rem;
    border-bottom: none;
}
[data-testid="stTab"] {
    border-radius: 999px !important;
    font-weight: 600;
    color: var(--gr-text-muted) !important;
    padding: 0.4rem 1rem !important;
    transition: all 0.15s ease;
}
[data-testid="stTab"] p {
    color: inherit !important;
}
[data-testid="stTab"][aria-selected="true"] {
    color: #fff !important;
    background-color: var(--gr-primary) !important;
}
[data-testid="stTab"] .react-aria-SelectionIndicator {
    display: none;
}

/* 알림 박스 (success/info/warning/error) */
[data-testid="stAlertContainer"], [data-testid="stAlert"] {
    border-radius: var(--gr-radius-sm);
    border: 1px solid var(--gr-border);
}

/* 카드형 컨테이너 (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: var(--gr-radius) !important;
    border-color: var(--gr-border) !important;
}

/* 익스팬더 */
[data-testid="stExpander"] {
    border-radius: var(--gr-radius-sm);
    border-color: var(--gr-border);
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
