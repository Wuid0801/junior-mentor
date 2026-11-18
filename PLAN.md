# 주니어 개발자용 AI 코딩 사용 분석 스킬 — 기획

> 스킬 이름 `junior-mentor` · 2026-11-18 · 처음부터 작성 (mentor 코드 미사용)
> 아이디어 참고: [smixs/mentor](https://github.com/smixs/mentor) — 코드는 가져오지 않는다

## 0. 확정 요구사항

### 요청서

| # | 요구사항 |
|---|---|
| 1 | 사용 기록 분석: 세션, 작업 내용, 도구 사용, 반복 패턴 |
| 2 | 문제점 발견: 비효율적인 작업 방식, 반복 오류 |
| 3 | 개발자 피드백: 주니어 관점의 개선 방법 + 관련 기술 개념을 간결하게 |
| 4 | HTML 보고서: 통계와 분석 결과 시각화 |
| 5 | 다국어: 한국어·영어 기본, 확장 가능한 구조 |
| 6 | 개인정보 보호: 로컬 데이터 기반, 민감정보 노출 방지 |

- **제외**: 퀴즈·실습, 학습 진도 관리, 학습 계획 생성, 별도 DB
- **원칙**: 최소 구현, 코드는 기획 확정 후, 테스트는 사용자가 요청할 때만 실행

### 결정 사항 (2026-11-18)

| # | 항목 | 결정 |
|---|---|---|
| D1 | 보고서 독자 | 본인만. 프로젝트명은 가리지 않고, 마스킹 범위는 §4 그대로 |
| D2 | 스킬 이름 | `junior-mentor` (호출 `/junior-mentor`) |
| D3 | Codex 범위 | 로그 분석 + **Codex 안에서 스킬 실행**까지 |
| D4 | 기본 기간 | 30일 (호출 시 변경 가능). 세션 5개 미만이면 패턴 분석 없이 통계만 + "데이터 부족" 안내 |
| D5 | 프롬프트 발췌 | 마스킹한 120자 발췌를 반복 문제 카드 근거에만 |
| D6 | 문제 신호 임계값 | 같은 오류 3회 이상 / 한 세션 같은 파일 수정 5회 이상 (상수) |
| D7 | 보고서 위치 | `~/.claude/usage-data/junior-mentor-report.html`, 매번 덮어쓰기 |
| D8 | 코드 출처 | mentor 코드·문구를 쓰지 않고 처음부터 작성. 구조와 디자인도 새로 |
| D9 | 단일 세션 모드 | 넣지 않는다 (요구사항 아님) |
| D10 | 라이선스 | 사용자가 원격 저장소를 만들 때 정한다. 그전까지 LICENSE 파일 없음. README에 "아이디어 참고: smixs/mentor" 한 줄 |
| D11 | git | 원격 연결 없는 로컬 저장소만. 원격 추가·push는 사용자가 한다 |
| D12 | 집계 제외 | MCP 도구(이름 `mcp__…`: 브라우저·앱·작업 도구) 오류, 에이전트 내부 오류(`<tool_use_error>`, `[Request interrupted`, `[Tool call interrupted`), 사용자가 도구 실행을 거절한 경우("The user doesn't want to proceed")는 오류 집계에서 뺀다 |

위 두 표에 없는 내용은 **제안**이다.

---

## 1. mentor와의 관계

- 같은 문제(에이전트 사용 기록 → 피드백 보고서)를 푼 선행 사례로 **아이디어만 참고**한다.
- 다른 점: 주니어 관점(반복 문제 → 개선 방법 → 관련 개념), 한국어, 민감정보 마스킹, Windows 지원, 실제 로그에서 확인한 노이즈 제거(§4).
- 코드·CSS·문구·테스트 픽스처는 가져오지 않는다 (D8).

---

## 2. MVP 기능과 사용 흐름

### 기능
1. **사용 통계**: 세션·프롬프트·활동일·도구별 호출·편집 파일·토큰·언어·프로젝트·일별 추이·모델
2. **문제 신호** (스크립트 계산, 근거 포함)
   - 도구 오류: 도구별 실패 수 (D12 제외 적용)
   - 반복 오류: 오류 첫 줄을 정규화(숫자·경로 제거)해 같은 묶음이 3회 이상
   - 같은 파일 반복 수정: 한 세션에서 같은 파일 편집 5회 이상
   - 수정 요청·중단 횟수
3. **피드백** (LLM, 섹션 5개): `summary`, `patterns`(topics + habits), `strengths`, `problems`(최대 3: 근거·왜 문제·개선 방법·관련 개념), `tips`(최대 3)
4. **HTML 보고서** 1개, 덮어쓰기

### 사용 흐름
```
사용자: "/junior-mentor [claude|codex|both] [기간]" 또는 "내 AI 코딩 습관 분석해줘"
 1. collect.py        로그 읽기 → 마스킹 → stats.json + 텍스트 다이제스트
 2. 에이전트           다이제스트 + rubric.md → analysis.json (사용자 언어)
 3. render_report.py  stats.json + analysis.json → report.html (--lang 항상 전달)
 4. 에이전트           보고서 열기 (Claude Code: SendUserFile render / Codex: 경로 출력), 채팅엔 2줄만
```

---

## 3. 디렉터리 구조

```
junior-mentor/
├── SKILL.md               # 트리거, 4단계 워크플로, analysis.json 스키마
├── scripts/
│   ├── logs.py            # 로그 찾기·읽기 → 세션 기록, 마스킹, 오류 시그니처
│   ├── collect.py         # 기간 필터·집계·문제 신호 → stats.json + 다이제스트
│   └── render_report.py   # stats + analysis → HTML
├── tests/                 # 표준 라이브러리 unittest
├── references/rubric.md   # 판단 기준, 신호→개념 매핑, 말투 규칙
├── locales/en.json, ko.json  # 보고서 라벨 + 수정 요청 패턴
└── evals/evals.json
```

---

## 4. 수집 · 분석 · 보고서

### 수집 (로그는 읽기만)
- Python 표준 라이브러리만, `uv run --no-project python`, 네트워크 코드 없음
- Claude: `~/.claude/projects/**/*.jsonl` (경로에 `subagents`, `tool-results`가 있으면 제외). Codex: `~/.codex/sessions/**/rollout-*.jsonl`, `~/.codex/archived_sessions/rollout-*.jsonl`
- 기간: 파일 수정 시각으로 1차 거르고, **기록 하나하나의 시각으로 기간 밖 기록을 버린다** (앱이 오래된 파일을 건드리는 경우가 있고 — 실제 로그 29개 중 16개 — 한 세션이 여러 날에 걸치기도 함). 날짜는 이 PC의 현지 날짜로 센다
- 이어서 한 세션은 앞 기록을 새 파일에 복사한다 → 기록 `uuid`로 파일 사이 중복을 한 번만 센다
- 토큰: Claude는 같은 메시지 id의 사용량을 한 번만, Codex는 누적값의 기간 안 증가분만 (추론 토큰은 출력에 이미 포함)
- 실패한 편집은 반복 수정에 세지 않는다. 중단은 Claude `[Request interrupted`, Codex `turn_aborted`(interrupted)
- 깨진 줄·객체가 아닌 줄은 건너뛰고 수를 센다 → 보고서 하단 표시

### 사용자 프롬프트로 세지 않는 것 (실제 로그에서 확인)
- 하네스가 감싼 태그 블록(이름에 `-`·`_`가 있는 `<…>…</…>`)과 맨 앞 태그 블록은 지우고 남은 글자만 본다. 남은 게 없거나 `<`로 시작하면 프롬프트 아님 (`[Image #1] …`, `[긴급] …`은 프롬프트)
- 컨텍스트 압축 요약(`isCompactSummary`, "This session is being continued…")
- 하네스가 넣는 메시지: 스킬 본문("Base directory for this skill:"), 서브에이전트 보고("Another Claude session sent a message"), 스킬 재호출("(Re-invocation of"), 세션 인계("Background (from the session that started this one)")
- 중단은 `[Request interrupted` 텍스트로 센다
- Codex는 "My request for Codex:" 뒤의 글만 프롬프트

### 마스킹 (읽은 직후, 저장·출력 전)

| 대상 | 치환 |
|---|---|
| 키·토큰 (`sk-`, `ghp_`·`gho_`…, `github_pat_`, `AKIA…`, `xox?-`, JWT, PEM 개인키) | `[SECRET]` |
| `password=`, `token:` 같은 키-값 | 값만 `[SECRET]` |
| 이메일 (최상위 도메인이 영문자일 때만 — `react@18.3.1`은 그대로) | `[EMAIL]` |
| 홈 경로 (경로가 시작하는 위치의 `C:\Users\<이름>`, `/Users/<이름>`, `/home/<이름>`) | `~` |
| 숫자가 섞인 40자 이상 무작위 문자열 | `[REDACTED]` |

- 영문자·숫자 바로 뒤의 키 접두사는 키로 보지 않는다 (`task-management-system` 보존). 한글 바로 뒤는 키로 본다 (`키는sk-…야`)
- `src/app/users/page.tsx`처럼 경로 중간의 `users/`는 그대로 둔다

### 오류 시그니처
- 헤더 줄(`Exit code 1`, `Exit code: 1`, `Wall time:`, `Total output lines:`, `Output:`)을 건너뛴 첫 줄 → 마스킹 → 경로는 `<path>`, 숫자는 `N`
- 권한 거부("Permission to use…", "Permission for this…")는 `Permission denied` 하나로 묶는다
- Codex 실패 판정: 출력이 `Exit code: N`(N≠0) 텍스트, `{"metadata": {"exit_code"}}` JSON 문자열, `exit_code`를 가진 객체

### 분석 역할 분담

| 스크립트 | LLM |
|---|---|
| 숫자, 신호, 근거(세션·횟수·짧은 발췌) | 신호 해석, Top 3 선정, 개선 방법, 개념 설명 |

### 보고서
- 새 디자인: 밝은 테마 기본 + 시스템 다크 모드, 시스템 글꼴, CSS 막대, JS 없음, 외부 리소스 없음
- 섹션: 머리말 → 통계 타일 → 요약 → 일별 막대 → 작업 패턴 → 잘한 점 → 반복 문제(도구별 오류 막대 + 카드) → 다음에 해볼 것 → 하단(기간, 세션 수, 읽지 못한 줄, LLM 추정·마스킹 안내)
- 데이터 부족이면 통계 타일·일별 막대·"데이터 부족" 안내만

---

## 5. 다국어 지원

- 고정 문구는 `locales/<lang>.json`의 `labels`, 수정 요청 패턴은 `correction_patterns`
- 언어 선택: `--lang` > `analysis.lang` > `en`. `ko-KR`처럼 지역이 붙어도 앞부분(`ko`)으로 읽는다
- 누락 키는 `en.json`으로 대체, 모르는 언어도 `en`
- 수정 요청 탐지는 모든 locale 패턴을 합쳐 쓴다
- 본문(LLM 작성)은 `lang`으로. ko는 개념명에 영어 병기 — 예: "경쟁 조건(race condition)"
- 언어 추가 = JSON 1개 + eval 1개, 코드 수정 없음

---

## 6. 기술적 제약 · 주의사항

1. **로그 형식은 비공개이고 자주 바뀐다.** 모르는 레코드는 무시하고 계속 읽는다. 읽지 못한 줄 수를 보고서에 표시한다.
2. **Windows**: 경로 비교는 `Path.parts`로, 콘솔은 cp949라 출력 전에 UTF-8로 바꾼다, 임시 폴더는 `tempfile.gettempdir()`, `python`이 Microsoft Store 스텁일 수 있어 `uv run`을 쓴다.
3. **개인정보 한계**: 마스킹은 패턴 기반이라 완벽하지 않다. 다이제스트는 스킬을 실행하는 에이전트의 모델이 읽는다. SKILL.md와 보고서에 적는다.
4. **컨텍스트 크기**: 다이제스트의 세션 목록은 신호가 많은 순으로 60개까지.
5. **휴리스틱 오탐**: 수정 요청 정규식·오류 묶음은 추정치로 표시한다.
6. **LLM 개념 설명**: rubric 매핑 표로 방향을 잡고 외부 링크는 넣지 않는다.
7. **Codex 실행 (D3)**: SKILL.md의 명령은 스킬 폴더 기준 경로. Codex엔 SendUserFile이 없어 경로만 출력. Codex가 `~/.agents/skills/`를 읽는지는 실제로 확인해야 한다. 이 PC의 Codex 세션 하나가 프롬프트 0개로 집계됨 — 새 입력 형식일 수 있어 Codex 실행 때 확인.

---

## 7. 개발 순서

| 순서 | 작업 | 완료 기준 |
|---|---|---|
| 1 | `logs.py` | `tests/test_logs.py` 통과 (마스킹·시그니처·프롬프트 판정·오류 귀속) |
| 2 | `collect.py` | `tests/test_collect.py` 통과 (30일 필터, 반복 오류, 반복 수정, 빈 기간, 60개 상한) |
| 3 | `render_report.py` + locales | `tests/test_report.py` 통과 (이스케이프, 외부 요청 0, 데이터 부족, BOM) |
| 4 | SKILL.md·rubric·README·evals | 문서 검토 |
| 5 | 실제 로그로 1회 실행 | 보고서 확인 |
| 6 | Codex에서 1회 실행 | 스킬 인식, 같은 위치에 보고서 |

## 8. 추가 검토 필요

없음. 구현하면서 확인할 것: Codex 스킬 인식 위치와 Codex 새 입력 형식(§6-7).
