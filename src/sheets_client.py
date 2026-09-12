"""Google Sheets 읽기 전용 클라이언트 (서비스 계정 인증) - 주요 상품 목록용."""
from __future__ import annotations

from google.oauth2 import service_account
from googleapiclient.discovery import build

from . import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

_HEADER_LIKE_VALUES = {"상품명", "상품", "product", "products", "이름"}


def get_sheets_service():
    if not config.GCP_SERVICE_ACCOUNT_INFO:
        raise RuntimeError(
            "서비스 계정 정보가 없습니다. .streamlit/secrets.toml 의 [gcp_service_account] 를 채워주세요."
        )
    credentials = service_account.Credentials.from_service_account_info(
        config.GCP_SERVICE_ACCOUNT_INFO, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def read_product_list(
    spreadsheet_id: str = config.PRODUCT_SHEET_ID,
    range_name: str = config.PRODUCT_SHEET_RANGE,
) -> list[str]:
    """상품명이 나열된 시트의 한 열을 읽어 리스트로 반환한다. 헤더로 보이는 첫 줄은 제외."""
    service = get_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    rows = result.get("values", [])
    products = [row[0].strip() for row in rows if row and row[0].strip()]
    if products and products[0].strip().lower() in _HEADER_LIKE_VALUES:
        products = products[1:]
    # 중복 제거 (순서 유지)
    seen = set()
    unique_products = []
    for name in products:
        if name not in seen:
            seen.add(name)
            unique_products.append(name)
    return unique_products
