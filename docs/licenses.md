# 오픈소스·모델 라이선스

2026-10-11에 개발 PC(Windows 11)의 실제 설치본에서 버전과 라이선스 표기를 확인해 작성했다. 패키지 버전은 `pip list`, `package-lock.json`, Ollama `api/tags`, Hugging Face 캐시 리비전에서 가져왔다. 고지문은 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)에 있다.

> 이 저장소 자체의 라이선스(LICENSE 파일)는 아직 정하지 않았다. 아래 GPL 항목 때문에 배포 형태를 정할 때 함께 결정해야 한다(D-029).

## 요약

| 구분 | 결론 |
|---|---|
| 저장소에 포함된 서드파티 코드·모델 | **없음.** 모델 파일, 음성, `node_modules`, `.venv`는 모두 Git에서 제외된다. |
| GitHub Pages 배포물(프론트 빌드) | React(MIT), onnxruntime-web(MIT), vad-web(ISC), Silero VAD 모델(MIT)이 들어간다. 모두 고지만 하면 된다. |
| 주의가 필요한 것 | **espeak-ng와 phonemizer(GPL-3.0+)**: Kokoro TTS가 실행 중에 불러온다(D-029). **NVIDIA CUDA/cuDNN 휠**: 독점 라이선스라 재배포 조건이 따로 있다. |
| 학습 데이터 | 이 프로젝트는 모델을 학습하지 않는다. 평가용 음성은 Kokoro로 직접 합성하고(제3자 녹음 없음), Git에 올리지 않는다. |

## 모델

| 모델 | 버전 / 리비전 | 라이선스 | 용도 | 받는 곳 | 수정 |
|---|---|---|---|---|---|
| Qwen3-8B (Ollama `qwen3:8b`, Q4_K_M) | digest `500a1f067a9f` | Apache-2.0 | NPC 대사, 피드백 생성, 보조 슬롯 추출 | `ollama pull qwen3:8b` | 없음 |
| Whisper small.en (CTranslate2 변환: Systran/faster-whisper-small.en) | `d1d751a5f827` | MIT (OpenAI 가중치, Systran 변환) | 음성 인식 | 첫 실행 시 Hugging Face에서 자동 다운로드 | 없음 |
| Kokoro-82M v1.0 (ONNX, `kokoro-v1.0.onnx`, `voices-v1.0.bin`) | kokoro-onnx 릴리스 `model-files-v1.0` | Apache-2.0 | NPC 음성 합성 | README의 curl 명령 | 없음 |
| wav2vec2-base-960h (ONNX 변환: Xenova/wav2vec2-base-960h) | `a19f851b3d42` | Apache-2.0 (원본 facebook/wav2vec2-base-960h) | 대화 후 단어 정렬(멈춤 구간) | 첫 사용 시 Hugging Face에서 자동 다운로드 | 없음 |
| Silero VAD v5 (`silero_vad_v5.onnx`, vad-web 포함) | vad-web 0.0.30 동봉 | MIT | 브라우저 발화 구간 검출 | npm 패키지에서 `public/vad/`로 복사 | 없음 |

- 학습 데이터 라이선스(LibriSpeech CC BY 4.0 등)는 모델 제공자가 고지할 몫이다. 이 프로젝트는 데이터를 재배포하지 않는다.
- 가중치를 바꾸거나 다시 학습하지 않았다. 모델 파일은 Git에 올리지 않고 사용자가 직접 받는다.

## 백엔드 Python 패키지

필수(`requirements.txt`, CI에서도 설치)

| 패키지 | 버전 | 라이선스 | 용도 |
|---|---|---|---|
| FastAPI | 0.115.6 | MIT | REST·WebSocket 서버 |
| Starlette | 0.41.3 | BSD-3-Clause | FastAPI 기반 |
| Uvicorn (+websockets 17.2) | 0.32.1 | BSD-3-Clause | ASGI 서버 |
| Pydantic / pydantic-settings | 2.10.3 / 2.6.1 | MIT | 메시지·설정 검증 |
| SQLAlchemy | 2.0.36 | MIT | 학습 기록(SQLite) |
| PyYAML | 6.0.2 | MIT | 장면 YAML |
| jsonschema | 4.23.0 | MIT | 장면·응답 스키마 검사 |
| httpx | 0.28.1 | BSD-3-Clause | Ollama 호출 |
| NumPy | 2.5.4 | BSD-3-Clause 외 | 오디오 처리, CTC 정렬 |
| pytest / Ruff (개발용) | 8.3.4 / 0.8.4 | MIT | 테스트·린트 |

음성(`requirements-ai.txt`, `requirements-gpu.txt`, 선택 설치)

| 패키지 | 버전 | 라이선스 | 용도 | 주의 |
|---|---|---|---|---|
| faster-whisper | 1.1.0 | MIT | Whisper 실행 | |
| CTranslate2 | 4.8.2 | MIT | Whisper 추론 엔진 | |
| tokenizers / huggingface-hub | 0.23.3 / 2.2.0 | Apache-2.0 | 토크나이저, 모델 다운로드 | |
| PyAV | 19.0.1 | BSD-3-Clause | faster-whisper 의존성(파일 디코딩, 이 앱은 사용 안 함) | 휠에 FFmpeg(LGPL) 포함 |
| onnxruntime-gpu | 1.22.0 | MIT | Kokoro, wav2vec2 실행 | |
| kokoro-onnx | 0.4.7 | MIT | Kokoro 실행 래퍼 | GPL 의존성 2개 ↓ |
| **phonemizer-fork** | 3.3.1 | **GPL-3.0-or-later** | Kokoro의 텍스트→발음기호(G2P) | D-029 |
| **espeakng-loader** | 0.2.4 | 패키지 표기 없음, 포함된 **espeak-ng 라이브러리·데이터는 GPL-3.0-or-later** | phonemizer가 쓰는 espeak-ng DLL 동봉 | D-029 |
| NVIDIA CUDA runtime / cuBLAS / cuDNN / cuFFT / cuRAND 휠 | 12.4 / 9.10.2 | NVIDIA 독점 라이선스 | GPU 실행 | 재배포 시 NVIDIA 조건 확인 |

간접 의존성(colorlog, segments, dlinfo, joblib, tqdm, protobuf, sympy, coloredlogs, flatbuffers, attrs 등)은 모두 MIT, BSD, Apache-2.0, MPL-2.0 계열이다.

## 프론트엔드 npm 패키지 (빌드 결과에 포함)

| 패키지 | 버전 | 라이선스 | 용도 |
|---|---|---|---|
| react / react-dom / scheduler | 18.3.1 / 18.3.1 / 0.23.2 | MIT | UI |
| @ricky0123/vad-web | 0.0.30 | ISC | 브라우저 VAD |
| onnxruntime-web / onnxruntime-common | 1.30.0 | MIT | VAD 모델 실행(wasm) |
| protobufjs, @protobufjs/* | 7.6.6 | BSD-3-Clause | onnxruntime-web 의존성 |
| flatbuffers, long | 25.9.23, 5.3.2 | Apache-2.0 | onnxruntime-web 의존성 |
| guid-typescript, platform | 1.0.9, 1.3.6 | ISC, MIT | onnxruntime-web 의존성 |

개발 도구(Vite 5.4.11, TypeScript 5.6.3, Vitest 2.1.8, @vitejs/plugin-react 4.3.4)는 MIT이고 빌드 결과에는 들어가지 않는다.

## 외부 프로그램

| 프로그램 | 라이선스 | 비고 |
|---|---|---|
| Ollama | MIT | 사용자가 별도 설치. 저장소에 포함하지 않음 |
| Node.js, Python | MIT 계열, PSF | 실행 환경 |

## 배포 형태별 준수 사항

| 배포 형태 | 해야 할 일 |
|---|---|
| 소스 저장소 공개 (현재) | 서드파티 파일을 포함하지 않으므로 이 문서와 THIRD_PARTY_NOTICES.md 유지로 충분하다. |
| GitHub Pages (프론트 빌드) | 빌드에 들어가는 MIT/ISC/BSD/Apache 고지를 THIRD_PARTY_NOTICES.md로 제공한다. Apache-2.0 패키지는 NOTICE 파일이 있으면 함께 고지한다. |
| 서버로 서비스 운영 (설치본을 나눠 주지 않음) | GPL-3.0은 네트워크 이용을 배포로 보지 않으므로(AGPL과 다름) 소스 공개 의무는 생기지 않는다. 고지는 유지한다. |
| 설치본·Docker 이미지로 배포 (`.venv`, espeak-ng 포함) | espeak-ng·phonemizer의 GPL-3.0 조건을 따라야 한다: 해당 소스 제공, 라이선스 전문 동봉. phonemizer를 같은 프로세스에서 import하므로 앱 전체가 GPL과 호환되는 라이선스여야 한다는 해석이 있다. 대안은 D-029. NVIDIA 휠은 NVIDIA 재배포 조건을 따른다. |
| 모델 파일 재배포 | Apache-2.0(Qwen3, Kokoro, wav2vec2)은 라이선스 사본과 NOTICE를 함께 배포하고 수정 여부를 표시한다. MIT(Whisper, Silero)는 저작권 고지를 포함한다. |

## 다시 확인하는 방법

```powershell
cd backend
.venv\Scripts\python.exe -m pip list --format=freeze
.venv\Scripts\python.exe -c "import importlib.metadata as m; print(m.metadata('phonemizer-fork')['License'][:40])"
cd ..\frontend
npm ls --omit=dev --all
```

패키지를 추가하거나 버전을 올리면 이 표와 THIRD_PARTY_NOTICES.md를 함께 고친다.
