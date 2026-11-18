#!/usr/bin/env python3
"""Read Claude Code and Codex session logs into Session records, with secrets masked.

Logs are only read. Every text field that leaves read_session() has gone through mask().
"""
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

CLAUDE_ROOT = Path.home() / ".claude" / "projects"
CODEX_ROOT = Path.home() / ".codex"
LOCALES = Path(__file__).resolve().parent.parent / "locales"
EXCERPT = 120  # max chars of a prompt or error kept as evidence (PLAN D5)
HEAD = 1000    # only a text's head is ever shown; masking a bounded string keeps the regexes fast
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def find_logs(agent, claude_root=CLAUDE_ROOT, codex_root=CODEX_ROOT):
    """Session log files for agent = claude | codex | both. Subagent transcripts are skipped."""
    found = []
    if agent in ("claude", "both"):
        found += [p for p in Path(claude_root).rglob("*.jsonl")
                  if not {"subagents", "tool-results"} & set(p.parts)]
    if agent in ("codex", "both"):
        root = Path(codex_root)
        found += list((root / "sessions").rglob("rollout-*.jsonl"))
        found += list((root / "archived_sessions").glob("rollout-*.jsonl"))
    return found


# ── masking ─────────────────────────────────────────────────────────────────
# ASCII character classes on purpose: \w would also eat Hangul glued to a secret.

def _random_like(m):
    s = m[0]
    has_digit = re.search(r"\d", s)
    hex_only = re.fullmatch(r"[0-9a-fA-F]+", s)
    mixed_case = re.search(r"[a-z]", s) and re.search(r"[A-Z]", s)
    return "[REDACTED]" if has_digit and (hex_only or mixed_case) else s


MASKS = [
    (re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----.*?(?:-----END[^-]*PRIVATE KEY-----|\Z)", re.S), "[SECRET]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[SECRET]"),
    # not right after an ASCII letter/digit: "task-manager" stays, "키는sk-…" does not
    (re.compile(r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}"
                r"|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]+)"), "[SECRET]"),
    # key: any identifier holding a secret-ish word (SECRET_KEY, DB_PASSWORD, GITHUB_TOKEN, api_key);
    # value: quoted, or a run of printable ASCII except , and ; (so "token: 만료" keeps the Korean)
    (re.compile(r"([A-Za-z0-9_-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key"
                r"|private[_-]?key)[A-Za-z0-9_-]*)([\"']?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[!-+\--:<-~]+)", re.I),
     r"\1\2[SECRET]"),
    # letters-only top-level domain that is not a file extension: react@18.3.1 and logo@2x.png stay
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*"
                r"\.(?!(?:png|jpe?g|gif|svg|webp|ico|bmp|js|mjs|cjs|ts|tsx|jsx|css|scss|json|md|html?|py|txt|map)"
                r"(?![A-Za-z0-9-]))[A-Za-z]{2,}(?![A-Za-z0-9-])"), "[EMAIL]"),
    # A home dir only where a path starts, so src/app/users/ and "GET /users/1" stay.
    # Windows needs a drive (C:\Users\x, escaped C:\\Users\\x, git-bash /c/Users/x);
    # macOS /Users and Linux /home are case-sensitive; /home/<name> only with a deeper path after it,
    # so a web route like "/home/feed" stays (this machine's own home is replaced exactly anyway).
    (re.compile(r"(?<![^\s'\"`(=\[,:])(?:[A-Za-z]:|/[a-z](?=/))[\\/]+[Uu][Ss][Ee][Rr][Ss][\\/]+[^\\/\s'\"`]+"),
     "~"),
    (re.compile(r"(?<![^\s'\"`(=\[,:])/(?:Users/[^/\s'\"`]+|home/[^/\s'\"`]+(?=/))"), "~"),
    (re.compile(r"[A-Za-z0-9+_=-]{40,}"), _random_like),
]


def _home_patterns():
    home = str(Path.home())
    if len(home) <= 3:  # e.g. "/" — replacing it would mangle every path
        return []
    variants = {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}
    # only a whole path segment: C:\Users\kim must not turn C:\Users\kimberly into ~berly
    return [re.compile(re.escape(v) + r"(?![^\\/\s'\"`])", re.I) for v in variants]


HOME_MASKS = _home_patterns()


def mask(text):
    if not text:
        return text or ""
    for rx in HOME_MASKS:
        text = rx.sub("~", text)
    for rx, repl in MASKS:
        text = rx.sub(repl, text)
    return text


# ── prompts ─────────────────────────────────────────────────────────────────

# Context blocks the harness wraps around the user's words. Names with - or _ are never
# ordinary HTML a user would paste (system-reminder, ide_opened_file, environment_context...).
# Only closed blocks count, so "<Button> 클릭이 안 돼" or "<branch-name>으로" survive.
# Closing tags may repeat the attributes (</pasted_content id="x">).
INJECTED_BLOCK = re.compile(r"<([a-z][a-z0-9]*[-_][a-z0-9_-]*)\b[^>]*>.*?</\1\b[^>]*>", re.S | re.I)
LEADING_BLOCK = re.compile(r"^\s*<([A-Za-z][\w-]*)\b[^>]*>.*?</\1\b[^>]*>", re.S)
COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
PASTED_TAG = re.compile(r"</?pasted_content\b[^>]*>")  # pasted text is the user's: keep it, drop the wrapper
CODEX_ASK = re.compile(r"#+\s*My request for Codex:\s*")
# Turns written by the harness, not by the user (checked on the lowercased start of the text)
HARNESS_TURNS = (
    "this session is being continued from a previous conversation",  # context compaction summary
    "base directory for this skill:",                                 # skill body
    "another claude session sent a message",                          # subagent hand-back
    "(re-invocation of",                                              # skill re-invocation
    "background (from the session that started this one)",          # session hand-off brief
    "# agents.md instructions",                                       # Codex AGENTS.md injection
)


def prompt_text(raw):
    """The user's own words from a user turn, or None if the turn is not a real prompt."""
    text = raw or ""
    args = COMMAND_ARGS.search(text)
    if args:  # a slash command: what the user typed after it is the prompt
        text = args[1]
    ask = CODEX_ASK.search(text)
    if ask:
        text = text[ask.end():]
    text = INJECTED_BLOCK.sub("", PASTED_TAG.sub("", text))
    while LEADING_BLOCK.match(text):
        text = LEADING_BLOCK.sub("", text, count=1)
    text = text.strip()
    # "[Image #1] 이거 왜 깨져?" is a prompt; "[Request interrupted" is handled before this
    if not text or text.lower().startswith(HARNESS_TURNS):
        return None
    return text


def _correction_pattern():
    patterns = []
    for f in sorted(LOCALES.glob("*.json")):
        patterns += json.loads(f.read_text(encoding="utf-8")).get("correction_patterns", [])
    # no outer \b: Korean particles glue onto the word ("아니라고")
    joined = "|".join(f"(?:{p})" for p in dict.fromkeys(patterns))
    return re.compile(joined or r"(?!)", re.I)


CORRECTION = _correction_pattern()


# ── errors ──────────────────────────────────────────────────────────────────

# Lines that come before the real error: exit-code headers, npm "> script" echoes, banners (=====)
ERROR_HEADER = re.compile(r"(?:Exit code\b|Wall time:|Total output lines:|Output:|> |[=\-_*#~]{3,})")
PATH_TOKEN = re.compile(r"[^\s'\"`]*[\\/][^\s'\"`]*")
CODEX_EXIT = re.compile(r"^Exit code: (-?\d+)", re.M)
# Not failures of the user's work (PLAN D12): agent bookkeeping, interrupted calls (counted on their
# own), and the user declining a tool call.
NOT_FAILURES = ("<tool_use_error>", "[Request interrupted", "[Tool call interrupted",
                "The user doesn't want to proceed")


def error_signature(text):
    """First real error line with paths and numbers blanked, so repeats group together."""
    lines = [l.strip() for l in str(text or "").splitlines()]
    lines = [l for l in lines if l and not ERROR_HEADER.match(l)]
    if not lines:
        return ""
    # a Python traceback names the exception on its last line, not its first
    line = lines[-1] if lines[0].startswith("Traceback (most recent call last)") else lines[0]
    if line.startswith(("Permission to use", "Permission for this")):
        return "Permission denied"
    line = mask(line[:HEAD])
    if not re.search(r"[^\W\d_]", PATH_TOKEN.sub("", line)):
        return ""  # nothing but punctuation or a bare path: no signal
    line = re.sub(r"\d+", "N", PATH_TOKEN.sub("<path>", line))
    return " ".join(line.split())[:EXCERPT]


def codex_error_text(output):
    """Error text if a Codex tool output reports a non-zero exit, else None."""
    if isinstance(output, list):  # exec tool: items whose text holds the JSON result
        for item in output:
            text = item.get("text") if isinstance(item, dict) else None
            err = codex_error_text(text) if text else None
            if err is not None:
                return err
        return None
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except ValueError:
            m = CODEX_EXIT.search(output[:300])
            return output if m and m[1] != "0" else None
    if isinstance(output, dict):
        code = output.get("exit_code", (output.get("metadata") or {}).get("exit_code"))
        return str(output.get("output", "")) if code not in (0, None) else None
    return None


# ── sessions ────────────────────────────────────────────────────────────────

@dataclass
class Session:
    source: str
    file: str
    cwd: str = ""
    models: set = field(default_factory=set)
    prompts: list = field(default_factory=list)
    corrections: list = field(default_factory=list)
    interrupts: int = 0
    tools: Counter = field(default_factory=Counter)
    errors: Counter = field(default_factory=Counter)      # tool name -> failures
    error_sigs: Counter = field(default_factory=Counter)  # signature -> occurrences
    edits: Counter = field(default_factory=Counter)       # file path -> edits
    out_tokens: int = 0
    in_tokens: int = 0
    days: Counter = field(default_factory=Counter)        # local date -> prompts
    first_ts: str = ""
    last_ts: str = ""
    bad_lines: int = 0

    def add_prompt(self, raw, ts=""):
        text = prompt_text(raw)
        if text:
            self.prompts.append(text)
            self.days[local_day(ts)] += 1
            if CORRECTION.search(text):
                self.corrections.append(text)

    def add_error(self, tool, text):
        if tool.startswith("mcp__") or str(text).lstrip().startswith(NOT_FAILURES):
            return
        self.errors[tool] += 1
        sig = error_signature(text)
        if sig:
            self.error_sigs[sig] += 1


def local_day(ts):
    """'2026-11-18T23:30:00Z' -> the date on this machine's clock ('2026-11-19' in Korea), '?' if unknown."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date().isoformat()
    except (AttributeError, ValueError):
        return "?"


def _block_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def _claude_record(rec, s, state):
    if rec.get("cwd") and not s.cwd:
        s.cwd = rec["cwd"]
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return
    model = msg.get("model")
    if model and not model.startswith("<"):  # "<synthetic>" is not a real model
        s.models.add(model)
    usage, mid = msg.get("usage"), msg.get("id")
    seen = state.setdefault("usage_ids", set())
    # one answer is logged as several lines sharing a message id and the same usage
    if isinstance(usage, dict) and (mid is None or mid not in seen):
        seen.add(mid)
        s.out_tokens += usage.get("output_tokens") or 0
        s.in_tokens += sum(usage.get(k) or 0 for k in
                           ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    content = msg.get("content")
    blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
    names = state.setdefault("names", {})
    edit_of = state.setdefault("edit_of", {})  # tool_use id -> file it tried to edit
    if msg.get("role") == "assistant":
        for b in blocks:
            if b.get("type") == "tool_use":
                name = b.get("name") or "?"
                names[b.get("id")] = name
                s.tools[name] += 1
                inp = b.get("input") or {}
                target = (inp.get("file_path") or inp.get("notebook_path")) if name in EDIT_TOOLS else None
                if target:
                    s.edits[target] += 1
                    edit_of[b.get("id")] = target
    elif msg.get("role") == "user" and not rec.get("isMeta") and not rec.get("isCompactSummary"):
        for b in blocks:
            if b.get("type") == "tool_result" and b.get("is_error") is True:
                target = edit_of.pop(b.get("tool_use_id"), None)
                if target:  # a failed edit changed nothing, so it is not churn
                    s.edits[target] -= 1
                    if s.edits[target] <= 0:
                        del s.edits[target]
                s.add_error(names.get(b.get("tool_use_id"), "?"), _block_text(b.get("content")))
        raw = content if isinstance(content, str) else \
            "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if raw.lstrip().startswith("[Request interrupted"):
            s.interrupts += 1
        else:
            s.add_prompt(raw, rec.get("timestamp") or "")


def _codex_record(rec, s, state):
    p = rec.get("payload") if isinstance(rec.get("payload"), dict) else {}
    kind = p.get("type")
    names = state.setdefault("names", {})
    if rec.get("type") in ("session_meta", "turn_context"):
        s.cwd = s.cwd or p.get("cwd") or ""
        if p.get("model"):
            s.models.add(p["model"])
    elif kind == "user_message":
        state["has_user_events"] = True
        s.add_prompt(p.get("message") or "", rec.get("timestamp") or "")
    elif kind == "message" and p.get("role") == "user":
        # newer rollouts log the ask only as a response item; used when no user_message events exist
        text = "\n".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
        state.setdefault("user_items", []).append((text, rec.get("timestamp") or ""))
    elif kind == "turn_aborted":
        if p.get("reason") == "interrupted":
            s.interrupts += 1
    elif kind in ("function_call", "custom_tool_call"):
        name = p.get("name") or "?"
        names[p.get("call_id")] = name
        s.tools[name] += 1
    elif kind in ("function_call_output", "custom_tool_call_output"):
        err = codex_error_text(p.get("output"))
        if err is not None:
            s.add_error(names.get(p.get("call_id"), "?"), err)
    elif kind == "patch_apply_end":
        changes = p.get("changes")
        targets = [p["path"]] if isinstance(p.get("path"), str) else \
            list(changes) if isinstance(changes, dict) else []
        for t in targets:
            s.edits[t] += 1
    elif kind == "token_count":
        total = (p.get("info") or {}).get("total_token_usage")
        if isinstance(total, dict):
            state["usage"] = total  # cumulative: the last one wins


def read_session(path, since="", seen=None):
    """One log file as a Session.

    since: 'YYYY-MM-DDTHH:MM:SS' (UTC); records stamped earlier are skipped, so a long session
           only contributes what happened inside the window.
    seen:  record uuids already read from other files; resumed or forked sessions copy earlier
           records into a new file, and those must not be counted twice.
    """
    path = Path(path)
    s = Session("codex" if path.name.startswith("rollout-") else "claude", path.name)
    handle = _codex_record if s.source == "codex" else _claude_record
    state = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                rec = None
            if not isinstance(rec, dict):
                s.bad_lines += 1
                continue
            if not s.cwd and isinstance(rec.get("cwd"), str):
                s.cwd = rec["cwd"]  # metadata: fine to take from skipped (old or copied) records
            ts = rec.get("timestamp")
            if since and isinstance(ts, str) and ts[:19] < since:
                p = rec.get("payload")
                if isinstance(p, dict) and p.get("type") == "token_count":
                    # Codex totals are cumulative: remember where the window starts
                    state["usage_before"] = (p.get("info") or {}).get("total_token_usage") or {}
                continue
            uid = rec.get("uuid")
            if seen is not None and isinstance(uid, str):
                if uid in seen:
                    continue
                seen.add(uid)
            if isinstance(ts, str):
                s.first_ts = s.first_ts or ts
                s.last_ts = max(s.last_ts, ts)
            handle(rec, s, state)
    if s.source == "codex":
        if not state.get("has_user_events"):
            for raw, ts in state.get("user_items", []):
                s.add_prompt(raw, ts)
        usage, before = state.get("usage") or {}, state.get("usage_before") or {}

        def grown(key):
            return max(0, (usage.get(key) or 0) - (before.get(key) or 0))

        s.out_tokens = grown("output_tokens")  # reasoning tokens are already included here
        s.in_tokens = grown("input_tokens")    # so are cached input tokens
    s.prompts = [mask(t[:HEAD]) for t in s.prompts]
    s.corrections = [mask(t[:HEAD]) for t in s.corrections]
    s.cwd = mask(s.cwd)
    edits = Counter()
    for target, n in s.edits.items():
        edits[mask(target)] += n
    s.edits = edits
    return s
