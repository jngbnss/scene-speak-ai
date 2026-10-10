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
| 3 | 음성 입력 + 음성 출력 | 4 + 5 | ⬜ 대기 |
| 4 | 발화 분석 + 평가 리포트 + OSS 정리 | 6 + 7 | ⬜ 대기 |

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

## 단계 3 — 음성 입력 + 음성 출력 ⬜ 대기

- 브라우저 Silero VAD, faster-whisper 어댑터 (hotwords, 단어 신뢰도)
- Kokoro TTS 어댑터, 실패 시 텍스트로 대체
- 단계별 지연 기록, EXP-ASR-001 실행 스크립트

## 단계 4 — 발화 분석 + 평가 리포트 + OSS 정리 ⬜ 대기

- 사후 정렬(멈춤, 저신뢰 단어, 다시 들어볼 구간), 복습 따라 말하기
- 평가 하네스와 개선 전후 비교 리포트
- `docs/licenses.md`, `THIRD_PARTY_NOTICES.md`
