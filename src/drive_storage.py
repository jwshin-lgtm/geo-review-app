"""학습 상태/스타일 가이드/피드백 기록을 로컬 파일이 아니라 구글 드라이브에 저장한다.

Streamlit Cloud 컨테이너는 재배포·재부팅될 때마다 로컬 디스크가 통째로 초기화된다.
data/*.json을 로컬에만 저장하면 그때마다 학습 내용이 사라져서, 이미 학습했던
초안/최종본 쌍까지 처음부터 다시 학습시키느라 Gemini 토큰을 반복해서 낭비하게
된다. 대신 대상 드라이브 폴더(DRIVE_FOLDER_ID) 안에 파일로 저장해두면, 재배포와
무관하게 항상 이어서 쓸 수 있다.

주의: 이 기능을 쓰려면 서비스 계정이 해당 드라이브 폴더에 "편집자"로 공유되어
있어야 한다 (기존에는 "뷰어"로만 공유해도 됐지만, 이제는 쓰기 권한이 필요하다).
"""
from __future__ import annotations

import json

from . import config, drive_client


def load_json(file_name: str, default):
    file = drive_client.find_file_by_name(config.DRIVE_FOLDER_ID, file_name)
    if not file:
        return default
    raw = drive_client.download_file_bytes(file["id"])
    if not raw:
        return default
    return json.loads(raw.decode("utf-8"))


def save_json(file_name: str, data) -> None:
    drive_client.upload_json(config.DRIVE_FOLDER_ID, file_name, data)
