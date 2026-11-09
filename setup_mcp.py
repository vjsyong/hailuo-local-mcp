"""One-command setup for the LOCAL Hailuo video MCP server.

Run with Python 3.10+ (stdlib only -- this script needs no dependencies).

    Windows:          python setup_mcp.py --install --verify-key
    macOS / Linux:    python3 setup_mcp.py --install --verify-key

ONE KEY PER GROUP. Setup is single-pass: it completes fully even before the key
has been pasted. `server.py` reads `api-key.txt` on every tool call, so a
student can paste (or rotate) the key at any time with no restart and no second
setup run.

Side effects, in order:
  1. Creates api-key.txt from the example if a fresh clone lacks it (gitignored;
     this is the ONLY file a student edits).
  2. Creates .venv and installs requirements.txt (skipped if already present).
  3. Verifies the MCP SDK, client and server import cleanly.
  4. Writes mcp.local.json with absolute command/args (NO secrets, NO env).
  5. With --install, merges that block into the WorkBuddy MCP config(s), backing
     up first, preserving every other server, and reading the file back to
     verify. Also installs a local pre-commit guard against committing the key.
  6. With --verify-key, makes ONE no-cost TokenHub probe (skipped if no key yet).
     A failed/inconclusive probe NEVER fails the install.

The single key is never written into any config, printed, or committed. There
are no environment-variable key or endpoint overrides anywhere in this package.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import keyfile

BASE = Path(__file__).resolve().parent
KEY_FILE = BASE / "api-key.txt"
KEY_EXAMPLE = BASE / "api-key.example.txt"
VENV_DIR = BASE / ".venv"
REQUIREMENTS = BASE / "requirements.txt"
LOCAL_CONFIG = BASE / "mcp.local.json"
SERVER_NAME = "hailuo-video"
MIN_PYTHON = (3, 10)
LEGACY_ENV_VARS = (
    "TOKENHUB_API_KEY", "TOKENHUB_KEY_FILE", "TOKENHUB_BASE_URL",
    "TOKENHUB_MODEL", "MAX_VIDEOS_PER_DAY",
)

PRECOMMIT_HOOK = """#!/bin/sh
# Installed by setup_mcp.py --install. Blocks accidental API-key commits.
staged=$(git diff --cached --name-only 2>/dev/null) || exit 0
case "$staged" in
  *api-key.txt*)
    echo "BLOCKED: api-key.txt holds your API key and must never be committed." >&2
    exit 1 ;;
esac
case "$staged" in
  *api-key.example.txt*)
    echo "BLOCKED: api-key.example.txt is a tracked template. Paste your key into api-key.txt instead." >&2
    exit 1 ;;
esac
exit 0
"""


class SetupError(RuntimeError):
    """A clean, actionable setup failure (never a raw traceback)."""


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def config_paths() -> list[Path]:
    """Canonical path, plus the alternate path if that WorkBuddy dir exists.

    WorkBuddy builds have been documented with both locations. Writing both
    (only when the parent dir exists) avoids a silent 'SETUP OK' where the
    connector never appears.
    """
    paths = [Path.home() / ".workbuddy-ai" / "mcp.json"]
    alternate = Path.home() / ".workbuddy" / "mcp.json"
    if alternate.parent.is_dir():
        paths.append(alternate)
    return paths


def read_key() -> str | None:
    """The one key lives in api-key.txt only. No env var, no second source."""
    return keyfile.read_key_optional(KEY_FILE)


def warn_legacy_env() -> None:
    """Older builds accepted env overrides; they no longer do. Say so out loud."""
    found = [name for name in LEGACY_ENV_VARS if os.environ.get(name)]
    if found:
        print("[!!] Ignored legacy environment variables: " + ", ".join(found))
        print("     This version reads ONLY api-key.txt. Unset them to avoid confusion.")


def ensure_key_file() -> bool:
    """Create api-key.txt on a fresh clone. Return True if ONE real key is pasted."""
    if not KEY_FILE.exists():
        try:
            template = KEY_EXAMPLE.read_text(encoding="utf-8")
        except OSError:
            template = "PASTE_YOUR_TOKENHUB_API_KEY_HERE\n"
        KEY_FILE.write_text(template, encoding="utf-8")
        print("[!] Created api-key.txt -- this is the ONLY file you ever edit")
        print(f"    -> Paste your group's single API key into: {KEY_FILE}")
        print("    -> One line only, UTF-8, no quotes, no 'Bearer ' prefix.")
    if read_key() is None:
        print("[!] api-key.txt has no key yet (setup continues).")
        print(f"    -> Paste your group's single API key into {KEY_FILE} when ready.")
        print("    -> No restart needed: the server reads the file on every call.")
        return False
    print("[ok] ONE API key found in api-key.txt (value never displayed)")
    return True


def _imports_ok(py: Path) -> bool:
    try:
        return subprocess.call(
            [str(py), "-c", "import mcp, httpx, tokenhub, server, keyfile"],
            cwd=str(BASE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) == 0
    except OSError:
        return False


def ensure_venv() -> None:
    py = venv_python()
    if not py.exists():
        print("[..] creating .venv")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=str(BASE))
        except (subprocess.CalledProcessError, OSError) as exc:
            raise SetupError(
                "Could not create .venv. Use a Python 3.10+ build that includes venv "
                "(Ubuntu/Debian: sudo apt install python3-venv; macOS: install Python from "
                "python.org or Homebrew, then `xcode-select --install`) and re-run setup."
            ) from exc
    if _imports_ok(py):
        print("[ok] .venv ready (dependencies already installed)")
        return

    wheelhouse = os.environ.get("HAILUO_WHEELHOUSE", "").strip()
    cmd = [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    if wheelhouse:
        cmd += ["--no-index", "--find-links", wheelhouse]
        print(f"[..] installing from offline wheelhouse: {wheelhouse}")
    else:
        print("[..] installing dependencies (first run needs network access)")
    cmd += ["-r", str(REQUIREMENTS)]
    try:
        subprocess.check_call(cmd, cwd=str(BASE))
    except (subprocess.CalledProcessError, OSError) as exc:
        raise SetupError(
            "Dependency install failed. This first run needs PyPI access (or a "
            "corporate proxy). Offline alternative: point HAILUO_WHEELHOUSE at a "
            "folder of wheels and re-run. Details: " + type(exc).__name__
        ) from exc
    if not _imports_ok(py):
        raise SetupError("Dependencies installed but imports still fail. Re-run setup with --check.")
    print("[ok] .venv ready, MCP SDK + server import cleanly")


def build_block() -> dict:
    # .as_posix() keeps Windows paths safe when a human copy/pastes the JSON.
    return {
        SERVER_NAME: {
            "command": venv_python().as_posix(),
            "args": [(BASE / "server.py").as_posix()],
        }
    }


def _backup(path: Path) -> None:
    try:
        stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        backup = path.with_name(path.name + ".bak." + stamp)
        shutil.copy2(path, backup)
        try:
            os.chmod(backup, 0o600)
        except OSError:
            pass
        old = sorted(path.parent.glob(path.name + ".bak.*"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in old[5:]:
            try:
                stale.unlink()
            except OSError:
                pass
    except OSError as exc:
        print(f"[!!] could not back up {path}: {exc}")


def _merge_one(path: Path, entry: dict) -> str:
    """Merge into one config, tolerating every malformed shape. Never raises."""
    note = ""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            _backup(path)
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError):
                data = {}
                note += " (existing file was not valid JSON; replaced)"
            if not isinstance(data, dict):
                data = {}
                note += " (existing root was not an object; replaced)"
        else:
            data = {}
        had_servers_key = isinstance(data, dict) and "mcpServers" in data
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
            data["mcpServers"] = servers
            if had_servers_key:
                note += " (mcpServers was not an object; reset)"
        servers[SERVER_NAME] = entry

        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        readback = json.loads(path.read_text(encoding="utf-8"))
        servers_back = readback.get("mcpServers") if isinstance(readback, dict) else None
        ok = isinstance(servers_back, dict) and SERVER_NAME in servers_back
        return f"[{'ok' if ok else '!!'}] {path}{note}"
    except Exception as exc:
        return f"[!!] {path}: {type(exc).__name__}: {exc}"


def install_into_workbuddy(block: dict) -> list[str]:
    return [_merge_one(path, block[SERVER_NAME]) for path in config_paths()]


def uninstall_from_workbuddy() -> list[str]:
    """Remove ONLY our entry, backing up first. Never deletes the config file."""
    out: list[str] = []
    for path in config_paths():
        try:
            if not path.exists():
                out.append(f"[--] {path} (absent)")
                continue
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict) or not isinstance(data.get("mcpServers"), dict):
                out.append(f"[--] {path} (no mcpServers object; left untouched)")
                continue
            if SERVER_NAME not in data["mcpServers"]:
                out.append(f"[--] {path} (entry absent)")
                continue
            _backup(path)
            data["mcpServers"].pop(SERVER_NAME, None)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, path)
            out.append(f"[ok] removed {SERVER_NAME} from {path}")
        except Exception as exc:
            out.append(f"[!!] {path}: {type(exc).__name__}: {exc}")
    return out


def install_precommit_guard() -> str:
    git_dir = BASE / ".git"
    if not git_dir.is_dir():
        return "[--] no .git directory; pre-commit guard skipped"
    hooks = git_dir / "hooks"
    target = hooks / "pre-commit"
    try:
        hooks.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return "[--] existing pre-commit hook left untouched"
        with target.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(PRECOMMIT_HOOK)
        try:
            os.chmod(target, 0o755)
        except OSError:
            pass
        return "[ok] installed pre-commit guard (blocks committing api-key.txt)"
    except Exception as exc:
        return f"[!!] pre-commit guard not installed: {type(exc).__name__}"


def verify_key() -> int:
    try:
        return subprocess.call([str(venv_python()), str(BASE / "check_key.py")], cwd=str(BASE))
    except OSError:
        return 1


def _check_status() -> int:
    installed = venv_python().exists() and LOCAL_CONFIG.exists() and _imports_ok(venv_python())
    has_key = read_key() is not None
    print("[ok] install looks complete" if installed
          else "[!!] install incomplete -- run setup_mcp.py --install")
    print(f"[{'ok' if has_key else '!!'}] key: "
          f"{'ONE key present in api-key.txt' if has_key else 'paste your single key into api-key.txt'}")
    for path in config_paths():
        present = False
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                present = SERVER_NAME in (data.get("mcpServers") or {}) if isinstance(data, dict) else False
        except (ValueError, OSError):
            present = False
        print(f"[{'ok' if present else '!!'}] connector entry: {path}")
    return 0 if installed else 1


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"SETUP INCOMPLETE: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required "
              f"(found {sys.version.split()[0]}). Install a newer Python and re-run.")
        if sys.platform == "darwin":
            print("macOS: Xcode Command Line Tools ship Python 3.9 only. Install Python 3.10+ "
                  "from https://www.python.org/downloads/macos/ or `brew install python@3.12`, "
                  "then run `python3 setup_mcp.py --install --verify-key` again.")
        return 1

    ap = argparse.ArgumentParser(description="Set up the local Hailuo video MCP server.")
    ap.add_argument("--install", action="store_true", help="merge the config into the WorkBuddy MCP config(s)")
    ap.add_argument("--check", action="store_true", help="read-only status report")
    ap.add_argument("--verify-key", action="store_true",
                    help="one no-cost TokenHub probe; skipped if no key yet; never fails setup")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove only the hailuo-video entry from the WorkBuddy MCP config(s)")
    args = ap.parse_args()

    print(f"Repo      : {BASE}")
    print(f"Key file  : {KEY_FILE}")
    print(f"Python    : {sys.version.split()[0]}")
    print(f"Config(s) : {', '.join(str(p) for p in config_paths())}")
    print("-" * 70)
    warn_legacy_env()

    if args.uninstall:
        for line in uninstall_from_workbuddy():
            print(line)
        print("Entry removed. START A NEW CHAT SESSION for the change to take effect.")
        return 0

    if args.check:
        return _check_status()

    key_ready = ensure_key_file()
    try:
        ensure_venv()
    except SetupError as exc:
        print(f"SETUP INCOMPLETE: {exc}")
        print("The key file and any existing config were left untouched. No credit was spent.")
        return 1

    block = build_block()
    LOCAL_CONFIG.write_text(
        json.dumps({"mcpServers": block}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[ok] wrote paste-ready config -> {LOCAL_CONFIG}")

    if args.install:
        for line in install_into_workbuddy(block):
            print(line)
        print(install_precommit_guard())
        print("\nACTIVATION (one-time, in WorkBuddy):")
        print("  1. Connectors (left sidebar) -> Custom Connector (top-right) -> Trust 'hailuo-video'.")
        print("  2. START A NEW CHAT SESSION -- tool lists load when a session starts.")
        print("  The connector does NOT activate automatically. If it never appears, paste")
        print(f"  the block from {LOCAL_CONFIG} into WorkBuddy's MCP settings manually.")
    else:
        print("\nConfig was NOT installed globally. Paste the block from mcp.local.json")
        print("into your WorkBuddy MCP settings, or re-run with --install.")

    key_state = "NOT VALIDATED (no probe requested)"
    if args.verify_key:
        print("\n--- no-cost key probe ---")
        if not key_ready:
            print("SKIPPED - no key pasted yet. No network call, no credit spent.")
            key_state = "NOT VALIDATED (no key pasted yet)"
        elif verify_key() != 0:
            print("[!!] Key probe was inconclusive or the key was rejected. Setup itself IS complete.")
            print("     Re-run check_key.py after fixing the key; no credit was spent.")
            key_state = "NOT VALIDATED (probe inconclusive or key rejected)"
        else:
            print("[ok] key accepted (no credit spent)")
            key_state = "VALID (no credit spent)"

    print("\nINSTALL WRITTEN -- activation is NOT complete.")
    print(f"Key status : {key_state}")
    print("Credentials: ONE key per group, in api-key.txt. No env var, no second credential.")
    if not key_ready:
        print("Remaining  : paste the single key into api-key.txt (no restart needed).")
    print("BEFORE generating, run the no-cost checker:")
    print("    .venv/Scripts/python.exe check_key.py   (Windows)")
    print("    .venv/bin/python check_key.py           (macOS / Linux)")
    print("Activation PENDING: Trust 'hailuo-video' in Connectors, then START A NEW CHAT SESSION.")
    print("If the connector never appears, paste the block from mcp.local.json manually.")
    print("First run needs PyPI access; offline: set HAILUO_WHEELHOUSE to a folder of wheels.")
    print("Then ask your agent: 'generate a 4 second video of a cat on a desk'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
