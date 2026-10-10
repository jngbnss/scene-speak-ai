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
| 1 | 뼈대 + Scene Director (텍스트 주문) | 0 + 1 | 🟡 진행중 |
| 2 | LLM NPC + 피드백·학습 기록 | 2 + 3 | ⬜ 대기 |
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

## 단계 1 — 뼈대 + Scene Director 🟡 진행중

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
| CI 워크플로 | ⬜ |
| README, `.env.example`, 결정 기록 갱신 | ⬜ |
| 스모크 테스트 | ⬜ |

### 완료 기준

- pytest, Ruff, tsc, vitest, build, 장면 스키마 검사 통과
- 서버를 띄우고 다음 시나리오가 끝까지 동작
  - "I want hot latte" → "Large, please. And can I have oat milk?" → "Yes, that's all" → 주문 성공
  - 메뉴에 없는 요청(pumpkin spice latte), cold brew를 hot으로 요청 → 안내 후 정상 주문

---

## 단계 2 — LLM NPC + 피드백·학습 기록 ⬜ 대기

- `OllamaLLM` 어댑터 (Qwen3-8B, `think=false`, JSON Schema 강제)
- `LLMResponder`: 가드 실패 시 1회 재생성 → 템플릿 대체
- Learning Evaluator (스키마 검증, 재요청, 안전 기본값, 신뢰도 게이팅)
- SQLite 학습 기록, 피드백·복습 화면
- 대화 품질 실험 1회차, 피드백 라벨 데이터 형식

## 단계 3 — 음성 입력 + 음성 출력 ⬜ 대기

- 브라우저 Silero VAD, faster-whisper 어댑터 (hotwords, 단어 신뢰도)
- Kokoro TTS 어댑터, 실패 시 텍스트로 대체
- 단계별 지연 기록, EXP-ASR-001 실행 스크립트

## 단계 4 — 발화 분석 + 평가 리포트 + OSS 정리 ⬜ 대기

- 사후 정렬(멈춤, 저신뢰 단어, 다시 들어볼 구간), 복습 따라 말하기
- 평가 하네스와 개선 전후 비교 리포트
- `docs/licenses.md`, `THIRD_PARTY_NOTICES.md`
