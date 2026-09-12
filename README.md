---
title: GEO 원고 자동 수정
emoji: 📝
colorFrom: blue
colorTo: green
sdk: streamlit
app_file: app.py
pinned: false
---

# GEO 원고 자동 수정 웹앱

과거 초안→최종본 수정 이력을 분석해서, 새 달 초안에 비슷한 수정을 자동으로 반영하고
바뀐 부분을 하이라이트한 Word 파일로 다운로드하는 내부 도구입니다.

## 1. 준비물 (한 번만 하면 됩니다)

### 1-1. Gemini API 키 발급
1. https://aistudio.google.com/apikey 접속 (구글 계정 로그인)
2. "Create API key" 클릭 → 키 복사

### 1-2. 구글 서비스 계정 만들기 (드라이브 읽기 전용 접근용)
1. https://console.cloud.google.com 접속 → 새 프로젝트 생성 (예: `geo-review`)
2. 좌측 메뉴 "API 및 서비스" → "라이브러리" → "Google Drive API" 검색 → 사용 설정
3. 같은 방법으로 **"Google Sheets API"도 검색해서 사용 설정** (심의문구 가이드 탭의 상품 목록 시트를 읽는 데 필요)
4. "API 및 서비스" → "사용자 인증 정보" → "사용자 인증 정보 만들기" → "서비스 계정" 선택 → 이름 아무거나(예: `geo-review-bot`) 입력 후 생성
5. 생성된 서비스 계정 클릭 → "키" 탭 → "키 추가" → "새 키 만들기" → JSON 선택 → 다운로드
   (이 JSON 파일이 비밀키입니다. 절대 이메일/깃허브/채팅에 올리지 마세요)
6. JSON 파일을 열면 `client_email` 값이 있습니다 (예: `geo-review-bot@geo-review.iam.gserviceaccount.com`)
7. 구글 드라이브에서 원고가 있는 폴더를 우클릭 → "공유" → 6번의 이메일 주소를 추가 → 권한은 "뷰어"로 지정
8. **상품 목록이 들어있는 구글 시트도 똑같이 6번 이메일과 "뷰어"로 공유** (심의문구 가이드 탭에서 사용)

## 2. 로컬에서 실행해보기

1. Python 설치 (3.11 이상 권장)
2. 이 폴더에서:
   ```bash
   pip install -r requirements.txt
   ```
3. `.streamlit/secrets.toml.example` 파일을 복사해서 `.streamlit/secrets.toml` 로 저장하고,
   - `GEMINI_API_KEY` : 1-1에서 발급받은 키
   - `DRIVE_FOLDER_ID` : 원고가 들어있는 구글 드라이브 폴더 ID
   - `[gcp_service_account]` : 1-2에서 다운로드한 JSON 파일 내용을 그대로 옮겨 적기
4. 실행:
   ```bash
   streamlit run app.py
   ```
   브라우저가 자동으로 열립니다.

## 3. 팀원들과 웹으로 공유하기 (배포) — Hugging Face Spaces

GitHub을 거치지 않고, 계정 만드는 곳과 앱이 실제로 돌아가는 곳이 같은 서비스를 씁니다.

1. https://huggingface.co 에서 무료 회원가입
2. 우측 상단 프로필 → **New Space** 클릭
   - Space name: 아무거나 (예: `geo-review-app`)
   - License: 신경쓰지 않아도 됨
   - **Space SDK**: **Streamlit** 선택
   - Visibility: **Private** 선택 (팀 내부용이므로)
   - "Create Space" 클릭
3. Space가 만들어지면 상단 탭의 **Settings** → **Variables and secrets** 로 이동해서 아래 값들을 하나씩 "New secret"으로 추가 (TOML 문법 없이, Name/Value만 입력하면 됩니다):
   - `GEMINI_API_KEY` : 1-1에서 발급받은 키
   - `DRIVE_FOLDER_ID` : 원고가 들어있는 구글 드라이브 폴더 ID
   - `GCP_SERVICE_ACCOUNT_JSON` : 1-2에서 다운로드한 JSON 파일을 텍스트 편집기로 열어서, **내용 전체를 그대로 복사해서 붙여넣기** (필드별로 나눠 적을 필요 없음)
   - `APP_PASSWORD` : 팀원들과 공유할 비밀번호 (아무 문자열이나 직접 정하기) — Space가 Public이어도 이 비밀번호를 아는 사람만 앱을 쓸 수 있게 막아줍니다
4. 코드는 이 프로젝트를 만든 세션(Claude)이 직접 올려드립니다 — Space 이름만 알려주시면 됩니다
5. 몇 분 뒤 Space 페이지에서 앱이 뜨면, 그 페이지 주소를 팀원들에게 공유하면 됩니다 (Private Space는 Hugging Face 계정으로 로그인한, 초대된 사람만 볼 수 있습니다 → Settings에서 팀원 초대 가능)

> 참고: GitHub + Streamlit Community Cloud 조합도 여전히 가능하지만, 저장소 접근 권한을 별도로 연결해야 해서 단계가 하나 더 필요합니다. 위 Hugging Face 방식이 더 간단합니다.

## 4. 폴더 구조가 다를 때

`src/config.py`의 `DRAFT_FOLDER_NAME_CANDIDATES`, `FINAL_FOLDER_NAME_CANDIDATES`에
실제 드라이브의 폴더명(예: "초안", "final" 등)을 추가/수정하면 됩니다.

## 5. 문제 해결

- **"서비스 계정 정보가 없습니다" 오류**: (Streamlit Cloud) secrets.toml의 `[gcp_service_account]` 항목이 비어있음 / (Hugging Face) `GCP_SERVICE_ACCOUNT_JSON` 시크릿이 비어있거나 JSON 형식이 깨짐
- **"GEMINI_API_KEY가 설정되어 있지 않습니다" 오류**: secrets.toml에 키를 넣었는지 확인
- **드라이브 폴더 목록이 안 보임**: 해당 폴더를 서비스 계정 이메일(`client_email`)과 공유했는지 확인
- **자동 수정이 "원본과 동일"하다고만 나옴**: 스타일 가이드 규칙이 비어있거나, 이번 초안이 과거 패턴과 관련이 적을 수 있습니다. ②에서 스타일 가이드 규칙을 늘리거나 조정해보세요
