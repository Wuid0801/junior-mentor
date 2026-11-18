import json
import os
import unittest
from collections import Counter
from pathlib import Path

from helpers import TS, TempDirCase, call, failed, item, say
import logs  # noqa: E402  (helpers puts scripts/ on sys.path)


class MaskTest(unittest.TestCase):
    def test_masks_secrets_and_personal_data(self):
        cases = {
            "키는sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123야": "키는[SECRET]야",
            "token ghp_" + "a" * 36: "token [SECRET]",
            "AKIAABCDEFGHIJKLMNOP": "[SECRET]",
            "xoxb-1234-abcd-efgh": "[SECRET]",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123_-x": "[SECRET]",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIBOg\n-----END RSA PRIVATE KEY-----": "[SECRET]",
            "password=hunter2 다음": "password=[SECRET] 다음",
            "SECRET_KEY=django-insecure-abc123": "SECRET_KEY=[SECRET]",
            "DB_PASSWORD: hunter2": "DB_PASSWORD: [SECRET]",
            'api_key: "abc123"': "api_key: [SECRET]",
            "메일 dev.kim@example.com 로": "메일 [EMAIL] 로",
            r"C:\Users\홍길동\work\app.py": r"~\work\app.py",
            r"C:\\Users\\홍길동\\work": r"~\\work",
            "/Users/jane/proj/a.ts": "~/proj/a.ts",
            "/home/jane/proj": "~/proj",
            "seed " + "A1b2" * 11: "seed [REDACTED]",
            "sha " + "0123456789abcdef" * 3: "sha [REDACTED]",
        }
        for src, want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(logs.mask(src), want)

    def test_keeps_ordinary_text(self):
        for text in ("src/app/users/page.tsx", r"C:\proj\users\models.py", "GET /api/users/123",
                     "GET /users/123 에러", "fetch('/users/1')",
                     "task-management-system", "npm i react@18.3.1", "token: 만료되면 다시 로그인",
                     "test_user_profile_settings_panel_renders_v2_correctly",
                     "src/components/UserProfileSettingsPanel.tsx", "로그인 버그 고쳐줘"):
            with self.subTest(text=text):
                self.assertEqual(logs.mask(text), text)

    def test_own_home_is_replaced_by_whole_segment_only(self):
        home = str(Path.home())
        self.assertEqual(logs.mask(os.path.join(home, "x")), "~" + os.sep + "x")
        self.assertNotIn("~berly", logs.mask(home + "berly" + os.sep + "x"))


class ErrorTest(unittest.TestCase):
    def test_signature(self):
        cases = {
            "Error: Cannot find module 'react' at line 12": "Error: Cannot find module 'react' at line N",
            "  \nTypeError: x is undefined\n    at y": "TypeError: x is undefined",
            "Exit code 1\nnpm ERR! missing script: test": "npm ERR! missing script: test",
            "Exit code: 1\nWall time: 0.2 seconds\nTotal output lines: 40\nOutput:\nfatal: bad": "fatal: bad",
            "ENOENT: no such file '/home/kim/app/a.txt'": "ENOENT: no such file '<path>'",
            "Permission to use Bash with command rm -rf x has been denied.": "Permission denied",
            "Traceback (most recent call last):\n  File \"a.py\", line 3, in <module>\nKeyError: 'id'": "KeyError: 'id'",
            "======= test session starts =======\nFAILED tests/test_a.py::test_x - AssertionError":
                "FAILED <path> - AssertionError",
            "> app@0.1.0 build\n> next build\n\nError: Module not found": "Error: Module not found",
            ".": "",
            "/usr/local/lib/x.py": "",
            "x" * 300: "x" * logs.EXCERPT,
        }
        for src, want in cases.items():
            with self.subTest(src=src[:40]):
                self.assertEqual(logs.error_signature(src), want)

    def test_codex_error_text(self):
        self.assertEqual(logs.codex_error_text("Exit code: 1\nOutput:\nboom"), "Exit code: 1\nOutput:\nboom")
        self.assertIsNone(logs.codex_error_text("Exit code: 0\nOutput:\nok"))
        self.assertEqual(logs.codex_error_text(
            json.dumps({"output": "fatal: x", "metadata": {"exit_code": 128}})), "fatal: x")
        self.assertEqual(logs.codex_error_text({"exit_code": 2, "output": "bad"}), "bad")
        self.assertIsNone(logs.codex_error_text({"exit_code": 0}))
        self.assertIsNone(logs.codex_error_text([{"type": "input_text"}]))


class PromptTest(unittest.TestCase):
    def test_keeps_the_users_words(self):
        cases = {
            "<system-reminder>bg</system-reminder>\n파일 버그 고쳐줘": "파일 버그 고쳐줘",
            "고쳐줘\n<system-reminder>no, stop</system-reminder>": "고쳐줘",
            "<div>hi</div> 이 마크업 왜 깨져?": "이 마크업 왜 깨져?",
            "[Image #1] 이거 왜 깨져?": "[Image #1] 이거 왜 깨져?",
            "<Image /> 컴포넌트에서 사진이 안 떠": "<Image /> 컴포넌트에서 사진이 안 떠",
            "<branch-name>으로 체크아웃해줘": "<branch-name>으로 체크아웃해줘",
            "<command-name>/brainstorm</command-name>\n<command-args>로그인 아이디어</command-args>": "로그인 아이디어",
            '<pasted_content id="x1">\n로그인 기획서 정리해줘\n</pasted_content id="x1">': "로그인 기획서 정리해줘",
            '<system-reminder id="r1">bg</system-reminder id="r1">\n고쳐줘': "고쳐줘",
            "<environment_context>e</environment_context>\n## My request for Codex:\n스피너 작게": "스피너 작게",
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(logs.prompt_text(raw), want)

    def test_rejects_harness_turns(self):
        for raw in ("", "   ", "<command-name>/clear</command-name>",
                    "<command-name>/clear</command-name>\n<command-args></command-args>",
                    "This session is being continued from a previous conversation. no, stop",
                    "Base directory for this skill: ~/x\n\nno", "Another Claude session sent a message:\nwrong",
                    "(Re-invocation of /x — the skill instructions were previously loaded)",
                    "Background (from the session that started this one):\nstop",
                    "# AGENTS.md instructions for /x\n\n<INSTRUCTIONS>y</INSTRUCTIONS>",
                    "# AGENTS.md instructions\n\n<INSTRUCTIONS>y</INSTRUCTIONS>"):
            with self.subTest(raw=raw[:30]):
                self.assertIsNone(logs.prompt_text(raw))

    def test_correction_pattern(self):
        for text in ("아니 그게 아니라 버튼 색만 바꿔", "다시 해줘", "no, wrong, revert that",
                     "stop, that's not what I asked", "revert that"):
            self.assertTrue(logs.CORRECTION.search(text), text)
        for text in ("로그인 기능 만들어줘", "add a login page", "make sure there's no regression",
                     "add a stop button", "implement undo", "what's wrong with this test?"):
            self.assertFalse(logs.CORRECTION.search(text), text)


class ClaudeSessionTest(TempDirCase):
    def test_reads_prompts_errors_edits_and_tokens(self):
        usage = {"output_tokens": 10, "input_tokens": 1, "cache_read_input_tokens": 2}
        target = r"C:\Users\홍길동\proj\a.py"
        rows = [
            say("로그인 페이지 만들어줘", cwd=r"C:\Users\홍길동\proj"),
            call("t1", "Bash", mid="m1", usage=usage, command="npm test"),
            call("t2", "Edit", mid="m1", usage=usage, file_path=target),  # same answer, logged twice
            failed("t1", "Exit code 1\nError: Cannot find module 'react'"),
            failed("t2", "<tool_use_error>File has not been read yet</tool_use_error>"),
            call("t3", "mcp__browser__click"),
            failed("t3", "screenshot failed"),
            failed("t1", "[Tool call interrupted: the session ended]"),
            *[call(f"e{i}", "Edit", file_path=target) for i in range(4)],
            call("t4", "Read", usage={"output_tokens": 5}),  # no message id: counted
            call("t5", "Read", usage={"output_tokens": 5}),
            say("아니 그게 아니라 버튼 색만 바꿔"),
            say([{"type": "text", "text": "[Request interrupted by user]"}]),
            say("This session is being continued from a previous conversation. no, stop", isCompactSummary=True),
            say("<x>meta</x>", isMeta=True),
            say("Base directory for this skill: ~/x\n\nno, stop"),
            {"type": "api-request", "x": 1},
            {"type": "user", "message": "plain string"},
            {"type": "assistant", "message": {"role": "assistant", "model": "<synthetic>", "content": []}},
        ]
        s = logs.read_session(self.jsonl(rows, tail=b"\xff\xfe{broken\nnull\n[]\n\n"))
        self.assertEqual(s.source, "claude")
        self.assertEqual(s.prompts, ["로그인 페이지 만들어줘", "아니 그게 아니라 버튼 색만 바꿔"])
        self.assertEqual(s.corrections, ["아니 그게 아니라 버튼 색만 바꿔"])
        self.assertEqual(s.interrupts, 1)
        self.assertEqual(s.errors, Counter({"Bash": 1}))
        self.assertEqual(s.error_sigs, Counter({"Error: Cannot find module 'react'": 1}))
        self.assertEqual(s.edits, Counter({r"~\proj\a.py": 4}))  # the failed t2 edit does not count
        self.assertEqual(s.days, Counter({logs.local_day(TS): 2}))
        self.assertEqual((s.tools["Edit"], s.tools["Bash"]), (5, 1))
        self.assertEqual((s.out_tokens, s.in_tokens), (20, 3))
        self.assertEqual(s.models, {"claude-x"})
        self.assertEqual(s.cwd, r"~\proj")
        self.assertEqual(s.bad_lines, 3)
        self.assertEqual(s.last_ts, "2026-11-18T01:00:00Z")


class CodexSessionTest(TempDirCase):
    def test_reads_response_item_prompts_errors_and_cumulative_tokens(self):
        rows = [
            {"type": "session_meta", "timestamp": "2026-11-18T01:00:00Z",
             "payload": {"type": "session_meta", "cwd": "/home/kim/app"}},
            {"type": "turn_context", "payload": {"type": "turn_context", "model": "gpt-x"}},
            *[item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": t}]})
              for t in ("# AGENTS.md instructions for /x\n\n<INSTRUCTIONS>y</INSTRUCTIONS>",
                        "<environment_context>e</environment_context>", "차트 범례를 오른쪽으로 옮겨줘")],
            item({"type": "function_call", "call_id": "c1", "name": "shell"}),
            item({"type": "function_call_output", "call_id": "c1",
                  "output": "Exit code: 1\nWall time: 1s\nOutput:\nnpm ERR! missing script: test"}),
            item({"type": "custom_tool_call", "call_id": "c2", "name": "exec"}),
            item({"type": "custom_tool_call_output", "call_id": "c2",
                  "output": json.dumps({"output": "fatal: not a git repository", "metadata": {"exit_code": 128}})}),
            item({"type": "function_call", "call_id": "c3", "name": "shell"}),
            item({"type": "function_call_output", "call_id": "c3", "output": "Exit code: 0\nOutput:\nok"}),
            item({"type": "function_call", "call_id": "c4", "name": "mcp__browser__open"}),
            item({"type": "function_call_output", "call_id": "c4", "output": "Exit code: 1\nOutput:\nx"}),
            item({"type": "patch_apply_end", "changes": {"/home/kim/app/a.ts": {}, "/home/kim/app/b.ts": {}}},
                 kind="event_msg"),
            item({"type": "turn_aborted", "reason": "interrupted"}, kind="event_msg"),
            item({"type": "token_count", "info": {"total_token_usage": {
                "output_tokens": 50, "reasoning_output_tokens": 20, "input_tokens": 200}}}, kind="event_msg"),
            item({"type": "token_count", "info": {"total_token_usage": {
                "output_tokens": 80, "reasoning_output_tokens": 20, "input_tokens": 300}}}, kind="event_msg"),
        ]
        s = logs.read_session(self.jsonl(rows, name="rollout-2026-11-18-x.jsonl"))
        self.assertEqual(s.source, "codex")
        self.assertEqual(s.prompts, ["차트 범례를 오른쪽으로 옮겨줘"])
        self.assertEqual(s.errors, Counter({"shell": 1, "exec": 1}))
        self.assertEqual(set(s.error_sigs), {"npm ERR! missing script: test", "fatal: not a git repository"})
        self.assertEqual(s.edits, Counter({"~/app/a.ts": 1, "~/app/b.ts": 1}))
        self.assertEqual((s.out_tokens, s.in_tokens), (80, 300))  # reasoning is inside output_tokens
        self.assertEqual((s.models, s.cwd), ({"gpt-x"}, "~/app"))
        self.assertEqual(s.interrupts, 1)

    def test_user_message_events_win_over_response_items(self):
        rows = [item({"type": "user_message", "message": "차트 고쳐줘"}, kind="event_msg"),
                item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "차트 고쳐줘"}]})]
        s = logs.read_session(self.jsonl(rows, name="rollout-y.jsonl"))
        self.assertEqual(s.prompts, ["차트 고쳐줘"])


class WindowAndCopyTest(TempDirCase):
    SINCE = "2026-01-01T00:00:00"

    def test_records_before_the_window_are_skipped(self):
        path = self.jsonl([say("old", ts="2020-01-01T00:00:00Z"), say("new")])
        s = logs.read_session(path, since=self.SINCE)
        self.assertEqual((s.prompts, s.first_ts), (["new"], TS))

    def test_codex_tokens_count_only_growth_inside_the_window(self):
        def tokens(ts, out, inp):
            return {"type": "event_msg", "timestamp": ts, "payload": {"type": "token_count", "info": {
                "total_token_usage": {"output_tokens": out, "input_tokens": inp}}}}
        path = self.jsonl([tokens("2020-01-01T00:00:00Z", 30, 100), tokens(TS, 80, 300)], name="rollout-w.jsonl")
        s = logs.read_session(path, since=self.SINCE)
        self.assertEqual((s.out_tokens, s.in_tokens), (50, 200))

    def test_records_copied_into_a_resumed_session_count_once(self):
        first = self.jsonl([say("원본", uuid="u1")], name="a.jsonl")
        resumed = self.jsonl([say("원본", uuid="u1"), say("이어서", uuid="u2")], name="b.jsonl")
        seen = set()
        self.assertEqual(logs.read_session(first, seen=seen).prompts, ["원본"])
        self.assertEqual(logs.read_session(resumed, seen=seen).prompts, ["이어서"])

    def test_cwd_comes_from_skipped_records_too(self):
        path = self.jsonl([say("old", ts="2020-01-01T00:00:00Z", cwd="/srv/app"), say("new")])
        self.assertEqual(logs.read_session(path, since=self.SINCE).cwd, "/srv/app")


class FindLogsTest(TempDirCase):
    def test_skips_subagents_and_non_rollout_files(self):
        for rel in ("claude/p/a.jsonl", "claude/p/s/subagents/b.jsonl", "claude/p/tool-results/c.jsonl",
                    "codex/sessions/2026/11/18/rollout-1.jsonl", "codex/archived_sessions/rollout-2.jsonl",
                    "codex/sessions/other.jsonl"):
            path = self.dir.joinpath(*rel.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        claude, codex = self.dir / "claude", self.dir / "codex"
        names = sorted(p.name for p in logs.find_logs("both", claude, codex))
        self.assertEqual(names, ["a.jsonl", "rollout-1.jsonl", "rollout-2.jsonl"])
        self.assertEqual([p.name for p in logs.find_logs("claude", claude, codex)], ["a.jsonl"])


if __name__ == "__main__":
    unittest.main()
