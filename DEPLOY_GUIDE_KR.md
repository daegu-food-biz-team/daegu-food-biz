# DAEGU FOOD BIZ · 웹사이트 첫 배포 안내 (Mac·터미널 불필요)

## 목표
ZIP/HTML을 매번 다시 열지 않고, **한 번 만든 Streamlit 웹주소**를 계속 사용하는 방식입니다.

## 준비물
- GitHub 계정 (github.com)
- Streamlit Community Cloud 계정 (share.streamlit.io; GitHub로 로그인 가능)
- 이 프로젝트 폴더 (`DAEGU_FOOD_BIZ_Web_Starter`) 전체

## 최초 1회 배포
1. 이 ZIP 파일을 다운로드하고 압축 해제합니다.
2. GitHub에서 새 저장소를 만듭니다. 예: `daegu-food-biz`. 아직 팀의 원시자료 공개 정책이 정해지지 않았다면 **비공개 저장소**를 권장합니다. Streamlit Community Cloud에 저장소 접근 권한을 부여해야 합니다.
3. GitHub 저장소 `Add file` → `Upload files`에서 압축 해제한 **폴더 안의 파일과 하위 폴더**를 업로드하고 Commit 합니다. ZIP 파일 자체를 업로드하는 것이 아닙니다.
4. https://share.streamlit.io 에 로그인 → `Create app`(또는 `New app`) → `Deploy a public app from GitHub`에서 위 저장소를 선택합니다.
5. Branch: `main`, Main file path: `app.py`. Python 버전은 호환되는 지원 버전(예: 3.11)을 선택하고 배포합니다.
6. 배포되면 `https://...streamlit.app` 형태의 웹주소가 만들어집니다. 이 주소를 북마크하세요. 이후 사용자에게는 이 링크만 공유합니다.

## 다음 수정부터
- `app.py`, `assets/style.css` 또는 `data/*.csv`를 **같은 저장소에서 수정하고 Commit**하면 같은 웹주소에 변경 사항이 반영됩니다.
- 새 ZIP마다 새 앱을 배포할 필요가 없습니다.
- 이전 버전으로 되돌릴 수 있도록 GitHub Commit 기록을 유지합니다.

## 정책·데이터·API 주의
- 현재 앱은 144개 지역 자료 중 병목 진단 65개, 달성군·군위군 현황 14개를 포함합니다. 법정동 경계는 아직 미수령으로 **행정동 임시지도**입니다.
- Gemini API 키와 PostgreSQL 암호는 **절대로 GitHub 파일에 적지 마세요.** Streamlit Cloud 앱 설정의 Secrets에 `GEMINI_API_KEY` / `DATABASE_URL`로 입력합니다.
- 아직 실제 PostgreSQL 서버도, Gemini API 키도 연결하지 않았습니다. 현재 앱은 포함된 CSV와 템플릿 리포트로 작동합니다.
- 무료 Streamlit Community Cloud에도 실행 자원 및 절전 제한이 있습니다. 무료 LLM API도 사용량 한도가 있으므로 서비스가 무제한 무료인 것은 아닙니다.
- 원본 파일에 개인정보나 비공개 팀 자료가 있다면 공개 GitHub 저장소에 업로드하지 마세요. 커밋하기 전에 데이터 공개 범위를 확인하세요.

## 검사
- Python 문법 검사: `python -m compileall -q app.py data_access.py map_views.py scripts`
- 데이터 검사: `python -m unittest discover -s tests -v` (Python 라이브러리 설치 필요)
- 로컬 구동: `streamlit run app.py` (선택 사항이며 웹 배포 후 방문자에게는 필요 없음)

## 공식 문서
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/edit-your-app
