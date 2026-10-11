# 모델 선택 근거

모든 모델은 어댑터 뒤에 있어서 `.env`의 `*_PROVIDER`만 바꾸면 교체할 수 있다(`backend/app/ai/registry.py`). 아래는 기본값을 고른 이유다. 수치는 [experiments.md](experiments.md), 라이선스 상세는 [licenses.md](licenses.md)에 있다.

**실행 환경 기준:** 개발 PC는 RTX 4060 8GB, Windows 11이다. 실시간 모델 세 개(LLM, STT, TTS)가 **VRAM 8GB 안에 동시에 올라가야** 하고, 한 턴의 서버 처리 시간이 **3초 이내**여야 한다. 이 제약이 대부분의 선택을 결정했다.

## 요약

| 역할 | 선택 | 실측 성능 | 라이선스 | VRAM | 대안과 탈락 이유 |
|---|---|---|---|---|---|
| NPC 대사·피드백 (LLM) | **Qwen3-8B** Q4_K_M, Ollama, `think=false`, JSON Schema 강제 | NPC 응답 p95 0.89초, 메뉴 환각 0%, 최종 가드 통과 100%, 피드백 문법 탐지 F1 0.93 | Apache-2.0 | 약 5.5GB | 더 작은 모델(3~4B)은 JSON·지시 준수 부족 위험, 14B 이상은 8GB에 STT·TTS와 같이 못 올림 |
| 음성 인식 (STT) | **Whisper small.en**, faster-whisper(CTranslate2), int8_float16, 문장 프롬프트 | WER 0.030, 주문 정보 인식률 0.95, p95 349 ms (합성 음성) | MIT | 약 0.6GB | large-v3-turbo: WER은 비슷하지만 인식률이 더 낮고 Qwen3와 동시에 올리면 메모리 부족 |
| NPC 음성 (TTS) | **Kokoro-82M** v1.0 ONNX, GPU | 문장당 0.26~0.37초(서버 턴 실측) | Apache-2.0 (모델), MIT (kokoro-onnx). **G2P에 espeak-ng GPL-3.0** | 약 0.5GB | Piper: 더 가볍지만 음질이 떨어지고 역시 espeak-ng를 씀. XTTS 계열: 무겁고 라이선스 제약(CPML) |
| 발화 구간 검출 (VAD) | **Silero VAD v5**, 브라우저(`@ricky0123/vad-web`) | 무음은 서버로 보내지 않음 | MIT | 없음 (브라우저 CPU) | 서버 VAD는 무음까지 전송해야 해서 대역폭·지연 손해 |
| 대화 후 단어 정렬 | **wav2vec2-base-960h** ONNX + numpy CTC 정렬, CPU | 문장당 약 0.2초, 끼워 넣은 1.2초 멈춤을 정확히 검출 | Apache-2.0 | 없음 (CPU) | WhisperX/torchaudio: torch 약 2.5GB 추가 설치. Whisper 단어 타임스탬프만 쓰기: 정렬 실패 시 대체용으로 유지 |

## 역할별 근거

### LLM — Qwen3-8B

- **성능:** Director가 다음 행동을 정하고, LLM은 그 행동을 문장으로 표현만 한다. 그래서 8B로 충분했다. NPC 대사 78개 중 메뉴 환각 0건이었다. 출력 가드에 걸린 경우는 재생성과 템플릿 대체로 모두 막혔다(EXP-DLG-001). 피드백 문법 탐지는 프롬프트를 발화별 판정 방식으로 바꾼 뒤 F1 0.44에서 0.93으로 올랐다(EXP-FB-001).
- **지연:** Qwen3는 기본으로 thinking 모드를 켜서 응답이 수 초 늦어진다. `think=false`로 끄고, Ollama `format`에 JSON Schema를 넣어 구조를 강제했다.
- **유지관리:** Ollama가 모델 다운로드, GPU 배치, keep-alive를 맡는다. Windows 설치가 간단하다. llama.cpp 직접 연동은 교체 후보로 남겼다(`LlamaCppLLM`).
- **라이선스:** Apache-2.0이라 상업적 사용과 재배포에 제약이 적다.
- **한계:** 한국어 해설(`explanation_ko`)의 자연스러움은 사람 평가를 아직 하지 않았다.

### STT — Whisper small.en

- **성능:** 8개 조건을 비교했다(EXP-ASR-001). 힌트가 없으면 "oat milk"를 "oatmeal"로 알아듣는 식으로 메뉴 단어를 틀렸다. `hotwords`는 힌트 단어를 문장 끝에 덧붙이는 환각을 만들었다. 메뉴 단어를 넣은 자연스러운 문장을 `initial_prompt`로 주는 방식이 가장 좋았다.
- **지연:** p95 349 ms로 예산(1초)보다 여유가 있다.
- **실행 환경:** CTranslate2 int8 연산으로 VRAM을 적게 쓴다. 영어 전용(.en) 모델이 같은 크기의 다국어 모델보다 영어 정확도가 높다.
- **한계:** 측정은 합성 음성 기준이다. 한국인 화자 녹음으로 다시 재야 한다(EXP-ASR-001b). Qwen3-ASR-0.6B 비교(EXP-ASR-002)는 런타임이 달라 따로 진행한다.

### TTS — Kokoro-82M

- **성능:** 82M 파라미터로 가볍고, 공개 TTS 중 음질 평가가 높은 편이다. 장면 YAML에서 목소리(`af_heart` 등)를 고를 수 있다.
- **지연:** GPU에서 서버 턴 기준 0.26~0.37초다. CPU는 1.3~5.2초라서 GPU를 기본값으로 했다.
- **유지관리:** kokoro-onnx는 torch 없이 onnxruntime만으로 돌아간다. 모델 파일 두 개만 받으면 된다.
- **라이선스 주의:** 텍스트를 발음기호로 바꿀 때 espeak-ng(GPL-3.0)를 같은 프로세스에서 쓴다. 설치본을 배포하려면 대안이 필요하다(D-029).
- **장애 대응:** TTS가 실패하거나 모델이 없어도 NPC가 글로 답하고 대화는 계속된다(D-024).

### VAD — Silero VAD (브라우저)

- 브라우저에서 발화 구간만 잘라 보내므로 서버는 무음을 받지 않는다. 자산은 CDN 없이 앱이 직접 서빙한다(D-022, D-026).
- 서버도 -55 dBFS 이하 무음과 Whisper 환각("You")을 한 번 더 거른다(D-028).

### 정렬 — wav2vec2-base-960h

- 자유 대화에는 정답 문장이 없다. 그래서 정렬은 "어디서 오래 멈췄나"처럼 시간 정보에만 쓰고, 빠진 단어 판정은 정답 문장이 있는 복습 따라 말하기에서만 한다(design.md P2).
- WhisperX 대신 ONNX와 직접 구현한 CTC 정렬을 썼다. torch를 설치하지 않아도 되고, 이미 설치된 onnxruntime을 재사용한다(D-027).
- 세션이 끝난 뒤에만 돌기 때문에 CPU로 충분하다. GPU 메모리는 실시간 모델에 남겨 둔다.

## VRAM 예산 (RTX 4060 8GB 실측)

| 모델 | 대략적 사용량 |
|---|---|
| Qwen3-8B Q4 (Ollama, 컨텍스트 포함) | 약 5.5GB |
| Whisper small.en int8 | 약 0.6GB |
| Kokoro ONNX + CUDA 런타임 | 약 0.5~1GB |
| 합계 | 약 7.7GB |
| wav2vec2 | CPU에서 실행 (0GB) |

VRAM이 16GB 이상인 서버라면 STT를 large-v3-turbo(+ 문장 프롬프트)로 다시 비교할 가치가 있다(EXP-ASR-001의 D 조건).

## 교체 방법

1. `backend/app/ai/<역할>/`에 `types.py`의 Protocol을 만족하는 클래스를 추가한다.
2. `registry.py`의 `*_PROVIDERS`에 이름을 등록한다.
3. `.env`의 `*_PROVIDER`를 바꾸고 `evals/run.py`로 같은 데이터를 다시 측정한다.
4. `evals/compare.py` 또는 `/report` 화면에서 기존 결과와 비교한다.
