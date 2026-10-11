# SceneSpeak AI

가상의 뉴욕 카페에서 AI 직원과 영어로 주문하는 스토리형 여행 영어회화 서비스입니다. 정해진 문장을 따라 읽지 않고 자유롭게 말하면, Scene Director가 장면을 유지하고 대화가 끝나면 피드백을 줍니다.

- 설계: [docs/design.md](docs/design.md)
- 구현 계획과 진행 상황: [docs/implementation-plan.md](docs/implementation-plan.md)
- 결정 기록: [docs/decision-log.md](docs/decision-log.md)

## 현재 상태

단계 2(LLM NPC + 피드백·학습 기록)까지 구현했습니다.

- 텍스트로 주문하면 Scene Director가 주문 상태를 관리하고, Qwen3-8B(Ollama)가 Director가 정한 행동을 대사로 표현합니다. 출력 가드에 두 번 걸리면 장면 YAML의 템플릿 문장을 씁니다.
- 대화가 끝나면 Learning Evaluator가 문법·표현 피드백과 복습 문장을 만들고, 닉네임별로 SQLite에 저장합니다.
- 단계 3(음성 입력·출력)까지 실제 모델로 서버 전체를 검증했습니다(`docs/implementation-plan.md`). 기본값은 Mock이고, 아래 "음성 준비"를 따르면 마이크로 말하고 NPC 음성을 들을 수 있습니다.

## 실행 방법

필요한 것: Python 3.12, Node.js 20 이상, (LLM을 쓰려면) [Ollama](https://ollama.com)와 NVIDIA GPU. Python은 [uv](https://docs.astral.sh/uv/)로 설치하는 것을 권장합니다.

### LLM 준비 (Ollama)

```powershell
winget install Ollama.Ollama
ollama pull qwen3:8b          # 약 5.2GB
copy .env.example .env        # .env에서 LLM_PROVIDER=ollama 로 변경
```

`LLM_PROVIDER=mock`(기본값)이면 Ollama 없이 템플릿 대사로 동작합니다. 서버를 켜면 모델을 미리 메모리에 올립니다. 처음 한 번은 1~2분 걸릴 수 있습니다.

### 음성 준비 (선택, NVIDIA GPU 권장)

```powershell
cd backend
uv pip install --python .venv\Scripts\python.exe -r requirements-ai.txt
uv pip uninstall --python .venv\Scripts\python.exe onnxruntime
uv pip install --python .venv\Scripts\python.exe -r requirements-gpu.txt   # CUDA 12 라이브러리 (venv 안에만 설치)
mkdir ..\models\kokoro
curl.exe -L -o ..\models\kokoro\kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl.exe -L -o ..\models\kokoro\voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

`.env`에 `STT_PROVIDER=faster_whisper`, `TTS_PROVIDER=kokoro`를 넣습니다. Whisper `small.en` 모델(약 0.5GB)은 처음 실행할 때 자동으로 받습니다. 서버를 켤 때 세 모델을 미리 올리므로 처음에는 1~2분 걸립니다. 필요한 자원은 VRAM 약 7.7GB(Qwen3 포함), 디스크 약 5GB입니다.

음성 확인된 환경: RTX 4060 8GB, Windows 11. 서버 기준 한 턴(인식 → NPC 대사 → NPC 음성)에 약 1초가 걸립니다.

- 프론트는 반드시 `npm run dev`로 띄우세요. 마이크용 VAD 파일을 `public/vad/`로 복사하는 단계가 `predev`에 있어서, `npx vite`로 직접 띄우면 마이크가 동작하지 않습니다.
- 모델 파일이 없거나 GPU 라이브러리를 불러오지 못하면 서버는 꺼지지 않고 그 기능만 끕니다(로그에 `TTS disabled` 등). 이때 NPC는 글로만 답하고, 사용자는 타이핑으로 대화할 수 있습니다.
- `Could not load symbol cudnnGetLibConfig`로 서버가 종료되면 cuDNN 버전이 섞인 것입니다. `uv pip install --python .venv\Scripts\python.exe -r requirements-gpu.txt`로 cuDNN 9.10을 다시 설치하세요 (D-023).

Windows에서 스마트 앱 컨트롤이 PyAV DLL을 막아도 동작합니다(파일 디코딩만 꺼짐). 다른 프로젝트가 8000/5173 포트를 쓰고 있다면 백엔드는 `--port 8010`, 프론트는 `$env:BACKEND_PORT=8010; $env:FRONTEND_PORT=5183; npm run dev`로 띄웁니다.

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
| `Do you have something with chocolate?` | 규칙으로 못 알아들은 말은 LLM이 보조 추출 → hot chocolate |

대화가 끝나면 아래에 피드백이 나오고, 위쪽 **복습** 탭에서 닉네임별로 쌓인 복습 문장과 자주 틀린 부분을 볼 수 있습니다. 내 문장이 잘못 입력·인식됐다면 말풍선의 **고치기**로 수정할 수 있습니다. 피드백은 고친 문장으로 만들어집니다.

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

실제 모델 품질 측정은 `evals/README.md`와 `docs/experiments.md`를 보세요.

```powershell
cd backend
.venv\Scripts\python.exe ..\evals\run_dialogue.py --provider ollama --label my-run    # 대화 품질
.venv\Scripts\python.exe ..\evals\score_feedback.py --provider ollama --label my-run  # 피드백 정확도
```

## 장면 추가·수정

장면은 `scenes/*.yaml`에 있고 코드에는 메뉴나 대사가 없습니다. 수정한 뒤 `python -m app.scenes.validate`로 검사하세요. 검사 항목은 JSON Schema, 별칭 중복, 단계 참조, 템플릿 placeholder, 그리고 모든 템플릿 문장이 출력 가드를 통과하는지입니다. Director 동작을 바꿨다면 `evals/dialogue-cases.jsonl`에 케이스를 추가하세요.

## 데이터와 개인정보

`.env`, 모델 파일, 음성 녹음(`*.wav` 등), `data/`(학습 기록 DB), `evals/audio/`는 Git에 올리지 않습니다.

Talklish 등 기존 서비스의 이름, 대사, 캐릭터, 이미지는 사용하지 않으며 모든 장면 대사는 직접 작성합니다.
