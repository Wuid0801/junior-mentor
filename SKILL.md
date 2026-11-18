---
name: junior-mentor
description: >
  Reads the user's local Claude Code and Codex session logs and writes one HTML report for a
  junior developer: how they work, what goes well, up to 3 recurring problems (repeated errors,
  same-file churn, frequent corrections) each with a next step and the concept behind it, and
  tips. Use for "내 AI 코딩 습관 분석해줘", "클로드 코드·코덱스 사용 패턴 봐줘", "review how I
  use Claude Code", "analyze my agent sessions", or /junior-mentor [claude|codex|both] [days].
  Not for code review.
---

# junior-mentor

Feedback for a junior developer on how they work with AI coding agents, built from their own
local session logs.

## What you hand over
One HTML file. Your analysis goes into `junior-mentor-analysis.json`; the renderer turns it into
the report. The chat gets at most two lines. If the scripts cannot run, say why — do not write the
analysis into the chat instead.

## Paths
`<skill-dir>` means the folder that contains this file. Use its absolute path in double quotes.
Do not assume `~/.claude/skills/...`: Codex keeps skills elsewhere, and Windows home folders can
contain spaces and non-ASCII characters.

## Steps

1. **Collect.**
   ```bash
   uv run --no-project python "<skill-dir>/scripts/collect.py" --agent <claude|codex|both> --days <N>
   ```
   Defaults are `--agent both --days 30`; `/junior-mentor codex 14` means `--agent codex --days 14`.
   It prints a digest and ends with `[stats: <stats-path> — N sessions]`. The digest is the only
   evidence you may use. If it starts with `NOT ENOUGH DATA`, skip step 2.

2. **Write the analysis.** Read `<skill-dir>/references/rubric.md`, then write
   `junior-mentor-analysis.json` in the same folder as `<stats-path>`:
   ```json
   {"lang": "ko", "period": "최근 30일", "summary": "...",
    "sections": {
      "patterns":  {"topics": [{"topic": "...", "detail": "...", "share": "~40%"}], "habits": ["..."]},
      "strengths": ["..."],
      "problems":  [{"problem": "...", "evidence": "...", "why": "...", "fix": "...",
                     "concept": {"name": "...", "explain": "..."}}],
      "tips":      ["..."]}}
   ```
   - `lang` is the language the user wrote in: `ko` or `en`, otherwise `en`. Write every sentence in it.
   - `problems`: at most 3, each tied to a line of the digest. `tips`: at most 3.
   - `summary`: a few honest sentences, including what holds them back.
   - Quote the user's prompts only inside `evidence`, at most 120 characters each.
   - Write the file with your file-writing tool as UTF-8. Do not use PowerShell `>` redirection:
     Windows PowerShell 5 writes UTF-16, which the renderer cannot read.

3. **Render.**
   ```bash
   uv run --no-project python "<skill-dir>/scripts/render_report.py" --stats "<stats-path>" --analysis "<analysis-path>" --lang <ko|en>
   ```
   Leave out `--analysis` when step 2 was skipped, but always pass `--lang`. The report goes to
   `~/.claude/usage-data/junior-mentor-report.html` (replaced on every run); the script prints the path.

4. **Hand it over.** In Claude Code, send the file with SendUserFile and `display: render`. In Codex
   or anywhere else, print the path. Then at most two lines: the one change that would help most.

## Ground rules
- The feedback is about how the user works with the agent, not about the quality of the code.
- Use only numbers and quotes that appear in the digest. No invented figures, no links.
- The signals are heuristics. Say so where a reading is a guess.
- Privacy: the scripts only read local logs, make no network calls, and mask keys, tokens, emails
  and home paths before anything is written or printed. Masking is pattern-based, and you (the
  model) read the masked digest. Tell the user this if they ask.
- No quizzes, exercises, progress tracking or study plans.
