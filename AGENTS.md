# Hailuo local video MCP — one key per group

> **Canonical agent runbook: [README.md](README.md) §1 "Agent runbook — do
> exactly this".** If you are a student's WorkBuddy agent and were asked to set
> up this repo, execute that section in order. This file is the extended
> reference (design rationale, exact failure tables, teacher notes); its rules
> are identical, and **README.md wins** if they ever diverge. Do not improvise a
> different setup procedure.
>
> **README.md §0 "Students — start here" is student-facing** and holds the exact
> copy-paste kickoff prompt students send their agent. Expect that prompt as the
> trigger, then execute §1. Keep §0 free of agent internals.

This repository installs a **local STDIO MCP server** on each student's
computer. WorkBuddy launches `server.py` as a subprocess; there is no hosted
server, no port, no public URL, and no group-token system. The finished MP4 is
written to `videos/` and returned as a local absolute `video_path`.

Model: `minimax-video-h3` on Tencent Cloud TokenHub (international).
Auth: ONE `Authorization: Bearer <API key>` header. No SecretId/SecretKey, no
TC3 signing, no `user` field.

---

## The one rule: each group needs exactly ONE key

| | |
|---|---|
| Credentials per group | **1** — a single TokenHub API key |
| Where it goes | **line 1 of `api-key.txt`** in the repo root, nothing else |
| What the student types | nothing — just paste the key |
| Other credentials | none: no group token, no SecretId/SecretKey, no `user`, no env var, no config entry |

`api-key.txt` is the single source of truth. It is gitignored, created on first
setup from `api-key.example.txt`, and read by `server.py` on **every tool call** —
so pasting or rotating a key needs no restart and no second setup run. There is
deliberately **no** environment-variable key or endpoint override: an env var
would be a second place a key could hide and a second thing to get wrong.
`setup_mcp.py` prints a warning if any legacy `TOKENHUB_*` variable is set —
those variables are ignored.

`api-key.example.txt` **is** tracked and is only a placeholder. Never put a real
key in it. `setup_mcp.py --install` installs a local pre-commit hook that blocks
committing either file.

---

## Student quick start

1. Clone this repository.
2. Copy the **kickoff prompt** from
   [README.md §0](README.md#0-students--start-here) and paste it as your first
   message to your WorkBuddy agent. It creates `api-key.txt` for you and installs
   everything.
3. Open `api-key.txt` and paste **your group's single API key** on line 1 —
   plain text, UTF-8, no quotes, no `Bearer ` prefix. Save.
4. Run the **no-cost** key check (`check_key.py`) — or ask your agent to run it.
   It makes one task lookup, creates no video, and spends no credit.
5. In WorkBuddy: **Connectors** (left sidebar) → **Custom Connector**
   (top-right) → click **Trust** on `hailuo-video`.
6. **START A NEW CHAT SESSION.** Tool lists load when a session starts; the
   connector does not activate automatically.
7. Ask: *"Generate a 4 second video of a cat sitting on a desk."*

`api-key.txt` is the only file a student edits. Pasting can happen before or
after step 2 — both orders work, because the server reads the file on every
call. The two remaining manual actions are UI-only: Trust the connector and
start a new chat session (see README.md §1 Steps 6–7).

**One machine per group:** each group needs its own OS account **and** its own
clone of this repo. The server name (`hailuo-video`), `videos/`, `usage.jsonl`
and `pending.json` are per-clone, so two groups sharing one account/clone will
overwrite each other's connector entry and key file.

---

## For the agent — condensed reference

The executable, ordered runbook (Step 0 → Step 9, with exact output strings and
stop/go gates) is **[README.md §1](README.md#1-agent-runbook--do-exactly-this)**.
The commands and rules below are the same contract in compact form.

Requires **Python 3.10+** (3.11+ recommended). Run from the repository root:

```bash
# Windows
python setup_mcp.py --install --verify-key        # or: py -3.11 setup_mcp.py --install --verify-key

# macOS / Linux  (stock macOS has NO `python`, only `python3`)
python3 setup_mcp.py --install --verify-key
```

Never use bare `python` on macOS/Linux. Setup refuses to run on Python < 3.10
with a clear message rather than a cryptic pip-resolver error.

**macOS prerequisite (the one real blocker):** the `python3` shipped by Xcode
Command Line Tools is Python **3.9**, so setup will refuse it. Install Python
3.10+ first — `brew install python@3.12` or the installer from
<https://www.python.org/downloads/macos/> — then verify `python3 --version`
before running setup. If a wheel ever needs compiling, `xcode-select --install`.
Apple Silicon is supported. Tell students to edit `api-key.txt` in a plain-text
editor (VS Code, BBEdit, `nano`), **not** TextEdit's default Rich Text mode with
smart quotes; `keyfile.py` rejects UTF-16 and non-ASCII keys with an explicit
message, so this fails safely.

Setup is **single-pass**: it completes even if `api-key.txt` does not exist yet
or still holds the placeholder. It will:

1. Create `api-key.txt` from `api-key.example.txt` if missing.
2. Create `.venv/` and install `requirements.txt` — only if imports are not
   already satisfied (re-runs are offline-safe). First run needs PyPI access.
   Offline classroom: put wheels in a folder and set `HAILUO_WHEELHOUSE` to it;
   setup then installs with `--no-index --find-links`.
3. Verify `mcp`, `httpx`, `tokenhub`, `server`, `keyfile` import cleanly.
4. Write `mcp.local.json` with a ready-to-paste STDIO config using **absolute
   paths** to this machine's `.venv` python and `server.py`.
5. Merge that block into **both** `~/.workbuddy-ai/mcp.json` and
   `~/.workbuddy/mcp.json` (the latter only when that folder exists), preserving
   all other servers, tolerating malformed configs, backing up with a
   collision-proof name, and reading the file back to verify the entry landed.
6. Install a local pre-commit guard against committing the key.
7. Make ONE no-cost TokenHub auth probe — **skipped cleanly** if the key has not
   been pasted yet. A rejected/inconclusive probe **never fails setup**.

Other commands:

```bash
python3 setup_mcp.py --check          # read-only status of venv, key, both config entries
python3 setup_mcp.py --uninstall      # remove ONLY the hailuo-video entry (with backup)
python3 setup_mcp.py                  # dry run: builds venv + mcp.local.json, no global install
```

Then tell the student to paste their one key (if they have not already), run the
no-cost checker, click **Trust**, and **start a new chat session**. Do not
re-run setup after the paste — it is unnecessary. Setup prints its real status
(`INSTALL WRITTEN -- activation is NOT complete`, plus an explicit key status);
it never claims the connector is live.

No-cost checker (run before any generation):

```bash
.venv/Scripts/python.exe check_key.py    # Windows
.venv/bin/python check_key.py            # macOS / Linux
```

Only `HTTP 400` means **KEY VALID**. `401/403` = invalid key, `429` = throttled,
`5xx` / anything else = **INCONCLUSIVE** — never assume the key works.

Optional offline verification (zero credit, no TokenHub calls):

```bash
.venv/Scripts/python.exe selftest.py     # Windows
.venv/bin/python selftest.py             # macOS / Linux
```

### Agent rules — non-negotiable

- **One key.** Never ask a student for a second key, token, SecretId, SecretKey,
  `user` value, or header. If something fails, it is a bad single key or a
  network problem — not a missing second credential.
- **Never** print, echo, log, quote, summarise, or write the contents of
  `api-key.txt` into any file, commit, chat message, or config.
- **Never** put the key into `mcp.json`, `mcp.local.json`, an `env` block, or any
  persisted environment variable. The server reads it from `api-key.txt`.
- **Never** `git add` / commit `api-key.txt`, `api-key.example.txt` edits,
  `mcp.local.json`, `videos/`, `usage.jsonl`, `pending.json`, `.venv/`, or any
  `*.bak` file. Check `git status --short` first.
- **Never resubmit a paid job.** If any result has `resubmit_allowed: false`
  (with `pending: true`, `recoverable: true`, or `status: poll_interrupted`),
  call `check_video` with its `task_id`. Never call `generate_video` again for
  that prompt. Use `recent_tasks` if the id was lost.
- Do not change the defaults in `tokenhub.py` — model `minimax-video-h3`,
  cheapest settings 4s / 768P / 16:9.
- If the student pastes a key into chat instead, write it directly to
  `api-key.txt` without repeating it back, then continue. Do not guess,
  generate, or fetch a key.
- `server.py` must never write to stdout: stdout carries the JSON-RPC stream.
  The MCP SDK v2 claims fd 1 and diverts stray output to stderr; do **not** add
  `sys.stdout = sys.stderr` — that would make the SDK serve MCP over stderr.

### Generated MCP config shape

Windows:

```json
{
  "mcpServers": {
    "hailuo-video": {
      "command": "C:/.../hailuo-local-mcp/.venv/Scripts/python.exe",
      "args": ["C:/.../hailuo-local-mcp/server.py"]
    }
  }
}
```

macOS / Linux (setup picks this branch automatically via `os.name`):

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

No `env`, no `url`, no headers — STDIO servers use `command`/`args`. Paths use
forward slashes so they are safe to copy out of JSON on Windows and are already
native on macOS/Linux. The MCP SDK spawns `[command, *args]` without a shell, so
paths containing spaces are fine.

---

## Using it

| Tool | Purpose |
|---|---|
| `video_capabilities` | Model, ranges, `credentials_required: 1`, `key_source`, pending-job count |
| `generate_video` | One call: submit → poll → download → return local `video_path` |
| `submit_video` | Submit only, returns `task_id` (safest path on slow/unreliable clients) |
| `check_video` | Poll a `task_id`, returns `video_path` when done |
| `recent_tasks` | Recover a `task_id` lost to a timeout or network error |

Generation takes roughly 1–3 minutes; `generate_video` waits at most 120s by
default so a client-side timeout cannot swallow the result. If it returns
`pending: true`, call `check_video` with the returned `task_id`. Completed jobs
are idempotent: repeated `check_video` returns `reused: true` and the same MP4,
never a second download or a duplicate log record.

`videos/` is cleaned after 72 hours (only files this server created). A
per-machine daily cap of 60 submits is enforced via `usage.jsonl`; the log is
pruned automatically. Every tool returns a JSON dict — no exception ever
reaches the client as a traceback, and all error text is redacted of keys and
signed URLs.

---

## For the teacher — distributing this

1. Commit and push this repo to a private classroom org. Confirm with the
   WorkBuddy build you use that external edits to `mcp.json` are honoured
   (documented as restored in WorkBuddy 5.6.0+); if not, students paste the
   block from `mcp.local.json` into the MCP settings UI manually.
2. Give each of the 5 groups **its own single** TokenHub API key through a
   separate channel (LMS, email, in person) — never in the repo, never in an
   issue. One group → one key → one machine/OS account → one clone.
3. Students clone, run the one setup command, paste only their own key.
4. To revoke a group: rotate/delete that one key in the Tencent Cloud console.
   The student pastes the replacement into `api-key.txt`; no restart needed.
5. Keys live on student machines, so treat them as disposable and scope each to
   one group. If you need hard central quota control, use the hosted MCP design
   instead.
6. First classroom run needs PyPI access for `mcp==2.3.0` / `httpx==0.28.1`.
   For a locked-down lab, pre-build a wheelhouse per OS and set
   `HAILUO_WHEELHOUSE` before setup.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No TokenHub API key configured" | Paste the single key into `api-key.txt`, line 1, no quotes |
| Key saved as "Unicode" / UTF-16 | Re-save as UTF-8 (no BOM); `keyfile.py` reports this explicitly |
| `check_key.py` says `INVALID KEY` (401/403) | Wrong/expired key; re-paste — do not add a second credential |
| `check_key.py` says `INCONCLUSIVE` | Network/proxy/TokenHub outage; setup is fine, retry before generating |
| `command not found: python` | macOS/Linux: use `python3 setup_mcp.py --install --verify-key` |
| `SETUP INCOMPLETE: Python 3.10+ is required` (macOS) | Xcode CLT ships 3.9: `brew install python@3.12` or python.org installer; verify `python3 --version`, then re-run |
| "non-ASCII characters" / "looks like UTF-16" | TextEdit saved RTF/smart quotes or UTF-16; re-paste in VS Code / `nano`, save plain UTF-8 on line 1 |
| `pip` / TLS / venv error on first run | Needs PyPI + `python3-venv`; macOS: `xcode-select --install`; or use `HAILUO_WHEELHOUSE` offline wheels |
| Connector shows as unavailable | Trust it: Connectors → Custom Connector → Trust, then START A NEW CHAT SESSION |
| `generate_video` times out client-side | It returns a `task_id`; call `check_video`. Do NOT resubmit. Use `submit_video` next time |
| Lost the `task_id` | Call `recent_tasks`, then `check_video` with that id |
| Config lost after moving the folder | Re-run `python3 setup_mcp.py --install` to regenerate absolute paths |
| Two groups on one computer | Not supported: use separate OS accounts and separate clones |
| `ModuleNotFoundError: mcp` | Run with `.venv` python, or re-run `setup_mcp.py` |
| Nothing happens / JSON parse errors | Something printed to stdout — stdio servers must keep stdout clean |
