# Hailuo local video MCP — one key per group

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
deliberately **no** environment-variable key override: an env var would be a
second place a key could hide and a second thing to get wrong.

---

## Student quick start

1. Clone this repository.
2. Tell your WorkBuddy agent: **"Set up the video MCP in this repo."**
   The agent creates `api-key.txt` for you and installs everything.
3. Open `api-key.txt` and paste **your group's single API key** on line 1 —
   plain text, no quotes, no `Bearer ` prefix. Save.
4. In WorkBuddy: **Connectors** (left sidebar) → **Custom Connector**
   (top-right) → click **Trust** on `hailuo-video`.
5. Ask: *"Generate a 4 second video of a cat sitting on a desk."*

Pasting the key is the only manual step. You can do it before or after step 2 —
both orders work, because the server reads the file on every call.

---

## For the agent — do exactly this

Run from the repository root with the machine's default Python 3.11+:

```bash
python setup_mcp.py --install --verify-key
```

Setup is **single-pass**: it completes even if `api-key.txt` does not exist yet
or still holds the placeholder. It will:

1. Create `api-key.txt` from `api-key.example.txt` if missing.
2. Create `.venv/` and install `requirements.txt` into it.
3. Verify `mcp`, `httpx`, `tokenhub`, and `server` import cleanly.
4. Write `mcp.local.json` with a ready-to-paste STDIO config using **absolute
   paths** to this machine's `.venv` python and `server.py`.
5. Merge that block into `~/.workbuddy-ai/mcp.json`, preserving all other
   servers and backing up the old file as `mcp.json.bak.<timestamp>`.
6. Make ONE no-cost TokenHub auth probe — **skipped cleanly** if the key has not
   been pasted yet (no network call, no credit spent).

Then tell the student to paste their one key (if they have not already) and to
click **Trust** on `hailuo-video`. The connector does not activate automatically.

If setup reported the key was missing, do **not** attempt a probe or a
generation. Do not re-run setup after the paste — it is unnecessary. To confirm
the key later, run the no-cost checker:

```bash
.venv/Scripts/python.exe check_key.py    # Windows
.venv/bin/python check_key.py            # macOS / Linux
```

Optional offline verification (zero credit):

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
- **Never** `git add` / commit `api-key.txt`, `mcp.local.json`, `videos/`,
  `usage.jsonl`, `.venv/`, or any `*.bak` file. Check `git status --short` first.
- Do not change the defaults in `tokenhub.py` — model `minimax-video-h3`,
  cheapest settings 4s / 768P / 16:9.
- If the student pastes a key into chat instead, write it directly to
  `api-key.txt` without repeating it back, then continue. Do not guess,
  generate, or fetch a key.
- `server.py` must never write to stdout: stdout carries the JSON-RPC stream.

### Generated MCP config shape

```json
{
  "mcpServers": {
    "hailuo-video": {
      "command": "C:\\...\\hailuo-local-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\...\\hailuo-local-mcp\\server.py"]
    }
  }
}
```

No `env`, no `type`, no `url`, no headers — STDIO servers use `command`/`args`.

---

## Using it

| Tool | Purpose |
|---|---|
| `video_capabilities` | Model, ranges, and `credentials_required: 1` / `key_source` |
| `generate_video` | One call: submit → poll → download → return local `video_path` |
| `submit_video` | Submit only, returns `task_id` (use if the client times out) |
| `check_video` | Poll a `task_id`, returns `video_path` when done |

Generation takes roughly 1–3 minutes. If `generate_video` returns
`pending=true`, call `check_video` with the returned `task_id`.

`videos/` is cleaned after 72 hours. A per-machine daily cap (default 60) is
enforced via `usage.jsonl`; override with `MAX_VIDEOS_PER_DAY`.

---

## For the teacher — distributing this

1. `git init`, commit, and push this repo to a private classroom org.
2. Give each of the 5 groups **its own single** TokenHub API key through a
   separate channel (LMS, email, in person) — never in the repo, never in an
   issue. One group → one key.
3. Students clone; each pastes only their own key.
4. To revoke a group: rotate/delete that one key in the Tencent Cloud console.
   The student pastes the replacement into `api-key.txt`; no restart needed.
5. Because keys live on student machines, treat them as disposable and scope
   each to one group. If you need hard central quota control, use the hosted
   MCP design instead.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No TokenHub API key configured" | Paste the single key into `api-key.txt`, line 1, no quotes |
| `check_key.py` says `INVALID KEY` (401/403) | Wrong/expired key; re-paste — do not add a second credential |
| Connector shows as unavailable | Trust it: Connectors → Custom Connector → Trust |
| `generate_video` times out client-side | Use `submit_video`, then `check_video` with the `task_id` |
| Config lost after moving the folder | Re-run `python setup_mcp.py --install` to regenerate absolute paths |
| `ModuleNotFoundError: mcp` | Run with `.venv` python, or re-run `setup_mcp.py` |
| Nothing happens / JSON parse errors | Something printed to stdout — stdio servers must keep stdout clean |
