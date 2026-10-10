# 평가 데이터

| 파일 | 내용 | 사용처 |
|---|---|---|
| `dialogue-cases.jsonl` | Scene Director 대화 케이스 | `backend/tests/test_director.py` (CI) |
| `audio/` | 음성 녹음 (Git 제외) | 단계 3 음성인식 실험 |

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
