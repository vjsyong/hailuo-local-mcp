"""INTERNAL TEST ONLY -- launched by selftest.py, never by WorkBuddy.

Starts the real STDIO MCP server with all TokenHub HTTP calls stubbed out, so
the MCP handshake, tool registration, payload construction, polling, auth, and
local MP4 writing are exercised end-to-end with ZERO credit spent.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import tokenhub  # noqa: E402
import server  # noqa: E402

DUMP = Path(os.environ["SELFTEST_DUMP"])
VIDEO_DIR = Path(os.environ["SELFTEST_VIDEO_DIR"])
EXPECTED_KEY = os.environ.get("SELFTEST_EXPECTED_KEY", "")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Redirect all runtime output into the temp dir, away from the repo.
server.OUTPUT_DIR = VIDEO_DIR
server.USAGE_FILE = VIDEO_DIR / "usage.jsonl"


def fake_submit(api_key, payload):
    # Record a boolean only -- never write any key-like value to disk.
    DUMP.write_text(
        json.dumps({
            "key_seen": bool(api_key),
            "key_matches_file": bool(EXPECTED_KEY) and api_key == EXPECTED_KEY,
            "payload": payload,
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return "DRYRUN-TASK-1"


def fake_query(api_key, task_id):
    return {
        "status": "succeeded",
        "video_url": "https://example.invalid/fake.mp4",
        "resolution": "768P",
        "duration": 4,
        "ratio": "16:9",
        "model": "MiniMax-H3",
        "total_tokens": 200000,
        "request_id": "selftest-req",
        "message": "",
    }


def fake_save(url, dest):
    Path(dest).write_bytes(b"\x00\x00\x00 ftypisom" + b"0" * 128)
    return dest


tokenhub.submit = fake_submit
tokenhub.query = fake_query
tokenhub.save_video = fake_save

if __name__ == "__main__":
    server.mcp_server.run(transport="stdio")
