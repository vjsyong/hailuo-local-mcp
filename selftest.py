"""End-to-end STDIO MCP test with zero cloud spend.

Spawns the real server as a subprocess (with TokenHub calls stubbed) and talks
to it with the official MCP client -- exactly how WorkBuddy will talk to it.
Also asserts the ONE-KEY-PER-GROUP invariant.

    .venv/Scripts/python.exe selftest.py     # Windows
    .venv/bin/python selftest.py             # macOS / Linux
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BASE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="hailuo-local-selftest-"))
ENTRY = BASE / "selftest_dryrun_server.py"
FAKE_KEY = "DRYRUN_FAKE_KEY_SINGLE_FILE"
KEY_FILE = TMP / "api-key.txt"
KEY_FILE.write_text(FAKE_KEY + "\n", encoding="utf-8")


def params(env_overrides: dict) -> StdioServerParameters:
    env = dict(os.environ)
    env.update({
        "SELFTEST_DUMP": str(TMP / "submitted.json"),
        "SELFTEST_VIDEO_DIR": str(TMP / "videos"),
        "SELFTEST_EXPECTED_KEY": FAKE_KEY,
        "TOKENHUB_KEY_FILE": str(KEY_FILE),
        # Hostile by design: an env-var key must NOT become a second source.
        "TOKENHUB_API_KEY": "WRONG_ENV_KEY_MUST_BE_IGNORED",
    })
    env.update(env_overrides)
    return StdioServerParameters(
        command=sys.executable,
        args=[str(ENTRY)],
        env=env,
        cwd=str(BASE),
    )


def text_of(result) -> str:
    return "\n".join(c.text for c in result.content if hasattr(c, "text"))


def single_key_invariants() -> None:
    """One group = one key, one file, one header, and no `user` field."""
    import tokenhub

    headers = tokenhub._headers(FAKE_KEY)
    assert headers == {
        "Authorization": f"Bearer {FAKE_KEY}",
        "Content-Type": "application/json",
    }, headers
    assert sum("auth" in k.lower() or "key" in k.lower() for k in headers) == 1
    print("[ok] exactly ONE credential header: Authorization: Bearer <key>")

    payload = tokenhub.build_payload("A cat sitting on the desk", 4, "768P", "16:9")
    for forbidden in ("user", "api_key", "apiKey", "token", "secretId", "secretKey"):
        assert forbidden not in payload, f"payload must not carry {forbidden}"
    print("[ok] request body carries no user/second credential field")

    for name in ("server.py", "setup_mcp.py"):
        src = (BASE / name).read_text(encoding="utf-8")
        assert "TOKENHUB_API_KEY" not in src, f"{name} must not accept an env-var key"
    print("[ok] no env-var key override exists -- api-key.txt is the only source")

    cfg = BASE / "mcp.local.json"
    if cfg.exists():
        block = json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]["hailuo-video"]
        for forbidden in ("env", "headers", "url", "type"):
            assert forbidden not in block, f"MCP config must not carry {forbidden}"
    print("[ok] MCP config has no env/headers/url -- no place for a second key")


async def healthy_case() -> None:
    async with stdio_client(params({}), errlog=sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[ok] stdio initialize")

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            expected = {"video_capabilities", "submit_video", "check_video", "generate_video"}
            assert expected <= set(names), f"missing tools: {expected - set(names)}"
            print(f"[ok] tools/list -> {names}")

            caps = json.loads(text_of(await session.call_tool("video_capabilities", {})))
            assert caps["key_configured"] is True, caps["key_status"]
            assert caps["model"] == "minimax-video-h3"
            assert caps["credentials_required"] == 1
            assert caps["key_source"] == "api-key.txt (single file, one key)"
            print("[ok] video_capabilities: ONE key from api-key.txt, model minimax-video-h3")

            gen = await session.call_tool("generate_video", {
                "prompt": "A cat sitting on the desk",
                "duration": 4,
                "resolution": "768P",
                "ratio": "16:9",
            })
            assert not gen.is_error, text_of(gen)[:400]
            data = json.loads(text_of(gen))
            assert data["ok"] and data["status"] == "succeeded", data
            vp = Path(data["video_path"])
            assert vp.exists() and vp.stat().st_size > 0, "video_path missing on disk"
            assert data["file_size_bytes"] == vp.stat().st_size
            assert "download_url" not in data and "source_url" not in data
            print(f"[ok] generate_video -> local video_path ({vp.stat().st_size} bytes, no signed URL leaked)")

            submitted = json.loads((TMP / "submitted.json").read_text(encoding="utf-8"))
            assert submitted["key_seen"] is True
            assert submitted["key_matches_file"] is True, (
                "server used the env-var key instead of the single api-key.txt key"
            )
            print("[ok] server used the file key even with a hostile env-var key present")
            assert submitted["payload"] == {
                "model": "minimax-video-h3",
                "content": [{"type": "text", "text": "A cat sitting on the desk"}],
                "resolution": "768P",
                "duration": 4,
                "ratio": "16:9",
            }, submitted["payload"]
            print("[ok] TokenHub payload exactly matches the console curl")

            usage = (TMP / "videos" / "usage.jsonl").read_text(encoding="utf-8").strip().splitlines()
            assert any('"action": "done"' in line for line in usage), usage
            print(f"[ok] usage log wrote {len(usage)} records")


async def missing_key_case() -> None:
    overrides = {
        # Even a non-empty env key must NOT rescue a missing api-key.txt.
        "TOKENHUB_API_KEY": "WRONG_ENV_KEY_MUST_BE_IGNORED",
        "TOKENHUB_KEY_FILE": str(TMP / "definitely-not-a-key-file"),
    }
    async with stdio_client(params(overrides), errlog=sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            caps = json.loads(text_of(await session.call_tool("video_capabilities", {})))
            assert caps["key_configured"] is False
            assert "No TokenHub API key configured" in caps["key_status"]
            gen = await session.call_tool("generate_video", {"prompt": "a cat"})
            body = json.loads(text_of(gen))
            assert not gen.is_error, "missing key should be a clean result, not a traceback"
            assert body["ok"] is False and body["key_configured"] is False
            assert "Paste your single API key" in body["error"], body["error"]
            print("[ok] missing key returns a clean actionable error (no traceback)")


async def main() -> None:
    single_key_invariants()
    print("-" * 70)
    await healthy_case()
    await missing_key_case()
    print("\nSELFTEST PASSED (one key per group, no TokenHub calls, no credit spent)")


if __name__ == "__main__":
    import traceback

    try:
        anyio.run(main)
    except Exception as exc:
        print(f"\nSELFTEST FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(1)
