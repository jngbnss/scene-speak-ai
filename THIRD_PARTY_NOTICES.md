# Third-Party Notices

SceneSpeak AI uses the open-source software and models listed below. This repository does
not contain their files: Python and npm packages are installed by the user, and models are
downloaded at setup or first use. The GitHub Pages build includes the frontend packages
marked **(bundled)**. Versions and license checks: [docs/licenses.md](docs/licenses.md).

Each component is the property of its respective authors and is used under its own license.
Full license texts are included with each package (`site-packages/*.dist-info`,
`node_modules/*/LICENSE`) and at the URLs below.

## Models

| Component | License | Source |
|---|---|---|
| Qwen3-8B (via Ollama `qwen3:8b`) | Apache-2.0 | https://huggingface.co/Qwen/Qwen3-8B |
| Whisper small.en, CTranslate2 conversion | MIT | https://github.com/openai/whisper · https://huggingface.co/Systran/faster-whisper-small.en |
| Kokoro-82M v1.0 (ONNX) | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M · https://github.com/thewh1teagle/kokoro-onnx |
| wav2vec2-base-960h (ONNX export) | Apache-2.0 | https://huggingface.co/facebook/wav2vec2-base-960h · https://huggingface.co/Xenova/wav2vec2-base-960h |
| Silero VAD v5 **(bundled)** | MIT | https://github.com/snakers4/silero-vad |

## Frontend (npm)

| Component | License | Source |
|---|---|---|
| React, React DOM, scheduler **(bundled)** | MIT, Copyright (c) Meta Platforms, Inc. and affiliates | https://github.com/facebook/react |
| @ricky0123/vad-web **(bundled)** | ISC | https://github.com/ricky0123/vad |
| three.js **(bundled)** | MIT, Copyright © 2010-2024 three.js authors | https://github.com/mrdoob/three.js |
| onnxruntime-web, onnxruntime-common **(bundled)** | MIT, Copyright (c) Microsoft Corporation | https://github.com/microsoft/onnxruntime |
| protobufjs **(bundled)** | BSD-3-Clause | https://github.com/protobufjs/protobuf.js |
| flatbuffers **(bundled)** | Apache-2.0 | https://github.com/google/flatbuffers |
| long **(bundled)** | Apache-2.0 | https://github.com/dcodeIO/long.js |
| guid-typescript **(bundled)** | ISC | https://github.com/NicolasDeveloper/guid-typescript |
| platform **(bundled)** | MIT | https://github.com/bestiejs/platform.js |
| Vite, TypeScript, Vitest (build tools only) | MIT / Apache-2.0 | https://vitejs.dev · https://www.typescriptlang.org · https://vitest.dev |

## Backend (Python)

| Component | License | Source |
|---|---|---|
| FastAPI | MIT | https://github.com/fastapi/fastapi |
| Starlette | BSD-3-Clause | https://github.com/encode/starlette |
| Uvicorn, websockets, httpx | BSD-3-Clause | https://github.com/encode/uvicorn · https://github.com/python-websockets/websockets · https://github.com/encode/httpx |
| Pydantic, pydantic-settings | MIT | https://github.com/pydantic/pydantic |
| SQLAlchemy | MIT | https://github.com/sqlalchemy/sqlalchemy |
| PyYAML, jsonschema | MIT | https://github.com/yaml/pyyaml · https://github.com/python-jsonschema/jsonschema |
| NumPy | BSD-3-Clause | https://github.com/numpy/numpy |
| faster-whisper | MIT | https://github.com/SYSTRAN/faster-whisper |
| CTranslate2 | MIT | https://github.com/OpenNMT/CTranslate2 |
| ONNX Runtime (onnxruntime-gpu) | MIT | https://github.com/microsoft/onnxruntime |
| kokoro-onnx | MIT | https://github.com/thewh1teagle/kokoro-onnx |
| tokenizers, huggingface-hub | Apache-2.0 | https://github.com/huggingface |
| PyAV (includes FFmpeg libraries, LGPL) | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| **phonemizer-fork** | **GPL-3.0-or-later** | https://github.com/thewh1teagle/phonemizer-fork |
| **espeakng-loader (bundles eSpeak NG)** | **eSpeak NG: GPL-3.0-or-later** | https://github.com/thewh1teagle/espeakng-loader · https://github.com/espeak-ng/espeak-ng |
| NVIDIA CUDA runtime, cuBLAS, cuDNN, cuFFT, cuRAND (pip wheels) | NVIDIA proprietary license | https://docs.nvidia.com/cuda/eula/ · https://docs.nvidia.com/deeplearning/cudnn/latest/reference/eula.html |

### GPL components

eSpeak NG and phonemizer are licensed under the GNU General Public License v3.0 or later.
They are loaded at runtime by kokoro-onnx to convert text to phonemes for speech synthesis.
They are not included in this repository or in the GitHub Pages build. Anyone who
redistributes an installation that contains them (for example a Docker image or a packaged
virtual environment) must comply with the GPL, including providing the corresponding
source code. See decision D-029 in [docs/decision-log.md](docs/decision-log.md).

## External programs

| Component | License | Source |
|---|---|---|
| Ollama | MIT | https://github.com/ollama/ollama |
