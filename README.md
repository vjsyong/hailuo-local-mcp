# Hailuo Video MCP — local STDIO server, one API key per group

**This README is the canonical runbook for the student's WorkBuddy agent.** When a
student says *"Set up the video MCP in this repo"*, the agent executes [§1 Agent
runbook](#1-agent-runbook--do-exactly-this) in order, without improvising.
[AGENTS.md](AGENTS.md) is the extended reference and design rationale; if the two
ever disagree, this README wins.

```text
GOAL            Install a local STDIO MCP server that generates MiniMax H3 videos
                from inside WorkBuddy, using ONE Tencent Cloud TokenHub API key.

AGENT COMMAND   Windows:        python  setup_mcp.py --install --verify-key
                macOS / Linux:  python3 setup_mcp.py --install --verify-key
                (run from the directory containing this README)

STUDENT ACTIONS 1. Paste ONE API key into api-key.txt (line 1, plain text)
                2. Connectors -> Custom Connector -> Trust "hailuo-video"
                3. START A NEW CHAT SESSION
                These three are the ONLY manual steps. Everything else is yours.

CREDENTIALS     1 key. No env var, no group token, no SecretId/SecretKey,
                no user field, no headers, no second paste.

COST            Setup, --check, check_key.py and selftest.py spend ZERO credit.
                Only submit_video / generate_video create a paid job.

NEVER           Echo or log the key; put it in any config or commit; resubmit a
                paid job; write to server stdout; change model/endpoint/defaults;
                add an environment-variable override; patch code to "fix" failures.

SUCCESS         video_capabilities -> key_configured=true, credentials_required=1
                then generate_video -> video_path (a LOCAL absolute MP4 path)
```

---

## 0. What this is

WorkBuddy launches `server.py` as a subprocess on the student's own computer and
speaks MCP over stdin/stdout. There is **no hosted server, no port, no public
URL, and no group-token system**. The finished video is downloaded to `videos/`
and returned as a local absolute `video_path` — there is no `download_url` to
serve.

| | |
|---|---|
| Model | `minimax-video-h3` (also `minimax-video-h3-max`) |
| API | `https://tokenhub-intl.tencentcloudmaas.com/v1/wand/minimax-video-v2/...` |
| Auth | ONE `Authorization: Bearer <API key>` header |
| Not this | **Not** MPS `CreateAigcVideoTask`; no TC3 signing, no region, no `user` field |
| Key storage | line 1 of `api-key.txt` only, read on **every** tool call (no restart to rotate) |

**One group = one key = one OS account = one clone.** Two groups sharing a
machine/account will overwrite each other's connector entry and key file.

---

## 1. Agent runbook — do exactly this

### Step 0 — Orient (read-only, no side effects)

Set `REPO_ROOT` to the directory containing this README. Work from there; do not
guess a path. Then run:

```bash
git status --short                          # must be clean-ish; note untracked files
python --version        # Windows
python3 --version       # macOS / Linux
python3 setup_mcp.py --check               # read-only status (Windows: python ...)
```

`--check` returning exit code `1` on a fresh clone is **expected** — it means the
install has not run yet, not that something is broken. Do not treat it as an error
and do not try to "repair" files by hand.

### Step 1 — Prerequisites gate (STOP if unmet)

* **Python 3.10+** is required (3.11+ recommended). Setup exits `1` with
  `SETUP INCOMPLETE: Python 3.10+ is required` on older interpreters.
* **macOS:** there is no `python`, and the Xcode Command Line Tools `python3` is
  **3.9** — too old. Before setup, run `python3 --version`; if below 3.10, have
  the student install Python once:

  ```bash
  brew install python@3.12                 # or https://www.python.org/downloads/macos/
  python3 --version                       # must print 3.10 or newer
  xcode-select --install                  # only if pip later needs to compile a wheel
  ```

* **First run needs PyPI access** for `mcp==2.3.0` and `httpx==0.28.1`. For a
  locked-down lab, set `HAILUO_WHEELHOUSE` to a folder of wheels; setup then
  installs with `--no-index --find-links`.
* Never install dependencies globally, never create `.venv` by hand, never edit
  `~/.workbuddy-ai/mcp.json` by hand. `setup_mcp.py` does all of it.

### Step 2 — Run the ONE setup command

```bash
# Windows
python setup_mcp.py --install --verify-key        # or: py -3.11 setup_mcp.py --install --verify-key

# macOS / Linux  (never bare `python` here)
python3 setup_mcp.py --install --verify-key
```

Setup is **single-pass**: it completes fully even when `api-key.txt` does not
exist yet or still holds the placeholder. In order, it:

1. Creates `api-key.txt` from `api-key.example.txt` if missing (gitignored).
2. Creates `.venv/` and installs `requirements.txt` — skipped when imports
   already resolve, so re-runs are offline-safe.
3. Verifies `mcp`, `httpx`, `tokenhub`, `server`, `keyfile` import cleanly.
4. Writes `mcp.local.json` — a paste-ready STDIO config with **absolute**
   `command`/`args` paths, no secrets, no `env`, no `url`, no headers.
5. Merges the entry into `~/.workbuddy-ai/mcp.json`, and into
   `~/.workbuddy/mcp.json` when that folder exists — preserving every other
   server, tolerating malformed JSON, backing up with a collision-proof name,
   and reading the file back to confirm the entry landed.
6. Installs a local pre-commit guard that blocks committing `api-key.txt` or
   edits to `api-key.example.txt` (skipped if a hook already exists).
7. With `--verify-key`, makes **one no-cost** TokenHub auth probe. It is skipped
   cleanly if no key has been pasted, and a rejected/inconclusive probe **never
   fails the install**.

Do not pass `--install` twice, do not re-run setup after the key paste, and do
not run `selftest.py` as a "fix" — it is offline verification only.

### Step 3 — Interpret setup output (decision table)

| Exact output fragment | Meaning | Your next action |
|---|---|---|
| `SETUP INCOMPLETE: Python 3.10+ is required` | Wrong interpreter | Go to Step 1; do not continue |
| `SETUP INCOMPLETE: Could not create .venv` | Missing `venv` module / broken Python | Install a full Python 3.10+; re-run once |
| `SETUP INCOMPLETE: Dependency install failed` | No PyPI / proxy / wheelhouse | Fix network or set `HAILUO_WHEELHOUSE`; re-run |
| `[!!] Ignored legacy environment variables: ...` | Old `TOKENHUB_*` vars are set but ignored | Tell student to unset them; **do not** use them as a key source |
| `[!] Created api-key.txt -- this is the ONLY file you ever edit` | Normal on a fresh clone | Continue |
| `[!] api-key.txt has no key yet (setup continues).` | Normal — key not pasted | Continue to Step 4 |
| `[ok] ONE API key found in api-key.txt (value never displayed)` | Key already present | Continue to Step 5 |
| `[!!] <path>: ...` on a config merge line | That config could not be written | Use `mcp.local.json` as the manual paste fallback |
| `SKIPPED - no key pasted yet. No network call, no credit spent.` | Probe skipped | Continue to Step 4 |
| `[!!] Key probe was inconclusive or the key was rejected. Setup itself IS complete.` | Network or key problem, **not** an install failure | Continue to Step 5, do not re-run setup |
| `INSTALL WRITTEN -- activation is NOT complete.` | **Expected final line — install succeeded** | Continue to Step 6 |

If setup ends with `INSTALL WRITTEN -- activation is NOT complete.`, the agent's
job is **not finished**. The connector does not activate automatically; two human
UI actions in Step 6 are still required.

### Step 4 — Get the single key into `api-key.txt`

This is the only file a student edits. Ask for it in plain text:

> Paste your group's **one** API key into `api-key.txt` on line 1 — plain UTF-8
> text, no quotes, no `Bearer ` prefix, nothing else in the file. Save it.

Rules:

* `keyfile.py` normalises a UTF-8 BOM, surrounding quotes, a stray `Bearer `
  prefix, whitespace and control characters — but **rejects** UTF-16 / "Unicode"
  saves, non-ASCII characters (curly quotes from TextEdit), the placeholder text,
  empty files and implausibly long pastes, with an explicit message.
* On macOS, tell students to use VS Code, BBEdit or `nano`, **not** TextEdit in
  its default Rich Text / smart-quotes mode.
* If the student pastes the key into chat instead, write it **directly** to
  `api-key.txt` as a single line. Do **not** repeat it back, quote it, log it,
  summarise it, or echo it into any other file. Do not guess, generate or fetch
  a key.
* **Do not re-run `setup_mcp.py --install` after the paste.** The server reads
  `api-key.txt` on every tool call; no restart and no second setup pass is
  needed. Re-running install only creates noise and backup files.

### Step 5 — Verify the key with ZERO credit

```bash
.venv/Scripts/python.exe check_key.py    # Windows
.venv/bin/python check_key.py            # macOS / Linux
```

`check_key.py` performs **one task lookup on a deliberately nonexistent id** — it
creates no video job and spends no credit. Classify strictly:

| Output | Meaning | Action |
|---|---|---|
| `KEY VALID  [HTTP 400; auth accepted, probe task not found]` | Only valid result (exit 0) | Proceed to Step 6 |
| `INVALID KEY  [HTTP 401/403]` | Wrong or expired key | Re-paste the same single key. **Never** ask for a second credential |
| `THROTTLED  [HTTP 429]` | Auth fine, rate-limited | Wait, re-run. Do not generate yet |
| `INCONCLUSIVE` (5xx, 404, 200, 3xx, 408, network error) | Unknown | Fix network / retry. **Do not generate** — an unverified key would spend real credit |
| `MISSING KEY - ...` | Placeholder, bad encoding, or empty file | Go back to Step 4 |

### Step 6 — Activation: hand off the two UI actions

You cannot click these. Give the student these exact instructions:

> In WorkBuddy: **Connectors** (left sidebar) → **Custom Connector**
> (top-right) → click **Trust** on `hailuo-video`. Then **START A NEW CHAT
> SESSION**. Tool lists load when a session starts — the connector will not
> appear in the current chat.
>
> If it still never appears, open `mcp.local.json` and paste that `mcpServers`
> block into WorkBuddy's MCP settings manually.

**Do not skip the new-session step.** It is the single most common false
"setup failed" report.

### Step 7 — Verify the connector is live

In the **new** chat session, call `video_capabilities()`. Assert:

```text
transport            = "stdio (local)"
key_configured       = true
credentials_required = 1
model                = "minimax-video-h3"
```

If `key_configured` is false, go back to Step 4 (do not re-run setup). If the
tool is unavailable, go back to Step 6 (Trust + new session). Every tool returns
a JSON dict; no exception ever reaches the client as a traceback, and all error
text is redacted of keys and signed URLs.

### Step 8 — First generation (cheapest possible)

Use the minimal settings so the smoke test costs as little as possible:

```text
generate_video(prompt="A cat sitting on a desk", duration=4,
               resolution="768P", ratio="16:9")
```

Generation takes **1–3 minutes**; `generate_video` waits at most 120 s by
default, so it very often returns `pending: true` with a `task_id`. Follow [§4
Result handling](#4-result-handling--obey-resubmit_allowed) — do not treat
"pending" as failure. On success, report the local `video_path` to the student
and tell them to open the file directly; there is no URL.

### Step 9 — Report back

Tell the student: where the MP4 is (`video_path`), that it is a local file, and
that they can ask for more videos. Never include the key, a Bearer value, a
signed URL, or the contents of any config file in your reply. Do not commit
anything.

---

## 2. Hard invariants — never violate these

1. **One key.** Never ask a student for a second key, token, SecretId,
   SecretKey, `user` value or header. A failure means a bad single key or a
   network problem — not a missing second credential.
2. **Never expose the key.** Never print, echo, log, quote, summarise, or write
   the contents of `api-key.txt` into any file, commit, chat message, config,
   `env` block or persisted environment variable.
3. **Never commit secrets or runtime output.** Never `git add` / commit
   `api-key.txt`, edits to `api-key.example.txt`, `mcp.local.json`, `videos/`,
   `usage.jsonl`, `pending.json`, `.venv/`, `*.mp4.part` or any `*.bak`. Run
   `git status --short` first; never use `git add -A`.
4. **Obey `resubmit_allowed`.** See §4. A second submit for one prompt can bill
   twice.
5. **Do not change the deployment constants.** Model `minimax-video-h3`,
   `BASE_URL`, timeouts, resolution/duration rules, and the lack of environment
   overrides are deliberate. Never add `TOKENHUB_API_KEY`, `TOKENHUB_BASE_URL`
   or `TOKENHUB_MODEL` handling. Legacy `TOKENHUB_*` variables are ignored.
6. **`server.py` must never write to stdout.** stdout carries the JSON-RPC
   stream. The MCP SDK v2 claims fd 1 and diverts stray output to stderr; do
   **not** add `sys.stdout = sys.stderr` — that would make the SDK serve MCP
   over stderr.
7. **Do not patch code to work around a failure.** If you believe the code is
   wrong, stop, report the exact output, and leave the repo unchanged. This is a
   one-shot classroom deployment; a local "clever fix" would diverge from all
   other groups.
8. **Do not generate with an unverified key.** A real generation spends real
   credit from the group's allowance.

---

## 3. Tool contract (exact parameters)

All five tools are exposed by the `hailuo-video` STDIO server.

| Tool | Purpose |
|---|---|
| `video_capabilities()` | Model, valid ranges, `credentials_required`, `key_source`, `key_configured`, `daily_cap`, `pending_jobs`, output dir |
| `generate_video(...)` | Submit → poll → download → return local `video_path` |
| `submit_video(...)` | Submit only, returns `task_id` (safest on slow/unreliable clients) |
| `check_video(task_id, wait_seconds=0)` | Resume an already-paid job; returns `video_path` when done |
| `recent_tasks()` | Recover a `task_id` lost to a timeout or network error |

### Parameters

| Parameter | Applies to | Type / default | Valid values |
|---|---|---|---|
| `prompt` | `generate_video`, `submit_video` | required string | Non-empty scene description, ≤ 2000 characters |
| `duration` | `generate_video`, `submit_video` | `int` = `6` | H3: **4–15**; H3-Max: **5–15**. Must be a whole `int` (a float or bool is rejected, not rounded) |
| `resolution` | `generate_video`, `submit_video` | `"768P"` | H3: `768P`, `2K` (aliases `1080P`/`720P` → `768P`, `4K` → `2K`); H3-Max: `480P`, `768P` only |
| `ratio` | `generate_video`, `submit_video` | `"16:9"` | `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`. `adaptive` is **not** allowed for text-to-video |
| `model` | `generate_video`, `submit_video` | `""` | `""`/`h3`/`hailuo` → `minimax-video-h3`; `max`/`h3-max` → `minimax-video-h3-max` |
| `wait_seconds` | `generate_video` | `120` | 0–300 (clamped). Keeps a client-side timeout from swallowing a paid result |
| `wait_seconds` | `check_video` | `0` | 0–300 (clamped) |
| `task_id` | `check_video` | required string | 1–256 chars: letters, digits, `.`, `_`, `-`. Copy from a result or `recent_tasks` |

### Result shapes

```jsonc
// success (also "reused": true on an idempotent repeat check_video)
{"ok": true, "pending": false, "task_id": "...", "status": "succeeded",
 "model": "minimax-video-h3", "resolution": "768P", "duration": 4,
 "total_tokens": 200000, "video_path": "/abs/path/videos/<32hex>.mp4",
 "file_size_bytes": 750341,
 "hint": "This is a local file. Open it directly; no download URL is needed."}

// still generating — NOT a failure
{"ok": true, "pending": true, "resubmit_allowed": false,
 "task_id": "...", "status": "running", "hint": "... call check_video ..."}

// recoverable post-submit problem
{"ok": false, "recoverable": true, "resubmit_allowed": false,
 "task_id": "...", "status": "...", "error": "...", "hint": "..."}

// pre-submit failure (bad key, bad params) — no job was created
{"ok": false, "error": "...", "error_type": "...", "resubmit_allowed": true}
```

(`task_id`, `video_path`, `total_tokens` and `file_size_bytes` above are
illustrative values from one real 4s / 768P test — they differ per job.)

---

## 4. Result handling — obey `resubmit_allowed`

> **Never infer retry permission from `ok`, `status`, or the presence of an
> `error` field.** Read `resubmit_allowed` and act on that flag only.

| `resubmit_allowed` | What it means | Your action |
|---|---|---|
| `false` | A job has already been paid for (`pending: true`, `recoverable: true`, `status: poll_interrupted`, or any result carrying a `task_id`) | Call `check_video(task_id=...)`. If the id was lost, call `recent_tasks()`. **Never** call `generate_video` or `submit_video` again for that prompt |
| `true` | No paid job is outstanding — a bad key, rejected parameters, or TokenHub reported `failed` / `cancelled` | Fix the cause, then submit **once**. Follow the `hint` in the result |

Supporting behaviour:

* `POST` is never retried (a retry after a timeout could create a second paid
  job). Polling retries transient errors up to 3 times before returning a
  recoverable `poll_interrupted` result **with the `task_id`**.
* `pending.json` records submitted jobs; `recent_tasks()` lists the pending jobs
  plus the last 20 logged `task_id`s.
* Completion is **idempotent**: a succeeded task produces exactly one MP4 and one
  log record; repeated `check_video` returns `reused: true` and the same path.
* `videos/` is cleaned after **72 hours**, and only `<32 hex>.mp4` files this
  server created. A per-machine cap of **60 submits/day** is enforced via
  `usage.jsonl` (pruned automatically).
* Signed result URLs expire in **12 hours**; that is why MP4s are downloaded
  locally and validated (`ftyp` magic, content type, 200 MB limit, per-hop SSRF
  check) before being atomically moved into place.

---

## 5. Failure → exact action

| Symptom | Action |
|---|---|
| `No TokenHub API key configured` | Paste the single key into `api-key.txt`, line 1, no quotes |
| `still contains the placeholder text` | Replace `PASTE_YOUR_TOKENHUB_API_KEY_HERE` with the real key |
| `looks like UTF-16` / `not valid UTF-8` / `non-ASCII characters` | Re-save as UTF-8 (no BOM) in VS Code / BBEdit / `nano`; TextEdit RTF and smart quotes cause this |
| `implausibly long` | Re-paste **only** the key, not a whole cURL/JSON block |
| `KEY VALID` never appears | See Step 5. Do not generate |
| `API key rejected` (HTTP 401/403) | Wrong/expired key; re-paste. Never add a second credential |
| `rate limited` (429) | Wait and retry the same single key |
| `SETUP INCOMPLETE: Python 3.10+` (macOS) | Xcode CLT ships 3.9: `brew install python@3.12` or python.org installer, verify `python3 --version`, re-run setup |
| `command not found: python` | macOS/Linux: use `python3 setup_mcp.py --install --verify-key` |
| `pip` / TLS / venv error | Needs PyPI + `python3-venv`; macOS: `xcode-select --install`; offline: `HAILUO_WHEELHOUSE` |
| `ModuleNotFoundError: mcp` | Run with the `.venv` python, or re-run `setup_mcp.py --install` |
| Connector unavailable / missing | Step 6: Trust it, then **START A NEW CHAT SESSION** |
| `generate_video` times out client-side | It returns a `task_id`; call `check_video`. Do NOT resubmit. Prefer `submit_video` next time |
| Lost the `task_id` | Call `recent_tasks`, then `check_video` with that id |
| Config lost after moving the folder | Absolute paths are stale — re-run `setup_mcp.py --install` to regenerate |
| `Daily generation cap (60) reached` | Local safety limit; wait until the next local date or use a separate machine |
| Two groups on one computer | Not supported: separate OS accounts **and** separate clones |
| Nothing happens / JSON parse errors | Something wrote to stdout. STDIO servers must keep stdout clean — do not add prints |

---

## 6. Command reference

```bash
# setup (single pass; completes before the key is pasted)
python  setup_mcp.py --install --verify-key       # Windows
python3 setup_mcp.py --install --verify-key       # macOS / Linux

python3 setup_mcp.py --check          # read-only: venv / key / both config entries
python3 setup_mcp.py --uninstall      # remove ONLY hailuo-video (with backup)
python3 setup_mcp.py                  # dry run: builds .venv + mcp.local.json, no global install

# no-cost key probe (Windows: .venv/Scripts/python.exe)
.venv/bin/python check_key.py

# offline end-to-end regression suite (zero TokenHub calls, zero credit)
.venv/bin/python selftest.py

# offline classroom install
HAILUO_WHEELHOUSE=/path/to/wheels python3 setup_mcp.py --install --verify-key
```

`setup_mcp.py` prints `INSTALL WRITTEN -- activation is NOT complete.` on
success and never claims the connector is live. It exits `1` on an unsupported
Python or a failed dependency install; it may have *created* `api-key.txt`, but it
never overwrites an existing key value or any existing config. `--check` exits
`1` when the install is incomplete. `check_key.py`
exits `0` **only** for `KEY VALID` (HTTP 400).

---

## 7. Platform notes

| | Windows | macOS (Intel / Apple Silicon) | Linux |
|---|---|---|---|
| Setup command | `python setup_mcp.py --install --verify-key` | `python3 setup_mcp.py --install --verify-key` | `python3 setup_mcp.py --install --verify-key` |
| Venv python | `.venv/Scripts/python.exe` | `.venv/bin/python` | `.venv/bin/python` |
| Python prerequisite | 3.10+ | **3.10+ — stock `python3` is 3.9** | 3.10+ and `python3-venv` |
| Config | `~/.workbuddy-ai/mcp.json` (+ `~/.workbuddy/mcp.json` if that folder exists) | same | same |

Generated STDIO config (setup picks the branch automatically via `os.name`):

```json
{
  "mcpServers": {
    "hailuo-video": {
      "command": "/Users/student/hailuo-local-mcp/.venv/bin/python",
      "args": ["/Users/student/hailuo-local-mcp/server.py"]
    }
  }
}
```

There is **no** `env`, `type`, `url` or `headers` key — STDIO servers use
`command`/`args` only. Paths use forward slashes (`.as_posix()`), so they are
copy-safe on Windows and native on macOS/Linux. The MCP SDK spawns
`[command, *args]` without a shell, so paths with spaces are safe (though a
simple clone path like `~/hailuo-local-mcp` is still best). `.gitattributes`
forces LF endings; the pre-commit guard uses `#!/bin/sh` with mode 0755.

**Verified macOS compatibility:** the only OS branch in the repo is
`venv_python()`; everything else uses portable `pathlib`, `os.replace`,
`os.chmod`, `threading` and `st_mtime`. MCP SDK 2.3.0 is cross-platform — its
Windows-only module guards every Windows import behind `sys.platform == "win32"`,
and `pywin32` is the only OS-gated dependency (`sys_platform == 'win32'`, skipped
by pip on macOS). Source-verified on Windows; the final confirmation should be
one Mac student running the full flow before you distribute to all groups.

---

## 8. Student quick start (human-facing)

1. Clone this repo.
2. Tell your WorkBuddy agent: **"Set up the video MCP in this repo."**
   Your agent creates `api-key.txt` and installs everything.
3. Paste your group's **single API key** into `api-key.txt` on line 1 — plain
   text, UTF-8, no quotes, no `Bearer ` prefix. Save. This is the only file you
   edit.
4. In WorkBuddy: **Connectors → Custom Connector → Trust `hailuo-video`**, then
   **start a new chat session**.
5. Ask: *"Generate a 4 second video of a cat sitting on a desk."*

Before generating, your agent runs `check_key.py` — a free check that creates no
video and spends no credit. The finished MP4 appears in `videos/`; your agent
will give you its full local path.

- **Never commit `api-key.txt`.** It is gitignored and a hook blocks it.
- **Never put a real key in `api-key.example.txt`** — that file is tracked.
- One group = one key = one computer/OS account = one clone.

---

## 9. For the teacher — distribution and rotation

> Student agents should **not** act on this section.

1. Push this repo to a private classroom org. Confirm your WorkBuddy build
   honours external edits to `mcp.json`; if not, students paste the block from
   `mcp.local.json` into the MCP settings UI manually.
2. Give each of the 5 groups **its own single** TokenHub API key via a separate
   channel (LMS, email, in person) — never in the repo, never in an issue.
3. Students clone, the agent runs the one setup command, and the student pastes
   only their own key.
4. To revoke a group: rotate/delete that **one** key in the Tencent Cloud
   console. The student pastes the replacement into `api-key.txt` — no restart,
   no second setup.
5. Keys live on student machines, so treat them as disposable and scope each to
   one group. If you need hard central quota control, use the hosted MCP design
   instead of this local one.
6. First classroom run needs PyPI access. For a locked-down lab, pre-build a
   wheelhouse **per OS** and set `HAILUO_WHEELHOUSE` before setup.
7. Pilot one Windows machine **and one Mac** through the full flow (Python →
   setup → paste key → Trust → new session → 4-second generation) before
   distributing to all 5 groups.

---

## 10. Architecture and security model

```text
WorkBuddy  --stdio-->  server.py  --Bearer-->  TokenHub submit/query
                          |
                          +-- reads api-key.txt on EVERY call (one key only)
                          +-- pending.json  : paid job recovery
                          +-- usage.jsonl   : per-machine daily cap + idempotency
                          +-- videos/       : local MP4, no URL served
```

* No environment-variable key or endpoint override exists: an env var would be a
  second place a key could hide, and a `TOKENHUB_BASE_URL` override could
  silently exfiltrate the key.
* Every error string is passed through `tokenhub.redact()`; raw upstream
  response bodies are never returned.
* Downloads follow redirects manually so **every hop** is SSRF-checked, and are
  written to `.part` then atomically `os.replace()`d after validation.
* `task_id` is validated against `^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$` so a
  hallucinated id cannot turn a GET into a different endpoint.
* All five tools catch every exception and return a JSON dict, so a traceback
  never reaches the client and a paid `task_id` is never lost.

---

## 11. Acceptance checklist (agent: confirm before saying "done")

- [ ] `git status --short` shows no secret or runtime file staged.
- [ ] `setup_mcp.py --check` reports install complete and the connector entry in
      the expected config path(s).
- [ ] `api-key.txt` holds exactly one key and is **gitignored**; the key was
      never echoed anywhere.
- [ ] `check_key.py` printed `KEY VALID`.
- [ ] Student clicked **Trust** and started a **new chat session**.
- [ ] `video_capabilities()` returned `key_configured: true`,
      `credentials_required: 1`, `model: minimax-video-h3`.
- [ ] First generation used `duration=4`, `resolution=768P`, `ratio=16:9`.
- [ ] Any `resubmit_allowed: false` result was resumed with `check_video`, never
      resubmitted.
- [ ] The student received a local `video_path`, not a URL.

---

## 12. Files in this repo

| File | Role |
|---|---|
| `README.md` | **This file — canonical agent runbook** |
| `AGENTS.md` | Extended reference, rationale, teacher notes |
| `setup_mcp.py` | Stdlib-only one-command installer (`--install` / `--check` / `--verify-key` / `--uninstall`) |
| `server.py` | MCP STDIO server, 5 tools, paid-job recovery |
| `tokenhub.py` | TokenHub client: validation, redaction, SSRF-safe atomic download |
| `keyfile.py` | Shared single-key reader / normaliser / prompt validator |
| `check_key.py` | No-cost credential probe |
| `selftest.py`, `selftest_dryrun_server.py` | Offline regression suite (no cloud calls, no credit) |
| `api-key.example.txt` | Tracked placeholder — **never** put a real key here |
| `api-key.txt` | Student's local secret — gitignored, created on setup |
| `mcp.example.json` | Shape-only config example — do not paste |
| `mcp.local.json` | Generated paste-ready config — gitignored |
| `requirements.txt` | `mcp==2.3.0`, `httpx==0.28.1` |
| `.gitignore`, `.gitattributes` | Secret hygiene, LF line endings |

---

## Requirements

- Python 3.10+ (3.11+ recommended)
- WorkBuddy with custom MCP connector support
- `mcp==2.3.0`, `httpx==0.28.1` (installed into `.venv` automatically)
- One Tencent Cloud TokenHub API key per group
- Network access to PyPI on the first run (or a wheelhouse), and to TokenHub
  for generation
