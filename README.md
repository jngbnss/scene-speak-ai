# SceneSpeak AI

도트로 그린 뉴욕 거리를 돌아다니며 카페 바리스타, 핫도그 노점상, 경찰관, 호텔 직원, 지하철 역무원과 영어로 대화하는 여행 영어회화 서비스입니다. 정해진 문장을 따라 읽지 않고 자유롭게 말하면, 장면 규칙이 대화를 이끌고 대화가 끝나면 피드백과 다시 들어볼 구간을 보여줍니다.

- 설계: [docs/design.md](docs/design.md)
- 구현 계획과 진행 상황: [docs/implementation-plan.md](docs/implementation-plan.md)
- 결정 기록: [docs/decision-log.md](docs/decision-log.md)
- 아키텍처: [docs/architecture.md](docs/architecture.md) · 모델 선택: [docs/model-selection.md](docs/model-selection.md) · 실험: [docs/experiments.md](docs/experiments.md)
- 라이선스: [docs/licenses.md](docs/licenses.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## 현재 상태

- **뉴욕 도트 월드 (단계 5):** 방향키·WASD(모바일은 화면의 방향 버튼)로 걷다가 느낌표(!)가 뜬 사람에게 다가가 Space를 누르면 대화가 시작됩니다. 미션 5개를 끝내면 체크 표시가 쌓입니다.
- **카페 주문:** Scene Director가 주문 상태를 관리하고, Qwen3-8B(Ollama)는 Director가 정한 행동을 대사로만 표현합니다. 출력 가드에 두 번 걸리면 장면 YAML의 템플릿 문장을 씁니다.
- **거리 미션 4개:** 핫도그 주문, 길 묻기, 호텔 체크인, 지하철 문의입니다. 해야 할 일은 규칙으로 판정하고, NPC는 장면 파일에 적힌 사실만 말합니다(D-030).
- **음성:** 마이크로 말하면 Whisper가 인식하고, NPC는 Kokoro 음성으로 답합니다. 서버 기준 한 턴에 약 1~2초가 걸립니다.
- **대화 후:** 다음을 제공합니다. 점수는 매기지 않습니다.
  - 문법·표현 피드백과 복습 문장
  - **다시 들어볼 구간:** 0.8초 이상 멈춘 곳과 인식이 불확실한 단어를 표시하고, 클릭하면 내 녹음을 재생합니다.
  - 복습 탭의 **따라 말하기:** 빠진 단어와 덧붙인 단어를 보여줍니다.
- **평가 리포트:** `evals/run.py`로 같은 데이터를 다시 측정하고, `evals/compare.py`나 화면의 **평가 리포트** 탭에서 두 결과를 비교합니다.

모델이 없어도 Mock 모드로 화면과 흐름을 확인할 수 있습니다. 이때 NPC는 템플릿 문장으로 답합니다.

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

`.env`에 다음을 넣습니다.

```
STT_PROVIDER=faster_whisper
TTS_PROVIDER=kokoro
ALIGNER_PROVIDER=wav2vec2
```

- Whisper `small.en` 모델(약 0.5GB)은 처음 실행할 때 자동으로 받습니다.
- 정렬 모델(wav2vec2, 약 380MB)은 대화가 처음 끝날 때 받고, CPU에서 실행됩니다.
- 서버를 켤 때 실시간 모델 세 개를 미리 올리므로 처음에는 1~2분 걸립니다.
- 필요한 자원은 VRAM 약 7.7GB(Qwen3 포함), 디스크 약 5.5GB입니다.

음성 확인된 환경: RTX 4060 8GB, Windows 11. 서버 기준 한 턴(인식 → NPC 대사 → NPC 음성)에 약 1~2초가 걸립니다.

- 프론트는 반드시 `npm run dev`로 띄우세요. 마이크용 VAD 파일을 `public/vad/`로 복사하는 단계가 `predev`에 있어서, `npx vite`로 직접 띄우면 마이크가 동작하지 않습니다.
- 모델 파일이 없거나 GPU 라이브러리를 불러오지 못해도 서버는 꺼지지 않고 그 기능만 끕니다(로그에 `TTS disabled` 등). 이때 NPC는 글로만 답하고, 사용자는 타이핑으로 대화할 수 있습니다.
- `Could not load symbol cudnnGetLibConfig`로 서버가 종료되면 cuDNN 버전이 섞인 것입니다. `uv pip install --python .venv\Scripts\python.exe -r requirements-gpu.txt`로 cuDNN 9.10을 다시 설치하세요 (D-023).

Windows에서 스마트 앱 컨트롤이 PyAV DLL을 막아도 동작합니다(파일 디코딩만 꺼짐).

다른 프로젝트가 8000/5173 포트를 쓰고 있다면 포트를 바꿔 띄웁니다.
- 백엔드: `--port 8010`
- 프론트: `$env:BACKEND_PORT=8010; $env:FRONTEND_PORT=5183; npm run dev`

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

## 해볼 시나리오 (전체 데모)

백엔드와 프론트를 띄우고 http://localhost:5173 에서 닉네임을 넣으면 타임스스퀘어 위쪽 길가에서 시작합니다.

1. **경찰관 (바로 아래 타임스스퀘어 광장):** `Excuse me, how do I get to Central Park?` → `How long does it take to walk?` → `Thank you.` → 미션 성공. 오른쪽 할 일 4개가 모두 체크됩니다.
2. **바리스타 (오른쪽 CAFÉ 앞)**
   - `I want hot latte.` → `Large, please.`
   - `Yeah, sure.` → NPC가 무엇을 원하는지 되묻습니다.
   - `Oat milk, please.` → `That's all.` → 주문 성공
   - 피드백에서 `I want hot latte` → `a hot latte` 지적을 확인합니다.
3. **핫도그 노점 (카페 아래, 길 건너):** `Can I get a hot dog?` → `Mustard, please.` → `How much is it?` → `Thanks!`
4. **호텔 (왼쪽 HOTEL 앞):** `Hi, I have a reservation.` → `My name is Mina Kim.` → `What time is breakfast?` → `Thank you.`
5. **지하철 역무원 (GRAND CENTRAL 앞 SUBWAY 입구):** `Which train goes to Brooklyn Bridge?` → `How much is the fare?` → `Can I pay with my card?` → `Thanks!`
6. 마이크로 말한 대화라면 피드백 아래 **다시 들어볼 구간**에서 ▶ 버튼으로 내 목소리를 다시 들어 보세요. 일부러 1초 넘게 쉬어 보면 `‖ 1.2초` 표시가 나옵니다.
7. **복습** 탭에서 복습 문장의 **따라 말하기**를 누르고, 소리 내어 읽거나 입력해 보세요. 빠진 단어와 덧붙인 단어를 보여줍니다.
8. **평가 리포트** 탭에서 두 측정 결과를 골라 지표 변화를 봅니다. `#/report` 주소로 바로 열 수도 있습니다.

카페 장면만 따로 확인할 때 쓰는 입력 예:

| 입력 | 기대 결과 |
|---|---|
| `Can I get a pumpkin spice latte?` | 메뉴에 없다고 안내 |
| `A medium hot cold brew.` → `Sure.` | iced만 가능하다고 안내 후 iced로 변경 |
| `A medium iced americano with oat milk.` | 우유를 넣을 수 없는 음료라고 안내 |
| `Never mind, cancel my order.` | 주문 취소 |
| `Do you have something with chocolate?` | 규칙이 못 알아들은 말은 LLM이 보조로 추출 → hot chocolate |

내 문장이 잘못 입력되거나 잘못 인식됐다면 말풍선의 **고치기**로 수정할 수 있습니다. 피드백은 고친 문장으로 만들어집니다.

### GitHub Pages

main에 푸시하면 프론트가 https://jngbnss.github.io/scene-speak-ai/ 에 배포됩니다. 거리 돌아다니기와 평가 리포트(빌드에 포함된 결과 파일)는 Pages에서도 동작합니다. 대화에는 AI 모델이 있는 백엔드가 필요해서 로컬에서 실행해야 합니다.

## 테스트

```powershell
cd backend
.venv\Scripts\python.exe -m pytest           # Director, 미션 대화, 추출기, 가드, 정렬, WebSocket, REST, 응답 스키마
.venv\Scripts\python.exe -m pytest -m model  # 실제 음성 모델 (Kokoro → Whisper, wav2vec2 정렬)
.venv\Scripts\ruff.exe check . ; .venv\Scripts\ruff.exe format --check .
.venv\Scripts\python.exe -m app.scenes.validate   # 장면 파일 검사 (카페 + 미션 대화)

cd ..\frontend
npm run typecheck ; npm test ; npm run build
```

CI(`.github/workflows/ci.yml`)는 같은 검사를 Mock 어댑터로만 실행하며 AI 모델을 내려받지 않습니다. AI 응답 JSON 스키마는 저장된 예시 응답(fixture)으로 검사합니다.

### 품질 측정 (평가 하네스)

자세한 내용은 `evals/README.md`와 `docs/experiments.md`를 보세요. 평가 하네스는 대화 품질, 피드백 정확도, 음성인식을 한 번에 측정합니다. 결과는 `evals/results/{시각}-suite-{라벨}.json`에 저장되고, 모델, 설정, git 커밋이 함께 기록됩니다.

```powershell
cd backend
.venv\Scripts\python.exe ..\evals\asr\make_synthetic.py                  # 음성인식 평가용 합성 음성 (최초 1회)
.venv\Scripts\python.exe ..\evals\run.py --label before --asr-context none   # 전체 측정
.venv\Scripts\python.exe ..\evals\run.py --label after                       # 바꾼 뒤 다시 측정
.venv\Scripts\python.exe ..\evals\compare.py ..\evals\results\<before>.json ..\evals\results\<after>.json
.venv\Scripts\python.exe ..\evals\run.py --label quick --only dialogue       # 일부만
```

## 장면 추가·수정

장면 파일은 두 종류이고, 코드에는 메뉴나 대사가 없습니다.

| 위치 | 종류 | 적는 것 |
|---|---|---|
| `scenes/*.yaml` | 카페처럼 주문 슬롯을 채우는 장면 | 메뉴, 별칭, 의도 표현, 단계, 행동별 지시·템플릿, 가드 규칙 |
| `scenes/talks/*.yaml` | 할 일 체크리스트형 미션 대화 | 단계별 판정 정규식, NPC가 말해도 되는 사실, 템플릿 대사 |

수정한 뒤에는 `python -m app.scenes.validate`로 검사하세요.
- 카페 장면 검사: JSON Schema, 별칭 중복, 단계 참조, 템플릿 placeholder, 모든 템플릿 문장의 출력 가드 통과
- 미션 대화 검사: 정규식 컴파일, 템플릿 대사의 가드 통과

이어서 할 일:
- **Director 동작을 바꿨다면:** `evals/dialogue-cases.jsonl`에 케이스를 추가하세요.
- **새 미션을 월드에 세우려면:**
  1. `frontend/src/features/world/map.ts`의 `NPCS`에 위치와 `sceneId`를 추가합니다.
  2. `backend/tests/test_talk.py`의 `WALKTHROUGHS`에 모범 대화를 넣습니다.

## 데이터와 개인정보

다음은 Git에 올리지 않습니다: `.env`, 모델 파일, 음성 녹음(`*.wav` 등), `data/`(학습 기록 DB와 녹음), `evals/audio/`.

사용자 녹음은 "다시 들어볼 구간" 재생에만 쓰고, 기본 7일 뒤 서버를 시작할 때 삭제합니다(`AUDIO_RETENTION_DAYS`).

Talklish 등 기존 서비스의 이름, 대사, 캐릭터, 이미지는 사용하지 않습니다. 모든 장면 대사는 직접 작성했고, 맵과 캐릭터는 코드로 직접 그렸습니다.
