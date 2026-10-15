# Musicoma 데스크톱 앱 (설치판)

`dist/Musicoma Setup <버전>.exe` 를 실행하면 Electron 셸 "Musicoma" 를 설치한다
(설치 위치 선택 가능, 시작 메뉴 + 바탕화면 바로가기).

## 실행하면 하는 일
1. 엔진(127.0.0.1:47800)과 화면 서버(:47802)가 이미 떠 있는지 본다.
2. 없으면 직접 띄운다 — 엔진 → `ui/server.py` 순서, 창 없이. 로그는 `%LOCALAPPDATA%\Musicoma\logs\`
   (`shell.log`, `engine.log`, `ui-server.log`). 그동안 작은 시작 화면에 진행 상황이 나온다.
3. 준비되면 http://127.0.0.1:47802 를 1600×1000 창으로 연다.
4. 닫으면 **이 앱이 띄운 프로세스만** 끈다. 원래 떠 있던 엔진·서버는 건드리지 않는다.

## 전제 (개인용 "개발 설치")
Python·엔진은 설치 파일에 들어 있지 않다. 루트 폴더에 다음이 있어야 한다.
- `engine/build/musicoma_engine_artefacts/Release/musicoma-engine.exe` (+ `sfizz.dll`) — 엔진 빌드
- `.venv/Scripts/python.exe` — 의존성 설치된 가상환경
- `ui/server.py`, `ui/web/`

## 루트 폴더 바꾸기
기본은 `D:\0.Musicoma`. 다른 곳이면 `%APPDATA%\Musicoma\config.json`:
```json
{ "root": "E:\\somewhere\\0.Musicoma" }
```

## 다시 빌드
```
cd app
npm install
npm run dist        # → dist/Musicoma Setup 0.1.0.exe
npm start           # 설치 없이 바로 실행
```
아이콘을 바꾸면 `python scripts/make-icon.py` (Pillow) 로 `build/icon.ico` 를 다시 만든다.
서명 인증서가 없으면 서명은 자동으로 건너뛴다(그래서 첫 실행 때 SmartScreen 경고가 뜰 수 있다).
