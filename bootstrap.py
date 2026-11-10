#!/usr/bin/env python3
"""Zero-prerequisite entry point for the local Hailuo video MCP.

Run with ANY Python 3.6+ (stdlib only, no dependencies, no network package):

    python3 bootstrap.py --install --verify-key     # macOS / Linux
    python  bootstrap.py --install --verify-key     # Windows

It does three things, in order, then delegates to setup_mcp.py:

  1. Finds the repo. If setup_mcp.py is not next to this file, it DOWNLOADS the
     GitHub ZIP and extracts it with zipfile -- no `git`, no `tar`, no `unzip`
     needed. That is the "lowest common denominator" path.
  2. Finds a Python 3.10+ interpreter: the one running this script, PATH names,
     the `py` launcher, and WorkBuddy's OWN bundled Python (Windows, macOS and
     Linux app locations). A stock macOS 3.9 can run this script; bootstrap then
     finds a newer interpreter to run setup with.
  3. Runs setup_mcp.py with that interpreter. Arguments pass through unchanged;
     with no arguments it defaults to --install --verify-key.

Read-only helpers:

    python3 bootstrap.py --find-python   # print the 3.10+ interpreter, spend nothing
    HAILUO_ZIP=/path/repo.zip           # use a local ZIP instead of downloading
    HAILUO_REPO_DIR=/path/clone         # reuse an existing extraction/clone
    HAILUO_PYTHON=/path/python3         # force one interpreter (path only)

HAILUO_* variables are INSTALLATION PATH HINTS ONLY. They are never credentials:
the one API key lives on line 1 of api-key.txt and nowhere else. bootstrap.py
never reads, prints, copies or writes any key.

If no Python 3.10+ exists anywhere on the machine, this prints the single
one-time human install that is still required. Git is NEVER required.
"""

import glob
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

MIN_PYTHON = (3, 10)
SETUP_SCRIPT = "setup_mcp.py"
ZIP_URL = "https://codeload.github.com/vjsyong/hailuo-local-mcp/zip/refs/heads/main"
REPO_DIR_NAME = "hailuo-local-mcp"
PROBE_CODE = "import sys;print('%d.%d.%d' % sys.version_info[:3])"
DEFAULT_SETUP_ARGS = ["--install", "--verify-key"]

WINDOWS_PY = ("python.exe", "python3.exe")
POSIX_PY = ("bin/python3", "python3", "bin/python", "python")
PY_VERSIONS = ("3.13", "3.12", "3.11", "3.10")

INSTALL_HELP = """
BOOTSTRAP INCOMPLETE: no Python 3.10+ interpreter was found anywhere on this
machine (PATH, `py` launcher, or WorkBuddy's bundled Python were all checked).

This is the ONLY situation that needs a human install, and it is one-time:

  Windows : https://www.python.org/downloads/windows/  (or: winget install Python.Python.3.12)
            In the installer, CHECK "Add python.exe to PATH".
  macOS   : brew install python@3.12   OR   https://www.python.org/downloads/macos/
            (the Xcode Command Line Tools python3 is 3.9 -- too old)
  Linux   : sudo apt install python3.12 python3.12-venv   (or your distro's equivalent)

Then re-run:  python3 bootstrap.py --install --verify-key
              (Windows: python bootstrap.py --install --verify-key)

Do NOT install git. It is not needed -- bootstrap downloads the repo ZIP itself.
Do NOT install anything globally beyond Python; dependencies go into .venv.
No API key has been touched and no credit has been spent.
"""


class BootstrapError(RuntimeError):
    """A clean, actionable bootstrap failure (never a raw traceback)."""


def log(message):
    print(message, flush=True)


def version_of(argv):
    """Return the version string if argv is a working Python >= MIN_PYTHON."""
    try:
        out = subprocess.check_output(
            list(argv) + ["-c", PROBE_CODE],
            stderr=subprocess.DEVNULL, universal_newlines=True, timeout=15,
        ).strip()
    except Exception:
        return None
    if not out:
        return None
    parts = out.splitlines()[-1].split(".")
    if len(parts) < 2:
        return None
    try:
        major, minor = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if (major, minor) < MIN_PYTHON:
        return None
    return out


def path_candidates():
    """Interpreter names found via PATH / the Windows py launcher."""
    if os.name == "nt":
        out = [["python"], ["python3"]]
        out += [["py", "-" + v] for v in PY_VERSIONS]
    else:
        out = [["python3"], ["python"]]
        out += [["python" + v] for v in PY_VERSIONS]
    return out


def bundled_candidates():
    """WorkBuddy's own Python -- present even when the student has none installed."""
    home = Path.home()
    roots = [home / ".workbuddy-ai" / "binaries" / "python" / "versions"]
    if os.name == "nt":
        names = WINDOWS_PY
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            roots.append(Path(local) / "Programs" / "WorkBuddyAI" / "resources" / "vendor" / "python")
    else:
        names = POSIX_PY
        roots += [
            Path("/Applications/WorkBuddy AI.app/Contents/Resources/vendor/python"),
            Path("/Applications/WorkBuddyAI.app/Contents/Resources/vendor/python"),
            home / "Applications" / "WorkBuddy AI.app" / "Contents" / "Resources" / "vendor" / "python",
        ]
    found = []
    for root in roots:
        # Versioned layouts: ~/.workbuddy-ai/binaries/python/versions/<ver>/python
        try:
            children = sorted(glob.glob(str(root / "*")))
        except OSError:
            children = []
        for child in children:
            for name in names:
                candidate = Path(child) / name
                if candidate.is_file():
                    found.append([str(candidate)])
        # Flat layouts: .../vendor/python/python.exe or .../vendor/python/bin/python3
        for name in names:
            candidate = root / name
            if candidate.is_file():
                found.append([str(candidate)])
    return found


def discover_python():
    """Return (argv, version, origin) for the first usable Python 3.10+, else Nones."""
    candidates = []
    override = os.environ.get("HAILUO_PYTHON", "").strip()
    if override:
        candidates.append(("HAILUO_PYTHON override", [override]))
    candidates.append(("current interpreter", [sys.executable]))
    for argv in path_candidates():
        candidates.append(("PATH", argv))
    for argv in bundled_candidates():
        candidates.append(("WorkBuddy bundled Python", argv))

    seen = set()
    for origin, argv in candidates:
        key = tuple(argv)
        if key in seen:
            continue
        seen.add(key)
        version = version_of(argv)
        if version:
            return argv, version, origin
    return None, None, None


def download(url, dest):
    """Download with urllib, then fall back to curl. Never uses git."""
    try:
        import urllib.request
        request = urllib.request.Request(
            url, headers={"User-Agent": "hailuo-local-mcp-bootstrap/1.0"})
        with urllib.request.urlopen(request, timeout=45) as response:
            with dest.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        return True
    except Exception as exc:
        log("[!] direct download failed (%s); trying curl" % type(exc).__name__)
    curl = shutil.which("curl")
    if not curl:
        return False
    try:
        subprocess.check_call([curl, "-fsSL", "-o", str(dest), url], timeout=90)
        return True
    except Exception:
        return False


def extract_repo(zip_path, target):
    """Extract the GitHub ZIP without extractall (explicit path-traversal guard)."""
    try:
        archive = zipfile.ZipFile(str(zip_path))
    except (OSError, zipfile.BadZipFile) as exc:
        raise BootstrapError("not a readable ZIP: %s" % type(exc).__name__)
    with archive:
        names = archive.namelist()
        matches = [n for n in names
                   if n == SETUP_SCRIPT or n.endswith("/" + SETUP_SCRIPT)]
        if not matches:
            raise BootstrapError("the ZIP does not contain %s" % SETUP_SCRIPT)
        prefix = matches[0][:-len(SETUP_SCRIPT)]
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BootstrapError("cannot create %s: %s" % (target, type(exc).__name__))
        root = str(target.resolve())
        written = 0
        for name in names:
            if name.endswith("/") or not name.startswith(prefix):
                continue
            rel = name[len(prefix):]
            clean = rel.replace("\\", "/").split("/")
            if not rel or rel.startswith("/") or ".." in clean:
                continue
            dest = (target / rel).resolve()
            if not str(dest).startswith(root + os.sep):
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as src, dest.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                written += 1
            except (OSError, KeyError, RuntimeError):
                continue
    if not (target / SETUP_SCRIPT).is_file():
        raise BootstrapError("extraction finished but %s is missing" % SETUP_SCRIPT)
    return written


def ensure_repo():
    """Return (repo_dir, how). Downloads the ZIP when there is no clone and no git."""
    here = Path(__file__).resolve().parent
    if (here / SETUP_SCRIPT).is_file():
        return here, "existing clone / extraction"

    override = os.environ.get("HAILUO_REPO_DIR", "").strip()
    if override:
        candidate = Path(override).expanduser().resolve()
        if (candidate / SETUP_SCRIPT).is_file():
            return candidate, "HAILUO_REPO_DIR"
        log("[!!] HAILUO_REPO_DIR has no %s: %s" % (SETUP_SCRIPT, candidate))

    target = Path.cwd() / REPO_DIR_NAME
    if (target / SETUP_SCRIPT).is_file():
        return target, "existing ZIP extraction"

    local_zip = os.environ.get("HAILUO_ZIP", "").strip()
    if local_zip:
        zip_path = Path(local_zip).expanduser().resolve()
        if not zip_path.is_file():
            raise BootstrapError("HAILUO_ZIP does not exist: %s" % zip_path)
        log("[..] using local repo ZIP: %s" % zip_path)
    else:
        zip_path = Path.cwd() / (REPO_DIR_NAME + ".zip")
        log("[..] no clone and no git required: downloading repo ZIP")
        log("    %s" % ZIP_URL)
        if not download(ZIP_URL, zip_path):
            raise BootstrapError(
                "could not download the repo ZIP. Check internet access, or set "
                "HAILUO_ZIP to a locally supplied copy of the repo ZIP.")
    if not zip_path.is_file() or zip_path.stat().st_size < 100:
        raise BootstrapError("downloaded ZIP is empty or missing: %s" % zip_path)
    with zip_path.open("rb") as handle:
        if handle.read(2) != b"PK":
            raise BootstrapError("downloaded file is not a ZIP (proxy / captive portal?)")
    count = extract_repo(zip_path, target)
    # A standalone bootstrap.py run from a parent directory should leave a copy
    # inside the extracted repo, so re-running from the repo root also works.
    if not (target / "bootstrap.py").is_file():
        try:
            shutil.copyfile(str(Path(__file__).resolve()), str(target / "bootstrap.py"))
        except OSError:
            pass
    log("[ok] extracted %d files -> %s (no git used)" % (count, target))
    return target, "ZIP download"


def no_python_help():
    log(INSTALL_HELP.strip())
    return 1


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)

    if "--find-python" in args:
        interp, version, origin = discover_python()
        if not interp:
            return no_python_help()
        log("PYTHON_OK  %s" % " ".join(interp))
        log("VERSION    %s" % version)
        log("SOURCE     %s" % origin)
        if origin.startswith("WorkBuddy bundled"):
            log("NOTE       .venv will be based on WorkBuddy's bundled Python; "
                "re-run bootstrap.py once if WorkBuddy upgrades its Python.")
        return 0

    log("=" * 70)
    log("Hailuo video MCP -- zero-prerequisite bootstrap")
    log("No git required. No system-level install required when a Python 3.10+ exists.")
    log("=" * 70)

    try:
        repo, how = ensure_repo()
    except BootstrapError as exc:
        log("BOOTSTRAP INCOMPLETE: %s" % exc)
        log("No config was changed, no key was touched, no credit was spent.")
        return 1
    log("[ok] repo: %s (%s)" % (repo, how))

    interp, version, origin = discover_python()
    if not interp:
        return no_python_help()
    log("[ok] Python %s -- %s" % (version, " ".join(interp)))
    log("     source: %s" % origin)
    if origin.startswith("WorkBuddy bundled"):
        log("[!] Using WorkBuddy's bundled Python as the .venv base. If a WorkBuddy")
        log("    update replaces that Python, re-run bootstrap.py once.")

    setup_args = [a for a in args if a != "--find-python"] or list(DEFAULT_SETUP_ARGS)
    setup_path = str(repo / SETUP_SCRIPT)
    command = list(interp) + [setup_path] + setup_args
    log("-" * 70)
    log("[..] running setup: %s %s %s" % (" ".join(interp), SETUP_SCRIPT, " ".join(setup_args)))
    try:
        return subprocess.call(command, cwd=str(repo))
    except OSError as exc:
        log("BOOTSTRAP INCOMPLETE: could not launch setup (%s)" % type(exc).__name__)
        log("No credit was spent.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
