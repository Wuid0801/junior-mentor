# junior-mentor

주니어 개발자가 Claude Code·Codex를 어떻게 쓰고 있는지 로컬 사용 기록으로 분석해, HTML 보고서 한 장으로 피드백하는 에이전트 스킬입니다.
An agent skill that reads your local Claude Code and Codex session logs and gives a junior developer feedback on how they work with AI agents, as one HTML report.

아이디어 참고 / Idea credit: [smixs/mentor](https://github.com/smixs/mentor) (코드는 사용하지 않음 / no code reused)

## 보고서 / Report

| 섹션 / Section | 내용 / Content |
|---|---|
| 일하는 방식 / How you work | 주제별 묶음, 사용한 도구·언어, 습관 / themes, tools, languages, habits |
| 잘하고 있는 점 / Going well | 근거가 있는 강점 / strengths with evidence |
| 반복되는 문제 / Problems that keep coming back | 최대 3개: 근거, 왜 문제인가, 다음엔 이렇게, 관련 개념 / up to 3: evidence, why, next time, concept |
| 이번 주에 해볼 것 / Try this week | 최대 3개 / up to 3 |

문제 신호 / Problem signals: 도구 실패(MCP·브라우저 도구 제외), 같은 오류 3회 이상, 한 세션에서 같은 파일 5회 이상 수정, 수정 요청·중단 횟수 / failed tool calls (MCP and browser tools excluded), the same error 3+ times, the same file edited 5+ times in one session, correction prompts and interrupts.

## 설치 / Install

[`uv`](https://github.com/astral-sh/uv)가 필요합니다 / Requires `uv`.

- Claude Code: `SKILL.md`, `scripts/`, `references/`, `locales/`를 `~/.claude/skills/junior-mentor/`에 복사 / copy them to `~/.claude/skills/junior-mentor/`
- Codex: 같은 파일을 `~/.agents/skills/junior-mentor/`에 복사 (인식 위치는 확인 중) / copy to `~/.agents/skills/junior-mentor/` (location still being verified)

## 사용 / Use

```
내 AI 코딩 습관 분석해줘
/junior-mentor            # 두 에이전트, 최근 30일 / both agents, last 30 days
/junior-mentor codex 14   # Codex만, 최근 14일 / Codex only, last 14 days
```

보고서는 `~/.claude/usage-data/junior-mentor-report.html`에 저장되고 매번 덮어씁니다. 세션이 5개 미만이면 숫자만 보여 줍니다.
The report is written to `~/.claude/usage-data/junior-mentor-report.html` and replaced on every run. With fewer than 5 sessions it shows numbers only.

## 개인정보 / Privacy

- 스크립트는 로컬 로그를 읽기만 하고 네트워크를 쓰지 않습니다. 보고서는 외부 리소스·JS가 없는 HTML 한 파일입니다.
- 키·토큰·이메일·홈 경로는 기록·출력 전에 가립니다. 패턴 기반이라 완벽하지 않습니다.
- 분석 단계에서는 스킬을 실행하는 에이전트의 모델이 가려진 요약을 읽습니다.
- The scripts only read local logs and make no network calls; the report is a single HTML file with no external resources or JavaScript.
- Keys, tokens, emails and home paths are masked before anything is written or printed. Masking is pattern-based and not perfect.
- In the analysis step, the model of the agent running the skill reads the masked digest.

## 개발 / Development

```bash
uv run --no-project python -m unittest discover -s tests -v
```

## 라이선스 / License

아직 정하지 않았습니다 / Not decided yet.
