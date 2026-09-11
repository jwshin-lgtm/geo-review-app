"""앱 전역 설정. 실제 값은 .streamlit/secrets.toml 또는 환경변수에서 읽는다.

Hugging Face Spaces처럼 "Repository secrets"가 단순 키-값(환경변수)만 지원하는
플랫폼을 위해, 서비스 계정 JSON은 GCP_SERVICE_ACCOUNT_JSON 환경변수(JSON 문자열
전체)로도 넣을 수 있게 되어 있다.
"""
import json
import os

try:
    import streamlit as st
    _SECRETS = st.secrets
    _SECRETS_OK = True
except Exception:
    _SECRETS = {}
    _SECRETS_OK = False


def _has_secret(key: str) -> bool:
    if not _SECRETS_OK:
        return False
    try:
        return key in _SECRETS
    except Exception:
        # secrets.toml이 아예 없는 로컬 실행 등 - 시크릿 미사용으로 취급
        return False


def _get(key: str, default: str | None = None) -> str | None:
    if _has_secret(key):
        return _SECRETS[key]
    return os.environ.get(key, default)


GEMINI_API_KEY = _get("GEMINI_API_KEY")
DRIVE_FOLDER_ID = _get("DRIVE_FOLDER_ID", "1Xzb7MLEyM0TFwbuKKr0YiGyhpRCz13bc")

# 서비스 계정 정보 (dict).
# - Streamlit Cloud: secrets.toml의 [gcp_service_account] 테이블
# - Hugging Face Spaces 등: GCP_SERVICE_ACCOUNT_JSON 환경변수(JSON 문자열 전체)
if _has_secret("gcp_service_account"):
    GCP_SERVICE_ACCOUNT_INFO = dict(_SECRETS["gcp_service_account"])
elif os.environ.get("GCP_SERVICE_ACCOUNT_JSON"):
    GCP_SERVICE_ACCOUNT_INFO = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
else:
    GCP_SERVICE_ACCOUNT_INFO = None

# 월별 폴더 아래에서 초안/최종본을 찾을 때 시도할 폴더명 후보 (실제 명명 규칙 확인 후 조정)
DRAFT_FOLDER_NAME_CANDIDATES = ["초안", "draft", "Draft"]
FINAL_FOLDER_NAME_CANDIDATES = ["최종본", "최종", "final", "Final"]

GOOGLE_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GOOGLE_NATIVE_DOC_MIME = "application/vnd.google-apps.document"

GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash")

# Space가 Public이어도 아무나 못 쓰게 막는 팀 공용 비밀번호. 시크릿에 없으면 잠금 화면 자체를 건너뛴다
# (로컬 개발 편의용 - 실제 배포 시에는 반드시 APP_PASSWORD 시크릿을 넣을 것).
APP_PASSWORD = _get("APP_PASSWORD")

STYLE_GUIDE_CACHE_PATH = "data/style_guide_cache.json"
