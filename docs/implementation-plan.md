# 구현 계획

SceneSpeak MVP를 어떤 순서로, 어떤 설계로 만드는지 정리한 문서다. 설계의 근거는 [design.md](design.md), 결정 기록은 [decision-log.md](decision-log.md), 단계별 프롬프트 원문은 [build-prompts.md](build-prompts.md)에 있다.

## 작업 규칙

1. 작업을 시작하기 전에 이 문서에서 해당 단계를 **🟡 진행중**으로 바꾸고 커밋·푸시한다.
2. 구현 → 자동 테스트(pytest, Ruff, tsc, vitest, build, 장면 스키마 검사) → **스모크 테스트**(실제 서버를 띄워 시나리오 실행)를 한다.
3. 문제가 없으면 **✅ 완료**로 바꾸고 결과를 적은 뒤 커밋·푸시한다.
4. 막히면 **⛔ 막힘**으로 바꾸고 원인과 다음 행동을 적는다.

상태 표시: ⬜ 대기 · 🟡 진행중 · ✅ 완료 · ⛔ 막힘

## 전체 진행 상황

| 단계 | 내용 | 설계 Phase | 상태 |
|---|---|---|---|
| 1 | 뼈대 + Scene Director (텍스트 주문) | 0 + 1 | ✅ 완료 |
| 2 | LLM NPC + 피드백·학습 기록 | 2 + 3 | ✅ 완료 |
| 3 | 음성 입력 + 음성 출력 | 4 + 5 | ✅ 완료 |
| 4 | 발화 분석 + 평가 리포트 + OSS 정리 | 6 + 7 | ✅ 완료 |
| 5 | 뉴욕 도트 월드 (돌아다니며 여러 NPC와 대화) | 추가 | ✅ 완료 |

## 디렉터리 설계

```
scene-speak-ai/
├─ scenes/                     장면 데이터 (코드와 분리)
│  ├─ new-york-cafe.yaml       메뉴, 별칭, 의도 표현, 단계, 행동별 지시·템플릿, 가드 규칙
│  └─ schema/scene.schema.json 장면 JSON Schema
├─ backend/                    Python 3.12 · FastAPI
│  ├─ app/
│  │  ├─ core/config.py        설정 (.env의 *_PROVIDER로 모델 선택)
│  │  ├─ ai/                   모델 어댑터 (교체 가능)
│  │  │  ├─ types.py           STT/LLM/TTS/Aligner Protocol과 결과 타입
│  │  │  ├─ registry.py        provider 이름 → 구현 선택
│  │  │  └─ stt|llm|tts|alignment/  mock.py (단계 2~4에서 실제 구현 추가)
│  │  ├─ scenes/               Scene Director (핵심 모듈)
│  │  │  ├─ models.py          장면 Pydantic 모델
│  │  │  ├─ loader.py          YAML 로더
│  │  │  ├─ extractor.py       규칙 기반 슬롯·의도 추출, 메뉴 외 품목 감지
│  │  │  ├─ director.py        주문 상태 머신, 다음 행동 결정, 성공 판정
│  │  │  ├─ guard.py           NPC 대사 검증 (메뉴 외 품목, 금지 표현, 문장 수)
│  │  │  ├─ responder.py       행동 → 대사 (단계 1: 템플릿, 단계 2: LLM)
│  │  │  ├─ conversation.py    세션 = Director + Responder
│  │  │  └─ validate.py        장면 파일 검사 CLI
│  │  ├─ api/                  WebSocket /ws/session, 메시지 계약
│  │  ├─ evaluation/           (단계 2) Learning Evaluator
│  │  └─ users/                (단계 2) 학습 기록 저장
│  └─ tests/
├─ frontend/                   React · TypeScript · Vite
│  ├─ src/
│  │  ├─ types/messages.ts     백엔드 메시지 계약의 TS 버전
│  │  ├─ services/             WebSocket 클라이언트
│  │  └─ features/
│  │     ├─ conversation/      대화 화면, 상태 리듀서, 세션 훅
│  │     ├─ scenes/            주문 상태 패널
│  │     ├─ microphone/        (단계 3)
│  │     └─ feedback/          (단계 2)
│  └─ tests/
├─ evals/                      평가 데이터 (음성 파일은 Git 제외)
│  └─ dialogue-cases.jsonl     Director 대화 케이스 (pytest가 사용)
├─ docs/
└─ .github/workflows/ci.yml
```

## 핵심 설계 원칙

- **주문 상태는 Scene Director만 가진다.** LLM은 Director가 고른 행동을 문장으로 바꾸기만 한다. 과업 성공은 Director 상태로 판정한다.
- **장면 지식은 YAML에만 있다.** 메뉴, 별칭, 의도 표현("that's all", "never mind"), 행동별 템플릿, 금지 표현을 코드에 쓰지 않는다.
- **모든 NPC 대사는 가드를 통과해야 한다.** 장면 검사기는 모든 템플릿 문장이 가드를 통과하는지 CI에서 확인한다.
- **모델은 Protocol 뒤에 숨긴다.** CI는 Mock만 사용하고 모델을 내려받지 않는다.

---

## 단계 1 — 뼈대 + Scene Director ✅ 완료

**목표:** 브라우저에서 텍스트로 주문하면 Director가 상태를 관리하고 템플릿 대사로 응답해 주문 완료(또는 취소)까지 진행된다.

### 구현 항목

| 항목 | 상태 |
|---|---|
| 장면 YAML + JSON Schema | ✅ |
| 어댑터 Protocol + Mock 4종 + 레지스트리 | ✅ |
| 규칙 추출기 (최장 일치, 메뉴 외 수식어 감지, 부정어 처리) | ✅ |
| Director 상태 머신 (14개 행동, 단계 전이 검증, 제안 수락, 턴 제한) | ✅ |
| Output Guard | ✅ |
| 장면 검사 CLI (스키마 + 참조 무결성 + 템플릿 가드 검사) | ✅ |
| WebSocket `/ws/session` | ✅ |
| 대화 케이스 20개 (`evals/dialogue-cases.jsonl`) | ✅ |
| 프론트: 대화 화면, 주문 상태 패널, 결과 배너 | ✅ |
| CI 워크플로 | ✅ |
| README, `.env.example`, 결정 기록 갱신 (D-011 ~ D-014) | ✅ |
| 스모크 테스트 | ✅ |

### 완료 기준

- pytest, Ruff, tsc, vitest, build, 장면 스키마 검사 통과
- 서버를 띄우고 다음 시나리오가 끝까지 동작
  - "I want hot latte" → "Large, please. And can I have oat milk?" → "Yes, that's all" → 주문 성공
  - 메뉴에 없는 요청(pumpkin spice latte), cold brew를 hot으로 요청 → 안내 후 정상 주문

### 결과 (2026-10-11)

| 검사 | 결과 |
|---|---|
| pytest | 86개 통과 (대화 케이스 20개 포함) |
| Ruff lint / format | 통과 |
| 장면 파일 검사 | 통과 |
| tsc / vitest / build | 통과 / 5개 통과 / 통과 |
| 스모크 테스트 | 5개 시나리오 통과 (정상 주문, 메뉴 밖 요청, cold brew hot, Americano + 우유, 취소) |

스모크 방법: uvicorn(8000)과 Vite(5173)를 띄우고 Vite 프록시를 거쳐 `ws://localhost:5173/ws/session`으로 시나리오를 실행했다.

발견하고 고친 문제: Vite 프록시가 `localhost`를 IPv6로 연결해 WebSocket이 거부됨 → 대상을 `127.0.0.1`로 변경 (D-014).

남은 한계: 메뉴에 없는 일반 명사는 감지하지 못하고 clarify로 처리한다 (D-012, 단계 2에서 보완).

---

## 단계 2 — LLM NPC + 피드백·학습 기록 ✅ 완료

**목표:** Qwen3-8B NPC와 텍스트로 자연스럽게 주문하고, 대화가 끝나면 구조화된 피드백을 보며, 오류와 복습 문장이 닉네임별로 저장된다.

### 구현 항목

| 항목 | 상태 |
|---|---|
| Ollama 설치, `qwen3:8b` (RTX 4060 8GB, 100% GPU, VRAM 6.8GB 사용) | ✅ |
| `OllamaLLM` 어댑터 (`think=false`, JSON Schema 강제, 서버 시작 시 모델 미리 올리기) | ✅ |
| `LLMResponder`: 가드 실패 → 위반 내용을 알려 1회 재생성 → 템플릿 대체 | ✅ |
| 종료 행동에서 질문 금지 규칙 | ✅ |
| `LLMAssist`: 규칙이 아무것도 못 찾은 발화만 LLM 추출, 메뉴 id로 재매핑 (D-015) | ✅ |
| Learning Evaluator: 한 줄씩 판정, 재요청, 안전 기본값, 인용 검증, 신뢰도 게이팅, 짧은 답·조언 필터 (D-016) | ✅ |
| SQLite 학습 기록 (사용자, 세션, 발화, 피드백, 복습 문장, 오류), 반복 오류 집계 | ✅ |
| WebSocket: 닉네임, 전사 수정, `feedback_pending` / `feedback_ready` | ✅ |
| REST: `GET /api/sessions/{id}/feedback`, `GET /api/users/{id}/review` | ✅ |
| 프론트: 닉네임 화면, 입력 중 표시, 말풍선 고치기, 피드백 화면, 복습 탭 | ✅ |
| 평가 스크립트 `run_dialogue.py`, `score_feedback.py`, 라벨 데이터 10개 + 라벨링 가이드 | ✅ |
| 실험 기록 `docs/experiments.md` (EXP-DLG-001, EXP-FB-001) | ✅ |

### 결과 (2026-10-11)

| 검사 | 결과 |
|---|---|
| pytest | 138개 통과 (Ollama 없이 Mock으로) |
| Ruff / 장면 검사 | 통과 |
| tsc / vitest / build | 통과 / 7개 통과 / 통과 |
| 스모크 테스트 (실제 Qwen3, Vite 프록시 경유) | 3개 시나리오 통과: 정상 주문, 메뉴 밖 요청 + LLM 보조 추출, 취소. 각각 피드백 생성·조회, 복습 API 확인 |

| 실험 | 기준 → 개선 후 |
|---|---|
| 피드백 문법 탐지 F1 | 0.444 → **0.933** (recall 0.29 → 1.0, 두 번 측정 동일) |
| NPC 메뉴 환각률 | 0% → 0% |
| NPC 최종 응답 가드 통과율 | 100% → 100% |
| NPC LLM 응답 p95 | 1026 ms → 1233 ms (예산 1.2초를 약간 초과, 다음 실험 대상) |

### 스모크 테스트에서 발견하고 고친 문제

- 가드가 "We only serve cold brew"를 메뉴 외 품목으로 오인 → 동사·부사 불용어 추가
- "matcha latte"가 그냥 latte로 주문됨 (규칙 추출기 버그) → 메뉴 외 단어가 붙은 음료는 메뉴 외 품목으로 처리, 회귀 케이스 추가
- 주문이 끝났는데 NPC가 다시 질문 → 종료 행동에서 질문 금지
- 피드백 요약이 프롬프트 예시를 베낌, 취소한 대화에도 "잘 마쳤어요" → 대화 결과를 프롬프트에 넣고 예시 제거
- 복습 문장 자리에 조언이 들어감 → 조언 필터
- 테스트가 로컬 `.env`를 읽어 실패 → 테스트는 `.env`를 무시

### 남은 한계

- 피드백 평가 데이터가 10개라 수치의 신뢰 구간이 넓다. 라벨링 가이드대로 50개까지 늘려야 한다.
- 피드백 생성에 4~6초가 걸린다. 대화 중이 아니라 끝난 뒤라서 "분석 중" 표시로 처리했다.
- 브라우저 화면은 빌드와 API 스모크로만 확인했다. 직접 클릭해 보는 확인은 사용자 검토로 남긴다.

---

## 단계 3 — 음성 입력 + 음성 출력 ✅ 완료

**목표:** 마이크로 영어 주문을 하면 음성이 텍스트로 바뀌고, NPC 대사가 영어 음성으로 재생된다.

### 막힘과 해소 (2026-10-11)

서버 전체 스모크 테스트 중 PC의 디스크·RAM 여유가 0이 되어 멈췄다(다른 프로젝트 작업이 동시에 실행됨). 여유가 생긴 뒤(디스크 15GB, RAM 8GB) 재개했고, 실제로는 다음 두 문제가 더 있었다.

1. **서버가 모델을 올리다 종료** — cuDNN 버전 혼재(9.10 로더 + 9.1 하위 DLL). 가상환경 cuDNN을 9.10.2로 맞춰 해결 (D-023).
2. **`npm run dev`에서 마이크가 동작하지 않음** — Vite 개발 서버가 onnxruntime-web의 `.mjs` 동적 import를 거부. 개발 서버 플러그인으로 해결 (D-026).

### 구현 항목

| 항목 | 상태 |
|---|---|
| `FasterWhisperSTT` 어댑터 (단어별 신뢰도, 문맥 힌트 방식 선택, 시작 시 미리 로드) | ✅ |
| `KokoroTTS` 어댑터 (GPU/CPU, 실패 시 텍스트로 대체) | ✅ |
| Windows 대응: PyAV 차단 시 대체, venv 안 CUDA 12 라이브러리 (D-019) | ✅ |
| WebSocket: `audio_utterance`, `npc_audio`, `npc_audio_failed`, `turn_timing`, 저신뢰 단어 | ✅ |
| 녹음 저장과 보존 기간(기본 7일) 정리 | ✅ |
| 프론트: 마이크(브라우저 Silero VAD), NPC 음성 재생·음소거, 불확실 단어 표시, 응답 시간 표시 | ✅ |
| 실제 모델 왕복 테스트 (`pytest -m model`: Kokoro로 만든 음성을 Whisper가 인식) | ✅ 통과 |
| EXP-ASR-001 (합성 음성 기준선, 8개 조건) → small.en + 문장 프롬프트 채택 | ✅ |
| 포트를 환경 변수로 변경 가능하게 (`BACKEND_PORT`, `FRONTEND_PORT`) | ✅ |
| 실제 모델로 서버 전체 스모크 테스트 (음성 발화 → 인식 → NPC 음성, 턴 지연 측정) | ✅ |
| 실제 Chrome + 가짜 마이크(WAV 재생)로 브라우저 VAD → 인식 → NPC 응답 | ✅ |
| 음성 모델이 없거나 실패해도 텍스트로 대화 지속 (시작 시점 포함, D-024) | ✅ |
| NPC 검증 보강: 주문 복창 상태 검사, 역할 혼동, 구체적 재생성 (D-025) | ✅ |
| 사람 목소리·실제 마이크·스피커로 주문해 보기 | ⬜ 사용자 확인 필요 |
| README 음성 설정 안내 | ✅ |

### 지금까지 측정한 것

| 항목 | 값 |
|---|---|
| STT small.en GPU (문장 프롬프트) | p50 236 ms, p95 349 ms, WER 0.030, 주문 정보 인식률 0.95 (합성 음성) |
| TTS Kokoro GPU | 문장당 0.70 ~ 0.96초 |
| 서버 턴 지연 (실측, 3턴) | STT 127–135 ms, LLM 447–847 ms, TTS 257–370 ms, 합계 **0.93–1.26초** |
| 사용자 체감 지연 (추정) | 서버 합계 + VAD 종료 대기 0.7초(`redemptionMs`) ≈ 1.6–2.0초 (목표 3초 이내) |
| TTS 없이 (Kokoro 파일 없음) | 서버 합계 0.59–0.97초, 대화·피드백 정상 |
| 브라우저 가짜 마이크 | 마이크 켬 → 사용자 말풍선까지 7.1초 (WAV 앞 무음 2초 + VAD 로드 포함) |
| NPC 재측정 (EXP-DLG-001, D-025 후) | 장면 이탈 9.0%, 템플릿 대체 5.1%, 최종 가드 통과 100%, LLM p95 888 ms |
| 테스트 | pytest 163개 + 실제 모델 1개, vitest 13개 |

스모크 방법: `STT_PROVIDER=faster_whisper TTS_PROVIDER=kokoro LLM_PROVIDER=ollama`로 uvicorn(8010)과 `BACKEND_PORT=8010 FRONTEND_PORT=5183 npm run dev`를 띄우고, Kokoro(am_michael)로 만든 손님 음성 3문장을 Vite 프록시를 거쳐 `audio_utterance`로 보냈다. 인식 → NPC 대사 → NPC 음성 → 주문 성공 → 피드백 저장까지 확인했다. 합성 음성이라 한국인 발화 인식률은 대표하지 않는다.

남은 문제

- 사람 목소리와 실제 마이크·스피커로는 아직 확인하지 않았다 (사용자 확인 필요).
- 무음만 들어오면 Whisper가 "You"를 만들어 낸다. 브라우저 VAD가 무음을 거르지만 서버 쪽 방어는 없다.
- NPC 재측정에서 템플릿 대체율이 3.8% → 5.1%로 올랐다. 검사가 엄격해진 결과(실제 오류를 잡음)이지만, 문장 수 위반을 줄이는 실험이 필요하다.

---

## 단계 4 — 발화 분석 + 평가 리포트 + OSS 정리 ✅ 완료

| 항목 | 상태 |
|---|---|
| wav2vec2 ONNX 정렬기 + numpy CTC 강제 정렬 (D-027) | ✅ |
| 대화 후 발화 분석: 0.8초 이상 멈춤, 저신뢰 단어, 다시 들어볼 구간 | ✅ |
| 피드백 화면 구간 재생, 내 녹음 듣기 API | ✅ |
| 복습 따라 말하기 (빠진·덧붙인 단어, 불확실 단어는 탓하지 않음) | ✅ |
| 무음·Whisper 환각 서버 방어 (D-028) | ✅ |
| `evals/run.py`, `evals/compare.py` | ✅ |
| 평가 리포트 화면 (탭, `#/report`, GitHub Pages에서는 빌드에 포함된 결과 파일) | ✅ |
| run.py 두 번 실행 + compare.py·리포트 화면으로 비교 (EXP-HARNESS-001) | ✅ |
| `docs/licenses.md`, `THIRD_PARTY_NOTICES.md`, espeak-ng 확인 (D-029) | ✅ |
| `docs/model-selection.md`, `docs/architecture.md`, experiments 정리 | ✅ |
| CI: AI 응답 JSON 스키마 fixture 검사, compare 실행 (GitHub에서 통과) | ✅ |
| README 전체 데모 시나리오 | ✅ |
| 사용자 실제 음성 테스트에서 발견한 "샷 추가 '네'" 버그 수정 (D-031) | ✅ |

### 측정

| 항목 | 값 |
|---|---|
| 정렬 (3.7초 문장) | CPU 약 220 ms. 끼워 넣은 1.2초 멈춤을 정확히 검출 (EXP-ALIGN-001) |
| 하네스 재현성 | 음성인식 힌트 없음 WER 0.052 / 인식률 0.892, 문장 프롬프트 0.030 / 0.950. EXP-ASR-001의 A, H와 같음 |
| LLM 지표 실행 간 잡음 | 같은 설정에서 장면 이탈률 ±3.6%p, NPC p95 ±370 ms. 비교하려면 반복 측정 필요 |
| 테스트 | pytest 221개 + 실제 모델 2개, vitest 26개 |

### 남은 문제

- 정렬과 멈춤 검출은 합성 음성과 사용자 1명 세션으로만 확인했다. 한국인 화자 녹음으로 사람 라벨과 비교해야 한다.
- 저장소 라이선스가 정해지지 않았다. espeak-ng(GPL) 때문에 배포 형태와 함께 정해야 한다(D-029).
- NPC 문장 수 위반(장면 이탈의 대부분)을 줄이는 실험이 남아 있다.

---

## 단계 5 — 뉴욕 도트 월드 ✅ 완료

**목표:** 뉴욕 거리를 도트 캐릭터로 돌아다니다가 NPC에게 다가가 영어로 대화한다. 카페 주문 외에 핫도그 주문, 길 묻기, 호텔 체크인, 지하철 문의 장면을 추가한다.

- 사용자 요청으로 MVP 범위 밖에서 추가한 단계다(2026-10-11).
- 카페 장면은 기존 Scene Director를 그대로 쓴다. 새 장면은 미션 대화(talk) 형식이다. 장면 YAML에 해야 할 일(단계)과 판정 규칙, NPC가 말해도 되는 사실을 적고, 진행 판정은 LLM이 아니라 규칙이 한다(D-030).
- 맵과 캐릭터는 외부 이미지 없이 코드로 그린다(라이선스 문제 없음).

| 항목 | 상태 |
|---|---|
| 뉴욕 맵 (센트럴 파크, 59th·45th St, 7·5 Av, 타임스스퀘어, 카페, 호텔, 그랜드 센트럴, 지하철 입구, 핫도그 카트) | ✅ |
| 캐릭터 이동(방향키·WASD·모바일 방향 버튼), 충돌, 카메라, 지나가는 사람 3명 | ✅ |
| NPC 5명: 다가가면 안내, Space로 대화, 미션 완료 표시(닉네임별 저장) | ✅ |
| 미션 대화 엔진 `TalkSession` + `TalkGuard`(사실에 없는 가격, 종료 후 질문 차단) | ✅ |
| 미션 4개 YAML + 장면 검사 CLI 확장 | ✅ |
| 평가기 프롬프트 장면별 일반화 (카페 프롬프트는 글자 그대로 유지, 비교 검사함) | ✅ |
| 닉네임 로그인 API (대화 전에도 복습 탭), 동시 생성 경쟁 조건 수정 | ✅ |
| 테스트: 미션별 모범 대화, 가드, WebSocket 끝까지, 맵 도달 가능성, 충돌 | ✅ |
| 실제 모델 + Chrome 스모크 (경찰관 미션 성공, 모바일 390px) | ✅ (EXP-WORLD-000) |

### 남은 문제

- 미션 판정이 정규식이라 표현이 다양하면 단계를 놓칠 수 있다. 카페처럼 LLM 보조 판정을 붙일 수 있다.
- 미션 대화 NPC의 품질(장면 이탈, 지연)을 실제 LLM으로 재는 평가 케이스가 아직 없다.
- 사람 목소리로 거리 미션을 해 보는 확인은 사용자 몫으로 남는다.
