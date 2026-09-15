"""토스 스타일(차분한 그레이+블루, 라운드형 컴포넌트)의 커스텀 CSS."""
import streamlit as st

CUSTOM_CSS = """
<style>
:root {
    --gr-primary: #3E5C76;
    --gr-primary-dark: #2E4258;
    --gr-bg-soft: #F4F5F7;
    --gr-border: #E4E7EC;
    --gr-text: #1A1D29;
    --gr-text-muted: #6B7280;
    --gr-radius: 12px;
    --gr-radius-sm: 8px;
}

/* 전체 폭/여백 정리 */
[data-testid="stMainBlockContainer"] {
    max-width: 1000px;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
}

/* 제목/헤더 */
h1, h2, h3, [data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {
    color: var(--gr-text);
    font-weight: 700;
    letter-spacing: -0.02em;
}
[data-testid="stHeading"] h2 {
    margin-top: 0.4rem;
    margin-bottom: 0.2rem;
}

/* 캡션 */
[data-testid="stCaptionContainer"], .stCaption, small {
    color: var(--gr-text-muted) !important;
}

/* 버튼 (기본) */
[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button {
    border-radius: var(--gr-radius-sm);
    border: 1px solid var(--gr-border);
    font-weight: 600;
    padding: 0.5rem 1.1rem;
    transition: all 0.15s ease;
    box-shadow: none;
}
[data-testid="stButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover,
[data-testid="stDownloadButton"] button:hover {
    border-color: var(--gr-primary);
    color: var(--gr-primary);
    transform: translateY(-1px);
}

/* 버튼 (primary) */
[data-testid="stButton"] button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background-color: var(--gr-primary);
    border: none;
    color: #fff;
    box-shadow: 0 2px 8px rgba(62, 92, 118, 0.25);
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

/* 탭 - 알약(pill) 모양 */
[data-testid="stTabs"] [role="tablist"] {
    gap: 0.4rem;
    border-bottom: 1px solid var(--gr-border);
}
[data-testid="stTabs"] button[role="tab"] {
    border-radius: var(--gr-radius-sm) var(--gr-radius-sm) 0 0;
    font-weight: 600;
    color: var(--gr-text-muted);
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: var(--gr-primary);
    background-color: var(--gr-bg-soft);
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
