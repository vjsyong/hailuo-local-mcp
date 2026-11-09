"""Local STDIO MCP server: MiniMax H3 video generation with one pasted API key.

Runs ON THE STUDENT'S COMPUTER. WorkBuddy launches this as a subprocess and
talks MCP over stdin/stdout -- no host, no port, no public URL, no group tokens.

Each group needs EXACTLY ONE credential: the single TokenHub API key on line 1
of `api-key.txt` beside this file. No SecretId/SecretKey, no group token, no
`user` field, and NO environment-variable overrides anywhere in this package.
The key is read on every tool call, so pasting/rotating needs no restart.

Finished videos go to videos/<hash>.mp4 and are returned as a local absolute
`video_path`. There is no URL to serve.

CRITICAL for stdio: never write to stdout. The MCP SDK claims fd 1 itself and
diverts stray output to stderr; our code only ever writes to stderr.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

import keyfile
import tokenhub

BASE_DIR = Path(__file__).resolve().parent
# Module-level so the offline selftest can redirect them; production never
# reads an environment variable to decide any of these.
KEY_FILE = BASE_DIR / "api-key.txt"
OUTPUT_DIR = BASE_DIR / "videos"
USAGE_FILE = BASE_DIR / "usage.jsonl"
PENDING_FILE = BASE_DIR / "pending.json"

MAX_PER_DAY = 60
VIDEO_TTL_HOURS = 72
POLL_INTERVAL = 5
MAX_WAIT_SECONDS = 300
MAX_POLL_FAILURES = 3
USAGE_MAX_BYTES = 1024 * 1024

KEY_SOURCE = "api-key.txt (single file, one key)"
CREDENTIALS_REQUIRED = 1

_usage_lock = threading.Lock()
_submit_lock = threading.Lock()
_finish_lock = threading.Lock()
_pending_lock = threading.Lock()
_runtime_started = False
_OWN_MP4 = re.compile(r"^[0-9a-f]{32}\.mp4$")


class PollInterrupted(RuntimeError):
    """All poll retries failed; the (already paid for) task is recoverable."""


def load_api_key() -> str:
    """Return the ONE key. All failures become a clean RuntimeError."""
    try:
        return keyfile.read_api_key(KEY_FILE)
    except keyfile.KeyFileError as exc:
        raise RuntimeError(str(exc)) from exc


NO_RESUBMIT = "DO NOT resubmit this prompt: a job may already be paid for."


def _failure(exc: BaseException, api_key: str = "", task_id: str = "",
             recoverable: bool = False) -> dict[str, Any]:
    """Turn ANY exception into a safe, actionable MCP result (never a traceback).

    `resubmit_allowed` is explicit so an LLM never mistakes a post-submit error
    for "the generation failed, try again" and burns a second job's credit.
    """
    message = tokenhub.redact(str(exc) or type(exc).__name__, api_key)
    paid = bool(task_id) or recoverable
    out: dict[str, Any] = {
        "ok": False, "error": message, "error_type": type(exc).__name__,
        "resubmit_allowed": not paid,
    }
    if task_id:
        out["task_id"] = task_id
    if paid:
        out["recoverable"] = True
        out["hint"] = f"Call check_video with the task_id to resume. {NO_RESUBMIT}"
    return out


def _pending_result(task_id: str, status: str) -> dict[str, Any]:
    """A job that is still live is NOT a failure. Never let an agent resubmit."""
    return {
        "ok": True, "pending": True, "resubmit_allowed": False,
        "task_id": task_id, "status": status,
        "hint": f"Still generating. Call check_video with this task_id in a minute. {NO_RESUBMIT}",
    }


def _recoverable_result(task_id: str, error: str, status: str = "unknown") -> dict[str, Any]:
    return {
        "ok": False, "recoverable": True, "resubmit_allowed": False,
        "task_id": task_id, "status": status, "error": error,
        "hint": f"Call check_video with this task_id to resume. {NO_RESUBMIT}",
    }


def _log(**fields: Any) -> None:
    """Best-effort usage log. A full disk must never lose a paid task_id."""
    record = {"ts": time.time(), "date": date.today().isoformat(), **fields}
    try:
        with _usage_lock:
            USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with USAGE_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def _submits_today() -> int:
    if not USAGE_FILE.exists():
        return 0
    today = date.today().isoformat()
    count = 0
    try:
        with _usage_lock, USAGE_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(rec, dict) and rec.get("date") == today and rec.get("action") == "submit":
                    count += 1
    except OSError:
        return 0
    return count


def _pending_read() -> dict[str, Any]:
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _pending_write(data: dict[str, Any]) -> None:
    tmp = PENDING_FILE.with_name(PENDING_FILE.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, PENDING_FILE)


def _pending_add(task_id: str, payload: dict[str, Any]) -> None:
    try:
        content = payload.get("content") or []
        prompt = content[0].get("text", "")[:200] if content and isinstance(content[0], dict) else ""
        with _pending_lock:
            PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = _pending_read()
            data[task_id] = {
                "ts": time.time(), "prompt": prompt, "model": payload.get("model", ""),
                "resolution": payload.get("resolution", ""), "duration": payload.get("duration"),
            }
            _pending_write(data)
    except Exception:
        pass  # bookkeeping must never lose the returned task_id


def _pending_remove(task_id: str) -> None:
    try:
        with _pending_lock:
            data = _pending_read()
            if task_id in data:
                data.pop(task_id)
                _pending_write(data)
    except Exception:
        pass


def _pending_list() -> list[dict[str, Any]]:
    """Tolerate a hand-edited/corrupt pending.json: filter BEFORE sorting."""
    with _pending_lock:
        data = _pending_read()
    items = [(str(tid), info) for tid, info in data.items() if isinstance(info, dict)]

    def ts(kv):
        value = kv[1].get("ts", 0)
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0

    items.sort(key=ts, reverse=True)
    return [{"task_id": tid, **info} for tid, info in items[:20]]


def _done_video(task_id: str) -> dict[str, Any] | None:
    """Idempotency: a succeeded task must produce exactly one MP4 / done record."""
    if not USAGE_FILE.exists():
        return None
    found: dict[str, Any] | None = None
    try:
        with _usage_lock, USAGE_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(rec, dict) or rec.get("action") != "done":
                    continue
                if rec.get("task_id") != task_id:
                    continue
                name = str(rec.get("file") or "")
                if not _OWN_MP4.match(name):
                    continue
                path = OUTPUT_DIR / name
                if not path.is_file() or path.stat().st_size == 0:
                    continue
                found = {
                    "ok": True, "task_id": task_id, "status": tokenhub.SUCCESS_STATUS,
                    "pending": False, "model": rec.get("model") or tokenhub.MODEL,
                    "resolution": rec.get("resolution", ""), "duration": rec.get("duration"),
                    "total_tokens": rec.get("total_tokens"),
                    "video_path": str(path), "file_size_bytes": path.stat().st_size,
                    "hint": "This is a local file. Open it directly; no download URL is needed.",
                }
    except OSError:
        return None
    return found


def _clamp_wait(wait_seconds: Any) -> int:
    try:
        return min(max(0, int(wait_seconds)), MAX_WAIT_SECONDS)
    except (TypeError, ValueError):
        return MAX_WAIT_SECONDS


def _start_runtime() -> None:
    """Import-safe startup: mkdir + cleanup thread only when actually serving."""
    global _runtime_started
    if _runtime_started:
        return
    _runtime_started = True
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[hailuo-video] warning: cannot create {OUTPUT_DIR}: {exc}", file=sys.stderr)
    threading.Thread(target=_cleanup_loop, daemon=True, name="hailuo-cleanup").start()


def _cleanup_loop() -> None:
    """Only delete MP4s this server created; prune the usage log."""
    while True:
        try:
            cutoff = time.time() - VIDEO_TTL_HOURS * 3600
            for path in OUTPUT_DIR.glob("*.mp4"):
                if not _OWN_MP4.match(path.name):
                    continue
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError:
                    pass
            for part in OUTPUT_DIR.glob("*.mp4.part"):
                try:
                    if time.time() - part.stat().st_mtime > 3600:
                        part.unlink()
                except OSError:
                    pass
            _prune_usage()
        except Exception as exc:
            print(f"[hailuo-video] cleanup skipped: {type(exc).__name__}", file=sys.stderr)
        time.sleep(3600)


def _prune_usage() -> None:
    try:
        if not USAGE_FILE.exists() or USAGE_FILE.stat().st_size <= USAGE_MAX_BYTES:
            return
        with _usage_lock:
            lines = USAGE_FILE.read_text(encoding="utf-8").splitlines()[-5000:]
            tmp = USAGE_FILE.with_name(USAGE_FILE.name + ".tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.replace(tmp, USAGE_FILE)
    except OSError:
        pass


def _submit_sync(api_key: str, payload: dict[str, Any]) -> str:
    """Atomic cap check + submit + log. POST is never retried (double billing)."""
    with _submit_lock:
        if _submits_today() >= MAX_PER_DAY:
            raise RuntimeError(f"Daily generation cap ({MAX_PER_DAY}) reached on this machine.")
        task_id = tokenhub.submit(api_key, payload)
        _log(action="submit", task_id=task_id,
             **{k: v for k, v in payload.items() if k != "content"})
    _pending_add(task_id, payload)
    return task_id


async def _poll(api_key: str, task_id: str, wait_seconds: Any) -> dict[str, Any]:
    """Poll with bounded retries; a transient error never raises away a task_id."""
    deadline = time.monotonic() + _clamp_wait(wait_seconds)
    failures = 0
    while True:
        try:
            result = await asyncio.to_thread(tokenhub.query, api_key, task_id)
            failures = 0
        except Exception as exc:
            failures += 1
            if failures > MAX_POLL_FAILURES:
                raise PollInterrupted(tokenhub.redact(str(exc), api_key)) from exc
            await asyncio.sleep(min(2 ** failures, 8))
            continue
        status = result.get("status", "unknown")
        if status == tokenhub.SUCCESS_STATUS or status in tokenhub.FAIL_STATUSES:
            return result
        if status not in tokenhub.ACTIVE_STATUSES:
            result["unexpected_status"] = True
            return result
        if time.monotonic() >= deadline:
            result["timed_out"] = True
            return result
        await asyncio.sleep(POLL_INTERVAL)


def _finish_sync(task_id: str, result: dict[str, Any], api_key: str = "") -> dict[str, Any]:
    """Idempotent finish; every failure path keeps the task_id recoverable."""
    status = result.get("status", "unknown")
    if status in tokenhub.FAIL_STATUSES:
        _log(action="fail", task_id=task_id, message=result.get("message", ""), status=status)
        _pending_remove(task_id)
        return {
            "ok": False, "pending": False, "resubmit_allowed": True,
            "task_id": task_id, "status": status,
            "error": result.get("message") or f"TokenHub task {status}",
            "hint": "The job ended without a video. It is safe to re-phrase the prompt and submit a new job.",
        }
    if result.get("unexpected_status"):
        return _recoverable_result(
            task_id, f"Unexpected task status '{status}' from TokenHub.", status
        )
    if result.get("timed_out") or status != tokenhub.SUCCESS_STATUS:
        return _pending_result(task_id, status)

    with _finish_lock:
        existing = _done_video(task_id)
        if existing:
            _pending_remove(task_id)
            return {**existing, "reused": True}

        video_url = result.get("video_url") or ""
        if not video_url:
            return _recoverable_result(
                task_id, "Task succeeded but no video URL was returned.", status
            )
        # Deterministic name: even without the lock, one task = one file.
        filename = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:32] + ".mp4"
        dest = str(OUTPUT_DIR / filename)
        try:
            tokenhub.save_video(video_url, dest)
            size = os.path.getsize(dest)
            if size == 0:
                raise RuntimeError("Downloaded video was empty.")
        except Exception as exc:
            return _recoverable_result(
                task_id, tokenhub.redact(str(exc), api_key), status
            )
        _log(action="done", task_id=task_id, file=filename,
             model=result.get("model", ""), resolution=result.get("resolution", ""),
             duration=result.get("duration"), total_tokens=result.get("total_tokens"), bytes=size)
        _pending_remove(task_id)
        return {
            "ok": True, "task_id": task_id, "status": tokenhub.SUCCESS_STATUS,
            "pending": False, "model": result.get("model") or tokenhub.MODEL,
            "resolution": result.get("resolution", ""), "duration": result.get("duration"),
            "total_tokens": result.get("total_tokens"), "video_path": dest,
            "file_size_bytes": size,
            "hint": "This is a local file. Open it directly; no download URL is needed.",
        }


mcp_server = MCPServer(
    "hailuo-video",
    instructions=(
        "Generate short videos with MiniMax H3 (minimax-video-h3) on Tencent Cloud "
        "TokenHub. Call generate_video with a scene description; it returns "
        "video_path, a local absolute path to the finished MP4. Generation takes "
        "1-3 minutes. If a result has resubmit_allowed=false (pending=true, "
        "recoverable=true, or status=poll_interrupted), call check_video with its "
        "task_id -- the job is already paid for, NEVER resubmit the prompt. "
        "Use recent_tasks to recover a task_id lost to a timeout. "
        "Exactly one credential is needed: the group's single API key in "
        "api-key.txt beside the server, read on every call (no restart needed). "
        "Never ask the user for a second key or token."
    ),
)


@mcp_server.tool()
def video_capabilities() -> dict[str, Any]:
    """Report the model, endpoint, valid ranges, and whether the single key is configured."""
    try:
        try:
            load_api_key()
            key_state = "configured"
        except RuntimeError as exc:
            key_state = f"MISSING - {exc}"
        return {
            "transport": "stdio (local)",
            "key_configured": key_state == "configured",
            "key_status": key_state,
            "key_source": KEY_SOURCE,
            "key_file": str(KEY_FILE),
            "credentials_required": CREDENTIALS_REQUIRED,
            "model": tokenhub.MODEL,
            "also_available": tokenhub.MODEL_H3_MAX,
            "base_url": tokenhub.BASE_URL,
            "auth": "Authorization: Bearer <single API key> (no SecretId/SecretKey, no user field)",
            "duration_seconds_h3": [tokenhub.MIN_DURATION, tokenhub.MAX_DURATION],
            "duration_seconds_h3_max": [tokenhub.MIN_DURATION_MAX_MODEL, tokenhub.MAX_DURATION],
            "resolutions_h3": list(tokenhub.H3_RESOLUTIONS),
            "resolutions_h3_max": list(tokenhub.H3_MAX_RESOLUTIONS),
            "ratios": list(tokenhub.RATIOS),
            "default": {"duration": 6, "resolution": "768P", "ratio": "16:9"},
            "daily_cap": MAX_PER_DAY,
            "pending_jobs": len(_pending_list()),
            "video_output_dir": str(OUTPUT_DIR),
            "note": "Text-to-video only; ratio is required and cannot be 'adaptive'. Result URLs expire in 12h, so MP4s are downloaded locally. A result with pending=true or recoverable=true means the job is already paid for -- use check_video, never resubmit. All results are JSON dicts; no exception ever reaches the client as a traceback.",
        }
    except Exception as exc:
        return _failure(exc)


@mcp_server.tool()
def recent_tasks() -> dict[str, Any]:
    """Recover paid jobs whose task_id was lost to a timeout or network error."""
    try:
        pending = _pending_list()
        recent: list[dict[str, Any]] = []
        if USAGE_FILE.exists():
            with _usage_lock, USAGE_FILE.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()[-20:]
            for line in lines:
                try:
                    rec = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(rec, dict) and rec.get("task_id"):
                    recent.append({
                        "task_id": str(rec["task_id"]), "action": rec.get("action"),
                        "status": rec.get("status"), "date": rec.get("date"),
                    })
        return {
            "ok": True, "pending": pending, "recent": recent,
            "hint": "Call check_video with any task_id to resume a paid job; do NOT resubmit.",
        }
    except Exception as exc:
        return _failure(exc)


@mcp_server.tool()
async def submit_video(
    prompt: str,
    duration: int = 6,
    resolution: str = "768P",
    ratio: str = "16:9",
    model: str = "",
) -> dict[str, Any]:
    """Submit a MiniMax H3 video job without waiting. Returns task_id for check_video."""
    api_key = ""
    try:
        api_key = load_api_key()
        payload = tokenhub.build_payload(prompt, duration, resolution, ratio, model)
        task_id = await asyncio.to_thread(_submit_sync, api_key, payload)
        return {"ok": True, "task_id": task_id, "status": "queued", "model": payload["model"],
                "hint": "Call check_video with this task_id in 1-3 minutes."}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return _failure(exc, api_key)


@mcp_server.tool()
async def check_video(task_id: str, wait_seconds: int = 0) -> dict[str, Any]:
    """Poll a submitted, already-paid job. Returns video_path when done."""
    # Pre-flight failures (no valid key / no usable id) bill nothing, so they
    # must NOT be reported as a recoverable paid job.
    try:
        api_key = load_api_key()
    except Exception as exc:
        return _failure(exc)
    try:
        clean_id = tokenhub.validate_task_id(task_id)
    except Exception as exc:
        return _failure(exc, api_key)

    try:
        result = await _poll(api_key, clean_id, wait_seconds)
        return await asyncio.to_thread(_finish_sync, clean_id, result, api_key)
    except PollInterrupted as exc:
        return {**_failure(exc, api_key, task_id=clean_id), "status": "poll_interrupted"}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return _failure(exc, api_key, task_id=clean_id)


@mcp_server.tool()
async def generate_video(
    prompt: str,
    duration: int = 6,
    resolution: str = "768P",
    ratio: str = "16:9",
    model: str = "",
    wait_seconds: int = 120,
) -> dict[str, Any]:
    """Generate a video and return video_path, a local absolute path to the MP4.

    Takes 1-3 minutes; waits at most 120s by default so a client-side timeout
    cannot swallow the result. Cheapest test: duration=4, resolution=768P.
    Any result with resubmit_allowed=false means the job is already paid for --
    call check_video with its task_id, NEVER call generate_video again.
    """
    api_key = ""
    task_id = ""
    try:
        api_key = load_api_key()
        payload = tokenhub.build_payload(prompt, duration, resolution, ratio, model)
        task_id = await asyncio.to_thread(_submit_sync, api_key, payload)
        result = await _poll(api_key, task_id, wait_seconds)
        return await asyncio.to_thread(_finish_sync, task_id, result, api_key)
    except PollInterrupted as exc:
        return {**_failure(exc, api_key, task_id=task_id), "status": "poll_interrupted"}
    except asyncio.CancelledError:
        if task_id:
            _pending_add(task_id, {"content": [{"type": "text", "text": prompt}]})
        raise
    except Exception as exc:
        return _failure(exc, api_key, task_id=task_id)


def main() -> None:
    """Real STDIO entrypoint. Importing this module has NO side effects."""
    _start_runtime()
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
