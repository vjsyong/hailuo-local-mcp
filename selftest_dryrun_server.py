"""INTERNAL TEST ONLY -- launched by selftest.py, never by WorkBuddy.

Imports the REAL server module, redirects its runtime files into a temp dir,
stubs every TokenHub HTTP call, then invokes the REAL `server.main()` STDIO
entrypoint. Exercise modes via SELFTEST_MODE so edge cases can be reproduced
offline with zero cloud spend.
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
MODE = os.environ.get("SELFTEST_MODE", "healthy")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Redirect runtime state away from the repo. Production reads no env vars;
# only this test harness does.
server.KEY_FILE = Path(os.environ["SELFTEST_KEY_FILE"])
server.OUTPUT_DIR = VIDEO_DIR
server.USAGE_FILE = VIDEO_DIR / "usage.jsonl"
server.PENDING_FILE = VIDEO_DIR / "pending.json"
if MODE == "poll_error":
    server.MAX_POLL_FAILURES = 0  # fail fast, no retry backoff in the test
if os.environ.get("SELFTEST_CORRUPT_PENDING") == "1":
    # A hand-edited/corrupt pending.json must never crash video_capabilities.
    server.PENDING_FILE.write_text('{"bad": 42, "junk": "text"}', encoding="utf-8")

_query_count = 0


def fake_submit(api_key, payload):
    if MODE == "submit_error":
        # Deliberately embeds the key to prove every returned error is redacted.
        raise PermissionError(f"HTTP 401: rejected Bearer {EXPECTED_KEY}")
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
    global _query_count
    _query_count += 1
    if MODE == "poll_error":
        raise RuntimeError("HTTP 503: simulated upstream failure")
    if MODE == "running":
        return {"status": "running", "video_url": "", "message": ""}
    if MODE == "unknown_status":
        return {"status": "mystery", "video_url": "", "message": ""}
    if MODE == "running_then_succeeded" and _query_count == 1:
        return {"status": "running", "video_url": "", "message": ""}
    return {
        "status": "succeeded",
        "video_url": "https://cdn.example.invalid/fake.mp4?sign=SECRET",
        "resolution": "768P", "duration": 4, "ratio": "16:9",
        "model": "MiniMax-H3", "total_tokens": 200000,
        "request_id": "selftest-req", "message": "",
    }


def fake_save(url, dest):
    if MODE == "save_error":
        raise RuntimeError("Result URL has expired; simulated download failure")
    Path(dest).write_bytes(b"\x00\x00\x00 ftypisom" + b"0" * 128)
    return dest


tokenhub.submit = fake_submit
tokenhub.query = fake_query
tokenhub.save_video = fake_save

if __name__ == "__main__":
    server.main()
