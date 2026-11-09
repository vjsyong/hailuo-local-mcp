"""No-cost check of the pasted single TokenHub API key.

Queries a deliberately nonexistent task id. A task lookup creates NO video job,
so no generation credit is spent. Never prints the key or an upstream body.

    .venv/Scripts/python.exe check_key.py      # Windows
    .venv/bin/python check_key.py             # macOS / Linux
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import keyfile  # noqa: E402
import tokenhub  # noqa: E402

KEY_FILE = BASE / "api-key.txt"


def main() -> int:
    print(f"Key file : {KEY_FILE}")
    print(f"Endpoint : GET {tokenhub.BASE_URL}{tokenhub.QUERY_PATH.format(task_id='<bogus>')}")
    print("Probe is a task lookup only -- no video is generated, no credit is spent.")
    print("-" * 70)
    try:
        api_key = keyfile.read_api_key(KEY_FILE)
    except keyfile.KeyFileError as exc:
        print(f"MISSING KEY - {exc}")
        return 1

    try:
        status = tokenhub.probe_key(api_key)
    except Exception as exc:
        print(f"INCONCLUSIVE - could not reach TokenHub ({type(exc).__name__}).")
        print("Setup itself can still be complete; check your network and re-run this probe.")
        return 1

    # Strict classification. A REAL valid key returns 400 "Task is not exist."
    # Anything else (404, 200, 3xx, 408, 429, 5xx) must never be called valid.
    if status in (401, 403):
        print(f"INVALID KEY  [HTTP {status}]")
        print("Paste the correct single API key into api-key.txt (one line, no quotes).")
        return 1
    if status == 429:
        print("THROTTLED  [HTTP 429] - auth was accepted but the group is rate-limited. Try later.")
        return 1
    if status >= 500:
        print(f"INCONCLUSIVE  [HTTP {status}] - TokenHub is temporarily unavailable. Retry later.")
        return 1
    if status == 400:
        print("KEY VALID  [HTTP 400; auth accepted, probe task not found]")
        print("Ready. Ask your WorkBuddy agent to generate a video.")
        return 0
    print(f"INCONCLUSIVE  [HTTP {status}] - unexpected status; check TOKENHUB endpoint/network.")
    print("Do NOT assume the key is valid. Re-run this probe before generating.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
