#!/usr/bin/env python3
"""Turn the session logs of the last N days into stats.json and a text digest for the model.

    uv run --no-project python collect.py [--agent claude|codex|both] [--days 30] [--out PATH]
"""
import argparse
import json
import os
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from logs import EXCERPT, find_logs, local_day, read_session

STATS_PATH = Path(tempfile.gettempdir()) / "junior-mentor-stats.json"
ANALYSIS_NAME = "junior-mentor-analysis.json"  # written by the model next to the stats file
REPEAT_MIN = 3         # same error signature this often in the window = repeated (PLAN D6)
CHURN_MIN = 5          # same file edited this often in one session = churn (PLAN D6)
MIN_SESSIONS = 5       # fewer sessions: stats only, no pattern analysis (PLAN D4)
DIGEST_SESSIONS = 60   # sessions listed for the model, most signals first (PLAN §6-4)
TOP = 10
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin", ".go": "Go",
    ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".c": "C", ".cpp": "C++",
    ".swift": "Swift", ".dart": "Dart", ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell",
    ".md": "Markdown", ".json": "JSON", ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML",
}


def collect(agent, days, files=None):
    since = time.time() - days * 86400
    since_ts = datetime.fromtimestamp(since, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    paths = find_logs(agent) if files is None else [Path(f) for f in files]
    totals, tools, tool_errors = Counter(), Counter(), Counter()
    sigs, sig_sessions, langs, projects, per_day = Counter(), Counter(), Counter(), Counter(), Counter()
    unreadable = Counter(lines=0, files=0)
    models, touched, churn, rows = set(), set(), [], []
    seen = set()  # record uuids, shared across files (resumed sessions copy earlier records)
    first = last = ""
    for path in sorted(paths):
        try:
            if path.stat().st_mtime < since:  # cheap pre-filter; read_session drops older records
                continue
            s = read_session(path, since=since_ts, seen=seen)
        except Exception:  # a log shape we cannot read must not stop the whole report
            unreadable["files"] += 1
            continue
        unreadable["lines"] += s.bad_lines
        if not s.prompts and not s.tools:
            continue  # empty, aborted, or nothing new inside the window
        day = local_day(s.last_ts or s.first_ts)
        n_errors = sum(s.errors.values())
        totals.update(sessions=1, prompts=len(s.prompts), tool_calls=sum(s.tools.values()),
                      edits=sum(s.edits.values()), out_tokens=s.out_tokens, in_tokens=s.in_tokens,
                      corrections=len(s.corrections), interrupts=s.interrupts, tool_errors=n_errors)
        tools.update(s.tools)
        tool_errors.update(s.errors)
        sigs.update(s.error_sigs)
        sig_sessions.update(set(s.error_sigs))
        models |= s.models
        touched |= set(s.edits)
        langs.update(LANGUAGES[ext] for ext in (os.path.splitext(f)[1].lower() for f in s.edits)
                     if ext in LANGUAGES)
        projects[s.cwd or "?"] += 1
        per_day.update(s.days)
        if s.first_ts:
            first = min(first or s.first_ts, s.first_ts)
        last = max(last, s.last_ts)
        churn += [{"file": f, "edits": n, "date": day, "session": s.file}
                  for f, n in s.edits.items() if n >= CHURN_MIN]
        rows.append({
            "file": s.file, "source": s.source, "date": day, "cwd": s.cwd,
            "prompts": len(s.prompts), "first_prompt": s.prompts[0][:EXCERPT] if s.prompts else "",
            "corrections": [c[:EXCERPT] for c in s.corrections[:2]], "correction_count": len(s.corrections),
            "errors": n_errors, "interrupts": s.interrupts, "out_tokens": s.out_tokens,
            "top_tools": dict(s.tools.most_common(5)),
        })
    totals["files"] = len(touched)
    return {
        "agent": agent, "days": days,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "span": {"first": first, "last": last, "active_days": len([d for d in per_day if d != "?"])},
        "totals": dict(totals),
        "per_day": dict(sorted(per_day.items())),
        "tools": dict(tools.most_common(20)),
        "languages": dict(langs.most_common()),
        "models": sorted(models),
        "projects": dict(projects.most_common(TOP)),
        "tool_errors": dict(tool_errors.most_common(TOP)),
        "repeated_errors": [{"signature": k, "count": n, "sessions": sig_sessions[k]}
                            for k, n in sigs.most_common() if n >= REPEAT_MIN][:TOP],
        "churn": sorted(churn, key=lambda c: -c["edits"])[:TOP],
        "unreadable": dict(unreadable),
        "enough_data": totals["sessions"] >= MIN_SESSIONS,
        "sessions": rows,
    }


def _pairs(counts):
    return ", ".join(f"{k} {v}" for k, v in counts.items())


def _oneline(text):
    return " ".join(text.split())


def digest(st):
    t = st["totals"]
    out = []
    if not st["enough_data"]:
        out.append(f"NOT ENOUGH DATA: {t.get('sessions', 0)} sessions (< {MIN_SESSIONS}). "
                   "Skip the analysis step and render stats only.")
    out += [
        f"# junior-mentor digest — {st['agent']}, last {st['days']} days",
        f"span {st['span']['first'] or '?'} → {st['span']['last'] or '?'} · "
        f"{st['span']['active_days']} active days",
        "",
        "## Totals",
        f"- sessions {t.get('sessions', 0)} · prompts {t.get('prompts', 0)} · tool calls "
        f"{t.get('tool_calls', 0)} · edits {t.get('edits', 0)} in {t.get('files', 0)} files",
        f"- output tokens {t.get('out_tokens', 0):,} · input tokens {t.get('in_tokens', 0):,}",
        f"- correction-like prompts {t.get('corrections', 0)} · interrupts {t.get('interrupts', 0)} · "
        f"tool errors {t.get('tool_errors', 0)}",
        f"- models: {', '.join(st['models']) or '?'}",
        f"- unreadable log lines {st['unreadable']['lines']}, files {st['unreadable']['files']}",
        "",
        "## Problem signals (heuristic — the evidence for `problems`)",
        "- tool errors by tool: " + (_pairs(st["tool_errors"]) or "none"),
        f"- same error {REPEAT_MIN}+ times:",
        *([f"  {e['count']}x in {e['sessions']} sessions: {e['signature']}" for e in st["repeated_errors"]]
          or ["  none"]),
        f"- same file edited {CHURN_MIN}+ times in one session:",
        *([f"  {c['edits']}x {c['file']} ({c['date']}, {c['session']})" for c in st["churn"]] or ["  none"]),
        "",
        "## Usage",
        "- tools: " + (_pairs(st["tools"]) or "none"),
        "- languages (edited files): " + (_pairs(st["languages"]) or "none"),
        "- projects: " + (_pairs(st["projects"]) or "none"),
        "",
        "## Sessions (most signals first; group the first prompts into topics)",
    ]
    ranked = sorted(st["sessions"], reverse=True,
                    key=lambda r: (r["correction_count"] + r["errors"] + r["interrupts"], r["prompts"]))
    for i, r in enumerate(ranked[:DIGEST_SESSIONS], 1):
        out.append(f"{i}. [{r['source']}] {r['date']} {r['cwd']} — {r['prompts']} prompts, "
                   f"{r['errors']} errors, {r['correction_count']} corrections, {r['interrupts']} interrupts, "
                   f"{r['out_tokens']:,} out tokens")
        out.append(f"   first: “{_oneline(r['first_prompt'])}”")
        out += [f"   correction: “{_oneline(c)}”" for c in r["corrections"]]
    if len(ranked) > DIGEST_SESSIONS:
        out.append(f"… {len(ranked) - DIGEST_SESSIONS} more sessions omitted")
    return "\n".join(out)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp949
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Collect junior-mentor stats from local agent logs.")
    parser.add_argument("--agent", choices=["claude", "codex", "both"], default="both")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out", type=Path, default=STATS_PATH)
    args = parser.parse_args(argv)
    # if the model then fails to write a new analysis, the renderer must not pick up last run's
    (args.out.parent / ANALYSIS_NAME).unlink(missing_ok=True)
    st = collect(args.agent, args.days)
    args.out.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(digest(st))
    print(f"\n[stats: {args.out} — {st['totals'].get('sessions', 0)} sessions]")


if __name__ == "__main__":
    main()
