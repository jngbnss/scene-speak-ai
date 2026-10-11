# Decision Log

형식: ID / 날짜 / 결정 / 근거 / 대안 / 상태

## D-001 텍스트 우선 수직 슬라이스
- 날짜: 2026-10-11
- 결정: Mock 어댑터로 전체 흐름을 연결한 뒤 텍스트 대화로 Scene Director·Evaluator를 먼저 완성하고, 음성 부품은 병렬 스파이크 후 교체한다.
- 근거: 핵심 차별점(장면 유지, 과업 판정, 피드백 정확도)을 가장 먼저 검증할 수 있고, GPU 없이도 전원이 개발할 수 있다.
- 대안: 음성 우선, 클라우드 API 프로토타입
- 상태: 채택

## D-002 주문 상태는 Scene Director가 소유
- 날짜: 2026-10-11
- 결정: 슬롯 상태와 과업 성공 판정은 Director가 결정적으로 수행한다. LLM은 추출 후보 제시와 대사 생성만 맡는다.
- 근거: 상태 표류와 메뉴 환각을 막고, 판정 정확도를 단위 테스트로 보장한다.
- 대안: LLM이 대화 이력으로 상태 관리
- 상태: 채택

## D-003 실시간 턴 루프와 사후 분석 분리
- 날짜: 2026-10-11
- 결정: 정렬(Aligner)과 Learning Evaluator는 세션 종료 후에만 실행한다.
- 근거: 턴 지연 예산(약 3초) 보호
- 상태: 채택

## D-004 브라우저 측 Silero VAD
- 날짜: 2026-10-11
- 결정: `@ricky0123/vad-web`(Silero ONNX)로 브라우저에서 발화 구간을 감지하고 발화 단위로 전송한다.
- 근거: 대역폭·서버 부하 감소, 즉각적인 UI 피드백
- 대안: 서버 측 Silero VAD 스트리밍
- 상태: 채택

## D-005 턴 기반 대화, barge-in 제외
- 날짜: 2026-10-11
- 결정: MVP는 턴 기반. NPC 말 끊기와 전이중 대화는 제외한다.
- 상태: 채택

## D-006 LLM 런타임: Ollama, thinking 비활성화
- 날짜: 2026-10-11
- 결정: Qwen3-8B Q4를 Ollama로 실행하고 `think=false`, JSON Schema `format`, 응답 토큰 제한을 적용한다. 턴당 LLM 호출은 1회로 제한한다.
- 근거: Qwen3 thinking 모드의 지연, 4bit 모델의 JSON 준수율 보완
- 대안: llama.cpp 서버 (어댑터로 교체 가능하게 유지)
- 상태: 채택

## D-007 정렬 결과를 발음 점수로 표현하지 않음
- 날짜: 2026-10-11
- 결정: 자유 발화에서는 긴 멈춤, 저신뢰 단어, 재청취 구간만 제공한다. 누락 단어는 정답 문장이 있는 복습 따라 말하기 모드에서만 제공한다.
- 근거: 자유 발화에는 reference 문장이 없어 누락 단어 검출이 원리적으로 불가능하다.
- 상태: 채택

## D-008 피드백 신뢰도 게이팅
- 날짜: 2026-10-11
- 결정: ASR 저신뢰 단어가 포함된 구간은 문법 지적에서 제외하고 "인식 불확실"로 표시한다. 사용자가 전사를 정정할 수 있다.
- 근거: ASR 오류를 사용자 오류로 오판하는 것이 가장 큰 신뢰 손실 요인이다.
- 상태: 채택

## D-009 EXP-ASR-001 범위
- 날짜: 2026-10-11
- 결정: 1차 ASR 실험은 faster-whisper small.en / large-v3-turbo × hotwords 유무 4조건으로 한정한다. Qwen3-ASR-0.6B는 EXP-ASR-002로 분리한다.
- 근거: 동일 런타임에서 변수를 통제하기 위해서다.
- 상태: 채택

## D-010 RAG 미도입
- 날짜: 2026-10-11
- 결정: 반복 오류 조회는 SQLite 질의로 처리한다. 임베딩·FAISS는 필요가 측정되면 도입한다.
- 상태: 채택

## D-011 장면 YAML 확장
- 날짜: 2026-10-11
- 결정: 설계 초안의 장면 구조에 다음을 추가했다.
  - `intents` (cancel/done/deny/confirm 표현), `off_menu_terms`, `guard.forbidden_patterns`, `menu.extra_shots.aliases`
  - 각 action에 `phase` (행동이 장면 단계를 결정)
  - 행동 추가: `ask_drink`, `ask_change`, `clarify`, `handle_unsupported_temperature`, `handle_unsupported_milk`, `acknowledge_cancel`, `end_unfinished`
  - 우유 선택지 `none`(no milk)
- 근거: 의도 표현과 금지 표현까지 YAML에 두어야 "장면 지식은 코드에 쓰지 않는다" 원칙이 지켜진다. 메뉴 제약(cold brew는 iced만, Americano는 우유 불가)을 행동으로 구분해야 템플릿과 LLM 지시가 정확해진다.
- 상태: 채택

## D-012 메뉴 외 품목 감지 방식
- 날짜: 2026-10-11
- 결정: 음료 별칭 바로 앞에 장면 어휘·불용어가 아닌 단어가 붙으면("pumpkin spice latte") 메뉴 외 품목으로 본다. `off_menu_terms`에 있는 단어도 메뉴 외 품목이다. 같은 로직을 출력 가드에서 재사용한다.
- 근거: 단계 1에는 LLM이 없으므로 규칙만으로 "없는 메뉴"를 판단해야 한다. 가드와 공유하면 NPC가 "maple latte"를 지어내는 것도 같은 기준으로 막힌다.
- 한계: 메뉴에 없는 일반 명사("something sweet")는 감지하지 못하고 clarify로 처리된다. 단계 2에서 LLM의 extracted 값으로 보완한다.
- 상태: 채택

## D-013 단계 1 응답은 템플릿만 사용
- 날짜: 2026-10-11
- 결정: `Responder` 인터페이스를 두고 단계 1은 `TemplateResponder`(YAML fallback 문장)만 구현한다. 장면 검사기는 모든 fallback 문장이 출력 가드를 통과하는지 CI에서 확인한다.
- 근거: 단계 2의 LLM 응답이 가드에 두 번 실패할 때 쓸 안전한 문장이 항상 존재해야 한다.
- 상태: 채택

## D-014 Vite 프록시는 127.0.0.1로 연결
- 날짜: 2026-10-11
- 결정: 개발 프록시 대상을 `localhost`가 아니라 `127.0.0.1:8000`으로 지정한다.
- 근거: Node 17 이상은 `localhost`를 IPv6(`::1`)로 먼저 연결하는데, uvicorn 기본 설정은 `127.0.0.1`만 열어 WebSocket 프록시가 ECONNREFUSED로 실패했다(스모크 테스트에서 발견).
- 상태: 채택

## D-015 LLM 보조 추출은 규칙이 아무것도 못 찾았을 때만
- 날짜: 2026-10-11
- 결정: NPC 응답 생성과 주문 정보 추출을 한 번의 LLM 호출로 합치려던 설계(design.md 3.1의 `{reply, extracted}`)를 나눴다. 평소에는 규칙 추출 + NPC 응답 1회만 호출한다. 규칙이 슬롯·의도·메뉴 외 품목을 하나도 찾지 못한 경우에만 LLM 추출을 한 번 더 호출한다. LLM이 준 값은 장면 별칭으로 다시 매핑해서 메뉴 id만 상태에 들어간다. 영문자가 없는 입력은 LLM에 보내지 않는다.
- 근거: Director는 응답을 만들기 전에 행동을 정해야 하므로, 응답과 같은 호출에서 받은 추출값은 다음 턴에야 쓸 수 있다. 대부분의 발화는 규칙으로 처리되므로 평균 호출 수는 턴당 1회 근처를 유지한다. D-012의 한계("something sweet")를 보완한다.
- 상태: 채택

## D-016 피드백의 과업 성공·빠진 정보는 Director 값
- 날짜: 2026-10-11
- 결정: Learning Evaluator는 LLM에게 문법·표현·추천 문장·복습 문장·요약만 요청한다. `task_success`와 `missed_information`은 Director 상태로 채운다. LLM이 고친 문장이 실제 사용자 발화를 인용하지 않으면 버린다. ASR 신뢰도가 낮은 단어를 건드리는 지적도 버린다. 짧은 구어체 답에 대한 지적도 버린다(EXP-FB-001). 버린 항목은 `dropped`에 남긴다.
- 근거: "모든 AI 결과를 스키마와 규칙으로 검증한다"는 원칙. 버린 항목을 남겨야 평가 때 원인을 추적할 수 있다.
- 상태: 채택

## D-017 학습 기록은 닉네임 기반 로컬 사용자
- 날짜: 2026-10-11
- 결정: MVP는 로그인 없이 닉네임으로 사용자를 구분한다(design.md 8절 열린 질문 3의 권장안). 사용자가 전사를 고치면 원래 인식 결과는 `asr_text`에 남기고, 피드백은 고친 문장으로 만든다.
- 상태: 채택

## D-018 실험 결과 파일은 Git에 포함
- 날짜: 2026-10-11
- 결정: `evals/results/*.json`은 커밋한다. 음성이나 개인정보가 없고, 개선 전후 비교의 근거이기 때문이다.
- 상태: 채택

## D-019 Windows 실행 환경 대응
- 날짜: 2026-10-11
- 결정:
  - PyAV DLL을 Windows 스마트 앱 컨트롤이 차단해서 faster-whisper import가 실패했다. PyAV는 파일 디코딩에만 쓰이고 우리는 PCM을 직접 넘기므로, PyAV를 불러올 수 없을 때는 빈 모듈로 대체한다(`app/ai/runtime.py`). 보안 정책은 바꾸지 않는다.
  - CUDA 12 라이브러리(cuBLAS, cuDNN, cudart, cuFFT, cuRAND)는 NVIDIA pip 패키지로 가상환경 안에만 설치하고, 실행 시 DLL 경로를 등록한다(`requirements-gpu.txt`). 시스템 CUDA 설치는 필요 없다.
  - onnxruntime-gpu 1.31은 CUDA 13용이라 CUDA 12용 1.22를 쓴다.
- 상태: 채택

## D-020 음성 모델 기본값
- 날짜: 2026-10-11
- 결정: STT는 faster-whisper `small.en`(GPU, `int8_float16`)에 문장 프롬프트, 토큰 제한 없음(EXP-ASR-001 조건 H). TTS는 Kokoro-82M ONNX(GPU). 서버를 시작할 때 세 모델(LLM, STT, TTS)을 미리 올린다.
- 근거: CPU에서는 STT가 3~7초, TTS가 2~5초 걸려 턴 예산 3초를 넘는다. GPU에서는 STT 0.24~0.35초, TTS 0.7~1.0초. VRAM은 Qwen3 포함 약 7.7GB / 8GB로 빠듯하다.
- 상태: 채택

## D-021 TTS 라이선스 주의 (GPL)
- 날짜: 2026-10-11
- 결정: kokoro-onnx(MIT)는 `phonemizer-fork`(GPL-3.0+)와 `espeakng-loader`(espeak-ng DLL, GPL-3.0)에 의존한다. 서버에서 실행만 하는 MVP에는 문제가 없지만, 백엔드를 묶어서 배포한다면 GPL 의무(소스 공개 등)가 생긴다. NVIDIA CUDA 라이브러리는 독점 라이선스라 함께 묶어 배포하지 않는다. 단계 4의 `docs/licenses.md`에서 대안(espeak-ng를 쓰지 않는 G2P)과 함께 정리한다.
- 상태: 채택 (단계 4에서 재검토)

## D-022 브라우저 VAD 자산은 직접 서빙, NPC가 말할 때는 마이크 일시정지
- 날짜: 2026-10-11
- 결정: `@ricky0123/vad-web` 0.0.30(Silero v5)의 모델·AudioWorklet·onnxruntime wasm을 빌드 전에 `public/vad/`로 복사해 직접 서빙한다(CDN 의존 없음, GitHub Pages에서도 동작). NPC 음성이 재생 중이거나 응답을 기다리는 동안에는 VAD를 일시정지해 NPC 목소리가 녹음되지 않게 한다.
- 상태: 채택

## D-023 가상환경 cuDNN을 ctranslate2와 같은 9.10으로 맞춤
- 날짜: 2026-10-11
- 결정: `requirements-gpu.txt`의 `nvidia-cudnn-cu12`를 9.1.0.70에서 9.10.2.21로 올린다.
- 근거: ctranslate2 4.8.2(faster-whisper)는 `cudnn64_9.dll`(9.10.2)만 자체 포함하고, 나머지 cuDNN 하위 DLL은 검색 경로에서 찾는다. 가상환경의 9.1 하위 DLL이 잡히면 `Could not load symbol cudnnGetLibConfig`로 프로세스가 종료됐다. 서버는 Kokoro(onnxruntime) 세션을 Whisper 첫 추론보다 먼저 만들기 때문에 서버에서만 재현됐고, `pytest -m model`은 통과했다. 9.10.2에서 서버 워밍업, 모델 테스트, Kokoro CUDA 실행을 모두 확인했다.
- 상태: 채택

## D-024 음성 모델을 불러오지 못하면 앱 대신 음성만 끈다
- 날짜: 2026-10-11
- 결정: STT/TTS 어댑터 생성이 `AdapterError`, `ImportError`, `OSError`로 실패하면 경고를 남기고 `None`으로 둔다. TTS가 없으면 NPC는 텍스트로만 답하고, STT가 없으면 사용자는 타이핑한다.
- 근거: Kokoro 모델 파일이 없으면 서버가 아예 시작하지 못했다. 설계의 "TTS를 꺼도 대화 지속"을 시작 시점까지 확장한다.
- 상태: 채택

## D-025 NPC 대사 검증 보강
- 날짜: 2026-10-11
- 결정: (1) 주문을 다시 말하는 대사(`confirm_order`, `close`)가 Director 상태와 다르면 거부한다. (2) 장면 금지 패턴에 역할 혼동("can I get a …")을 추가한다. (3) 재생성 요청은 위반별로 고칠 점을 구체적으로 주고 temperature를 0.6에서 0.9로 올린다. 평가 결과에 거부된 첫 대사도 남긴다.
- 근거: 같은 단계 2를 따로 구현해 본 별도 실험(로컬 브랜치)의 측정에서, 막연한 재생성 요청에는 모델이 같은 문장을 그대로 돌려줬고, 바리스타가 손님처럼 주문하는 대사가 가드를 통과했다. 이식 후 재측정에서 주문 복창 검사가 실제 오류("medium iced Americano with oat milk" — 우유를 뺀 주문)를 잡았다.
- 상태: 채택

## D-026 개발 서버에서 VAD 자산을 정적 파일로 서빙
- 날짜: 2026-10-11
- 결정: D-022를 보완해, Vite 개발 서버 플러그인이 `/vad/*`를 모듈 변환 없이 그대로 서빙한다.
- 근거: onnxruntime-web은 `/vad/ort-wasm-simd-threaded.mjs`를 동적 `import()`로 불러오는데, Vite 개발 서버는 `public/` 파일의 모듈 import를 500으로 거부해 `npm run dev`에서만 마이크가 동작하지 않았다(빌드 결과물은 정상). Chrome 가짜 마이크 테스트에서 발견했다.
- 상태: 채택


## D-027 정렬기는 WhisperX·torch 대신 wav2vec2 ONNX + 직접 구현한 CTC 강제 정렬
- 날짜: 2026-10-11
- 결정: 대화 후 단어 정렬은 `facebook/wav2vec2-base-960h`의 ONNX 변환(Xenova, 리비전 고정)을 onnxruntime으로 돌리고, CTC 강제 정렬(torchaudio `forced_align`과 같은 비터비 알고리즘)은 numpy로 구현한다(`app/ai/alignment/ctc.py`). 기본 실행 장치는 CPU다. 정렬이 실패하면 Whisper 단어 타임스탬프로 대신한다.
- 근거: WhisperX나 torchaudio를 쓰려면 torch(CUDA 포함 약 2.5GB)를 추가로 설치해야 한다. onnxruntime은 Kokoro 때문에 이미 설치돼 있다. 정렬은 세션이 끝난 뒤에만 돌아서 CPU로 충분하다(합성 음성 3.7초 문장 기준 약 0.2초). GPU는 실시간 모델(Qwen3, Whisper, Kokoro)이 이미 VRAM 7.7GB를 쓰고 있어 비워 둔다. 1.2~1.5초 무음을 끼워 넣은 합성 음성에서 멈춤 위치와 길이를 정확히 찾았다(`pytest -m model`).
- 한계: 영어 문자 단위 모델이라 숫자는 단어로 바꿔 정렬하고, 기호만 있는 단어는 건너뛴다. 한국인 발화에서의 정렬 정확도는 아직 측정하지 않았다.
- 상태: 채택

## D-028 무음과 Whisper 환각을 서버에서도 거른다
- 날짜: 2026-10-11
- 결정: 음성 크기가 -55 dBFS보다 작으면 인식기에 보내지 않고 `no_speech`로 답한다. 인식 결과가 "you", "thank you" 같은 흔한 환각 문장이면서 평균 단어 신뢰도가 0.5 미만이면 버린다.
- 근거: 단계 3 남은 문제. 브라우저 VAD가 무음을 거르지만, 다른 클라이언트나 VAD 오작동에서 무음이 들어오면 Whisper가 "You"를 만들어 내고 대화 턴으로 처리됐다.
- 상태: 채택

## D-029 Kokoro TTS의 espeak-ng(GPL-3.0) 의존성
- 날짜: 2026-10-11
- 확인: kokoro-onnx 0.4.7은 텍스트를 발음기호로 바꿀 때 `phonemizer-fork` 3.3.1(GPL-3.0-or-later)을 import하고, `espeakng-loader` 0.2.4가 동봉한 espeak-ng DLL(GPL-3.0-or-later)을 같은 프로세스에서 불러온다(`kokoro_onnx/tokenizer.py`). 설계 위험 7번이 실제로 해당된다.
- 영향: 저장소와 GitHub Pages 빌드에는 이 파일들이 들어가지 않는다. 사용자가 직접 설치하고, 서버로 서비스만 하는 경우 GPL-3.0(AGPL 아님)의 소스 공개 의무는 생기지 않는다. 그러나 `.venv`나 Docker 이미지처럼 espeak-ng가 들어간 설치본을 배포하면 GPL 조건을 따라야 한다. 같은 프로세스에서 import하므로 앱 전체가 GPL과 호환돼야 한다는 해석도 있다.
- 결정: MVP는 현 구성을 유지한다. TTS는 어댑터 뒤에 있고 선택 설치(`requirements-ai.txt`)이며, 없어도 앱이 동작한다(D-024). `docs/licenses.md`와 `THIRD_PARTY_NOTICES.md`에 명시한다.
- 배포 전 대안: (1) TTS를 별도 프로세스(HTTP 서비스)로 분리해 GPL 구성요소와 앱을 독립 프로그램으로 둔다. (2) espeak-ng 없이 사전 기반 G2P(예: misaki의 영어 사전, Apache-2.0)만 쓰고 사전에 없는 단어는 철자 규칙으로 처리한다. 장면 어휘가 정해져 있어 가능성이 높다. (3) 저장소를 GPL-3.0으로 공개한다. 저장소 라이선스를 정할 때 함께 결정한다.
- 상태: 확인 완료, 배포 형태 결정 시 재검토

## D-030 월드 NPC는 "미션 대화"(talk) 장면으로, 진행 판정은 규칙이
- 날짜: 2026-10-11
- 결정: 단계 5(뉴욕 도트 월드)에서 카페 외 NPC는 `scenes/talks/*.yaml`의 미션 대화 형식을 쓴다. 장면 파일에 사용자가 해낼 단계(정규식으로 판정), NPC가 말해도 되는 사실, 단계별 템플릿 대사, 종료 대사를 적는다. 모든 단계를 해내면 성공, 작별 인사나 턴 제한이면 미완료다. NPC 대사는 LLM이 만들되 문장 수, 금지 표현, 사실에 없는 가격, 종료 후 질문을 가드가 검사하고, 1회 재생성 후 템플릿으로 대체한다. 카페는 기존 Scene Director를 그대로 쓴다.
- 근거: 길 묻기, 체크인, 지하철 문의는 슬롯 채우기보다 "할 일 체크리스트"에 가깝다. Director를 장면마다 새로 짜지 않고 데이터만으로 장면을 늘릴 수 있다. 판정을 LLM에 맡기지 않는다는 기존 원칙(P4)을 유지해 결정적으로 테스트할 수 있다(`tests/test_talk.py`의 장면별 모범 대화). 맵과 캐릭터는 이미지 파일 없이 코드로 그려 라이선스 문제가 없다.
- 한계: 정규식 판정이라 표현이 다양하면 단계를 놓칠 수 있다. 카페의 LLM 보조 추출 같은 장치는 아직 없다. 미션 대화의 NPC 품질은 아직 `run_dialogue.py`로 측정하지 않는다.
- 상태: 채택

## D-031 옵션 제안에 "네"만 답하면 무엇을 원하는지 되묻는다
- 날짜: 2026-10-11
- 결정: "우유나 샷 추가 하실래요?"에 슬롯 없이 "Yeah, sure."만 답하면 `ask_which_option`으로 되묻는다. "It is everything." 같은 종료 표현도 장면 의도에 추가했다.
- 근거: 사용자 실제 음성 테스트에서 "Extra shot?"에 "Yeah, sure"라고 답했는데 샷이 추가되지 않고, 같은 확인 질문을 두 번 받았다. 회귀 케이스 `yes-to-options-asks-which`를 추가했다.
- 상태: 채택
