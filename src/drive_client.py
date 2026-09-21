"""Google Drive 클라이언트 (서비스 계정 인증).

학습 상태/스타일 가이드를 드라이브에 저장하는 기능(drive_storage.py) 때문에
읽기 전용이 아니라 읽기/쓰기 스코프를 쓴다. 이 서비스 계정은 대상 폴더에
"편집자"로 공유되어 있어야 쓰기가 정상 동작한다.
"""
from __future__ import annotations

import io
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from . import config

SCOPES = ["https://www.googleapis.com/auth/drive"]


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
    """폴더 안의 파일/폴더 목록. [{id, name, mimeType, modifiedTime}, ...]"""
    service = get_drive_service()
    items: list[dict] = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
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
    """폴더명에 후보 문자열이 '포함'되어 있으면 매칭한다.

    실제 폴더명이 "01. 초안", "02. 최종"처럼 번호/공백이 붙어있는 경우가 많아
    정확히 일치하는 이름만 찾으면 못 찾기 때문에 부분 일치로 판단한다.
    """
    subfolders = list_subfolders(folder_id)
    for candidate in name_candidates:
        for folder in subfolders:
            if candidate.lower() in folder["name"].lower():
                return folder
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


def download_file_bytes(file_id: str) -> bytes:
    """구글 문서가 아닌 일반 파일(JSON 등)을 그대로 바이트로 받는다."""
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def find_file_by_name(folder_id: str, name: str) -> dict | None:
    service = get_drive_service()
    safe_name = name.replace("'", "\\'")
    query = f"'{folder_id}' in parents and name = '{safe_name}' and trashed = false"
    response = service.files().list(q=query, fields="files(id, name)").execute()
    files = response.get("files", [])
    return files[0] if files else None


def upload_json(folder_id: str, name: str, data: dict) -> None:
    """JSON 데이터를 폴더 안에 파일로 저장한다 (같은 이름 파일이 있으면 덮어쓰기)."""
    service = get_drive_service()
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="application/json")
    existing = find_file_by_name(folder_id, name)
    if existing:
        service.files().update(fileId=existing["id"], media_body=media).execute()
    else:
        service.files().create(body={"name": name, "parents": [folder_id]}, media_body=media).execute()
