"""The single source of truth for reading the ONE pasted TokenHub API key.

Stdlib only: setup_mcp.py must be able to import this before .venv exists, and
server.py / check_key.py use the exact same normalisation so a key that passes
setup cannot fail in the server (or vice versa).

No value from the key file is ever included in an exception or log message.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

PLACEHOLDER_MARKERS = ("PASTE_", "YOUR_API_KEY", "REPLACE_WITH", "EXAMPLE")
MAX_KEY_LENGTH = 4096
MAX_PROMPT_CHARS = 2000


class KeyFileError(RuntimeError):
    """A safe, user-facing key-file error. Never contains the key itself."""


def normalize_key_line(line: str) -> str:
    """Normalise one pasted line without ever rejecting a legitimate key.

    Handles the classroom classics: UTF-8 BOM, surrounding quotes, a stray
    `Bearer ` prefix, trailing whitespace, and accidental internal spaces.
    """
    text = (line or "").strip().lstrip("\ufeff").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'`":
        text = text[1:-1].strip()
    if text[:7].lower() == "bearer ":
        text = text[7:].strip()
    text = "".join(text.split())
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    return text


def read_api_key(path: Path) -> str:
    """Return the one key, or raise KeyFileError with an actionable message."""
    path = Path(path)
    where = f"{path} (one line, no quotes, no 'Bearer ' prefix)"

    if not path.exists():
        raise KeyFileError(
            "No TokenHub API key configured. Paste your single API key into " + where
        )
    if not path.is_file():
        raise KeyFileError(
            f"Key path {path} is not a file. Delete that folder and let setup recreate api-key.txt."
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise KeyFileError(
            f"Cannot read {path} ({type(exc).__name__}). Check file permissions and try again."
        ) from exc

    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:64]:
        raise KeyFileError(
            f"{path} looks like UTF-16 ('Unicode'), not UTF-8. "
            "Open it in a text editor and save as UTF-8 (no BOM), then paste the single key again."
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise KeyFileError(
            f"{path} is not valid UTF-8. Re-save it as UTF-8 and paste the single key again."
        ) from exc

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise KeyFileError(
            "No TokenHub API key configured. Paste your single API key into " + where
        )
    key = normalize_key_line(lines[0])
    if not key:
        raise KeyFileError(
            "No TokenHub API key configured. Paste your single API key into " + where
        )
    if any(marker in key.upper() for marker in PLACEHOLDER_MARKERS):
        raise KeyFileError(
            f"{path} still contains the placeholder text. Replace it with your single real API key."
        )
    if len(key) > MAX_KEY_LENGTH:
        raise KeyFileError("The pasted key is implausibly long. Re-paste just the single API key.")
    try:
        key.encode("ascii")
    except UnicodeEncodeError as exc:
        raise KeyFileError(
            "The pasted key contains non-ASCII characters. Re-paste only the single API key."
        ) from exc
    return key


def read_key_optional(path: Path) -> str | None:
    """Read the key for setup/status checks; return None for any problem."""
    try:
        return read_api_key(path)
    except KeyFileError:
        return None


def clean_prompt(prompt: object) -> str:
    """Validate and normalise a scene description before it is sent (and billed)."""
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a text scene description.")
    text = unicodedata.normalize("NFC", prompt)
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    text = " ".join(text.split()).strip()
    if not text:
        raise ValueError("prompt must be a non-empty scene description.")
    if len(text) > MAX_PROMPT_CHARS:
        raise ValueError(
            f"prompt is too long ({len(text)} characters). Keep it under {MAX_PROMPT_CHARS}."
        )
    return text
