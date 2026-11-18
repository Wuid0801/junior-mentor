#!/usr/bin/env python3
"""Render stats.json (and the model's analysis.json) as one self-contained HTML report.

    uv run --no-project python render_report.py [--stats PATH] [--analysis PATH] [--lang ko|en] [--out PATH]

No JavaScript and no external resources: the file opens the same offline in any browser.
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta
from html import escape
from pathlib import Path

from collect import STATS_PATH
from logs import LOCALES

REPORT_PATH = Path.home() / ".claude" / "usage-data" / "junior-mentor-report.html"

CSS = """
:root{--bg:#f7f7f4;--card:#fff;--ink:#1f2328;--muted:#656d76;--line:#d8dee4;
  --accent:#2563eb;--warn:#c2410c;--warn-bg:#fff7ed}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--card:#1b1f24;--ink:#e6edf3;
  --muted:#9198a1;--line:#30363d;--accent:#6ea8fe;--warn:#f0a35e;--warn-bg:#2a1f14}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
main{max-width:820px;margin:0 auto;padding:40px 16px 64px}
.kicker{margin:0;color:var(--accent);font-weight:600;font-size:13px;letter-spacing:.04em}
h1{margin:6px 0 4px;font-size:clamp(26px,4.5vw,36px);line-height:1.2}
h2{font-size:20px;margin:0 0 12px}
h3{font-size:15px;margin:18px 0 8px}
section{margin-top:36px}
.sub,.muted,.axis,footer{color:var(--muted);font-size:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-top:24px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.tile b{display:block;font-size:24px;font-variant-numeric:tabular-nums}
.tile span{color:var(--muted);font-size:13px}
.summary{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
  border-radius:12px;padding:18px 20px}
.summary p{margin:0;white-space:pre-wrap}
.days{display:flex;align-items:flex-end;gap:3px;height:110px;padding:12px;
  background:var(--card);border:1px solid var(--line);border-radius:12px}
.days i{flex:1;min-width:2px;background:var(--accent);border-radius:3px 3px 0 0}
.axis{display:flex;justify-content:space-between;margin:6px 2px 0}
.topics{width:100%;border-collapse:collapse}
.topics td{padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.topics .share{width:64px;color:var(--accent);font-variant-numeric:tabular-nums}
.topics span{color:var(--muted);font-size:14px}
.tags{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:6px}
.tags li{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:13px}
.notes{padding-left:20px;margin:12px 0 0}
.notes li{margin:6px 0}
.bars{display:grid;gap:6px;margin-bottom:16px}
.bar{display:grid;grid-template-columns:minmax(70px,140px) 1fr 48px;align-items:center;gap:8px;font-size:13px}
.bar span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar i{height:10px;background:var(--warn);border-radius:5px}
.bar b{text-align:right;font-variant-numeric:tabular-nums}
.problem{background:var(--warn-bg);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.problem h3{margin:0 0 8px;font-size:17px}
.problem p{margin:6px 0}
.problem .evidence{color:var(--muted);font-size:14px}
.problem .fix b{color:var(--accent)}
.problem .concept{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-top:10px}
footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--line)}
"""


def lang_code(lang):
    """'ko-KR' / 'ko_KR' -> 'ko'; anything that is not plain letters -> 'en' (it ends up in <html lang> and a path)."""
    code = re.split(r"[-_]", str(lang or ""))[0].lower()
    return code if code.isalpha() else "en"


def _locale_labels(code):
    path = LOCALES / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")).get("labels", {}) if path.is_file() else {}


def labels(lang):
    """Labels for lang, with every missing key taken from English."""
    return {**_locale_labels("en"), **_locale_labels(lang_code(lang))}


def e(value):
    return escape(str(value if value is not None else ""))


def num(value):
    return f"{round(value or 0):,}"


def as_list(value):
    return value if isinstance(value, list) else []


def as_dict(value):
    return value if isinstance(value, dict) else {}


def tiles(st, L):
    t, span = as_dict(st.get("totals")), as_dict(st.get("span"))
    items = [(t.get("sessions"), L["t_sessions"]), (t.get("prompts"), L["t_prompts"]),
             (span.get("active_days"), L["t_days"]), (t.get("tool_calls"), L["t_tools"]),
             (t.get("files"), L["t_files"]), ((t.get("out_tokens") or 0) / 1000, L["t_ktokens"])]
    return ('<section class="tiles">'
            + "".join(f'<div class="tile"><b>{num(n)}</b><span>{e(label)}</span></div>' for n, label in items)
            + "</section>")


def _calendar(per_day):
    """Every date from the first to the last active day, quiet days as 0, so gaps stay visible."""
    counts = {}
    for d, n in as_dict(per_day).items():
        try:
            counts[date.fromisoformat(d)] = n
        except (TypeError, ValueError):
            continue  # "?" or junk
    if not counts:
        return []
    first, last = min(counts), max(counts)
    return [(first + timedelta(i), counts.get(first + timedelta(i), 0)) for i in range((last - first).days + 1)]


def day_bars(per_day, L):
    days = [(d.isoformat(), n) for d, n in _calendar(per_day)]
    if not days:
        return ""
    top = max(n for _, n in days) or 1
    bars = "".join(f'<i style="height:{max(4, round(n / top * 100)) if n else 0}%" title="{e(d)} · {num(n)}"></i>'
                   for d, n in days)
    return (f'<section><h2>{e(L["by_day"])}</h2><div class="days">{bars}</div>'
            f'<p class="axis"><span>{e(days[0][0])}</span><span>{e(days[-1][0])}</span></p></section>')


def tags(counts, L):
    if not counts:
        return f'<p class="muted">{e(L["none"])}</p>'
    return '<ul class="tags">' + "".join(f"<li>{e(k)} <b>{num(v)}</b></li>" for k, v in counts.items()) + "</ul>"


def notes(items, L):
    items = [x for x in as_list(items) if x]
    if not items:
        return f'<p class="muted">{e(L["none"])}</p>'
    return '<ul class="notes">' + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"


def topics(items):
    rows = [r for r in as_list(items) if isinstance(r, dict)]
    if not rows:
        return ""
    return ('<table class="topics">'
            + "".join(f'<tr><td class="share">{e(r.get("share"))}</td><td><b>{e(r.get("topic"))}</b><br>'
                      f'<span>{e(r.get("detail"))}</span></td></tr>' for r in rows)
            + "</table>")


def error_bars(counts, L):
    if not counts:
        return ""
    top = max(counts.values()) or 1
    rows = "".join(f'<div class="bar"><span title="{e(k)}">{e(k)}</span>'
                   f'<i style="width:{max(2, round(v / top * 100))}%"></i><b>{num(v)}</b></div>'
                   for k, v in counts.items())
    return f'<h3>{e(L["tool_errors"])}</h3><div class="bars">{rows}</div>'


def problem_cards(items, L):
    cards = []
    for p in as_list(items):
        p = p if isinstance(p, dict) else {"problem": p}  # tolerate a plain string from the model
        parts = [f'<h3>{e(p.get("problem"))}</h3>']
        parts += [f'<p class="{key}"><b>{e(L[key])}</b> {e(p[key])}</p>'
                  for key in ("evidence", "why", "fix") if p.get(key)]
        concept = p.get("concept")
        concept = {"name": concept} if isinstance(concept, str) else as_dict(concept)
        if concept.get("name"):
            parts.append(f'<p class="concept"><b>{e(L["concept"])} · {e(concept["name"])}</b> '
                         f'{e(concept.get("explain"))}</p>')
        cards.append('<article class="problem">' + "".join(parts) + "</article>")
    return "".join(cards) or f'<p class="muted">{e(L["no_problems"])}</p>'


def render(st, an, lang):
    code = lang_code(lang)
    L = labels(code)
    st, an = as_dict(st), as_dict(an)
    sec = as_dict(an.get("sections"))
    pat = as_dict(sec.get("patterns"))
    totals = as_dict(st.get("totals"))
    period = an.get("period") or L["period"].format(n=st.get("days", "?"))
    models = ", ".join(as_list(st.get("models"))) or "?"
    body = [
        f'<header><p class="kicker">junior-mentor</p><h1>{e(L["h1"])}</h1>'
        f'<p class="sub">{e(period)} · {e(L["agent"])} {e(st.get("agent", "?"))} · {e(L["models"])} {e(models)}</p>'
        f"</header>",
        tiles(st, L),
    ]
    if st.get("enough_data", True):
        body += [
            f'<section class="summary"><h2>{e(L["summary"])}</h2><p>{e(an.get("summary"))}</p></section>',
            day_bars(st.get("per_day"), L),
            f'<section><h2>{e(L["s_pat"])}</h2>{topics(pat.get("topics"))}'
            f'<h3>{e(L["tools"])}</h3>{tags(as_dict(st.get("tools")), L)}'
            f'<h3>{e(L["langs"])}</h3>{tags(as_dict(st.get("languages")), L)}'
            f'{notes(pat.get("habits"), L)}</section>',
            f'<section><h2>{e(L["s_win"])}</h2>{notes(sec.get("strengths"), L)}</section>',
            f'<section><h2>{e(L["s_prob"])}</h2>{error_bars(as_dict(st.get("tool_errors")), L)}'
            f'{problem_cards(sec.get("problems"), L)}</section>',
            f'<section><h2>{e(L["s_tips"])}</h2>{notes(sec.get("tips"), L)}</section>',
        ]
    else:
        body += [f'<section class="summary"><h2>{e(L["low_data"])}</h2><p>{e(L["low_data_text"])}</p></section>',
                 day_bars(st.get("per_day"), L)]
    unreadable = as_dict(st.get("unreadable"))
    foot = L["foot"].format(time=st.get("generated", "?"), sessions=totals.get("sessions", 0),
                            lines=unreadable.get("lines", 0), files=unreadable.get("files", 0))
    body.append(f"<footer>{e(foot)}</footer>")
    return (f'<!doctype html>\n<html lang="{code}">\n<head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(L["title"])}</title><style>{CSS}</style></head>\n'
            f'<body><main>{"".join(body)}</main></body>\n</html>\n')


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # Windows consoles default to cp949
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Render the junior-mentor HTML report.")
    parser.add_argument("--stats", type=Path, default=STATS_PATH)
    parser.add_argument("--analysis", type=Path)
    parser.add_argument("--lang")
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    # utf-8-sig: JSON written by PowerShell (e.g. from Codex on Windows) may start with a BOM
    st = json.loads(args.stats.read_text(encoding="utf-8-sig"))
    an = {}
    if args.analysis:
        if args.analysis.is_file():
            an = as_dict(json.loads(args.analysis.read_text(encoding="utf-8-sig")))
        else:
            print(f"warning: no analysis at {args.analysis}; its sections will be empty", file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(st, an, args.lang or an.get("lang") or "en"), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
