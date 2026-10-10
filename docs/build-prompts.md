# 구현 프롬프트 4단계

각 프롬프트를 Claude Code에 순서대로 붙여넣는다. 앞 단계의 테스트가 통과한 뒤 다음 단계로 넘어간다.

| 프롬프트 | 포함 Phase | 끝나면 되는 것 | 예상 |
|---|---|---|---|
| 1 | 0 + 1 | 텍스트로 주문하면 템플릿 대사로 주문 완료까지 진행 | 1–1.5일 |
| 2 | 2 + 3 | Qwen3 NPC와 텍스트 대화, 대화 후 피드백·학습 기록 | 1.5–2.5일 |
| 3 | 4 + 5 | 마이크로 말하고 NPC 음성으로 답 듣기 | 1.5–3일 |
| 4 | 6 + 7 | 다시 들어볼 구간, 평가 하네스, 개선 전후 비교 리포트 | 2일 |

---

## 프롬프트 1 — 뼈대 + Scene Director

```
docs/design.md와 docs/decision-log.md를 먼저 읽고, 설계의 Phase 0과 Phase 1을 구현해줘.

목표: 브라우저에서 텍스트로 카페 주문을 하면, Scene Director가 주문 상태를 관리하고 YAML 템플릿 대사로 응답해서 주문 완료(또는 취소)까지 진행되는 상태.

구현 범위
1. 저장소 구조: design.md와 원래 계획의 디렉터리 구조(frontend/, backend/, scenes/, evals/, docs/, .github/workflows/)를 만든다.
2. .gitignore: .env, 모델 파일(*.gguf, *.onnx, *.pt, *.bin, models/), 오디오(*.wav, *.mp3, *.webm, evals/audio/), data/, node_modules, __pycache__, .venv
3. 백엔드 (Python 3.12, FastAPI, Pydantic v2, pytest, Ruff)
   - backend/app/ai/types.py: design.md 3절의 STT/LLM/TTS/Aligner Protocol과 결과 모델
   - backend/app/ai/*/mock.py: 각 어댑터의 Mock 구현, 설정(.env의 *_PROVIDER)으로 고르는 레지스트리
   - backend/app/scenes/: 장면 YAML 로더, Pydantic 장면 모델, RuleExtractor(별칭 최장 일치, 메뉴에 없는 수식어 감지), Director 상태 머신(phase, slots, next_action, 성공·종료 판정), OutputGuard(메뉴 외 품목, 2문장 초과 검사)
   - Phase 1에서는 NPC 대사를 actions의 fallback 템플릿으로 만든다 (LLM은 Mock).
   - WebSocket /ws/session: design.md 2.4의 메시지 중 session_start, text_utterance, session_end, scene_state, npc_reply, task_result, error
4. scenes/new-york-cafe.yaml (design.md 4절 그대로) + scenes/schema/scene.schema.json + 스키마 검사 스크립트(별칭 중복, phases.next 참조, placeholder 유효성)
5. 프론트엔드 (React + TypeScript + Vite): 대화 화면, 텍스트 입력, 주문 상태 패널(필수/선택 슬롯, phase), 주문 성공 표시. 상태 관리는 React 기본 기능만.
6. CI (.github/workflows/ci.yml, permissions: contents: read): Ruff, pytest, tsc, vite build, 장면 스키마 검사. 모델 다운로드 금지.
7. evals/dialogue-cases.jsonl: 정상 주문, 크기 변경, 메뉴에 없는 요청, cold brew를 hot으로 요청, 취소, 주제 이탈 등 최소 15개 케이스. pytest가 이 파일로 Director를 검증한다.
8. README.md: 실행 방법(Windows PowerShell 기준 포함), .env.example

완료 기준
- pytest, ruff, tsc, build, 스키마 검사가 로컬에서 모두 통과
- 백엔드와 프론트를 띄우고 "I want hot latte" → "Large, please" → "Yes, that's all"로 주문 성공까지 진행됨
- 메뉴에 없는 요청과 cold brew hot 요청이 handle_unavailable로 처리됨

규칙: 테스트 없이 완료 처리하지 말 것. 설계와 다르게 결정한 것은 docs/decision-log.md에 추가. 끝나면 실행 명령, 테스트 결과, 남은 문제를 요약해줘. 커밋은 하지 말 것.
```

---

## 프롬프트 2 — LLM NPC + 피드백·학습 기록

```
docs/design.md, docs/decision-log.md, 현재 코드를 먼저 확인하고 Phase 2와 Phase 3을 구현해줘.

목표: Qwen3-8B NPC와 텍스트로 자연스럽게 주문하고, 대화가 끝나면 구조화된 피드백을 보고, 오류와 복습 문장이 SQLite에 저장되는 상태.

시작 전 확인: nvidia-smi로 GPU와 VRAM을 확인하고, Ollama 설치 여부와 qwen3:8b 모델 유무를 확인해. 없으면 설치·다운로드 명령을 알려주고 내가 실행할 때까지 Mock으로 개발을 계속해.

Phase 2 — LLM NPC
1. backend/app/ai/llm/ollama.py: OllamaLLM 어댑터. think=false, format에 JSON Schema 전달, max_tokens·timeout 설정, keep_alive로 모델 상주. 지연·토큰 수를 LLMResult에 기록.
2. NPC 프롬프트: 장면 YAML(persona, forbidden, 허용 메뉴)과 Director의 next_action + 현재 상태만 넣는다. 응답 스키마는 design.md 3.1의 {reply, extracted}.
3. 흐름: Director가 next_action 결정 → LLM이 대사 생성 → OutputGuard 실패 시 1회 재생성 → 또 실패하면 YAML fallback 템플릿. extracted는 Director가 메뉴와 대조한 뒤에만 반영.
4. LLM 실패·타임아웃 시 템플릿으로 대화 지속.
5. evals/run_dialogue.py: dialogue-cases.jsonl을 실제 LLM으로 돌려 장면 이탈률, 메뉴 환각률, 재생성률, 평균·p95 응답 시간을 JSON으로 출력. 결과를 docs/experiments.md에 "문제 → 기준 측정 → 원인 분석 → 개선 → 재측정 → 결과" 형식으로 1회차 기록.

Phase 3 — Learning Evaluator + 저장
1. backend/app/evaluation/: 세션 종료 후 전체 대화를 LLM에 보내 원래 계획의 피드백 JSON(task_success, grammar_errors, unnatural_expressions, missed_information, recommended_sentences, review_items, summary)과 uncertain_spans를 받는다. task_success는 LLM 값이 아니라 Director 판정으로 덮어쓴다.
2. Pydantic 검증 실패 시 1회 재요청 → 그래도 실패하면 안전한 기본 결과.
3. 신뢰도 게이팅: 사용자 발화에 단어 신뢰도가 있고 0.6 미만이면, 그 단어가 포함된 grammar_errors는 제거하고 uncertain_spans로 옮긴다. (텍스트 모드에서는 신뢰도가 없으므로 그대로 둔다.)
4. SQLAlchemy + SQLite: users(닉네임), sessions, utterances, feedback_items, review_items. 반복 오류 집계 쿼리. data/ 폴더에 DB 저장.
5. WebSocket: transcript_fix, feedback_ready 추가. REST: GET /sessions/{id}/feedback, GET /users/{id}/review.
6. 프론트: 피드백 화면(과업 결과, 문법·표현, 불확실한 단어, 복습 문장), 복습 목록 화면, 닉네임 입력.
7. evals/feedback-cases.jsonl: 사람이 정답을 표시할 수 있는 문장 50개 형식과 예시 10개를 만들고, 정밀도·재현율·F1을 계산하는 스크립트를 만든다. 나머지 40개 라벨링은 내가 하도록 가이드를 evals/README.md에 적어줘.

완료 기준
- CI는 Mock으로 전부 통과 (실제 Ollama 호출 없음)
- 로컬에서 실제 Qwen3로 주문 완주 → 피드백 화면 → 복습 목록에 저장 확인
- 평가 JSON 파싱 실패, LLM 타임아웃 상황의 테스트 존재

규칙은 프롬프트 1과 같다. 끝나면 측정 수치와 남은 문제를 요약해줘. 커밋은 하지 말 것.
```

---

## 프롬프트 3 — 음성 입력 + 음성 출력

```
docs/design.md, docs/decision-log.md, 현재 코드를 확인하고 Phase 4와 Phase 5를 구현해줘.

목표: 마이크 버튼을 누르고 영어로 주문하면 음성이 텍스트로 바뀌고, NPC 대사가 영어 음성으로 재생되는 상태. 원래 계획의 완료 조건 1~9번이 실제로 동작해야 한다.

시작 전 확인: GPU, CUDA/cuDNN 상태, Python 패키지 설치 가능 여부, espeak-ng 설치 여부. Windows에서 막히는 부분은 해결 방법(또는 WSL2 전환)을 먼저 알려줘.

Phase 4 — 음성 입력
1. 프론트: @ricky0123/vad-web(Silero)로 발화 감지, 16kHz mono PCM으로 변환해 audio_utterance 전송. 마이크 버튼, 녹음 중·처리 중 상태 표시, 마이크 권한 거부 시 안내 + 텍스트 입력으로 대체.
2. 백엔드: backend/app/ai/stt/faster_whisper.py. 모델은 .env로 선택(small.en int8 CPU / large-v3-turbo float16 GPU), word_timestamps=True, 단어 신뢰도, 장면 메뉴 단어를 hotwords로 전달. 모델은 서버 시작 시 1회 로드.
3. user_transcript 메시지에 words와 low_confidence_spans 포함. 프론트에서 저신뢰 단어를 표시하고, 사용자가 전사를 고칠 수 있게(transcript_fix).
4. 세션 동안 사용자 오디오를 data/audio/{session}/에 저장하고 보존 기간(.env, 기본 7일) 지난 파일을 지우는 정리 함수.
5. 단계별 지연 로그(VAD 종료 → STT → Director → LLM → Guard → TTS)를 세션마다 기록.

Phase 5 — 음성 출력
1. backend/app/ai/tts/kokoro.py: Kokoro-82M, 장면 YAML의 voice 사용, 24kHz WAV 반환.
2. npc_audio 메시지로 전송, 프론트에서 재생. 실패 시 npc_audio_failed를 보내고 텍스트로 대화 계속.
3. 사용자 첫 클릭 이후에만 오디오 재생(브라우저 자동재생 정책).

실험 준비
- evals/asr/: design.md 5절 EXP-ASR-001을 실행하는 스크립트. 입력은 evals/audio/manifest.jsonl(파일 경로, 정답 전사, 정답 슬롯, 조건). 출력은 조건별 WER(jiwer + Whisper 정규화), 슬롯 정확도(RuleExtractor 재사용), 지연 p50/p95, RTF, 최대 메모리.
- 혼자 녹음할 수 있게 30문장 스크립트와 녹음 가이드를 evals/README.md에 추가. 소음 합성 스크립트는 소음 파일 경로를 인자로 받게.

완료 기준
- CI는 Mock으로 통과, 실제 모델 테스트는 pytest 마커(@pytest.mark.model)로 분리하고 기본 실행에서 제외
- 로컬에서 마이크로 주문 완주, NPC 음성 재생, TTS를 꺼도 대화 지속
- 3턴 대화의 단계별 지연 수치를 보고

규칙은 같다. 끝나면 측정한 지연, 막힌 설치 문제, 남은 문제를 요약해줘. 커밋은 하지 말 것.
```

---

## 프롬프트 4 — 발화 분석 + 평가 리포트 + OSS 정리

```
docs/design.md, docs/decision-log.md, docs/experiments.md, 현재 코드를 확인하고 Phase 6과 Phase 7을 구현해줘.

목표: 대화 후 다시 들어볼 구간을 보여주고, 같은 테스트 데이터로 개선 전후를 비교할 수 있으며, 오픈소스 라이선스 문서가 정리된 상태. 원래 계획의 완료 조건 10번 충족.

Phase 6 — 발화 분석 (세션 종료 후에만 실행)
1. backend/app/ai/alignment/: wav2vec2 영어 정렬 어댑터(WhisperX 또는 torchaudio). 결과는 단어별 시작·끝, 앞 멈춤 길이.
2. 피드백에 추가: 0.8초 이상 멈춤, 저신뢰 단어, 다시 들어볼 구간(오디오 시작·끝). "발음 점수"라는 표현은 UI와 코드 어디에도 쓰지 않는다.
3. 복습 따라 말하기 모드: 복습 문장을 보여주고 사용자가 읽으면, 정답 문장과 비교해 누락·추가된 단어를 표시.
4. 프론트: 피드백 화면에서 구간 클릭 시 해당 부분 오디오 재생.

Phase 7 — 평가 하네스 + 리포트
1. evals/run.py: 대화(run_dialogue), 피드백(feedback-cases), ASR(manifest)을 한 번에 또는 골라서 실행. 결과는 evals/results/{날짜}-{라벨}.json (모델 이름, 설정, git 커밋, 지표 포함). results는 .gitignore에서 제외 여부를 정해 decision-log에 기록.
2. evals/compare.py: 결과 파일 두 개를 비교해 지표별 변화를 표로 출력.
3. 프론트 리포트 화면(/report): 결과 파일 목록, 두 개 골라 비교, 지표 표와 간단한 막대 차트.
4. docs/experiments.md를 지금까지의 실험으로 정리, docs/model-selection.md에 모델 선택 근거(성능, 라이선스, 유지관리, 실행 환경) 작성, docs/architecture.md 작성.

OSS 정리
1. 실제로 설치된 패키지·모델의 버전을 확인해 docs/licenses.md와 THIRD_PARTY_NOTICES.md 작성: 이름, URL, 버전, 라이선스, 사용 목적, 수정 여부, 배포 시 준수 사항.
2. Kokoro의 G2P가 espeak-ng(GPL-3.0)를 쓰는지 확인하고, 쓴다면 영향과 대안을 decision-log에 기록.
3. CI에 AI 응답 JSON 스키마 검사(fixture 기반) 추가.

완료 기준
- 같은 데이터로 run.py를 두 번(예: hotwords 없음/있음) 돌리고 compare.py와 리포트 화면에서 차이를 확인
- CI 통과
- README에 전체 데모 시나리오 실행 방법

규칙은 같다. 끝나면 최종 시연 순서와 남은 문제를 요약해줘. 커밋은 하지 말 것.
```
