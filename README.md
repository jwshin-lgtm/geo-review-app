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
3. "API 및 서비스" → "사용자 인증 정보" → "사용자 인증 정보 만들기" → "서비스 계정" 선택 → 이름 아무거나(예: `geo-review-bot`) 입력 후 생성
4. 생성된 서비스 계정 클릭 → "키" 탭 → "키 추가" → "새 키 만들기" → JSON 선택 → 다운로드
   (이 JSON 파일이 비밀키입니다. 절대 이메일/깃허브/채팅에 올리지 마세요)
5. JSON 파일을 열면 `client_email` 값이 있습니다 (예: `geo-review-bot@geo-review.iam.gserviceaccount.com`)
6. 구글 드라이브에서 원고가 있는 폴더를 우클릭 → "공유" → 5번의 이메일 주소를 추가 → 권한은 "뷰어"로 지정

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

## 3. 팀원들과 웹으로 공유하기 (배포)

1. 이 폴더를 GitHub private 저장소로 올립니다 (`secrets.toml`은 `.gitignore`에 있어 자동으로 제외됩니다)
2. https://share.streamlit.io 접속 → GitHub 계정 연결 → 방금 올린 저장소 선택, `app.py`를 진입점으로 지정 → Deploy
3. 앱 설정(⋮ 메뉴) → "Secrets" 에 `.streamlit/secrets.toml`에 적었던 내용을 그대로 붙여넣기
4. 배포되면 나온 URL을 팀원들에게 공유하면 됩니다

## 4. 폴더 구조가 다를 때

`src/config.py`의 `DRAFT_FOLDER_NAME_CANDIDATES`, `FINAL_FOLDER_NAME_CANDIDATES`에
실제 드라이브의 폴더명(예: "초안", "final" 등)을 추가/수정하면 됩니다.

## 5. 문제 해결

- **"서비스 계정 정보가 없습니다" 오류**: secrets.toml의 `[gcp_service_account]` 항목이 비어있거나 형식이 잘못됨
- **"GEMINI_API_KEY가 설정되어 있지 않습니다" 오류**: secrets.toml에 키를 넣었는지 확인
- **드라이브 폴더 목록이 안 보임**: 해당 폴더를 서비스 계정 이메일(`client_email`)과 공유했는지 확인
- **자동 수정이 "원본과 동일"하다고만 나옴**: 스타일 가이드 규칙이 비어있거나, 이번 초안이 과거 패턴과 관련이 적을 수 있습니다. ②에서 스타일 가이드 규칙을 늘리거나 조정해보세요
