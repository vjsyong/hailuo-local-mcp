# Hailuo local video MCP — setup instructions for an AI agent

This repository installs a **local STDIO MCP server** on a student's computer.
WorkBuddy launches `server.py` as a subprocess; there is no hosted server, no
port, no public URL, and no group-token system. The finished MP4 is written to
this repo's `videos/` folder and returned as a local absolute `video_path`.

Model: `minimax-video-h3` on Tencent Cloud TokenHub (international).
Auth: ONE `Authorization: Bearer <API key>` header. No SecretId/SecretKey, no
TC3 signing, no `user` field.

---

## For the student — the only manual step

1. Clone this repository.
2. Open `api-key.txt` in the repo root (if it does not exist, run
   `python setup_mcp.py` once and it will be created from the example).
3. Paste your group's single API key on line 1 — plain text, no quotes, no
   `Bearer ` prefix. Save.
4. Tell your WorkBuddy agent: **"Set up the video MCP in this repo."**

That's it. The agent does everything below.

---

## For the agent — do exactly this

Run from the repository root, with the machine's default Python 3.11+:

```bash
python setup_mcp.py --install --verify-key
```

This will:

1. Verify `api-key.txt` contains a real key (it never displays the value).
2. Create `.venv/` and install `requirements.txt` into it.
3. Verify `mcp`, `httpx`, `tokenhub`, and `server` import cleanly.
4. Write `mcp.local.json` with a ready-to-paste STDIO config using **absolute
   paths** to this machine's `.venv` python and `server.py`.
5. Merge that block into `~/.workbuddy-ai/mcp.json`, preserving all other
   servers and backing up the old file as `mcp.json.bak.<timestamp>`.
6. Make ONE no-cost TokenHub auth probe (a task lookup — no video generated).

Then confirm `SETUP OK` in the output and tell the student:

> Open **Connectors** in the WorkBuddy left sidebar → **Custom Connector** in
> the top-right → click **Trust** on `hailuo-video`. The connector does not
> activate automatically.

Optional verification (offline, zero credit):

```bash
# Windows
.venv/Scripts/python.exe selftest.py
# macOS / Linux
.venv/bin/python selftest.py
```

### Agent rules — non-negotiable

- **Never** print, echo, log, quote, summarise, or write the contents of
  `api-key.txt` into any file, commit, chat message, or config.
- **Never** put the key into `mcp.json`, `mcp.local.json`, an `env` block, or
  any environment variable that would be persisted. The server reads it from
  `api-key.txt` relative to its own path.
- **Never** `git add` / commit `api-key.txt`, `mcp.local.json`, `videos/`,
  `usage.jsonl`, `.venv/`, or any `*.bak` file. They are gitignored; check
  `git status --short` before any commit.
- Do not change the defaults in `tokenhub.py` — the model slug is
  `minimax-video-h3` and the cheapest settings are 4s / 768P / 16:9.
- If `setup_mcp.py` reports the key is missing, **stop** and ask the student to
  paste it. Do not guess, generate, or fetch a key.
- If the student pastes a key into chat instead, write it directly to
  `api-key.txt` without repeating it back, then continue.

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
`server.py` must never write to stdout: stdout carries the JSON-RPC stream.

---

## Using it

Ask your agent: *"Generate a 4 second video of a cat sitting on a desk."*

Tools exposed:

| Tool | Purpose |
|---|---|
| `video_capabilities` | Model, endpoint, valid ranges, and whether the key is configured |
| `generate_video` | One call: submit → poll → download → return local `video_path` |
| `submit_video` | Submit only, returns `task_id` (use if the client times out) |
| `check_video` | Poll a `task_id`, returns `video_path` when done |

Generation takes roughly 1–3 minutes. If `generate_video` returns
`pending=true`, call `check_video` with the returned `task_id`.

`videos/` is cleaned automatically after 72 hours. A per-machine daily cap
(default 60) is enforced via `usage.jsonl`; override with `MAX_VIDEOS_PER_DAY`.

---

## For the teacher — distributing this

1. `git init`, commit, and push this repo to a private classroom org.
2. Give each of the 5 groups **its own** TokenHub API key through a separate
   channel (LMS, email, in person) — never in the repo, never in an issue.
3. Students clone and paste only their own key.
4. To revoke a group: rotate/delete that key in the Tencent Cloud console. The
   student then pastes the replacement into `api-key.txt`; no restart needed —
   the server reads the file on every tool call.
5. Because keys live on student machines, treat them as disposable and scope
   each to one group. If you need hard central quota control, use the hosted
   MCP design instead.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No TokenHub API key configured" | Paste the key into `api-key.txt`, one line, no quotes |
| `check_key.py` says `INVALID KEY` (401/403) | Wrong/expired key; re-paste |
| Connector shows as unavailable | Trust it: Connectors → Custom Connector → Trust |
| `generate_video` times out client-side | Use `submit_video`, then `check_video` with the `task_id` |
| Config lost after moving the folder | Re-run `python setup_mcp.py --install` to regenerate absolute paths |
| `ModuleNotFoundError: mcp` | Run with `.venv` python, or re-run `setup_mcp.py` |
| Nothing happens / JSON parse errors | Something printed to stdout — stdio servers must keep stdout clean |
