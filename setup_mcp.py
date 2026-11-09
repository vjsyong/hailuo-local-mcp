"""One-command setup for the LOCAL Hailuo video MCP server.

Run with any Python 3.11+ (stdlib only -- this script needs no dependencies):

    python setup_mcp.py                 # set up + write mcp.local.json (safe)
    python setup_mcp.py --install       # also merge into ~/.workbuddy-ai/mcp.json
    python setup_mcp.py --check         # just validate this install
    python setup_mcp.py --verify-key    # also make one no-cost TokenHub auth probe

What it does:
  1. Creates api-key.txt from the example if missing (student pastes the key there).
  2. Creates a private .venv and installs requirements.txt into it.
  3. Verifies the MCP SDK and server import correctly.
  4. Generates a WorkBuddy STDIO MCP config with ABSOLUTE paths (no secrets).
  5. With --install, merges that block into ~/.workbuddy-ai/mcp.json, backing up
     the old file first and preserving every other server.

The API key is NEVER written into any config, printed, or committed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
KEY_FILE = BASE / "api-key.txt"
KEY_EXAMPLE = BASE / "api-key.example.txt"
VENV_DIR = BASE / ".venv"
REQUIREMENTS = BASE / "requirements.txt"
LOCAL_CONFIG = BASE / "mcp.local.json"
WORKBUDDY_CONFIG = Path.home() / ".workbuddy-ai" / "mcp.json"
SERVER_NAME = "hailuo-video"
PLACEHOLDER_MARKERS = ("PASTE_", "YOUR_API_KEY", "REPLACE_WITH", "EXAMPLE")


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def read_key() -> str | None:
    key = os.environ.get("TOKENHUB_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key or any(m in key.upper() for m in PLACEHOLDER_MARKERS):
        return None
    return key


def ensure_key() -> bool:
    if not KEY_FILE.exists():
        KEY_FILE.write_text(KEY_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print("[!] Created api-key.txt")
        print(f"    -> Paste your single TokenHub API key into: {KEY_FILE}")
        print("    -> Then re-run this command. This is the ONLY manual step.")
        return False
    if read_key() is None:
        print("[!] api-key.txt still contains the placeholder.")
        print(f"    -> Paste your single TokenHub API key into: {KEY_FILE}")
        print("    -> One line only, no quotes, no 'Bearer ' prefix.")
        return False
    print("[ok] api-key.txt contains a key (value never displayed)")
    return True


def ensure_venv() -> None:
    py = venv_python()
    if not py.exists():
        print("[..] creating .venv")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    print("[..] installing dependencies (quiet)")
    subprocess.check_call(
        [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "-r", str(REQUIREMENTS)],
        cwd=str(BASE),
    )
    subprocess.check_call(
        [str(py), "-c", "import mcp, httpx, tokenhub, server; print('imports ok')"],
        cwd=str(BASE),
        stdout=subprocess.DEVNULL,
    )
    print("[ok] .venv ready, MCP SDK + server import cleanly")


def build_block() -> dict:
    return {
        SERVER_NAME: {
            "command": str(venv_python()),
            "args": [str(BASE / "server.py")],
        }
    }


def install_into_workbuddy(block: dict) -> None:
    WORKBUDDY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if WORKBUDDY_CONFIG.exists():
        try:
            data = json.loads(WORKBUDDY_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[!!] {WORKBUDDY_CONFIG} is not valid JSON; refusing to overwrite it.")
            raise SystemExit(1)
        backup = Path(str(WORKBUDDY_CONFIG) + ".bak." + time.strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(WORKBUDDY_CONFIG, backup)
        print(f"[ok] backed up existing config -> {backup.name}")
    else:
        data = {}
    servers = data.setdefault("mcpServers", {})
    servers[SERVER_NAME] = block[SERVER_NAME]
    WORKBUDDY_CONFIG.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[ok] merged '{SERVER_NAME}' into {WORKBUDDY_CONFIG}")


def verify_key() -> int:
    return subprocess.call([str(venv_python()), str(BASE / "check_key.py")], cwd=str(BASE))


def main() -> int:
    ap = argparse.ArgumentParser(description="Set up the local Hailuo video MCP server.")
    ap.add_argument("--install", action="store_true", help="merge the config into ~/.workbuddy-ai/mcp.json")
    ap.add_argument("--check", action="store_true", help="validate this install and exit")
    ap.add_argument("--verify-key", action="store_true", help="run one no-cost TokenHub auth probe")
    args = ap.parse_args()

    print(f"Repo      : {BASE}")
    print(f"Key file  : {KEY_FILE}")
    print("-" * 70)

    if args.check:
        ok = ensure_key() and venv_python().exists()
        if ok:
            print("[ok] install looks complete")
        else:
            print("[!!] install incomplete -- run: python setup_mcp.py --install")
        return 0 if ok else 1

    if not ensure_key():
        return 1

    ensure_venv()
    block = build_block()
    LOCAL_CONFIG.write_text(
        json.dumps({"mcpServers": block}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] wrote paste-ready config -> {LOCAL_CONFIG}")

    if args.install:
        install_into_workbuddy(block)
        print("\nNEXT (one-time, in WorkBuddy): open Connectors in the left sidebar ->")
        print("Custom Connector in the top-right -> click 'Trust' on hailuo-video.")
        print("The connector does NOT activate automatically.")
    else:
        print("\nConfig was NOT installed. Paste the block from mcp.local.json into")
        print(f"{WORKBUDDY_CONFIG}, or re-run with --install.")
        print("Then open Connectors -> Custom Connector -> 'Trust' on hailuo-video.")

    if args.verify_key:
        print("\n--- no-cost key probe ---")
        if verify_key() != 0:
            return 1

    print("\nSETUP OK. Ask your agent: 'generate a 4 second video of a cat on a desk'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
