"""Tencent Cloud TokenHub (international) MiniMax video client.

    POST https://tokenhub-intl.tencentcloudmaas.com/v1/wand/minimax-video-v2/generation
    GET  https://tokenhub-intl.tencentcloudmaas.com/v1/wand/minimax-video-v2/tasks/{task_id}
    Authorization: Bearer <single API key>

There is NO SecretId/SecretKey pair, NO TC3-HMAC-SHA256 signing, NO region,
and NO `user` field. It is NOT the MPS CreateAigcVideoTask API.

Deliberately there are NO environment overrides. A student machine must not be
able to redirect the single Bearer key to another host (TOKENHUB_BASE_URL) or
silently switch the model. All constants below are the verified deployment
values; tests stub the functions instead of reconfiguring them.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from keyfile import clean_prompt

BASE_URL = "https://tokenhub-intl.tencentcloudmaas.com"
SUBMIT_PATH = "/v1/wand/minimax-video-v2/generation"
QUERY_PATH = "/v1/wand/minimax-video-v2/tasks/{task_id}"

MODEL = "minimax-video-h3"
MODEL_H3 = "minimax-video-h3"
MODEL_H3_MAX = "minimax-video-h3-max"
ALLOWED_MODELS = (MODEL_H3, MODEL_H3_MAX)

RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
H3_RESOLUTIONS = ("768P", "2K")
H3_MAX_RESOLUTIONS = ("480P", "768P")
RESOLUTION_ALIASES = {"1080P": "768P", "4K": "2K", "720P": "768P"}

MIN_DURATION = 4
MIN_DURATION_MAX_MODEL = 5
MAX_DURATION = 15

SUCCESS_STATUS = "succeeded"
FAIL_STATUSES = ("failed", "cancelled")
ACTIVE_STATUSES = ("queued", "running", "pending", "processing")

PROBE_TASK_ID = "4-WandVideo-00000000000000000000000000000000"

REQUEST_TIMEOUT = 30.0
DOWNLOAD_TIMEOUT = 180.0
MAX_VIDEO_BYTES = 200 * 1024 * 1024

_PRIVATE_HOSTS = {
    "localhost", "localhost.localdomain", "metadata", "metadata.google.internal",
    "0.0.0.0", "::1",
}


def redact(text: object, api_key: str = "") -> str:
    """Scrub keys, Bearer values, signed URLs and query secrets from any text.

    Every error string returned to a model goes through this. Raw upstream
    response bodies are never returned.
    """
    out = str(text or "")
    if api_key:
        out = out.replace(api_key, "<redacted>")
    out = re.sub(r"(?i)bearer\s+[A-Za-z0-9._\-]+", "Bearer <redacted>", out)
    out = re.sub(
        r"(?i)\b(sign|signature|token|key|secret|Expires|q-sign-algorithm|q-signature)="
        r"[^&\s\"'<>]+", r"\1=<redacted>", out
    )
    out = re.sub(r"https?://\S+", "<url>", out)
    return out[:300]


_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")


def validate_task_id(task_id: object) -> str:
    """Reject ids that could alter the query URL (slashes, '?', '#', '..', etc.).

    A model can hallucinate a task_id; it must never be able to turn a GET into
    a request for a different TokenHub endpoint.
    """
    if not isinstance(task_id, str):
        raise ValueError("task_id must be a string.")
    value = task_id.strip()
    if not _TASK_ID_RE.match(value):
        raise ValueError(
            "task_id must be 1-256 characters using only letters, digits, '.', "
            "'_' or '-'. Copy it from a submit_video / recent_tasks result."
        )
    return value


def _headers(api_key: str) -> dict[str, str]:
    if not api_key:
        raise ValueError("Empty TokenHub API key.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def resolve_model(model: str) -> str:
    """Accept a full slug (case-insensitive) or the short aliases h3 / max."""
    raw = (model or "").strip().lower()
    aliases = {
        "": MODEL,
        "h3": MODEL_H3,
        "h3-max": MODEL_H3_MAX,
        "max": MODEL_H3_MAX,
        "hailuo": MODEL_H3,
    }
    slug = aliases.get(raw, raw)
    if slug not in ALLOWED_MODELS:
        raise ValueError(f"Unsupported model '{model}'. Use one of: {', '.join(ALLOWED_MODELS)}.")
    return slug


def build_payload(
    prompt: str,
    duration: int = 6,
    resolution: str = "768P",
    ratio: str = "16:9",
    model: str = "",
) -> dict[str, Any]:
    """Build the exact V2 text-to-video request body, with strict validation."""
    text = clean_prompt(prompt)
    slug = resolve_model(model)
    is_max = slug == MODEL_H3_MAX

    # duration drives cost: never silently truncate floats or coerce strings/bools
    if isinstance(duration, bool) or not isinstance(duration, int):
        raise ValueError(
            f"duration must be a whole number of seconds (got {duration!r}); "
            "an LLM-supplied 4.9 would otherwise be silently billed as 4s."
        )
    low = MIN_DURATION_MAX_MODEL if is_max else MIN_DURATION
    if not low <= duration <= MAX_DURATION:
        raise ValueError(
            f"duration for {slug} must be {low}-{MAX_DURATION} seconds (got {duration})."
        )

    res = (resolution or "768P").strip().upper()
    if not is_max:
        res = RESOLUTION_ALIASES.get(res, res)
        allowed = H3_RESOLUTIONS
    else:
        allowed = H3_MAX_RESOLUTIONS
    if res not in allowed:
        hint = " (resolution aliases are H3-only)" if res in RESOLUTION_ALIASES else ""
        raise ValueError(
            f"resolution for {slug} must be one of {', '.join(allowed)} (got {resolution!r}){hint}."
        )

    aspect = (ratio or "16:9").replace("\uff1a", ":").replace(" ", "")
    if aspect not in RATIOS:
        raise ValueError(
            f"ratio must be one of {', '.join(RATIOS)}; 'adaptive' is not allowed for text-to-video."
        )

    return {
        "model": slug,
        "content": [{"type": "text", "text": text}],
        "resolution": res,
        "duration": duration,
        "ratio": aspect,
    }


def _safe_error(response: httpx.Response, api_key: str = "") -> str:
    """Fixed, redacted messages only -- never echo a raw upstream body."""
    code = response.status_code
    if code in (401, 403):
        msg = "API key rejected. Paste the correct single key into api-key.txt."
    elif code == 429:
        msg = "rate limited. Wait a moment and try again."
    elif code >= 500:
        msg = "TokenHub temporarily unavailable. Retry shortly."
    else:
        msg = "request rejected."
    base = f"HTTP {code}: {msg}"
    try:
        data = response.json()
    except Exception:
        return base
    detail = ""
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            detail = str(err.get("message") or err.get("code") or "")
        elif isinstance(err, str):
            detail = err
        if not detail:
            detail = str(data.get("message") or data.get("detail") or data.get("msg") or "")
    if detail:
        detail = redact(detail[:160], api_key).strip()
        if detail and "<url>" not in detail and "<redacted>" not in detail:
            base += f" ({detail})"
    return base


def _check_status(response: httpx.Response, api_key: str) -> None:
    if response.status_code >= 400:
        message = _safe_error(response, api_key)
        if response.status_code in (401, 403):
            raise PermissionError(message)
        raise RuntimeError(message)


def submit(api_key: str, payload: dict[str, Any]) -> str:
    """POST a generation job. Returns task_id.

    POST is NOT retried: a retry after a timeout could create a second paid job.
    """
    response = httpx.post(
        f"{BASE_URL}{SUBMIT_PATH}",
        headers=_headers(api_key),
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    _check_status(response, api_key)
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("TokenHub returned a non-JSON submit response.") from exc
    if not isinstance(data, dict):
        data = {}

    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raw_task = data.get("task")
        candidate = raw_task.get("id") if isinstance(raw_task, dict) else None
        task_id = candidate if isinstance(candidate, str) else ""
    task_id = (task_id or "").strip()
    if not task_id:
        raise RuntimeError("TokenHub accepted the request but returned no usable task_id.")
    return validate_task_id(task_id)


def query(api_key: str, task_id: str) -> dict[str, Any]:
    """GET task status. Always returns a normalised dict, whatever the shape."""
    tid = validate_task_id(task_id)
    url = f"{BASE_URL}{QUERY_PATH.format(task_id=tid)}"
    response = httpx.get(url, headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
    _check_status(response, api_key)
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("TokenHub returned a non-JSON query response.") from exc
    if not isinstance(data, dict):
        return {
            "status": "unknown", "video_url": "", "resolution": "", "duration": None,
            "ratio": "", "model": "", "total_tokens": None, "request_id": "",
            "message": "TokenHub returned an unexpected response shape.",
        }

    raw_task = data.get("task")
    if isinstance(raw_task, dict):
        task = raw_task
    elif raw_task is None:
        task = data  # tolerate a flat response
    else:
        task = {}
    status = str(task.get("status") or data.get("status") or "unknown").lower()
    content = task.get("content")
    content = content if isinstance(content, dict) else {}
    video_url = content.get("url") or task.get("video_url") or ""
    usage = data.get("tokenhub_usage")
    usage = usage if isinstance(usage, dict) else {}
    return {
        "status": status,
        "video_url": str(video_url) if isinstance(video_url, str) else "",
        "resolution": task.get("resolution", "") if isinstance(task.get("resolution", ""), str) else "",
        "duration": task.get("duration"),
        "ratio": task.get("ratio", "") if isinstance(task.get("ratio", ""), str) else "",
        "model": task.get("model", "") if isinstance(task.get("model", ""), str) else "",
        "total_tokens": usage.get("total_tokens"),
        "request_id": data.get("request_id", "") if isinstance(data.get("request_id", ""), str) else "",
        "message": redact(
            task.get("error") or task.get("message")
            or data.get("message") or data.get("error") or "", api_key
        ),
    }


def probe_key(api_key: str) -> int:
    """No-cost credential probe: GET a deliberately nonexistent task id.

    Returns only an HTTP status. Callers must classify strictly: a real valid
    key returns 400 ("Task is not exist."); 401/403 means bad key; 429 means
    throttled; 5xx/404/200/3xx are INCONCLUSIVE and must never be called valid.
    """
    url = f"{BASE_URL}{QUERY_PATH.format(task_id=PROBE_TASK_ID)}"
    response = httpx.get(url, headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
    return response.status_code


def _assert_safe_url(url: str) -> None:
    """Block SSRF into loopback / link-local / private networks."""
    parsed = urlparse(str(url))
    if parsed.scheme != "https":
        raise RuntimeError("Result URL must use https. Refusing to download.")
    host = (parsed.hostname or "").lower()
    if not host or host in _PRIVATE_HOSTS:
        raise RuntimeError("Result URL has no usable host. Refusing to download.")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        try:
            addr = ipaddress.ip_address(socket.gethostbyname(host))
        except (OSError, ValueError):
            return  # a normal CDN hostname we could not resolve offline
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise RuntimeError("Result URL points at a private network. Refusing to download.")


_REDIRECT_CODES = (301, 302, 303, 307, 308)


def _download_hop(url: str, part: Path) -> tuple[str | None, int]:
    """Fetch ONE hop. Returns (next_url, 0) on redirect, or (None, bytes) on data."""
    with httpx.stream(
        "GET", url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=False
    ) as response:
        if response.status_code in _REDIRECT_CODES and response.headers.get("location"):
            return urljoin(url, response.headers["location"]), 0
        if response.status_code in (403, 404, 410):
            raise RuntimeError(
                "The result URL has expired (12h limit). Call check_video again to fetch a fresh URL."
            )
        if response.status_code >= 400:
            raise RuntimeError(
                "Could not download the finished video. Call check_video again in a moment."
            )
        ctype = response.headers.get("content-type", "").lower().split(";")[0].strip()
        if ctype and not (ctype.startswith("video/") or ctype == "application/octet-stream"):
            raise RuntimeError(f"Result was not a video (content-type {ctype[:60]}).")
        total = 0
        with part.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=65536):
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise RuntimeError("Result video exceeds the 200 MB safety limit.")
                fh.write(chunk)
        return None, total


def save_video(url: str, dest: str) -> str:
    """Download a signed MP4 atomically, validating type, size and MP4 magic.

    Redirects are followed manually so EVERY hop is SSRF-checked before the
    request is made (httpx's automatic redirects would only let us inspect the
    final URL). Writes to `<dest>.part` and only replaces the final path after
    a complete, valid download.
    """
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    current = str(url)
    total = 0
    try:
        for _ in range(4):  # initial request + up to 3 redirects
            _assert_safe_url(current)
            following, written = _download_hop(current, part)
            if following is None:
                total = written
                break
            current = following
        else:
            raise RuntimeError("Too many redirects while downloading the finished video.")
        if total == 0:
            raise RuntimeError("Result video was empty.")
        with part.open("rb") as fh:
            if b"ftyp" not in fh.read(16):
                raise RuntimeError("Result was not a valid MP4 file.")
        os.replace(part, path)
    except BaseException:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return str(path)
