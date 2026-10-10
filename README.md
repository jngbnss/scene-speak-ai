# SceneSpeak AI

가상의 뉴욕 카페에서 AI 직원과 영어로 주문하는 스토리형 여행 영어회화 서비스입니다. 정해진 문장을 따라 읽지 않고 자유롭게 말하면, Scene Director가 장면을 유지하고 대화가 끝나면 피드백을 줍니다.

- 설계: [docs/design.md](docs/design.md)
- 구현 계획과 진행 상황: [docs/implementation-plan.md](docs/implementation-plan.md)
- 결정 기록: [docs/decision-log.md](docs/decision-log.md)

## 현재 상태

단계 1(뼈대 + Scene Director)까지 구현했습니다. 텍스트로 주문하면 Director가 주문 상태를 관리하고, 장면 YAML의 템플릿 문장으로 응답합니다. 음성인식, LLM, 음성 합성은 아직 Mock입니다.

## 실행 방법

필요한 것: Python 3.12, Node.js 20 이상. Python은 [uv](https://docs.astral.sh/uv/)로 설치하는 것을 권장합니다.

### Windows (PowerShell)

```powershell
# 백엔드
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload
```

```powershell
# 프론트엔드 (새 터미널)
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 을 엽니다.

### macOS / Linux

```bash
cd backend
uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --port 8000 --reload
# 새 터미널
cd frontend && npm install && npm run dev
```

## 해볼 시나리오

| 입력 | 기대 결과 |
|---|---|
| `I want hot latte.` → `Large, please. And can I have oat milk?` → `Yes, that's all.` | 주문 성공 |
| `Can I get a pumpkin spice latte?` | 메뉴에 없다고 안내 |
| `A medium hot cold brew.` → `Sure.` | iced만 가능하다고 안내 후 iced로 변경 |
| `A medium iced americano with oat milk.` | 우유가 안 되는 음료라고 안내 |
| `Never mind, cancel my order.` | 주문 취소 |

## 테스트

```powershell
cd backend
.venv\Scripts\python.exe -m pytest           # Director, 추출기, 가드, WebSocket, 어댑터
.venv\Scripts\ruff.exe check . ; .venv\Scripts\ruff.exe format --check .
.venv\Scripts\python.exe -m app.scenes.validate   # 장면 파일 검사

cd ..\frontend
npm run typecheck ; npm test ; npm run build
```

CI(`.github/workflows/ci.yml`)는 같은 검사를 Mock 어댑터로만 실행하며 AI 모델을 내려받지 않습니다.

## 장면 추가·수정

장면은 `scenes/*.yaml`에 있고 코드에는 메뉴나 대사가 없습니다. 수정한 뒤 `python -m app.scenes.validate`로 검사하세요. 검사 항목은 JSON Schema, 별칭 중복, 단계 참조, 템플릿 placeholder, 그리고 모든 템플릿 문장이 출력 가드를 통과하는지입니다. Director 동작을 바꿨다면 `evals/dialogue-cases.jsonl`에 케이스를 추가하세요.

## 데이터와 개인정보

`.env`, 모델 파일, 음성 녹음(`*.wav` 등), `data/`, `evals/audio/`는 Git에 올리지 않습니다.

Talklish 등 기존 서비스의 이름, 대사, 캐릭터, 이미지는 사용하지 않으며 모든 장면 대사는 직접 작성합니다.
