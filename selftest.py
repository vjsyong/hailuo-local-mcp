"""Offline regression suite for the local Hailuo video MCP server.

ZERO cloud spend: every TokenHub HTTP call is stubbed. Runs two layers:

  1. Unit tests -- payload validation, key normalisation, redaction, SSRF,
     malformed MCP configs, corrupt runtime files, strict key-probe status.
  2. Real STDIO MCP tests -- spawns selftest_dryrun_server.py (which calls the
     REAL server.main()) and talks to it with the official MCP client, exactly
     as WorkBuddy will. Covers success, recovery, redaction, idempotency and
     every "already paid for" failure path.

    .venv/Scripts/python.exe selftest.py     # Windows
    .venv/bin/python selftest.py             # macOS / Linux
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import anyio  # noqa: E402
from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

import check_key  # noqa: E402
import keyfile  # noqa: E402
import server  # noqa: E402
import setup_mcp  # noqa: E402
import tokenhub  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="hailuo-local-selftest-"))
ENTRY = BASE / "selftest_dryrun_server.py"
FAKE_KEY = "DRYRUN_FAKE_KEY_SINGLE_FILE"
KEY_FILE = TMP / "api-key.txt"
KEY_FILE.write_text(FAKE_KEY + "\n", encoding="utf-8")
CANONICAL = {
    "model": "minimax-video-h3",
    "content": [{"type": "text", "text": "A cat sitting on the desk"}],
    "resolution": "768P",
    "duration": 4,
    "ratio": "16:9",
}
_passed = 0


def ok(label: str) -> None:
    global _passed
    _passed += 1
    print(f"[ok] {label}")


def raises(fn, *args, **kwargs) -> BaseException:
    try:
        fn(*args, **kwargs)
    except BaseException as exc:
        return exc
    raise AssertionError(f"expected an exception from {getattr(fn, '__name__', fn)}")


def clearance(exc: BaseException, *types) -> None:
    assert isinstance(exc, types), f"expected {types}, got {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Fake HTTP layer (never touches the network)
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status=200, data=None, text="", headers=None,
                 url="https://cdn.example.invalid/fake.mp4", chunks=()):
        self.status_code = status
        self._data = data
        self.text = text
        self.headers = headers or {"content-type": "video/mp4"}
        self.url = url
        self._chunks = chunks

    def json(self):
        if self._data is None:
            raise ValueError("not JSON")
        return self._data

    def iter_bytes(self, chunk_size=65536):
        yield from self._chunks


class FakeStream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, *args):
        return False


# ---------------------------------------------------------------------------
# Layer 1: unit tests
# ---------------------------------------------------------------------------

def test_single_key_invariant() -> None:
    headers = tokenhub._headers(FAKE_KEY)
    assert headers == {
        "Authorization": f"Bearer {FAKE_KEY}",
        "Content-Type": "application/json",
    }, headers
    assert sum("auth" in k.lower() or "key" in k.lower() for k in headers) == 1
    ok("exactly ONE credential header: Authorization: Bearer <key>")

    payload = tokenhub.build_payload("A cat sitting on the desk", 4, "768P", "16:9")
    assert payload == CANONICAL, payload
    for forbidden in ("user", "api_key", "apiKey", "token", "secretId", "secretKey", "secretKey"):
        assert forbidden not in payload, f"payload must not carry {forbidden}"
    ok("canonical TokenHub payload matches the console curl; no second credential")

    # Hard runtime invariant: the server never consults the environment at all.
    # (Docstrings may *mention* old var names while explaining why they were removed.)
    for name in ("server.py", "tokenhub.py", "keyfile.py"):
        src = (BASE / name).read_text(encoding="utf-8")
        assert "os.environ" not in src, f"{name} must not read any env var at runtime"
        assert "getenv(" not in src, f"{name} must not read any env var at runtime"
    assert tokenhub.BASE_URL.startswith("https://tokenhub-intl.tencentcloudmaas.com")
    # setup_mcp.py only *names* legacy vars to warn that they are ignored.
    setup_src = (BASE / "setup_mcp.py").read_text(encoding="utf-8")
    assert 'os.environ.get("TOKENHUB_' not in setup_src
    assert 'os.environ["TOKENHUB_' not in setup_src
    assert 'os.environ.get("HAILUO_WHEELHOUSE"' in setup_src
    assert tokenhub.BASE_URL == "https://tokenhub-intl.tencentcloudmaas.com"
    assert tokenhub.MODEL == "minimax-video-h3"
    assert server.KEY_FILE == BASE / "api-key.txt"
    ok("no env overrides for key/endpoint/model; api-key.txt is the only source")

    cfg = BASE / "mcp.local.json"
    if cfg.exists():
        block = json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]["hailuo-video"]
        for forbidden in ("env", "headers", "url"):
            assert forbidden not in block, f"MCP config must not carry {forbidden}"
        assert Path(block["command"]).is_absolute() or "/" in block["command"]
    ok("MCP config has no env/headers/url -- no place for a second key")


def test_strict_payload_validation() -> None:
    # duration drives the bill: floats, strings and bools are silently wrong.
    for bad in (4.9, "4", True, 3, 16, 0, -1):
        exc = raises(tokenhub.build_payload, "a cat", bad)
        clearance(exc, ValueError)
    assert tokenhub.build_payload("a cat", 4)["duration"] == 4
    ok("duration rejects floats/strings/bools/out-of-range (no silent mis-billing)")

    assert tokenhub.build_payload("a cat", 4, "1080P")["resolution"] == "768P"
    assert tokenhub.build_payload("a cat", 4, "4K")["resolution"] == "2K"
    assert tokenhub.build_payload("a cat", 5, "480P", model="max")["model"] == "minimax-video-h3-max"
    for bad in ("480P", "999P", "adaptive"):
        clearance(raises(tokenhub.build_payload, "a cat", 4, bad), ValueError)
    clearance(raises(tokenhub.build_payload, "a cat", 5, "2K", model="max"), ValueError)
    ok("resolution aliases H3-only; H3-Max bounds enforced with a clear hint")

    for bad in ("adaptive", "16:10", "9:16:1"):
        clearance(raises(tokenhub.build_payload, "a cat", 4, "768P", bad), ValueError)
    assert tokenhub.build_payload("a cat", 4, "768P", "16：9")["ratio"] == "16:9"
    # An omitted/empty ratio is the documented default, not a billing error.
    assert tokenhub.build_payload("a cat", 4, "768P", "")["ratio"] == "16:9"
    ok("ratio rejects 'adaptive'/unknown values; normalises fullwidth colon and empty")

    assert tokenhub.build_payload("a cat", 4, model="H3")["model"] == "minimax-video-h3"
    assert tokenhub.build_payload("a cat", 5, model="MAX")["model"] == "minimax-video-h3-max"
    clearance(raises(tokenhub.build_payload, "a cat", 4, model="gpt-video"), ValueError)
    ok("resolve_model is case-insensitive and rejects unsupported slugs")

    for bad in (None, 123, "", "   ", "\x00", "x" * 2001):
        clearance(raises(keyfile.clean_prompt, bad), ValueError)
    assert keyfile.clean_prompt("  A  cat\n\tsitting  ") == "A cat sitting"
    assert keyfile.clean_prompt("cat\x07dog") == "cat dog"
    ok("prompt rejects non-str/empty/oversized and strips control characters")


def test_task_id_and_redaction() -> None:
    for bad in ("../etc", "a?b=1", "a#frag", "a/b", "", "   ", None, 5, "x" * 300, "\n"):
        clearance(raises(tokenhub.validate_task_id, bad), ValueError)
    assert tokenhub.validate_task_id(" 1480314028-minimax_video_h3-abc123 ") == \
        "1480314028-minimax_video_h3-abc123"
    tokenhub.validate_task_id(tokenhub.PROBE_TASK_ID)
    ok("task_id validation blocks path/query injection into the query URL")

    dirty = (f"HTTP 401 rejected Bearer {FAKE_KEY} at "
             "https://cdn.example.invalid/v.mp4?sign=SECRETKEY&Expires=123")
    clean = tokenhub.redact(dirty, FAKE_KEY)
    assert FAKE_KEY not in clean and "SECRETKEY" not in clean and "http" not in clean
    ok("redact() scrubs the key, Bearer values, signed URLs and query secrets")

    resp = FakeResponse(400, {"error": {"message": f"echo Authorization: Bearer {FAKE_KEY}"}})
    assert FAKE_KEY not in tokenhub._safe_error(resp, FAKE_KEY)
    assert FAKE_KEY not in tokenhub._safe_error(
        FakeResponse(401, {"error": {"message": FAKE_KEY}}), FAKE_KEY)
    ok("_safe_error never echoes a raw upstream body containing the key")

    f1 = server._failure(RuntimeError(f"boom Bearer {FAKE_KEY}"), FAKE_KEY)
    assert FAKE_KEY not in json.dumps(f1) and f1["resubmit_allowed"] is True
    f2 = server._failure(RuntimeError("poll lost"), FAKE_KEY, task_id="DRYRUN-TASK-1")
    assert f2["resubmit_allowed"] is False and f2["recoverable"] is True
    assert f2["task_id"] == "DRYRUN-TASK-1"
    ok("_failure is redacted and marks paid-job errors resubmit_allowed=false")


def test_key_file_normalisation() -> None:
    def read(raw: bytes, name: str) -> str:
        path = TMP / f"key_{name}.txt"
        path.write_bytes(raw)
        return keyfile.read_api_key(path)

    assert read(b"\xef\xbb\xbf\"Bearer ABC.123\"\n", "bom") == "ABC.123"
    assert read(b"'  ABC . 123 '\n", "quotes") == "ABC.123"
    assert read(b"bearer ABC123\n", "lowerbearer") == "ABC123"
    assert read(b"AB\x01CD\n", "control") == "ABCD"
    ok("BOM / quotes / Bearer prefix / control chars normalised to one key")

    for raw, name in (
        ("ABC".encode("utf-16"), "utf16"),
        (b"\x81\x82", "badutf8"),
        (b"PASTE_YOUR_TOKENHUB_API_KEY_HERE\n", "placeholder"),
        (b"ABC\xc3\xa9\n", "nonascii"),
        (b"A" * 5000, "toolong"),
        (b"\n\n  \n", "empty"),
    ):
        clearance(raises(read, raw, name), keyfile.KeyFileError)
    ok("UTF-16 / bad UTF-8 / placeholder / non-ASCII / huge / empty all give clean errors")

    directory = TMP / "key_directory"
    directory.mkdir(exist_ok=True)
    clearance(raises(keyfile.read_api_key, directory), keyfile.KeyFileError)
    assert keyfile.read_api_key(KEY_FILE) == FAKE_KEY
    assert keyfile.read_key_optional(TMP / "does-not-exist") is None
    ok("directory key path and missing key handled without a traceback")


def test_ssrf_and_atomic_download() -> None:
    for bad in ("http://cdn.example.invalid/v.mp4", "https://localhost/v.mp4",
                "https://127.0.0.1/v.mp4", "https://169.254.169.254/latest/meta-data",
                "https://10.0.0.1/v.mp4", "https:///v.mp4"):
        clearance(raises(tokenhub._assert_safe_url, bad), RuntimeError)
    tokenhub._assert_safe_url("https://cdn.example.invalid/v.mp4?sign=abc")
    ok("_assert_safe_url blocks http, loopback, link-local and private hosts")

    dest = TMP / "download.mp4"
    original = tokenhub.httpx.stream
    try:
        # Every redirect hop is checked: a hop into http/loopback must be refused.
        tokenhub.httpx.stream = lambda *a, **kw: FakeStream(
            FakeResponse(302, headers={"location": "http://127.0.0.1/evil.mp4"}, chunks=()))
        clearance(raises(tokenhub.save_video, "https://cdn.example.invalid/v.mp4", str(dest)),
                  RuntimeError)
        assert not dest.exists() and not (TMP / "download.mp4.part").exists()

        tokenhub.httpx.stream = lambda *a, **kw: FakeStream(
            FakeResponse(200, chunks=(b"\x00\x00\x00 ftypisom", b"0" * 128)))
        assert tokenhub.save_video("https://cdn.example.invalid/v.mp4", str(dest)) == str(dest)
        assert dest.read_bytes().startswith(b"\x00\x00\x00 ftypisom")
        ok("redirect to a private host refused; valid MP4 written atomically")

        tokenhub.httpx.stream = lambda *a, **kw: FakeStream(
            FakeResponse(200, chunks=(b"<!doctype html>not a video",)))
        dest2 = TMP / "notvideo.mp4"
        clearance(raises(tokenhub.save_video, "https://cdn.example.invalid/v.mp4", str(dest2)),
                  RuntimeError)
        assert not dest2.exists() and not (TMP / "notvideo.mp4.part").exists()
        ok("non-MP4 response rejected; no corrupt final file or .part left behind")
    finally:
        tokenhub.httpx.stream = original


def test_tokenhub_response_shapes() -> None:
    post, get = tokenhub.httpx.post, tokenhub.httpx.get
    try:
        for data in (["a", "b"], None, 42, "text", {"task": "notadict"},
                     {"task_id": {"x": 1}}):
            tokenhub.httpx.post = lambda *a, d=data, **kw: FakeResponse(200, d)
            clearance(raises(tokenhub.submit, FAKE_KEY, CANONICAL), RuntimeError)
        tokenhub.httpx.post = lambda *a, **kw: FakeResponse(200, {"task_id": "TASK-ok_1"})
        assert tokenhub.submit(FAKE_KEY, CANONICAL) == "TASK-ok_1"
        ok("submit() tolerates every non-dict / malformed JSON shape without AttributeError")

        tokenhub.httpx.get = lambda *a, **kw: FakeResponse(200, ["notadict"])
        assert tokenhub.query(FAKE_KEY, "TASK-ok_1")["status"] == "unknown"
        tokenhub.httpx.get = lambda *a, **kw: FakeResponse(
            200, {"task": {"status": "failed", "error": "unsafe prompt"}})
        failed = tokenhub.query(FAKE_KEY, "TASK-ok_1")
        assert failed["status"] == "failed" and failed["message"] == "unsafe prompt"
        tokenhub.httpx.get = lambda *a, **kw: FakeResponse(
            200, {"status": "succeeded", "content": {"url": "https://cdn.example.invalid/v.mp4"},
                  "tokenhub_usage": {"total_tokens": 200000}})
        succeeded = tokenhub.query(FAKE_KEY, "TASK-ok_1")
        assert succeeded["status"] == "succeeded" and succeeded["total_tokens"] == 200000
        ok("query() normalises list/flat/nested shapes and extracts video_url + usage")

        tokenhub.httpx.get = lambda *a, **kw: FakeResponse(
            401, {"error": {"message": f"Bearer {FAKE_KEY}"}})
        exc = raises(tokenhub.query, FAKE_KEY, "TASK-ok_1")
        clearance(exc, PermissionError)
        assert FAKE_KEY not in str(exc)
        ok("auth failures are PermissionError with a redacted, fixed message")
    finally:
        tokenhub.httpx.post, tokenhub.httpx.get = post, get


def test_malformed_mcp_configs() -> None:
    cfg = TMP / "home" / ".workbuddy-ai" / "mcp.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    original = setup_mcp.config_paths
    setup_mcp.config_paths = lambda: [cfg]
    entry = setup_mcp.build_block()["hailuo-video"]
    try:
        valid = json.dumps({"theme": "dark", "mcpServers": {"keep-me": {"command": "x"}}})
        shapes = [valid, "not json at all", "[1, 2, 3]", '"a string"',
                  '{"mcpServers": ["oops"]}', "\ufeff" + valid]
        for shape in shapes:
            cfg.write_text(shape, encoding="utf-8")
            line = setup_mcp._merge_one(cfg, entry)
            assert "[ok]" in line, (shape, line)
            data = json.loads(cfg.read_text(encoding="utf-8"))
            assert "hailuo-video" in data["mcpServers"]
        ok("_merge_one survives invalid JSON, BOM, list/string roots, bad mcpServers")

        cfg.write_text(valid, encoding="utf-8")
        setup_mcp._merge_one(cfg, entry)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["theme"] == "dark" and data["mcpServers"]["keep-me"]["command"] == "x"
        ok("merge preserves every other server and unrelated top-level keys")

        out = setup_mcp.uninstall_from_workbuddy()
        assert any("[ok] removed" in line for line in out), out
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert "hailuo-video" not in data["mcpServers"] and "keep-me" in data["mcpServers"]
        ok("--uninstall removes only our entry, keeping other servers")

        assert (BASE / "selftest_dryrun_server.py").read_text(encoding="utf-8").count("server.main()") >= 1
        ok("STDIO tests launch the REAL server.main() entrypoint")
    finally:
        setup_mcp.config_paths = original


def test_corrupt_pending_and_probe_classification() -> None:
    original = server.PENDING_FILE
    pending = TMP / "pending.json"
    pending.write_text('{"bad": 42, "junk": "text", "good": {"ts": 1, "prompt": "x"}}',
                       encoding="utf-8")
    server.PENDING_FILE = pending
    try:
        items = server._pending_list()
        assert len(items) == 1 and items[0]["task_id"] == "good", items
        pending.write_text("not json", encoding="utf-8")
        assert server._pending_list() == []
        ok("corrupt pending.json never crashes _pending_list / video_capabilities")
    finally:
        server.PENDING_FILE = original

    original_key = check_key.KEY_FILE
    original_probe = check_key.tokenhub.probe_key
    check_key.KEY_FILE = KEY_FILE
    try:
        expectations = {
            400: (0, "KEY VALID"), 401: (1, "INVALID KEY"), 403: (1, "INVALID KEY"),
            429: (1, "THROTTLED"), 500: (1, "INCONCLUSIVE"), 404: (1, "INCONCLUSIVE"),
            200: (1, "INCONCLUSIVE"), 302: (1, "INCONCLUSIVE"), 408: (1, "INCONCLUSIVE"),
        }
        for status, (rc, label) in expectations.items():
            check_key.tokenhub.probe_key = lambda k, s=status: s
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                got = check_key.main()
            assert got == rc and label in buf.getvalue(), (status, got, buf.getvalue())
        check_key.tokenhub.probe_key = lambda k: (_ for _ in ()).throw(OSError("offline"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert check_key.main() == 1
        assert "INCONCLUSIVE" in buf.getvalue()
        ok("only HTTP 400 is KEY VALID; 401/403/429/5xx/404/200/3xx are never green")
    finally:
        check_key.KEY_FILE = original_key
        check_key.tokenhub.probe_key = original_probe


def test_macos_posix_branch() -> None:
    """The repo's ONLY OS branch must produce a POSIX venv python on macOS."""
    from unittest.mock import patch

    with patch.object(setup_mcp.os, "name", "posix"):
        posix_python = setup_mcp.venv_python().as_posix()
        block = setup_mcp.build_block()["hailuo-video"]
    assert posix_python.endswith("/.venv/bin/python"), posix_python
    assert block["command"].endswith("/.venv/bin/python"), block
    assert block["args"][0].endswith("/server.py"), block
    for forbidden in ("env", "headers", "url", "type"):
        assert forbidden not in block, f"config must not carry {forbidden}"
    ok("macOS/Linux branch -> .venv/bin/python, no env/url/headers")

    for name in ("server.py", "tokenhub.py", "keyfile.py", "check_key.py"):
        src = (BASE / name).read_text(encoding="utf-8")
        for forbidden in ("msvcrt", "win32api", "pywintypes", "os.startfile",
                          "CREATE_NO_WINDOW", "shell=True"):
            assert forbidden not in src, f"{name} contains Windows-only {forbidden}"
    ok("runtime modules contain no Windows-only APIs")

    assert setup_mcp.PRECOMMIT_HOOK.startswith("#!/bin/sh\n")
    assert "eol=lf" in (BASE / ".gitattributes").read_text(encoding="utf-8")
    ok("pre-commit hook is POSIX /bin/sh and git enforces LF line endings")


def unit_tests() -> None:
    print("--- layer 1: unit / static regression tests ---")
    test_single_key_invariant()
    test_strict_payload_validation()
    test_task_id_and_redaction()
    test_key_file_normalisation()
    test_ssrf_and_atomic_download()
    test_tokenhub_response_shapes()
    test_malformed_mcp_configs()
    test_corrupt_pending_and_probe_classification()
    test_macos_posix_branch()


# ---------------------------------------------------------------------------
# Layer 2: real STDIO MCP sessions
# ---------------------------------------------------------------------------

def params(mode: str, key_file: Path, video_dir: Path, corrupt: bool = False):
    env = dict(os.environ)
    env.update({
        "SELFTEST_DUMP": str(TMP / f"submitted_{mode}.json"),
        "SELFTEST_VIDEO_DIR": str(video_dir),
        "SELFTEST_KEY_FILE": str(key_file),
        "SELFTEST_EXPECTED_KEY": FAKE_KEY,
        "SELFTEST_MODE": mode,
        # Hostile by design: legacy env knobs must NOT become a second source.
        "TOKENHUB_API_KEY": "WRONG_ENV_KEY_MUST_BE_IGNORED",
        "TOKENHUB_KEY_FILE": str(TMP / "definitely-not-a-key-file"),
        "TOKENHUB_BASE_URL": "https://attacker.invalid",
        "TOKENHUB_MODEL": "not-a-model",
    })
    if corrupt:
        env["SELFTEST_CORRUPT_PENDING"] = "1"
    return StdioServerParameters(
        command=sys.executable, args=[str(ENTRY)], env=env, cwd=str(BASE),
    )


@asynccontextmanager
async def session_for(mode: str, key_file: Path = KEY_FILE, corrupt: bool = False):
    video_dir = TMP / f"videos_{mode}"
    async with stdio_client(params(mode, key_file, video_dir, corrupt), errlog=sys.stderr) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            yield session, video_dir


async def call(session, name: str, args: dict):
    result = await session.call_tool(name, args)
    text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
    assert not result.is_error, f"{name} returned an MCP error / traceback: {text[:400]}"
    return json.loads(text)


async def healthy_case() -> None:
    async with session_for("healthy") as (session, video_dir):
        tools = await session.list_tools()
        names = {t.name for t in tools.tools}
        assert {"video_capabilities", "submit_video", "check_video",
                "generate_video", "recent_tasks"} <= names, names
        ok(f"stdio initialize + tools/list -> {sorted(names)}")

        caps = await call(session, "video_capabilities", {})
        assert caps["key_configured"] is True, caps["key_status"]
        assert caps["model"] == "minimax-video-h3"
        assert caps["credentials_required"] == 1
        assert caps["key_source"] == "api-key.txt (single file, one key)"
        ok("video_capabilities: ONE key from api-key.txt, model minimax-video-h3")

        data = await call(session, "generate_video", {
            "prompt": "A cat sitting on the desk", "duration": 4,
            "resolution": "768P", "ratio": "16:9",
        })
        assert data["ok"] and data["status"] == "succeeded", data
        vp = Path(data["video_path"])
        assert vp.exists() and vp.stat().st_size > 0
        assert data["file_size_bytes"] == vp.stat().st_size
        assert "download_url" not in data and "source_url" not in data
        assert "sign=SECRET" not in json.dumps(data)
        ok(f"generate_video -> local video_path ({vp.stat().st_size} bytes, no signed URL)")

        submitted = json.loads((TMP / "submitted_healthy.json").read_text(encoding="utf-8"))
        assert submitted["key_matches_file"] is True, "server used a hostile env-var key"
        assert submitted["payload"] == CANONICAL, submitted["payload"]
        ok("server used the file key despite hostile env vars; payload matches the curl")

        usage = (video_dir / "usage.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert any('"action": "done"' in line for line in usage), usage
        ok(f"usage log wrote {len(usage)} records")

        again = await call(session, "check_video", {"task_id": "DRYRUN-TASK-1"})
        assert again["ok"] and again.get("reused") is True, again
        assert again["video_path"] == str(vp)
        assert len(list(video_dir.glob("*.mp4"))) == 1
        ok("repeated check_video is idempotent: reused=true, exactly one MP4")

        recent = await call(session, "recent_tasks", {})
        assert recent["ok"] is True and "hint" in recent
        ok("recent_tasks is callable for recovering a lost task_id")


async def missing_key_case() -> None:
    async with session_for("missing_key", key_file=TMP / "no-key-file-at-all") as (session, _):
        caps = await call(session, "video_capabilities", {})
        assert caps["key_configured"] is False
        assert "No TokenHub API key configured" in caps["key_status"]
        body = await call(session, "generate_video", {"prompt": "a cat"})
        assert body["ok"] is False and body["resubmit_allowed"] is True
        assert "Paste your single API key" in body["error"], body["error"]
        ok("missing key -> clean actionable error, no traceback, no env-var rescue")


async def submit_error_case() -> None:
    async with session_for("submit_error") as (session, _):
        body = await call(session, "generate_video", {"prompt": "a cat"})
        assert body["ok"] is False and body["resubmit_allowed"] is True
        assert FAKE_KEY not in json.dumps(body), "API key leaked into an MCP error"
        assert "task_id" not in body
        ok("401-style submit failure is redacted; nothing was billed")


async def poll_error_case() -> None:
    async with session_for("poll_error") as (session, _):
        body = await call(session, "generate_video", {"prompt": "a cat"})
        assert body["status"] == "poll_interrupted", body
        assert body["recoverable"] is True and body["resubmit_allowed"] is False
        assert body["task_id"] == "DRYRUN-TASK-1"
        ok("transient poll failure keeps the paid task_id and forbids resubmit")
        recent = await call(session, "recent_tasks", {})
        assert any(p["task_id"] == "DRYRUN-TASK-1" for p in recent["pending"]), recent
        ok("recent_tasks recovers the paid task_id after a poll failure")


async def running_and_resume_case() -> None:
    async with session_for("running_then_succeeded") as (session, video_dir):
        pending = await call(session, "check_video", {"task_id": "DRYRUN-TASK-1", "wait_seconds": 0})
        assert pending["ok"] is True and pending["pending"] is True, pending
        assert pending["resubmit_allowed"] is False and pending["task_id"] == "DRYRUN-TASK-1"
        ok("a live job returns ok=true/pending=true (not a 'failure' an agent retries)")

        done = await call(session, "check_video", {"task_id": "DRYRUN-TASK-1"})
        assert done["ok"] and done["status"] == "succeeded", done
        assert Path(done["video_path"]).is_file()
        assert len(list(video_dir.glob("*.mp4"))) == 1
        ok("check_video resumes the same paid job -> video_path; no duplicate MP4")

        stuck = await call(session, "generate_video", {"prompt": "a cat", "wait_seconds": 0})
        assert stuck["ok"] is True or stuck["resubmit_allowed"] is False, stuck
        ok("generate_video with wait_seconds=0 always hands back a recoverable task_id")


async def unknown_status_case() -> None:
    async with session_for("unknown_status") as (session, _):
        body = await call(session, "generate_video", {"prompt": "a cat"})
        assert body["ok"] is False and body["recoverable"] is True
        assert body["resubmit_allowed"] is False and body["status"] == "mystery"
        assert body["task_id"] == "DRYRUN-TASK-1"
        ok("out-of-set upstream status is recoverable, not an endless poll")


async def save_error_case() -> None:
    async with session_for("save_error") as (session, video_dir):
        body = await call(session, "generate_video", {"prompt": "a cat"})
        assert body["ok"] is False and body["recoverable"] is True
        assert body["resubmit_allowed"] is False and body["task_id"] == "DRYRUN-TASK-1"
        assert not list(video_dir.glob("*.mp4")), "corrupt MP4 left behind"
        ok("download failure keeps the paid task_id and leaves no corrupt MP4")


async def bad_params_case() -> None:
    async with session_for("bad_params") as (session, _):
        for args in ({"prompt": "a cat", "ratio": "adaptive"},
                     {"prompt": "a cat", "resolution": "480P"},
                     {"prompt": "   "}):
            body = await call(session, "generate_video", args)
            assert body["ok"] is False and body["resubmit_allowed"] is True, (args, body)
            assert "task_id" not in body
        ok("invalid params -> clean pre-submit errors, safe to retry, nothing billed")

        unsafe = await call(session, "check_video", {"task_id": "../../admin?x=1"})
        assert unsafe["ok"] is False and unsafe["resubmit_allowed"] is True
        assert "task_id" not in unsafe
        ok("malicious task_id rejected cleanly (no path/query injection)")


async def corrupt_state_case() -> None:
    async with session_for("corrupt_pending", corrupt=True) as (session, _):
        caps = await call(session, "video_capabilities", {})
        assert caps["key_configured"] is True and caps["pending_jobs"] == 0
        ok("corrupt pending.json at startup does not crash video_capabilities")


async def stdio_tests() -> None:
    print("-" * 70)
    print("--- layer 2: real STDIO MCP sessions (zero TokenHub calls) ---")
    await healthy_case()
    await missing_key_case()
    await submit_error_case()
    await poll_error_case()
    await running_and_resume_case()
    await unknown_status_case()
    await save_error_case()
    await bad_params_case()
    await corrupt_state_case()


async def main() -> None:
    unit_tests()
    await stdio_tests()
    print("\n" + "=" * 70)
    print(f"SELFTEST PASSED -- {_passed} checks, no TokenHub calls, no credit spent")


if __name__ == "__main__":
    import traceback

    try:
        anyio.run(main)
    except Exception as exc:
        print(f"\nSELFTEST FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
