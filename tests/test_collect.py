import unittest
from datetime import datetime, timezone
from unittest import mock

from helpers import TempDirCase, call, failed, say
import collect  # noqa: E402  (helpers puts scripts/ on sys.path)
from logs import local_day  # noqa: E402

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CollectTest(TempDirCase):
    def sessions(self):
        paths = [self.jsonl([say("테스트 돌려줘", ts=NOW), call("t", "Bash"),
                             failed("t", f"Error: Cannot find module 'react' at line {i}")], f"s{i}.jsonl")
                 for i in (1, 2, 3)]
        paths.append(self.jsonl([say("리팩터링", ts=NOW)] +
                                [call(f"e{k}", "Edit", file_path="/home/kim/app/a.py") for k in range(5)],
                                "s4.jsonl"))
        paths += [self.jsonl([say("hello", ts=NOW)], f"s{i}.jsonl") for i in (5, 6)]
        # file modified now, but the conversation is years old: outside the window
        paths.append(self.jsonl([say("old", ts="2020-01-01T00:00:00Z")], "s7.jsonl"))
        paths.append(self.jsonl([{"type": "summary"}], "s8.jsonl"))  # nothing in it
        return paths

    def test_aggregates_signals_inside_the_window(self):
        st = collect.collect("claude", 30, files=self.sessions())
        self.assertEqual(st["totals"]["sessions"], 6)
        self.assertTrue(st["enough_data"])
        self.assertEqual(st["totals"]["tool_errors"], 3)
        self.assertEqual(st["tool_errors"], {"Bash": 3})
        self.assertEqual(st["repeated_errors"], [
            {"signature": "Error: Cannot find module 'react' at line N", "count": 3, "sessions": 3}])
        self.assertEqual((st["churn"][0]["file"], st["churn"][0]["edits"]), ("~/app/a.py", 5))
        self.assertEqual(st["languages"], {"Python": 1})
        self.assertEqual(st["per_day"], {local_day(NOW): 6})
        self.assertEqual(st["span"]["active_days"], 1)

    def test_resumed_session_copies_are_counted_once(self):
        first = self.jsonl([say("원본", ts=NOW, uuid="u1")], "a.jsonl")
        resumed = self.jsonl([say("원본", ts=NOW, uuid="u1"), say("이어서", ts=NOW, uuid="u2")], "b.jsonl")
        st = collect.collect("claude", 30, files=[first, resumed])
        self.assertEqual((st["totals"]["sessions"], st["totals"]["prompts"]), (2, 2))

    def test_empty_window_is_not_enough_data(self):
        st = collect.collect("claude", 30, files=[])
        self.assertEqual(st["totals"].get("sessions", 0), 0)
        self.assertFalse(st["enough_data"])
        self.assertTrue(collect.digest(st).startswith("NOT ENOUGH DATA"))

    def test_digest_lists_at_most_60_sessions(self):
        st = collect.collect("claude", 30, files=self.sessions())
        many = dict(st, sessions=[dict(st["sessions"][0], file=f"x{i}") for i in range(70)])
        out = collect.digest(many)
        self.assertEqual(out.count("[claude]"), 60)
        self.assertIn("10 more sessions omitted", out)
        self.assertIn("Problem signals", out)
        self.assertIn("0 out / 0 in tokens", out)  # per-session input tokens are evidence too

    def test_main_removes_last_runs_analysis(self):
        stale = self.dir / collect.ANALYSIS_NAME
        stale.write_text("{}", encoding="utf-8")
        with mock.patch("collect.find_logs", return_value=[]):
            collect.main(["--out", str(self.dir / "stats.json")])
        self.assertFalse(stale.exists())
        self.assertTrue((self.dir / "stats.json").exists())


if __name__ == "__main__":
    unittest.main()
