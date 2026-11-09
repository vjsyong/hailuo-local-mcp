"""Tencent Cloud TokenHub (international) MiniMax video client.

This is the API the teacher's console curl actually uses:

    POST https://tokenhub-intl.tencentcloudmaas.com/v1/wand/minimax-video-v2/generation
    GET  https://tokenhub-intl.tencentcloudmaas.com/v1/wand/minimax-video-v2/tasks/{task_id}
    Authorization: Bearer <single API key>

There is NO SecretId/SecretKey pair, NO TC3-HMAC-SHA256 signing, NO region,
and NO `user` field. It is NOT the MPS `CreateAigcVideoTask` API.

Generation is asynchronous: submit returns a task_id, then poll until the task
status is `succeeded` / `failed` / `cancelled`. The finished MP4 lives at
`task.content.url` and that URL expires after 12 hours, so the server downloads
it immediately into a local `videos/<uuid>.mp4` file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

BASE_URL = os.environ.get(
    "TOKENHUB_BASE_URL", "https://tokenhub-intl.tencentcloudmaas.com"
).rstrip("/")
SUBMIT_PATH = "/v1/wand/minimax-video-v2/generation"
QUERY_PATH = "/v1/wand/minimax-video-v2/tasks/{task_id}"

# Verified model slugs on the intl TokenHub "wand" V2 endpoint.
MODEL = os.environ.get("TOKENHUB_MODEL", "minimax-video-h3")
MODEL_H3 = "minimax-video-h3"
MODEL_H3_MAX = "minimax-video-h3-max"
ALLOWED_MODELS = (MODEL_H3, MODEL_H3_MAX)

# Text-to-video ratio cannot be "adaptive".
RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")

H3_RESOLUTIONS = ("768P", "2K")
H3_MAX_RESOLUTIONS = ("480P", "768P")
# Friendly aliases that the API silently downgrades for H3.
RESOLUTION_ALIASES = {"1080P": "768P", "4K": "2K", "720P": "768P"}

MIN_DURATION = 4
MIN_DURATION_MAX_MODEL = 5
MAX_DURATION = 15

SUCCESS_STATUS = "succeeded"
FAIL_STATUSES = ("failed", "cancelled")
ACTIVE_STATUSES = ("queued", "running", "pending", "processing")

# A deliberately nonexistent task id. Querying it creates no video job and
# spends no generation credit, which makes it a safe credential probe.
PROBE_TASK_ID = "4-WandVideo-00000000000000000000000000000000"

REQUEST_TIMEOUT = float(os.environ.get("TOKENHUB_TIMEOUT_SECONDS", "30"))
DOWNLOAD_TIMEOUT = float(os.environ.get("TOKENHUB_DOWNLOAD_TIMEOUT_SECONDS", "180"))


def _headers(api_key: str) -> dict[str, str]:
    if not api_key:
        raise ValueError("Empty TokenHub API key.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def resolve_model(model: str) -> str:
    """Accept a full slug or the short aliases 'h3' / 'max'."""
    raw = (model or "").strip()
    aliases = {
        "": MODEL,
        "h3": MODEL_H3,
        "h3-max": MODEL_H3_MAX,
        "max": MODEL_H3_MAX,
        "hailuo": MODEL_H3,
    }
    slug = aliases.get(raw.lower(), raw)
    if slug not in ALLOWED_MODELS:
        raise ValueError(
            f"Unsupported model '{model}'. Use one of: {', '.join(ALLOWED_MODELS)}."
        )
    return slug


def build_payload(
    prompt: str,
    duration: int = 6,
    resolution: str = "768P",
    ratio: str = "16:9",
    model: str = "",
) -> dict[str, Any]:
    """Build the exact V2 text-to-video request body, with validation.

    Mirrors the console example:
        {"model": "minimax-video-h3",
         "content": [{"type": "text", "text": "A cat sitting on the desk"}],
         "resolution": "768P", "duration": 4, "ratio": "16:9"}
    """
    text = (prompt or "").strip()
    if not text:
        raise ValueError("prompt must be a non-empty scene description.")

    slug = resolve_model(model)
    is_max = slug == MODEL_H3_MAX

    try:
        seconds = int(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"duration must be an integer number of seconds, got {duration!r}") from exc
    low = MIN_DURATION_MAX_MODEL if is_max else MIN_DURATION
    if not low <= seconds <= MAX_DURATION:
        raise ValueError(
            f"duration for {slug} must be {low}-{MAX_DURATION} seconds (got {seconds})."
        )

    res = (resolution or "768P").strip().upper()
    if not is_max:
        res = RESOLUTION_ALIASES.get(res, res)
        allowed = H3_RESOLUTIONS
    else:
        allowed = H3_MAX_RESOLUTIONS
    if res not in allowed:
        raise ValueError(
            f"resolution for {slug} must be one of {', '.join(allowed)} (got {resolution!r})."
        )

    aspect = (ratio or "16:9").strip()
    if aspect not in RATIOS:
        raise ValueError(
            f"ratio must be one of {', '.join(RATIOS)}; 'adaptive' is not allowed for text-to-video."
        )

    return {
        "model": slug,
        "content": [{"type": "text", "text": text}],
        "resolution": res,
        "duration": seconds,
        "ratio": aspect,
    }


def _error_message(response: httpx.Response) -> str:
    body = response.text.strip()
    try:
        data = response.json()
    except ValueError:
        return f"HTTP {response.status_code}: {body[:300]}"
    if isinstance(data, dict):
        for key in ("message", "error", "detail", "msg"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return f"HTTP {response.status_code}: {value[:300]}"
            if isinstance(value, dict) and value.get("message"):
                return f"HTTP {response.status_code}: {str(value['message'])[:300]}"
    return f"HTTP {response.status_code}: {body[:300]}"


def submit(api_key: str, payload: dict[str, Any]) -> str:
    """POST a generation job. Returns task_id."""
    response = httpx.post(
        f"{BASE_URL}{SUBMIT_PATH}",
        headers=_headers(api_key),
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code in (401, 403):
        raise PermissionError(_error_message(response))
    if response.status_code >= 400:
        raise RuntimeError(_error_message(response))
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"TokenHub returned non-JSON submit response: {response.text[:200]}") from exc
    task_id = data.get("task_id") or (data.get("task") or {}).get("id")
    if not task_id:
        raise RuntimeError(f"TokenHub submit returned no task_id: {str(data)[:300]}")
    return str(task_id)


def query(api_key: str, task_id: str) -> dict[str, Any]:
    """GET task status. Returns a normalized dict.

    Success response shape:
        {"task": {"id": ..., "status": "succeeded",
                  "content": {"url": "https://.../output.mp4"},
                  "resolution": "768P", "duration": 5, "ratio": "16:9"},
         "tokenhub_usage": {"total_tokens": 102655},
         "request_id": "..."}
    """
    url = f"{BASE_URL}{QUERY_PATH.format(task_id=task_id)}"
    response = httpx.get(url, headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
    if response.status_code in (401, 403):
        raise PermissionError(_error_message(response))
    if response.status_code >= 400:
        raise RuntimeError(_error_message(response))
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"TokenHub returned non-JSON query response: {response.text[:200]}") from exc

    task = data.get("task") if isinstance(data, dict) else None
    if not isinstance(task, dict):
        task = data if isinstance(data, dict) else {}
    status = str(task.get("status") or data.get("status") or "unknown").lower()
    content = task.get("content") or {}
    if not isinstance(content, dict):
        content = {}
    video_url = content.get("url") or task.get("video_url") or ""
    usage = data.get("tokenhub_usage") or {}
    return {
        "status": status,
        "video_url": str(video_url) if video_url else "",
        "resolution": task.get("resolution", ""),
        "duration": task.get("duration"),
        "ratio": task.get("ratio", ""),
        "model": task.get("model", ""),
        "total_tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
        "request_id": data.get("request_id", ""),
        "message": str(
            task.get("error")
            or task.get("message")
            or data.get("message")
            or data.get("error")
            or ""
        ),
    }


def probe_key(api_key: str) -> tuple[int, str]:
    """No-cost credential check: query a nonexistent task id.

    No generation job is created, so no credit is spent. Classification is
    done by HTTP status only (401/403 = bad key, anything else = accepted),
    so it does not depend on the exact error body shape.
    """
    url = f"{BASE_URL}{QUERY_PATH.format(task_id=PROBE_TASK_ID)}"
    response = httpx.get(url, headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
    return response.status_code, response.text.strip()[:300]


def save_video(url: str, dest: str) -> str:
    """Download the temporary result MP4 to a stable local path."""
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=65536):
                fh.write(chunk)
    return str(path)
