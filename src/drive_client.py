"""Google Drive 읽기 전용 클라이언트 (서비스 계정 인증)."""
from __future__ import annotations

import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from . import config

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    if not config.GCP_SERVICE_ACCOUNT_INFO:
        raise RuntimeError(
            "서비스 계정 정보가 없습니다. .streamlit/secrets.toml 의 [gcp_service_account] 를 채워주세요."
        )
    credentials = service_account.Credentials.from_service_account_info(
        config.GCP_SERVICE_ACCOUNT_INFO, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def list_children(folder_id: str) -> list[dict]:
    """폴더 안의 파일/폴더 목록. [{id, name, mimeType}, ...]"""
    service = get_drive_service()
    items: list[dict] = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
            )
            .execute()
        )
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return items


def list_subfolders(folder_id: str) -> list[dict]:
    return [
        item
        for item in list_children(folder_id)
        if item["mimeType"] == "application/vnd.google-apps.folder"
    ]


def list_docx_files(folder_id: str) -> list[dict]:
    """폴더 안의 문서 파일만 (일반 .docx + 구글 문서 네이티브 파일 모두 포함)."""
    return [
        item
        for item in list_children(folder_id)
        if item["mimeType"] in (config.GOOGLE_DOCX_MIME, config.GOOGLE_NATIVE_DOC_MIME)
    ]


def find_subfolder_by_candidates(folder_id: str, name_candidates: list[str]) -> dict | None:
    subfolders = {f["name"]: f for f in list_subfolders(folder_id)}
    for candidate in name_candidates:
        if candidate in subfolders:
            return subfolders[candidate]
    return None


def download_docx_bytes(file_id: str, mime_type: str) -> bytes:
    """파일을 .docx 바이트로 받는다. 구글 문서 네이티브 파일이면 docx로 export한다."""
    service = get_drive_service()
    if mime_type == config.GOOGLE_NATIVE_DOC_MIME:
        request = service.files().export_media(fileId=file_id, mimeType=config.GOOGLE_DOCX_MIME)
    else:
        request = service.files().get_media(fileId=file_id)

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()
