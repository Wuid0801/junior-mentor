"""Shared builders for synthetic Claude Code / Codex log rows."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

TS = "2026-11-18T01:00:00Z"


def say(text, ts=TS, **extra):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}, **extra}


def call(tid, name, mid=None, usage=None, **inp):
    msg = {"role": "assistant", "model": "claude-x",
           "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}
    if mid:
        msg["id"] = mid
    if usage:
        msg["usage"] = usage
    return {"type": "assistant", "message": msg}


def failed(tid, text):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": True, "content": text}]}}


def item(payload, kind="response_item"):
    return {"type": kind, "payload": payload}


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def jsonl(self, rows, name="session.jsonl", tail=b""):
        path = self.dir / name
        path.write_bytes(("\n".join(json.dumps(r) for r in rows) + "\n").encode("utf-8") + tail)
        return path
