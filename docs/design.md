# SceneSpeak AI — 설계 문서 (Office Hours 결과)

- 작성일: 2026-10-11
- 상태: 초안 (구현 전 승인 대상)
- 범위: MVP — 뉴욕 카페 장면 1개
- 진행 방식: 선택 지점마다 권장안(Recommended)으로 진행함. 각 결정은 `docs/decision-log.md`에 기록.

---

## 0. Office Hours 요약

### 0.1 이 프로젝트는 무엇을 증명해야 하는가

"AI가 영어로 대답한다"는 이미 흔하다. SceneSpeak의 차별점은 아래 **세 가지를 측정 가능하게** 보여주는 것이다.

1. **장면이 깨지지 않는다** — NPC가 메뉴에 없는 음료를 만들거나, 카페 직원 역할을 벗어나지 않는다.
2. **과업 성공을 기계가 정확히 판정한다** — "주문 완료"를 LLM의 감이 아니라 상태(state)로 판정한다.
3. **피드백이 틀리지 않는다** — 사용자가 맞게 말한 것을 틀렸다고 지적하지 않는다(특히 음성인식 오류 때문에).

즉 핵심 자산은 모델이 아니라 **Scene Director + Learning Evaluator + 평가 데이터셋**이다. 모델은 모두 교체 가능한 부품으로 둔다.

### 0.2 전제(premise) 점검 — 원래 프롬프트에서 수정이 필요한 부분

| # | 원래 전제 | 문제 | 수정안 (채택) |
|---|---|---|---|
| P1 | 처리 흐름이 `STT → Director → LLM → TTS → Evaluator`인 단일 파이프라인 | 실시간 루프(대화 턴)와 사후 분석(평가, 정렬)이 섞여 있음. 정렬·평가를 턴마다 돌리면 지연이 커짐 | **실시간 턴 루프**와 **세션 종료 후 분석 파이프라인**을 분리 |
| P2 | WhisperX 정렬로 "누락된 단어"를 알려준다 | 자유 발화에는 정답 문장(reference)이 없다. ASR 결과를 ASR 결과에 정렬하면 누락 단어는 원리적으로 검출 불가 | 자유 대화: **긴 멈춤, 저신뢰 단어, 다시 들어볼 구간**만 제공. 누락 단어는 **복습 따라 말하기 모드**(정답 문장이 있는 경우)에서만 제공 |
| P3 | Learning Evaluator가 인식된 문장의 문법을 지적한다 | ASR 오류를 사용자의 문법 오류로 오판할 위험. 가장 신뢰를 잃는 실패 | **신뢰도 게이팅**: 저신뢰 단어가 포함된 구간은 문법 지적 대상에서 제외하고 "인식 불확실"로 표시. 사용자가 전사를 정정할 수 있는 UI 제공 |
| P4 | LLM이 대화하면서 장면 규칙을 따른다 | 주문 상태를 LLM이 기억하게 하면 상태 표류(drift)·환각 메뉴가 발생하고 테스트 불가 | **주문 상태는 Scene Director가 소유**. LLM은 (a) 슬롯 추출 후보 제시 (b) Director가 정한 다음 행동을 자연스러운 문장으로 표현하는 역할만 |
| P5 | 음성 파이프라인부터 구축 | 7명 중 GPU 없는 팀원은 개발 불가, 핵심 로직(Director/Evaluator) 검증이 늦어짐 | **텍스트 우선 수직 슬라이스** → 음성은 병렬 스파이크로 붙임 |
| P6 | Silero VAD 위치 미정 | 서버 VAD는 무음까지 전부 전송해야 함 | **브라우저 측 Silero VAD**(ONNX, `@ricky0123/vad-web`)로 발화 구간만 전송 |
| P7 | Qwen3-8B 사용 | Qwen3는 기본적으로 thinking 모드가 켜져 있어 응답 지연이 수 초 증가 | Ollama 호출 시 **`think: false`**, 응답 길이 제한, JSON 스키마 강제(`format`) |

### 0.3 접근 방식 비교

| 접근 | 설명 | 장점 | 단점 |
|---|---|---|---|
| **A. 텍스트 우선 수직 슬라이스 (Recommended, 채택)** | Mock 어댑터로 전체 흐름을 먼저 연결 → 텍스트 대화로 Director/Evaluator 완성 → 음성 부품 교체 | 핵심 차별점을 가장 먼저 검증, GPU 없이도 전원 개발 가능, CI 테스트 용이 | 데모 "와우" 포인트(음성)가 2~3주 늦게 보임 → 음성 스파이크를 병렬로 돌려 보완 |
| B. 음성 우선 | VAD→STT→LLM→TTS를 먼저 연결 | 데모가 빨리 나옴 | 지연·장비 문제에 초기 시간을 소모, Director가 프롬프트 덩어리로 전락할 위험 |
| C. 클라우드 API로 프로토타입 후 OSS 교체 | 상용 API로 빠르게 구현 | 가장 빠름 | 프로젝트 요구(OSS 모델 선택 근거·비교 실험)와 맞지 않음, 교체 비용 |

---

## 1. MVP 구현 순서

**원칙: 각 단계는 "끝에서 끝까지 동작 + 테스트 통과" 상태로 끝난다.**

| 단계 | 목표 | 산출물 | 완료 기준 |
|---|---|---|---|
| **Phase 0. 뼈대** (1주) | 저장소·CI·Mock으로 걷는 해골(walking skeleton) | 디렉터리 구조, `.gitignore`, CI(Ruff/pytest/tsc/build/스키마 검사), 어댑터 인터페이스 + Mock, WebSocket 에코 | Mock STT→Mock LLM→Mock TTS로 브라우저에서 한 턴 왕복, CI green |
| **Phase 1. Scene Director** (1~2주) | 장면 YAML + 상태 머신 + 규칙 기반 슬롯 추출 | `scenes/new-york-cafe.yaml`, JSON Schema, Director 단위 테스트, 대화 케이스 `evals/dialogue-cases.jsonl` 초안 | 텍스트 입력만으로 주문 완료/취소/재질문이 결정적으로 동작, 메뉴 외 품목 거부 |
| **Phase 2. LLM NPC** (1주) | Qwen3-8B(Ollama) 연결, Director가 지시한 행동을 대사로 생성 | `OllamaLLM` 어댑터, NPC 프롬프트, 출력 검증기(메뉴 외 품목·역할 이탈 차단) | 텍스트 채팅 UI로 카페 주문 완주, 대화 품질 실험 1회차 기록 |
| **Phase 3. Evaluator + 저장** (1~2주) | 세션 종료 후 구조화 피드백 + SQLite 기록 | Evaluator(JSON 스키마 + 재시도 + 안전 기본값), SQLAlchemy 모델, 피드백 화면 | 라벨링한 테스트 문장 50개 기준 정밀도/재현율 측정 가능 |
| **Phase 4. 음성 입력** (Phase 1~3과 병렬 스파이크 → 통합) | 브라우저 VAD + faster-whisper | `FasterWhisperSTT` 어댑터, 마이크 UI, ASR 실험 1 결과 | 마이크로 주문 완주, 턴 지연 측정 로그 |
| **Phase 5. 음성 출력** | Kokoro TTS | `KokoroTTS` 어댑터, 오디오 재생, TTS 실패 시 텍스트 폴백 | TTS 프로세스를 죽여도 대화 지속 |
| **Phase 6. 발화 분석** | 정렬 기반 힌트(사후 분석) + 복습 따라 말하기 | `Aligner` 어댑터, 멈춤/저신뢰/재청취 구간, 복습 모드의 누락 단어 | "발음 점수"라는 표현 없이 구간 하이라이트 제공 |
| **Phase 7. 평가 하네스 & 리포트** | 동일 데이터 재실행으로 개선 전후 비교 | `evals/run.py`, 결과 JSON, 비교 리포트 화면 또는 `docs/experiments.md` | 완료 조건 10번 충족 |

병렬 트랙: Phase 0 직후부터 **음성 스파이크**(STT/TTS 지연 측정, 2명)와 **평가 데이터 수집·라벨링**(1명)을 시작한다.

---

## 2. 프론트엔드 / 백엔드 책임 구분

### 2.1 실시간 턴 루프

```
[Browser]                                         [Backend]
 mic → Web Audio(16kHz mono PCM)
     → Silero VAD (vad-web)  ── speech_end ──▶  STT adapter (faster-whisper)
                                                  → Scene Director: 슬롯 추출/검증, 다음 행동 결정
                                                  → LLM adapter: 행동을 대사로 표현 (JSON)
                                                  → Output Guard: 메뉴/역할 검증 (실패 시 1회 재생성 → 템플릿 폴백)
                                                  → TTS adapter (Kokoro, 실패 허용)
 transcript 표시 ◀── user_transcript ───────────
 NPC 텍스트/오디오 재생 ◀── npc_reply, npc_audio ─
 주문 상태 패널 ◀── scene_state ───────────────
```

### 2.2 세션 종료 후 분석 파이프라인 (비실시간)

```
session_end → Aligner(wav2vec2/WhisperX) → 멈춤/저신뢰 구간
            → Learning Evaluator(LLM, JSON 스키마) → 신뢰도 게이팅 → 피드백
            → SQLite 저장(오류, 복습 문장, 성공 여부)
            → feedback_ready 이벤트
```

### 2.3 책임 표

| 영역 | 프론트엔드 | 백엔드 |
|---|---|---|
| 오디오 | 마이크 권한, 캡처, 16kHz 리샘플, VAD, 발화 구간 전송, NPC 오디오 재생 | 오디오 디코딩·검증, 세션 동안 임시 보관(재청취용), 세션 후 보존 정책 적용 |
| 대화 상태 | 표시만 함 (상태 소유 X) | Scene Director가 단일 진실 원천(single source of truth) |
| AI 호출 | 없음 (브라우저에서 모델 호출 금지, VAD 제외) | 모든 모델 어댑터, 타임아웃·폴백 |
| 검증 | 입력 형태 검증 | 장면 스키마, LLM 출력 스키마, 메뉴/역할 가드 |
| 피드백 | 결과 렌더링, 전사 정정 UI, 재청취 구간 재생 | 평가, 신뢰도 게이팅, 저장 |
| 계측 | 클라이언트 측 지연(발화 종료→첫 오디오 재생) | 단계별 지연(STT/Director/LLM/TTS) 로그 |

### 2.4 WebSocket 메시지 (초안)

```
client → server
  session_start   { scene_id }
  audio_utterance { seq, sample_rate: 16000, pcm_base64 | binary frame }
  text_utterance  { seq, text }            # 텍스트 모드/디버그
  transcript_fix  { seq, corrected_text }  # 사용자 전사 정정
  session_end     { reason: "user" }

server → client
  user_transcript { seq, text, words[], low_confidence_spans[] }
  scene_state     { phase, slots, missing_required[] }
  npc_reply       { seq, text }
  npc_audio       { seq, format: "wav", sample_rate: 24000, data } | npc_audio_failed
  task_result     { success, reason }
  feedback_ready  { session_id }
  error           { code, message, recoverable }
```

턴 기반(push-to-talk + VAD 종료 감지)으로 시작하고, **NPC 말 끊기(barge-in)와 전이중(full-duplex)은 MVP에서 제외**한다.

---

## 3. AI 모델별 어댑터 인터페이스

Python `Protocol`로 정의하고, 설정(`.env`의 `STT_PROVIDER=faster_whisper|mock` 등)으로 레지스트리에서 선택한다. 모든 결과에 `model_id`와 `latency_ms`를 포함해 실험 기록에 그대로 쓴다.

```python
# backend/app/ai/types.py (설계안)
class WordInfo(BaseModel):
    word: str
    start: float          # sec
    end: float
    confidence: float | None

class Transcript(BaseModel):
    text: str
    words: list[WordInfo]
    language: str | None
    audio_duration_ms: int
    latency_ms: int
    model_id: str

class STTAdapter(Protocol):
    def transcribe(self, audio: AudioInput, *, hotwords: list[str] | None = None) -> Transcript: ...

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class LLMResult(BaseModel):
    text: str
    parsed: dict | None        # json_schema를 준 경우
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    model_id: str

class LLMAdapter(Protocol):
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        json_schema: dict | None = None,
        max_tokens: int = 128,
        temperature: float = 0.6,
    ) -> LLMResult: ...

class SpeechAudio(BaseModel):
    wav_bytes: bytes
    sample_rate: int
    latency_ms: int
    model_id: str

class TTSAdapter(Protocol):
    def synthesize(self, text: str, *, voice: str) -> SpeechAudio: ...

class AlignedWord(WordInfo):
    pause_before_ms: int

class AlignerAdapter(Protocol):
    def align(self, audio: AudioInput, text: str) -> list[AlignedWord]: ...
```

- **Mock 구현**: `MockSTT`(파일명→고정 전사), `MockLLM`(스크립트된 응답/스키마 기본값), `MockTTS`(무음 WAV), `MockAligner`. CI는 Mock만 사용.
- **실 구현 1순위**: `FasterWhisperSTT`, `OllamaLLM`(`think=false`, `format=<schema>`), `KokoroTTS`, `Wav2Vec2Aligner`.
- **교체 후보**: `LlamaCppLLM`, `Qwen3ASR`.
- 모든 어댑터 호출은 공통 래퍼에서 **타임아웃·예외→도메인 에러 변환·지연 로깅**을 처리한다.
- Learning Evaluator와 NPC는 같은 `LLMAdapter`를 쓰되 프롬프트·스키마만 다르다(평가용 모델을 나중에 따로 지정 가능).

### 3.1 Scene Director와 LLM의 역할 분리 (P4 상세)

```
user_text
  → RuleExtractor: 장면 YAML의 별칭(aliases)으로 슬롯 후보 추출 (결정적, 빠름)
  → LLM 추출(JSON) : 규칙으로 못 잡은 경우에만 호출하지 않고,
                     NPC 응답 생성과 같은 호출에서 {reply, extracted} 를 함께 받음
  → Director.merge : 두 후보를 메뉴 목록과 대조. 메뉴에 없는 값은 버리고 "unavailable" 행동 생성
  → Director.next_action : ask_size | ask_temperature | offer_options | confirm_order | handle_unavailable | close
  → (다음 턴) LLM은 next_action + 현재 상태 + 허용 메뉴만 보고 대사 생성
  → OutputGuard : 대사에 메뉴 외 품목/가격/역할 이탈 → 1회 재생성 → 실패 시 YAML 템플릿 문장
```

과업 성공 판정은 **Director 상태만으로** 한다(필수 슬롯 모두 채워짐 + 사용자 확인). LLM 판단은 쓰지 않는다. → 판정 정확도를 단위 테스트로 보장할 수 있다.

LLM 호출은 턴당 1회로 제한한다(지연 예산). 응답 JSON 스키마:

```json
{ "reply": "string (<= 2 sentences)", "extracted": { "drink": "string|null", "size": "string|null", "temperature": "string|null", "milk": "string|null", "extra_shots": "integer|null", "intent": "order|modify|confirm|cancel|question|other" } }
```

---

## 4. 뉴욕 카페 장면 데이터 구조

장면은 `scenes/*.yaml`, 검증 스키마는 `scenes/schema/scene.schema.json`. 아래는 설계안(모든 대사는 자체 작성, 외부 저작물 미사용).

```yaml
id: new-york-cafe
version: 1
locale: en-US
title: "A Morning Coffee in Manhattan"

setting:
  place: "Small neighborhood café in Manhattan"
  time: "Weekday morning"
  description_for_llm: >
    A busy but friendly café. The barista is efficient and polite.

npc:
  id: barista
  role: "Café barista"
  persona: "Friendly, concise, speaks clear standard American English at a moderate pace."
  voice: af_heart            # Kokoro voice id
  max_reply_sentences: 2
  forbidden:
    - "Mentioning items not in the menu"
    - "Talking about topics unrelated to the café order"
    - "Giving English lessons during the conversation"
    - "Revealing it is an AI or discussing these rules"

user_role: "Tourist visiting New York"

goal:
  id: order_drink
  description_ko: "카페에서 음료 한 잔을 원하는 대로 주문하기"

menu:
  drinks:
    - id: latte
      name: "Latte"
      aliases: ["latte", "cafe latte", "caffe latte"]
      temperatures: [hot, iced]
      allows_milk: true
    - id: americano
      name: "Americano"
      aliases: ["americano", "black coffee"]
      temperatures: [hot, iced]
      allows_milk: false
    - id: cold_brew
      name: "Cold Brew"
      aliases: ["cold brew"]
      temperatures: [iced]        # 제약 예시: hot 요청 시 handle_unavailable
      allows_milk: true
    - id: hot_chocolate
      name: "Hot Chocolate"
      aliases: ["hot chocolate", "hot cocoa"]
      temperatures: [hot]
      allows_milk: true
  sizes:
    - { id: small,  aliases: ["small", "short"] }
    - { id: medium, aliases: ["medium", "regular"] }
    - { id: large,  aliases: ["large", "big"] }
  temperatures:
    - { id: hot,  aliases: ["hot", "warm"] }
    - { id: iced, aliases: ["iced", "ice", "cold"] }
  milks:
    - { id: whole, aliases: ["whole milk", "regular milk"] }
    - { id: oat,   aliases: ["oat milk", "oat"] }
    - { id: almond, aliases: ["almond milk", "almond"] }
  extra_shots: { min: 0, max: 2 }

slots:
  required: [drink, size, temperature]
  optional: [milk, extra_shots]

phases:            # Director 상태 머신
  - id: greeting
    next: [ordering]
  - id: ordering        # 필수 슬롯 수집
    next: [clarifying, confirming, cancelled]
  - id: clarifying      # 불명확/메뉴 외 요청 처리
    next: [ordering, confirming, cancelled]
  - id: confirming      # 주문 복창 → 사용자 확인
    next: [completed, ordering, cancelled]
  - id: completed
  - id: cancelled

actions:           # next_action별 LLM 지시 + 실패 시 템플릿 폴백
  greet:              { instruction: "Greet the customer and ask what they would like.", fallback: "Hi there! What can I get for you today?" }
  ask_size:           { instruction: "Ask which size they want. Sizes: {sizes}.", fallback: "What size would you like?" }
  ask_temperature:    { instruction: "Ask if they want it hot or iced.", fallback: "Would you like that hot or iced?" }
  offer_options:      { instruction: "Briefly ask if they want a milk choice or an extra shot.", fallback: "Any milk preference or an extra shot?" }
  handle_unavailable: { instruction: "Politely say {item} is not available and suggest options from the menu.", fallback: "Sorry, we don't have that. We have {menu_list}." }
  confirm_order:      { instruction: "Repeat the full order and ask if that is everything.", fallback: "So that's {order_summary}. Is that everything?" }
  close:              { instruction: "Thank them and say the drink will be ready soon.", fallback: "Great, it'll be ready in a few minutes. Thanks!" }

success_condition:
  all_required_slots_filled: true
  user_confirmed: true

end_conditions:
  - phase: completed
  - phase: cancelled
  - max_user_turns: 12

learning:
  target_expressions:          # 복습/평가 참고용 (자체 작성)
    - "Can I get a {size} {temperature} {drink}?"
    - "Could I have that with {milk}?"
    - "That's all, thank you."
  feedback_focus: [request_forms, articles, politeness]
```

스키마 검사(CI): 필수 필드, 별칭 중복 금지, `temperatures`가 전역 정의 안에 있는지, 템플릿 placeholder 유효성, `phases.next` 참조 무결성.

---

## 5. 첫 번째 음성인식 비교 실험 (EXP-ASR-001)

**질문**: 카페 주문 맥락의 한국인 영어 발화에서, 지연 예산 안에 들어오면서 핵심 의도(슬롯)를 가장 잘 인식하는 가장 가벼운 설정은 무엇인가?

**범위 결정**: 1차 실험은 faster-whisper 계열만 비교한다(동일 런타임 → 변수 통제). Qwen3-ASR-0.6B는 런타임이 달라 EXP-ASR-002로 분리.

| 조건 | 모델 | 정밀도 | 문맥 힌트 |
|---|---|---|---|
| A | small.en | int8 (CPU) | 없음 |
| B | small.en | int8 (CPU) | 메뉴 `hotwords`/`initial_prompt` |
| C | large-v3-turbo | float16 (GPU) | 없음 |
| D | large-v3-turbo | float16 (GPU) | 메뉴 `hotwords`/`initial_prompt` |

**데이터** (`evals/audio/`는 Git 제외, 매니페스트만 커밋)
- 화자: 팀원 7명 + 가능하면 외부 지원자 (녹음·연구 사용 동의서 필수)
- 스크립트 발화: 1인당 30문장(메뉴명·크기·옵션·수정 요청 포함) → 정답 전사 확보
- 자유 발화: 1인당 10개, 사람이 전사
- 환경: 조용한 원본 + 카페 소음 합성(SNR 10dB, 5dB). 소음원은 라이선스 확인된 공개 데이터(예: DEMAND 데이터셋의 카페테리아 녹음, CC BY-SA)만 사용
- 총 약 (30+10) × 7 × 3 = 840 발화

**지표**
- WER (Whisper 영어 정규화 후 `jiwer`)
- **슬롯 인식 정확도**: 전사 → Director의 RuleExtractor → 정답 슬롯과 일치 비율 (= 핵심 의도 인식 성공률)
- 지연 p50/p95, RTF(처리시간/오디오 길이)
- 최대 RAM/VRAM
- 환각률: 소음 구간에서 존재하지 않는 문장 생성 비율

**결정 규칙 (사전 등록)**
> 슬롯 정확도 ≥ 95% 이고 STT p95 지연 ≤ 1.0초를 만족하는 조건 중 가장 가벼운 것을 기본값으로 채택. 만족하는 조건이 없으면 슬롯 정확도가 가장 높은 조건을 쓰고 지연 개선을 다음 실험으로 둔다.

**가설**: hotwords는 WER보다 슬롯 정확도를 더 크게 올리고, B와 C의 슬롯 정확도 차이는 작을 것이다.

**기록 형식**: `docs/experiments.md`에 문제 → 기준 측정 → 원인 분석 → 개선 → 재측정 → 결과·다음 실험 순.

**한계 명시**: 화자 수가 적고 연령·억양 분포가 편향됨. 결과를 일반화하지 않는다.

---

## 6. 예상되는 가장 큰 기술적 위험

| 순위 | 위험 | 왜 치명적인가 | 완화책 | 조기 검증 시점 |
|---|---|---|---|---|
| 1 | **턴 지연** (발화 종료→NPC 첫 음성 > 3초) | 대화감이 깨져 서비스 핵심 경험 실패 | 지연 예산: VAD 종료 0.3s + STT 0.7s + LLM 1.2s + TTS 0.5s ≈ 2.7s. Qwen3 `think=false`, `max_tokens` 제한, 모델 상주(keep_alive), 첫 문장 단위 TTS 스트리밍(후순위), 단계별 계측 | Phase 0 직후 음성 스파이크 |
| 2 | **ASR 오류가 문법 지적으로 둔갑** | 맞게 말했는데 틀렸다고 하면 학습 서비스 신뢰 붕괴 | 신뢰도 게이팅(P3), 전사 정정 UI, "잘못된 피드백 비율"을 1급 지표로 추적 | Phase 3 |
| 3 | **LLM 장면 이탈·메뉴 환각·상태 표류** | 과업 판정과 학습 경험이 모두 무너짐 | Director가 상태 소유, OutputGuard, 재생성 1회 → 템플릿 폴백, 적대적 대화 케이스(주제 이탈, 없는 메뉴 요청, 한국어 섞기) | Phase 1~2 |
| 4 | **4bit 8B 모델의 JSON 준수율** | Evaluator/추출 결과 파싱 실패 | Ollama structured output(`format`에 JSON Schema), Pydantic 검증, 1회 재요청 → 안전 기본값 | Phase 2 |
| 5 | **GPU 부족** (7명 중 일부만 GPU) | 개발 병목 | Mock 기본, 공용 GPU 서버 1대에 Ollama/STT 서비스화, CPU 개발용 대체 모델(예: Qwen3 소형) | Phase 0 |
| 6 | **"발음 점수" 과대 표현** | 신뢰·윤리 문제 | UI 문구 가이드: "다시 들어볼 부분", "인식이 불확실한 단어"만 사용 | Phase 6 |
| 7 | **라이선스** | 배포 불가 위험 | Kokoro의 G2P 경로에서 espeak-ng(GPL-3.0) 사용 여부 확인 및 격리 방안, Qwen3-ASR·wav2vec2 체크포인트별 라이선스 확인, 소음 데이터 CC BY-SA 고지 | Phase 0 (`docs/licenses.md`) |
| 8 | **브라우저 오디오 호환성** | 모바일 Safari 등에서 녹음 실패 | localhost/HTTPS 필수, AudioWorklet + 16kHz 리샘플, 모바일 Safari 수동 테스트 체크리스트 | Phase 4 |
| 9 | **평가 데이터 라벨링 부담** | F1을 못 내면 AI 역량 검증 불가 | 라벨 가이드 문서화, 2인 교차 라벨링 20% 샘플로 일치도 측정 | Phase 3 이전부터 |
| 10 | **개인정보** (팀원·사용자 음성) | 유출 시 문제 | 음성은 `.gitignore`, 세션 오디오 보존기간 설정(예: 7일), 동의서, 로그에 원본 오디오 미기록 | Phase 0 |

---

## 7. 7인 팀 역할 분담 초안

| 역할 | 주 담당 | 보조 담당 | 초반 2주 산출물 |
|---|---|---|---|
| **R1. 테크 리드 / Scene Director** | Director 상태 머신, RuleExtractor, OutputGuard, 장면 스키마 | 아키텍처 리뷰, decision-log 관리 | 장면 YAML+스키마, Director 단위 테스트 |
| **R2. LLM / 대화 품질** | `OllamaLLM` 어댑터, NPC 프롬프트, 대화 품질 실험 | Evaluator 프롬프트 공동 작업 | 적대적 대화 케이스 30개, 장면 이탈률 기준 측정 |
| **R3. 음성인식** | 브라우저 VAD 연동 협의, `FasterWhisperSTT`, EXP-ASR-001/002 | 녹음 프로토콜 | 지연 스파이크 결과, 실험 계획서 |
| **R4. 음성 합성·정렬 / 실시간 백엔드** | WebSocket 세션, `KokoroTTS`, `Aligner`, 지연 계측 | GPU 서버 운영 | Mock 왕복 WebSocket, TTS 지연 측정 |
| **R5. Learning Evaluator / 데이터** | Evaluator 스키마·재시도, 신뢰도 게이팅, 라벨링 가이드, 피드백 정밀도/재현율 | ASR 데이터 수집 | 라벨링 가이드, 문법 테스트 문장 50개 |
| **R6. 프론트엔드** | 대화 화면, 마이크·VAD, 주문 상태 패널, 피드백·복습 화면, 실험 리포트 화면 | 모바일 브라우저 테스트 | 텍스트 채팅 + Mock 오디오 UI |
| **R7. 플랫폼 / 품질 / OSS** | CI, SQLite·SQLAlchemy, 평가 하네스(`evals/run.py`), `licenses.md`, `THIRD_PARTY_NOTICES.md`, 개인정보 정책 | 테스트 전략 | CI green, 라이선스 표 초안, 동의서 양식 |

운영 규칙
- 주 1회 실험 리뷰: 각 실험은 `docs/experiments.md` 형식으로만 보고.
- 모든 PR은 테스트 포함 + CI 통과 + 결정 사항이 있으면 decision-log 갱신.
- 인터페이스(어댑터 타입, WebSocket 메시지, 장면 스키마) 변경은 R1 승인 필요.

---

## 8. 열린 질문 (구현 중 결정)

1. 공용 GPU 서버 사양 (VRAM 16GB 이상이면 Qwen3-8B Q4 + large-v3-turbo 동시 상주 가능 여부를 스파이크에서 확인)
2. 세션 오디오 보존 기간과 사용자 삭제 기능 범위
3. 사용자 계정: MVP는 로컬 단일 사용자(닉네임) vs 간단 로그인 → 권장: 닉네임 기반 로컬 사용자
4. 복습 화면을 MVP 마지막 주에 넣을지, 피드백 화면 내 섹션으로 대체할지

## 9. 다음 단계

승인되면 **Phase 0(뼈대)** 부터 구현한다: 디렉터리 구조, `.gitignore`, CI, 어댑터 Protocol + Mock, WebSocket 왕복, 장면 스키마 검사.
