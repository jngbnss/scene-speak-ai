# 아키텍처

이 문서는 지금 구현된 구조를 설명한다. 설계 배경은 [design.md](design.md), 결정 이유는 [decision-log.md](decision-log.md), 모델 선택은 [model-selection.md](model-selection.md)에 있다.

## 한눈에 보기

```
┌──────────────────── 브라우저 (React + Vite) ────────────────────┐
│ 마이크 → Silero VAD(wasm) → 16kHz PCM 발화                         │
│ 대화 화면 · 주문 패널 · 피드백(구간 재생) · 복습(따라 말하기) · /report │
└───────┬──────────── WebSocket /ws/session ─────────┬──────────────┘
        │ REST /api/*                                │
┌───────▼──────────────── 백엔드 (FastAPI) ──────────▼──────────────┐
│ 실시간 턴 루프                                                       │
│   STT(Whisper) → Scene Director → NPC Responder(LLM) → Output Guard │
│                                   └ 실패 시 재생성 1회 → 템플릿       │
│   → TTS(Kokoro, 실패해도 계속)                                      │
│ 세션 종료 후 분석                                                    │
│   Learning Evaluator(LLM, JSON) + 발화 분석(wav2vec2 정렬)            │
│ 저장: SQLite(사용자·대화·피드백·복습) · data/audio(녹음, 7일 보관)       │
└────────────────────────────────────────────────────────────────────┘
          ▲ Ollama(Qwen3-8B)        ▲ 장면 데이터 scenes/*.yaml
```

핵심 원칙은 두 가지다.

1. **주문 상태는 Scene Director만 가진다.** LLM은 Director가 정한 행동을 문장으로 표현하고, 규칙이 못 읽은 말에서 슬롯 후보를 제시만 한다. 그래서 메뉴 환각이나 상태 표류가 구조적으로 막히고, Director는 LLM 없이 결정적으로 테스트된다.
2. **실시간 루프와 사후 분석을 분리한다.** 정렬과 피드백 생성은 대화가 끝난 뒤에만 돈다. 대화 중 지연에 영향을 주지 않는다.

## 실시간 턴 흐름

| 순서 | 위치 | 하는 일 | 실패하면 |
|---|---|---|---|
| 1 | 브라우저 `useMicrophone` | Silero VAD로 발화 구간을 잘라 `audio_utterance`로 전송. NPC가 말하는 동안은 일시정지 | 마이크 오류를 화면에 표시, 타이핑으로 계속 |
| 2 | `api/ws.py` | 형식·길이 검사, -55 dBFS 이하 무음 거부, 녹음 저장 | `bad_audio` / `no_speech` 오류 |
| 3 | `ai/stt/faster_whisper.py` | 인식 + 단어별 신뢰도. 장면 메뉴 단어를 문장 프롬프트로 제공 | `stt_failed`, 다시 말하기 요청 |
| 4 | `scenes/extractor.py` → `llm_assist.py` | 규칙(별칭)으로 슬롯 추출, 못 읽으면 LLM 보조 추출 | 규칙 결과만 사용 |
| 5 | `scenes/director.py` | 상태 머신: 슬롯 병합, 메뉴·옵션 검증, 다음 행동 결정, 성공 판정 | (결정적, 실패 없음) |
| 6 | `scenes/responder.py` | 행동별 지시로 LLM 대사 생성(JSON) | 가드 위반 시 구체 지시로 1회 재생성 → 장면 템플릿 |
| 7 | `scenes/guard.py` | 메뉴 외 품목, 금지 표현, 문장 수, 주문 복창 일치 검사 | 6번의 재생성·템플릿 |
| 8 | `ai/tts/kokoro.py` | NPC 음성 합성 → `npc_audio` | `npc_audio_failed`, 글로만 표시 |

턴마다 `turn_timing`(STT, NPC, LLM, TTS, 합계 ms)을 보내고 서버 로그에도 남긴다.

## 세션 종료 후 분석

`task_result` 다음 `feedback_pending`을 보내고, 아래를 백그라운드 스레드에서 실행한 뒤 `feedback_ready`를 보낸다.

1. **Learning Evaluator** (`evaluation/evaluator.py`): 전체 대화를 LLM에 주고 발화별 문법 판정을 JSON으로 받는다. 실제 발화를 인용하지 않은 지적과 저신뢰 인식 단어를 건드리는 지적은 버린다. 과업 성공과 빠진 정보는 LLM이 아니라 Director 상태에서 계산한다. 출력이 잘못되면 1회 재시도하고, 그래도 실패하면 안전한 기본값을 쓴다.
2. **발화 분석** (`evaluation/speech.py`): 녹음된 발화마다 wav2vec2로 단어 시작·끝을 정렬한다. 0.8초 이상 멈춤과 인식 신뢰도가 낮은 단어를 "다시 들어볼 구간"(시작·끝 초)으로 만든다. 정렬이 실패하면 Whisper 단어 시각을 쓴다. 점수는 매기지 않는다.
3. 결과를 `Feedback.speech`에 붙여 SQLite에 저장하고, 복습 문장과 오류 유형을 사용자 기록에 쌓는다.

복습 따라 말하기(`POST /api/shadowing`)는 정답 문장이 있으므로 빠진 단어와 덧붙인 단어를 표시한다. 인식기가 확신하지 못한 단어는 "빠짐" 대신 "불확실"로 표시한다(`evaluation/shadowing.py`).

## 뉴욕 월드와 미션 대화 (단계 5)

```
브라우저: WorldView(canvas) ── NPC에게 다가가 Space ──▶ ConversationScreen(sceneId)
                                                         │ session_start {scene_id}
백엔드:   load_any(scene_id) ─┬─ scenes/new-york-cafe.yaml   → ConversationSession (Scene Director)
                              └─ scenes/talks/{id}.yaml       → TalkSession (단계 체크리스트)
```

- **월드**(`frontend/src/features/world/`)는 브라우저에서만 돈다. `map.ts`가 타일 지도와 NPC 위치·장면 ID를 정의한다. `draw.ts`는 타일과 캐릭터를 코드로 그리고(이미지 파일 없음), `physics.ts`는 충돌과 대화 가능 거리를 계산한다. 정적 지도는 한 번만 그려 두고, 매 프레임 카메라 영역만 확대해 복사한다.
- **미션 대화**(`backend/app/scenes/talk.py`)는 카페 세션과 같은 인터페이스(`start`, `handle_text`, `end`, `ended`, `user_turns`)를 가진다. 그래서 WebSocket, 피드백, 발화 분석을 그대로 쓴다.
  - 진행 판정: 사용자 발화를 장면 YAML의 단계별 정규식과 대조한다. 모든 단계를 해내면 성공, 작별 인사나 턴 제한이면 미완료다(D-030).
  - NPC 대사 검사(`TalkGuard`): 문장 수, 금지 표현, 장면 사실에 없는 가격, 종료 후 질문. 걸리면 1회 재생성 후 템플릿 대사를 쓴다.
- 클라이언트에는 `SceneInfo.kind`(`order` | `talk`)와 `slot_labels`가 전달된다. 오른쪽 패널은 카페에서는 주문 상태를, 미션에서는 할 일 체크리스트를 보여준다.
- 미션 완료 기록은 닉네임별로 브라우저(localStorage)에 남는다. 대화 기록과 피드백은 서버 SQLite에 저장된다.

## 백엔드 모듈

| 경로 | 역할 |
|---|---|
| `app/ai/types.py`, `registry.py` | STT·LLM·TTS·Aligner Protocol과 provider 선택. 모든 결과에 `model_id`, `latency_ms` 포함 |
| `app/ai/{stt,llm,tts,alignment}/` | 실제 어댑터(faster-whisper, Ollama, Kokoro, wav2vec2)와 Mock |
| `app/ai/runtime.py` | Windows용 CUDA DLL 경로 등록, PyAV 대체 |
| `app/scenes/` | 장면 모델·로더·검사, 추출기, Director, 가드, 응답기, 세션 |
| `app/evaluation/` | 피드백 스키마·평가기, 발화 분석, 따라 말하기 비교 |
| `app/users/` | SQLAlchemy 모델, Repository(학습 기록), AudioStore(녹음 보관·정리) |
| `app/api/` | WebSocket 메시지 계약(`messages.py` ↔ `frontend/src/types/messages.ts`), REST, 서비스 조립(`deps.py`) |

서비스 조립(`deps.py`)에서 음성 어댑터와 정렬기는 선택 사항이다. 모델 파일이나 GPU 라이브러리가 없으면 해당 기능만 끄고 앱은 텍스트 모드로 동작한다(D-024).

## 프론트엔드 모듈

| 경로 | 역할 |
|---|---|
| `features/world/` | 뉴욕 도트 맵, 캐릭터 그리기, 이동·충돌, NPC 정의 |
| `features/conversation/` | 대화 상태 리듀서, WebSocket 세션 훅, 대화 화면(전사 고치기 포함), NPC별 대화 화면 |
| `features/microphone/` | VAD 마이크 훅과 버튼 |
| `features/scenes/OrderPanel.tsx` | Director가 보낸 주문 상태 표시 (상태를 소유하지 않음) |
| `features/feedback/` | 피드백 카드, 복습 탭 |
| `features/speech/` | 다시 들어볼 구간(녹음 구간 재생), 따라 말하기 |
| `features/report/` | 평가 결과 비교 화면 `/report` (`evals/compare.py`와 같은 규칙) |
| `services/` | WebSocket 클라이언트, REST, 오디오(PCM 변환, NPC 음성 큐, 구간 재생) |

## 데이터

| 저장소 | 내용 | Git |
|---|---|---|
| `scenes/*.yaml` + `scenes/schema/` | 메뉴, 별칭, 단계, 행동별 지시·템플릿, 가드 규칙. 코드에는 대사·메뉴가 없음 | 포함 |
| `data/scenespeak.db` (SQLite) | users, sessions, utterances(원래 인식 결과 `asr_text` 보존), feedback, review_items, error_records | 제외 |
| `data/audio/{session}/{seq}.wav` | 사용자 녹음. 구간 재생용, 기본 7일 후 서버 시작 시 삭제 | 제외 |
| `evals/*.jsonl`, `evals/results/*.json` | 평가 데이터와 결과 (D-018) | 포함 |
| `models/`, Hugging Face 캐시 | 모델 파일 | 제외 |

## 평가 하네스

```
evals/run.py ──┬─ run_dialogue.run()      dialogue-cases.jsonl → NPC 품질·지연
               ├─ score_feedback.score()  feedback-cases.jsonl → 문법 탐지 P/R/F1
               └─ asr/run_asr.evaluate()  합성(또는 실제) 음성 manifest → WER·인식률·지연
               → evals/results/{시각}-suite-{라벨}.json (모델, 설정, git 커밋, 평탄화 지표, 방향)
evals/compare.py A.json B.json  → 지표별 변화와 개선/악화 판단
/report 화면                    → 같은 비교를 표와 막대로 (GitHub Pages에서는 빌드에 포함된 결과 파일 사용)
```

## 테스트와 CI

- `backend/tests`: Director·추출기·가드는 `dialogue-cases.jsonl`로 결정적으로 검사한다. WebSocket·REST는 Mock 어댑터로, CTC 정렬은 합성 확률 행렬로, LLM 응답 계약은 fixture로 검사한다. 실제 모델 테스트는 `pytest -m model`로 따로 실행한다.
- `frontend/tests`: 리듀서, 오디오 변환, 표시 문구, 리포트 비교.
- CI(`.github/workflows/ci.yml`): Ruff, 장면 검사, AI 응답 JSON 스키마, compare 스크립트, pytest(Mock), tsc, vitest, build. 모델은 내려받지 않는다.
- 배포(`deploy-pages.yml`): 프론트 빌드만 GitHub Pages에 올린다. 대화에는 백엔드가 필요하다.
