# Rubric — turning the digest into feedback

## From signal to advice

| What the digest shows | What to suggest | Concept to name |
|---|---|---|
| `same error 3+ times` | Read the error first, then paste it into the request with what you expected | stack trace, minimal reproduction |
| `same file edited 5+ times in one session` | Write "done when …" before asking; ask for one small change at a time | requirements, small commits |
| many correction-like prompts | Put context, constraints and one example into the first request | input/output specification |
| many interrupts | On bigger tasks, ask for a plan and approve it first | task decomposition, plan mode |
| `Permission denied` among the repeated errors | Allow only the safe, read-only commands you run often | principle of least privilege |
| one very long session, huge input tokens | One session per topic; carry over a three-line summary | context window |

These are hints. When the evidence points somewhere else, follow the evidence.

Shell quoting errors such as `unexpected EOF while looking for matching` come from commands the
agent wrote. They are the agent's problem unless a prompt shows the user caused them. MCP tool
errors are already left out of the counts.

## Writing a problem
- `problem`: one line — what keeps happening.
- `evidence`: copied from the digest — counts, date, session file, a quoted prompt.
- `why`: one or two sentences on what it costs.
- `fix`: one concrete thing to do next time, ideally something to copy: a request template, a
  line for CLAUDE.md or AGENTS.md, a setting.
- `concept`: a name plus one or two sentences, enough to search for and learn.

Choose by how often it happened and how much time it cost. Fewer than three is fine, and so is
none — then say the period looks healthy and use `tips` to raise the bar.

## Tone
- Talk about the habit, not the person. Short sentences. No praise padding.
- In Korean, write concept names as `한국어(English)`, e.g. "경쟁 조건(race condition)".
- No links. Do not grade the code that was produced.
- In Codex nearly every action is an `exec` or `shell` call; that alone is not a problem.

## Strengths and tips
- `strengths`: things that went well, each with evidence from the digest.
- `tips`: at most three actions for this week, preferably ones that prevent a listed problem.
