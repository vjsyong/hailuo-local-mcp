"""No-cost check of the pasted TokenHub API key.

Queries a deliberately nonexistent task id. A task lookup creates NO video job,
so no generation credit is spent. Run with the repo's venv Python:

    .venv/Scripts/python.exe check_key.py      # Windows
    .venv/bin/python check_key.py             # macOS / Linux
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import tokenhub  # noqa: E402
from server import KEY_FILE, load_api_key  # noqa: E402


def main() -> int:
    print(f"Key file : {KEY_FILE}")
    print(f"Endpoint : GET {tokenhub.BASE_URL}{tokenhub.QUERY_PATH.format(task_id='<bogus>')}")
    print("Probe is a task lookup only -- no video is generated, no credit is spent.")
    print("-" * 70)
    try:
        api_key = load_api_key()
    except RuntimeError as exc:
        print(f"MISSING KEY - {exc}")
        return 1

    try:
        status, body = tokenhub.probe_key(api_key)
    except Exception as exc:
        print(f"INCONCLUSIVE - {type(exc).__name__}: {str(exc)[:200]}")
        return 1

    if status in (401, 403):
        print(f"INVALID KEY  [HTTP {status}] {body[:200]}")
        print("Paste the correct API key into api-key.txt (one line, no quotes).")
        return 1
    if status >= 500:
        print(f"INCONCLUSIVE  [HTTP {status}] {body[:200]}")
        return 1
    print(f"KEY VALID  [HTTP {status}; auth accepted, probe task not found] {body[:160]}")
    print("Ready. Ask your WorkBuddy agent to generate a video.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
