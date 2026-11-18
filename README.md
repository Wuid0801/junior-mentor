# junior-mentor

Claude Code·Codex 사용 기록을 읽어, 주니어 개발자가 AI 에이전트와 어떻게 일하는지 HTML 보고서 한 장으로 알려 주는 에이전트 스킬입니다.

An agent skill that turns your local Claude Code and Codex logs into a one-page HTML report on how you work with AI agents.

## 보고서 내용

- **일하는 방식**: 주제별 작업, 자주 쓰는 도구·언어, 습관
- **잘하고 있는 점**
- **반복되는 문제** (최대 3개): 근거, 왜 문제인가, 다음엔 이렇게, 관련 개념
- **이번 주에 해볼 것** (최대 3개)

반복되는 문제는 같은 오류 3회 이상, 한 세션에서 같은 파일 5회 이상 수정, 수정 요청·중단, 권한 거부 같은 신호로 찾습니다.

## 설치

[uv](https://github.com/astral-sh/uv)가 필요합니다.

```bash
git clone https://github.com/Wuid0801/junior-mentor.git ~/.claude/skills/junior-mentor
```

Codex는 `~/.agents/skills/junior-mentor`에 같은 방법으로 설치합니다 (Codex 인식 위치는 확인 중).

## 사용

```
내 AI 코딩 습관 분석해줘
/junior-mentor              # Claude Code + Codex, 최근 30일
/junior-mentor codex 14     # Codex만, 최근 14일
```

보고서는 `~/.claude/usage-data/junior-mentor-report.html`에 저장되고 실행할 때마다 덮어씁니다. 세션이 5개 미만이면 숫자만 보여 줍니다.

## 개인정보

- 로컬 로그를 읽기만 하고 네트워크를 쓰지 않습니다.
- 키·토큰·이메일·홈 경로는 저장·출력 전에 가립니다. 패턴 기반이라 완벽하지는 않습니다.
- 분석 단계에서는 스킬을 실행한 에이전트의 모델이 가려진 요약을 읽습니다.

## 구조

```
SKILL.md                  스킬 정의와 실행 순서
scripts/logs.py           로그 읽기·마스킹
scripts/collect.py        기간 필터·집계 → stats.json + 요약
scripts/render_report.py  보고서 HTML
references/rubric.md      피드백 기준
locales/                  한국어·영어 문구
tests/                    unittest
```

## 개발

```bash
uv run --no-project python -m unittest discover -s tests
```

## 참고

- 아이디어 참고: [smixs/mentor](https://github.com/smixs/mentor) (코드는 사용하지 않음)
- 라이선스: 아직 정하지 않음
