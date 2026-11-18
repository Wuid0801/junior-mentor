import json
import unittest

from helpers import TempDirCase
import render_report as rr  # noqa: E402  (helpers puts scripts/ on sys.path)

STATS = {
    "agent": "both", "days": 30, "generated": "2026-11-18T00:00:00+00:00",
    "span": {"first": "2026-11-17", "last": "2026-11-18", "active_days": 2},
    "totals": {"sessions": 6, "prompts": 20, "tool_calls": 50, "files": 4, "out_tokens": 12000, "tool_errors": 3},
    "per_day": {"2026-11-17": 5, "2026-11-18": 15}, "tools": {"Bash": 30}, "languages": {"Python": 4},
    "models": ["m"], "tool_errors": {"Bash": 3}, "unreadable": {"lines": 2, "files": 0}, "enough_data": True,
}
ANALYSIS = {"lang": "ko", "summary": "요약", "sections": {
    "patterns": {"topics": [{"topic": "웹", "detail": "d", "share": "~50%"}], "habits": ["h"]},
    "strengths": ["s"], "tips": ["t"],
    "problems": [{"problem": "<script>alert(1)</script>", "evidence": "Bash 오류 3회", "why": "w", "fix": "f",
                  "concept": {"name": "최소 재현(minimal reproduction)", "explain": "x"}}]}}


class RenderTest(TempDirCase):
    def test_korean_report_is_escaped_and_offline(self):
        out = rr.render(STATS, ANALYSIS, "ko")
        self.assertIn('<html lang="ko">', out)
        self.assertIn(rr.labels("ko")["s_prob"], out)
        self.assertIn("최소 재현(minimal reproduction)", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script", out)  # no JS at all, and the model's text is escaped
        self.assertNotRegex(out, r'(src|href)\s*=\s*"https?:')
        self.assertNotIn("@import", out)

    def test_labels_fall_back_to_english_and_match(self):
        self.assertEqual(rr.labels("xx"), rr.labels("en"))
        keys = {code: set(json.loads((rr.LOCALES / f"{code}.json").read_text(encoding="utf-8"))["labels"])
                for code in ("en", "ko")}
        self.assertEqual(keys["ko"], keys["en"])

    def test_low_data_shows_numbers_only(self):
        en = rr.labels("en")
        out = rr.render(dict(STATS, enough_data=False), {}, "en")
        self.assertIn(en["low_data"], out)
        self.assertNotIn(en["s_prob"], out)

    def test_odd_inputs_do_not_crash(self):
        rr.render({}, {}, "en")
        out = rr.render(STATS, {"sections": {"problems": ["문제 하나"], "patterns": ["x"]}}, "ko-KR")
        self.assertIn('<html lang="ko">', out)
        self.assertIn("문제 하나", out)

    def test_main_reads_analysis_with_bom(self):
        stats, analysis, report = self.dir / "s.json", self.dir / "a.json", self.dir / "r.html"
        stats.write_text(json.dumps(STATS), encoding="utf-8")
        analysis.write_text(json.dumps(ANALYSIS), encoding="utf-8-sig")
        rr.main(["--stats", str(stats), "--analysis", str(analysis), "--out", str(report)])
        self.assertIn('<html lang="ko">', report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
