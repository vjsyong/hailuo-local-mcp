"""End-to-end STDIO MCP test with zero cloud spend.

Spawns the real server as a subprocess (with TokenHub calls stubbed) and talks
to it with the official MCP client -- exactly how WorkBuddy will talk to it.

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


def params(env_overrides: dict) -> StdioServerParameters:
    env = dict(os.environ)
    env.update({
        "SELFTEST_DUMP": str(TMP / "submitted.json"),
        "SELFTEST_VIDEO_DIR": str(TMP / "videos"),
        "TOKENHUB_API_KEY": "DRYRUN_FAKE_KEY",
        "TOKENHUB_KEY_FILE": str(TMP / "no-key-file-here"),
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
            print("[ok] video_capabilities: key configured, model minimax-video-h3")

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
        "TOKENHUB_API_KEY": "",
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
    await healthy_case()
    await missing_key_case()
    print("\nSELFTEST PASSED (no TokenHub calls, no credit spent)")


if __name__ == "__main__":
    import traceback

    try:
        anyio.run(main)
    except Exception as exc:
        print(f"\nSELFTEST FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(1)
