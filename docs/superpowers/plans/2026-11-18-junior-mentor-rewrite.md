# junior-mentor Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** mentor 코드 없이 junior-mentor 스킬을 처음부터 다시 작성한다 (기능·결정은 PLAN.md 그대로).

**Architecture:** `logs.py`가 로그 한 파일을 `Session` 데이터클래스로 읽고 마스킹한다. `collect.py`가 세션들을 기간으로 거르고 집계해 stats dict와 다이제스트를 만든다. `render_report.py`가 stats + analysis를 JS 없는 HTML로 그린다. 테스트는 `tests/`의 unittest.

**Tech Stack:** Python 표준 라이브러리(argparse, dataclasses, pathlib, re, json, html, unittest), `uv run --no-project python` (이 PC: 3.13.5).

**Spec:** `PLAN.md` (D1~D12, §4 규칙)

## Global Constraints

- mentor 코드·CSS·문구·픽스처를 옮기지 않는다 (D8). 의존성·네트워크 코드 없음
- 경로는 `pathlib`, 비교는 `Path.parts`. 로그는 `encoding="utf-8", errors="replace"`로 읽기만
- 각 스크립트 `main()` 시작에 `sys.stdout.reconfigure(encoding="utf-8")`
- 상수: `EXCERPT=120`, `REPEAT_MIN=3`, `CHURN_MIN=5`, `MIN_SESSIONS=5`, `DIGEST_SESSIONS=60`, 기본 기간 30일
- 중간 파일: `tempfile.gettempdir()/junior-mentor-stats.json`, 같은 폴더 `junior-mentor-analysis.json`. 보고서: `~/.claude/usage-data/junior-mentor-report.html`
- 커밋: Conventional Commits + 한국어 제목, Co-Authored-By 없음, 원격·push 없음
- 테스트는 작성만, 실행은 사용자 요청 시. 그전엔 `py_compile`만

## Review Focus

1. 알 수 없는 레코드·객체가 아닌 JSON 줄 → 무시하고 세션 유지 (test_logs)
2. 한글에 붙은 비밀값, 경로 중간 `users/`, `pkg@1.2.3`, `task-…` (test_logs 마스킹 표)
3. 기간 밖 대화가 최근에 수정된 파일 (test_collect)
4. 세션 0개·5개 미만 → 크래시 없이 데이터 부족 (test_collect, test_report)
5. LLM이 쓴 analysis의 이상한 모양(BOM, 문자열 배열, `ko-KR`) (test_report)

---

### Task 1: `scripts/logs.py` + `tests/test_logs.py`

**Interfaces (Produces):**
- `CLAUDE_ROOT`, `CODEX_ROOT` (Path), `LOCALES` = `Path(__file__).resolve().parent.parent / "locales"`, `EXCERPT = 120`
- `find_logs(agent: str, claude_root: Path = CLAUDE_ROOT, codex_root: Path = CODEX_ROOT) -> list[Path]` — agent ∈ claude|codex|both
- `mask(text: str) -> str` — PLAN.md §4 표와 규칙
- `error_signature(text: str) -> str` — §4 오류 시그니처, 결과 `[:EXCERPT]`
- `codex_error_text(output) -> str | None` — 실패면 오류 본문, 아니면 None
- `prompt_text(raw: str) -> str | None` — 사용자 프롬프트면 정리된 글, 아니면 None (§4 "세지 않는 것")
- `CORRECTION: re.Pattern` — 모든 `locales/*.json`의 `correction_patterns` 합집합
- `@dataclass Session`: `source, file, cwd, models: set, prompts: list, corrections: list, interrupts: int, tools: Counter, errors: Counter(도구별), error_sigs: Counter, edits: Counter(경로별), out_tokens, in_tokens, first_ts, last_ts, bad_lines`
- `read_session(path: Path) -> Session` — 끝에서 prompts·corrections·cwd·edits 키를 `mask`

- [ ] 테스트 작성: 마스킹 표(유지 케이스 포함), 시그니처(Claude/Codex 헤더·권한 거부·경로), `codex_error_text` 세 모양 + 성공, `prompt_text`(태그 블록 뒤 글, 압축 요약, 하네스 메시지 4종, Codex 마커), Claude 세션(도구 id→이름 귀속, `<tool_use_error>`·`[Tool call interrupted`·`mcp__` 제외, 중단 텍스트, 같은 파일 5회 → 마스킹된 키, 토큰 합), Codex 세션(누적 토큰은 마지막 값, call_id 귀속, `patch_apply_end` 편집), 깨진 바이트·`null` 줄 → `bad_lines`, `find_logs`의 subagents 제외
- [ ] 구현 → `py_compile` → 커밋 `feat: 로그 읽기·마스킹 모듈`

### Task 2: `scripts/collect.py` + `tests/test_collect.py`

**Interfaces:**
- Consumes: `find_logs`, `read_session`, `Session`, `EXCERPT`
- Produces: `collect(agent: str, days: int, files: list[Path] | None = None) -> dict`, `digest(stats: dict) -> str`, `STATS_PATH`, `main(argv=None)` (argparse `--agent --days --out`, 마지막 줄 `[stats: <경로> — N sessions]`)
- stats 키: `agent, days, generated, span{first,last,active_days}, totals{sessions,prompts,tool_calls,edits,files,out_tokens,in_tokens,corrections,interrupts,tool_errors}, per_day, tools, languages, models, projects, tool_errors, repeated_errors[{signature,count,sessions}], churn[{file,edits,date,session}], unreadable{lines,files}, enough_data, sessions[{file,source,date,cwd,prompts,first_prompt,corrections,errors,interrupts,out_tokens,top_tools}]`
- 다이제스트: 데이터 부족이면 첫 줄 `NOT ENOUGH DATA`, `## Problem signals` 섹션, 세션은 (수정+오류+중단, 프롬프트) 내림차순 60개, 넘치면 `… N more sessions omitted`

- [ ] 테스트 작성: 6세션(오류 3회 → 반복 오류 1묶음, 같은 파일 5회 → churn, 마스킹된 경로) + 오래된 대화 1개 제외, 빈 목록 → 데이터 부족, 70세션 → 60개 + 생략 줄
- [ ] 구현 → `py_compile` → 커밋 `feat: 기간 필터·집계·다이제스트`

### Task 3: `scripts/render_report.py` + locales + `tests/test_report.py`

**Interfaces:**
- Consumes: Task 2 stats 키
- Produces: `labels(lang: str) -> dict`, `render(stats: dict, analysis: dict, lang: str) -> str`, `REPORT_PATH`, `main(argv=None)` (argparse `--stats --analysis --lang --out`, analysis는 `utf-8-sig`, 없으면 stderr 경고)
- 언어: `lang.split("-")[0].lower()`가 영문자가 아니면 `en`
- analysis 스키마는 SKILL.md와 같음. 리스트 항목이 dict가 아니어도 크래시 없이 문자열로 표시

- [ ] 테스트 작성: ko 렌더(라벨·개념명), `<script>` 이스케이프, 외부 `src/href/@import` 없음, `labels("xx") == labels("en")`, ko·en 라벨 키 동일, 데이터 부족 분기(문제 섹션 없음, 안내 있음), 빈 입력, `ko-KR`, problems가 문자열 배열, BOM analysis로 `main()`
- [ ] 구현(새 디자인: 밝은 기본 + 다크 미디어 쿼리, JS 없음) → `py_compile` → 커밋 `feat: 보고서 렌더러와 로케일`

### Task 4: 문서·정리

- [ ] `SKILL.md` 새로 작성(명령은 `<skill-dir>` 기준, `--lang` 항상, 테스트 명령 없음), `references/rubric.md`·`README.md` 문장 새로 작성, `evals/evals.json` 점검
- [ ] 삭제: `LICENSE`, `scripts/digest.py`, 옛 계획 `docs/superpowers/plans/2026-11-18-junior-mentor.md`
- [ ] 커밋 `docs: 스킬 정의·판단 기준·README 재작성`

### Task 5 (사용자 요청 시): 테스트 실행·실제 로그·Codex

- [ ] `uv run --no-project python -m unittest discover -s tests -v` → 모두 OK
- [ ] 실제 로그로 보고서 생성, Codex 실행 확인
