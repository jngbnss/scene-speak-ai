# 평가 데이터

| 파일 | 내용 | 사용처 |
|---|---|---|
| `dialogue-cases.jsonl` | Scene Director 대화 케이스 | `backend/tests/test_director.py` (CI) |
| `feedback-cases.jsonl` | 피드백 정답 라벨 | `score_feedback.py` |
| `asr/` | 합성 음성 생성, 음성인식 측정 | `make_synthetic.py`, `run_asr.py` |
| `audio/` | 음성 녹음 (Git 제외) | 음성인식 실험 |
| `results/` | 측정 결과 JSON (커밋함, D-018) | `compare.py`, 화면의 평가 리포트 |

## 평가 하네스 (`run.py`, `compare.py`)

대화 품질, 피드백 정확도, 음성인식을 한 번에 또는 골라서 측정합니다. 결과 파일 `results/{시각}-suite-{라벨}.json`에는 다음이 들어갑니다.

- 모델 이름과 설정(LLM provider, Whisper 모델, 문맥 힌트 방식)
- git 커밋, 커밋하지 않은 변경 여부(`git_dirty`)
- 평탄화한 지표(`dialogue.scene_deviation_rate`, `asr.wer` 등)와 지표별 방향(낮을수록 좋음 / 높을수록 좋음)
- 섹션별 상세 결과

```powershell
cd backend
.venv\Scripts\python.exe ..\evals\run.py --label baseline
.venv\Scripts\python.exe ..\evals\run.py --label plain --asr-context none --note "힌트 없음"
.venv\Scripts\python.exe ..\evals\run.py --label dlg --only dialogue feedback
.venv\Scripts\python.exe ..\evals\compare.py results\A.json results\B.json [--markdown]
```

`compare.py`는 예전 단일 결과 파일(`*-dialogue-*`, `*-feedback-*`, `*-asr-*`)도 읽습니다. 같은 비교를 웹의 **평가 리포트** 탭(`#/report`)에서 표와 막대로 볼 수 있습니다.

## dialogue-cases.jsonl 형식

한 줄에 케이스 하나입니다.

```json
{
  "id": "cold-brew-hot-then-iced",
  "description": "사람이 읽을 설명",
  "scene": "new-york-cafe",
  "turns": [
    { "user": "Then cold brew, medium, hot please.",
      "expect": { "action": "handle_unsupported_temperature", "phase": "clarifying",
                  "slots": { "temperature": null }, "item": "..." } }
  ],
  "final": { "phase": "completed", "success": true }
}
```

- `expect`의 모든 필드는 선택입니다. 적은 것만 검사합니다.
- `slots`는 부분 일치입니다. `null`은 "비어 있어야 함"을 뜻합니다.
- 테스트는 Director가 낼 수 있는 모든 행동이 케이스 어딘가에 한 번 이상 나오는지도 확인합니다.

단계 2부터는 같은 파일을 실제 LLM으로 돌려 장면 이탈률과 메뉴 환각률을 측정합니다.

## 대화 품질 측정 (`run_dialogue.py`)

`dialogue-cases.jsonl`을 실제 LLM NPC로 실행해 다음을 잽니다. 결과는 `evals/results/`에 JSON으로 저장됩니다.

| 지표 | 뜻 |
|---|---|
| scene_deviation_rate | LLM의 첫 응답이 출력 가드에 걸린 비율 (장면 이탈) |
| menu_hallucination_rate | 첫 응답에 메뉴에 없는 품목이 나온 비율 |
| retry_rate / template_fallback_rate | 재생성 / 템플릿 대체 비율 |
| final_guard_pass_rate | 사용자에게 나간 최종 응답이 가드를 통과한 비율 (항상 1.0이어야 함) |
| action_accuracy | Director가 기대한 행동을 고른 비율 |
| latency_ms_* | NPC 응답 하나당 LLM 시간 (재생성 포함) |

```powershell
cd backend
.venv\Scripts\python.exe ..\evals\run_dialogue.py --provider ollama --label baseline
```

## 피드백 정확도 측정 (`feedback-cases.jsonl`, `score_feedback.py`)

사람이 정답을 단 대화로 Learning Evaluator의 문법 오류 탐지를 채점합니다. 지금은 10개이고 목표는 50개입니다.

```json
{"id": "fb-11", "lines": ["고객 발화 1", "고객 발화 2"], "gold": [{"original": "틀린 발화 원문", "type": "article"}], "note": "판단 근거"}
```

### 라벨링 가이드 (나머지 40개 작성 시)

1. `lines`에는 카페 주문 상황의 **고객 발화만** 순서대로 적습니다. 실제 한국인 학습자가 할 법한 실수를 넣으세요.
2. `gold`에는 **명백한 문법 오류**가 있는 발화만 적습니다. `original`은 해당 발화를 그대로 복사합니다. 한 발화에 오류가 여러 개여도 한 번만 적습니다(채점은 발화 단위).
3. 짧은 구어체("Large, please.", "Hot.", "Yes.")는 오류가 아닙니다.
4. 문법은 맞지만 어색한 표현("Give me…", "It is large.")은 `gold`에 넣지 않고 `note`에 적습니다. 이번 지표는 문법 오류만 셉니다.
5. 오류가 없는 대화도 전체의 30% 정도 넣으세요. 잘못된 지적(false feedback)을 재는 데 필요합니다.
6. `type`은 `article`, `plural`, `verb_form`, `subject_verb_agreement`, `word_order`, `preposition`, `tense` 중에서 고릅니다.
7. 가능하면 20%는 두 사람이 따로 라벨링해 일치도를 확인합니다.

```powershell
cd backend
.venv\Scripts\python.exe ..\evals\score_feedback.py --provider ollama --label baseline
```

지표: precision, recall, F1(발화 단위), false_feedback_rate(지적 중 틀린 비율), clean_cases_flagged(오류 없는 대화에 지적이 나온 수).
