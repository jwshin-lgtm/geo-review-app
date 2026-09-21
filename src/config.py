"""앱 전역 설정. 실제 값은 .streamlit/secrets.toml 또는 환경변수에서 읽는다.

Hugging Face Spaces처럼 "Repository secrets"가 단순 키-값(환경변수)만 지원하는
플랫폼을 위해, 서비스 계정 JSON은 GCP_SERVICE_ACCOUNT_JSON 환경변수(JSON 문자열
전체)로도 넣을 수 있게 되어 있다.
"""
import base64
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

# 팀원별로 무료 API 키를 여러 개 등록해두면, 한 키가 하루 사용량 한도를 넘겼을 때
# 자동으로 다음 키로 넘어가서 계속 쓸 수 있다. 쉼표/줄바꿈으로 구분해서 넣으면 된다
# (예: "키1, 키2, 키3"). 비워두면 GEMINI_API_KEY 하나만 쓴다.
_gemini_api_keys_raw = _get("GEMINI_API_KEYS")
if _gemini_api_keys_raw:
    GEMINI_API_KEYS = [
        key.strip()
        for key in _gemini_api_keys_raw.replace("\n", ",").split(",")
        if key.strip()
    ]
elif GEMINI_API_KEY:
    GEMINI_API_KEYS = [GEMINI_API_KEY]
else:
    GEMINI_API_KEYS = []
DRIVE_FOLDER_ID = _get("DRIVE_FOLDER_ID", "1Xzb7MLEyM0TFwbuKKr0YiGyhpRCz13bc")

# 서비스 계정 정보 (dict). 아래 중 먼저 발견되는 방식으로 읽는다.
# - GCP_SERVICE_ACCOUNT_JSON_B64: JSON 파일을 base64로 인코딩한 값 (TOML/환경변수 어디에
#   넣어도 특수문자로 깨질 일이 없어 가장 안전함 - 권장)
# - GCP_SERVICE_ACCOUNT_JSON: JSON 문자열 그대로 (Hugging Face 환경변수 등)
# - [gcp_service_account] TOML 테이블 (Streamlit secrets.toml에서 필드별로 나눠 적은 경우)
_service_account_json_b64 = _get("GCP_SERVICE_ACCOUNT_JSON_B64")
_service_account_json = _get("GCP_SERVICE_ACCOUNT_JSON")
if _service_account_json_b64:
    GCP_SERVICE_ACCOUNT_INFO = json.loads(base64.b64decode(_service_account_json_b64).decode("utf-8"))
elif _service_account_json:
    GCP_SERVICE_ACCOUNT_INFO = json.loads(_service_account_json)
elif _has_secret("gcp_service_account"):
    GCP_SERVICE_ACCOUNT_INFO = dict(_SECRETS["gcp_service_account"])
else:
    GCP_SERVICE_ACCOUNT_INFO = None

# 월별 폴더 아래에서 초안/최종본을 찾을 때 시도할 폴더명 후보 (실제 명명 규칙 확인 후 조정)
DRAFT_FOLDER_NAME_CANDIDATES = ["초안", "draft", "Draft"]
FINAL_FOLDER_NAME_CANDIDATES = ["최종본", "최종", "final", "Final"]

GOOGLE_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GOOGLE_NATIVE_DOC_MIME = "application/vnd.google-apps.document"

GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-3.6-flash")

# Space가 Public이어도 아무나 못 쓰게 막는 팀 공용 비밀번호. 시크릿에 없으면 잠금 화면 자체를 건너뛴다
# (로컬 개발 편의용 - 실제 배포 시에는 반드시 APP_PASSWORD 시크릿을 넣을 것).
APP_PASSWORD = _get("APP_PASSWORD")

STYLE_GUIDE_CACHE_PATH = "data/style_guide_cache.json"

# 심의문구 가이드 탭에서 쓸 "주요 상품" 목록이 들어있는 구글 시트
PRODUCT_SHEET_ID = _get("PRODUCT_SHEET_ID", "1fZXl7wWqHOdToA3KflB8KlYsWfu3AFIaLNvDiEtCeH8")
PRODUCT_SHEET_RANGE = _get("PRODUCT_SHEET_RANGE", "B:B")

# 심의문구 블록의 시작을 알리는 고정 문구 (KB증권 준법감시인 심사필 안내)
COMPLIANCE_ANCHOR_PATTERN = r"준법감시인\s*심사필"
