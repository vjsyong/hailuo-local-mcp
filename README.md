# Hailuo Video MCP

## 0. Students, Start here!

This repo lets you generate short videos from a text description inside
WorkBuddy. **You do not need to run any terminal commands** — your WorkBuddy
agent does all the setup for you.

**Repo:** <https://github.com/vjsyong/hailuo-local-mcp.git>

**Before you begin:** have the **one API key** your teacher gave your group
ready. Your key comes from your teacher (LMS, email, or in person) — it is never
inside this repo. You do **not** need to open or clone the repo yourself: the
prompt below carries the link, so your agent can fetch it even from a brand-new
chat where it knows nothing about this project.

**You do not need Git, and you do not need to install anything.** Your agent
downloads the repo itself and uses the Python that WorkBuddy already ships. On a
Mac with no usable Python anywhere, your agent may ask you to install Python
3.10+ once — that is the only possible extra step, and only on that machine.

### Copy this into your agent

Copy the **whole block** below and paste it as your **first message** to your
WorkBuddy agent. It is self-contained: it names the project, embeds the repo and
runbook links, and drives the install from start to finish.

```text
Set up the Hailuo video MCP for my student group, end to end. This is a fresh
chat and you know nothing about the project yet, so use the links below.

REPO      https://github.com/vjsyong/hailuo-local-mcp.git
RUNBOOK   https://raw.githubusercontent.com/vjsyong/hailuo-local-mcp/main/README.md
BOOTSTRAP https://raw.githubusercontent.com/vjsyong/hailuo-local-mcp/main/bootstrap.py
ZIP       https://codeload.github.com/vjsyong/hailuo-local-mcp/zip/refs/heads/main

Assume the LOWEST COMMON DENOMINATOR: this machine may have NO git and NO Python
on PATH. Do not ask me to install git. Do not run any system-level installer
without my explicit OK. Read the RUNBOOK (README.md §1) and follow it in order;
the condensed version is below.

1. GET THE CODE. If a clone already exists here, cd into it. Otherwise download
   the single BOOTSTRAP file (curl -fsSL -o bootstrap.py <BOOTSTRAP URL>, or
   Invoke-WebRequest -Uri <BOOTSTRAP URL> -OutFile bootstrap.py on Windows
   PowerShell). Do NOT use git for this and do NOT try to untar the ZIP with
   Git Bash's tar -- bootstrap.py handles the ZIP with Python's stdlib.
2. FIND ANY PYTHON that can RUN bootstrap.py (3.6+ is enough): python3, python,
   py -3, or WorkBuddy's OWN bundled Python under
   ~/.workbuddy-ai/binaries/python/versions/ (README §1 Step 0 has the exact
   commands for Windows, macOS and Linux). Call it <PY>.
3. RUN EXACTLY ONE SETUP COMMAND from the directory holding bootstrap.py:
       <PY> bootstrap.py --install --verify-key
   It downloads/extracts the ZIP if there is no clone, finds a Python 3.10+
   (including WorkBuddy's bundled one), and runs setup_mcp.py. You may first run
   `<PY> bootstrap.py --find-python` as a free read-only check. If it reports
   that no Python 3.10+ exists anywhere, stop and show me the exact one-time
   install it printed -- that is the only thing I might have to do myself.
4. Then follow README §1 Steps 3-9: read setup's output, have me paste my ONE
   key into api-key.txt on line 1, run the no-cost check_key.py, and hand me the
   two WorkBuddy UI actions (Trust hailuo-video, then START A NEW CHAT SESSION).

Hard rules — do not break any of these:
- I have exactly ONE API key. Never ask for a second key, token, SecretId,
  SecretKey, or any other credential. One key is all this tool needs.
- Never print, log, commit, or write my key into a config file or chat message.
  It belongs on line 1 of api-key.txt and nowhere else.
- Never generate a video until check_key.py reports KEY VALID. Generation spends
  real credit from my group's allowance.
- Never resubmit a job that already returned a task_id.
- Never modify the repo's code to work around a failure. If something breaks,
  stop and show me the exact output.

When setup is written, tell me the exact steps only I can do, wait for me, and
then tell me how to ask for my first 4-second test video.
```

### Then you do three things

1. **Paste your one API key** into `api-key.txt` on line 1 — plain text, UTF-8,
   no quotes, no `Bearer ` prefix, nothing else in the file. This is the only
   file you ever edit.
2. In WorkBuddy: **Connectors → Custom Connector → Trust `hailuo-video`**.
3. **Start a new chat session** — the connector only loads when a session starts.

Then ask: *"Generate a 4 second video of a cat sitting on a desk."* Your agent
will give you the full local path to the MP4 in `videos/`. Open it directly.

**That's it.** Everything below this line is written for your agent and your
teacher — you do not need to read it.

Three things worth knowing:

- **On a Mac**, your agent uses WorkBuddy's own Python when it can. Only if that
  is missing may it ask you to install Python 3.10+ once (the Python that ships
  with macOS is 3.9 — too old). Follow its instructions; it is a one-time
  install. **Git is never needed.**
- If your agent asks for a **second** key, a token, or a SecretId/SecretKey,
  something is wrong. Point it back at `README.md` and do not provide anything
  else — each group gets exactly one key.
- Never commit `api-key.txt`, and never put a real key into
  `api-key.example.txt`. Both are guarded automatically.

---

## 1. Agent runbook — do exactly this

**This README is the canonical runbook for the student's WorkBuddy agent.** The
student pastes the kickoff prompt from §0 above, which embeds the repo, raw
runbook, bootstrap and ZIP URLs — so you may have no prior context and must fetch
the code first (Step 0). **Assume the student has neither Git nor Python on
PATH:** Step 0 works without both. On receiving the prompt (or any equivalent
request), execute the steps below in order, without improvising.
[AGENTS.md](AGENTS.md) is the extended reference and design rationale; if the two
ever disagree, this README wins.

### Agent quick card

```text
TRIGGER         Student pastes the §0 kickoff prompt. It embeds REPO + RUNBOOK +
                BOOTSTRAP + ZIP URLs, so you may arrive with ZERO prior context.
                Fetch the code first (Step 0) -- git is OPTIONAL.

GOAL            Install a local STDIO MCP server that generates MiniMax H3 videos
                from inside WorkBuddy, using ONE Tencent Cloud TokenHub API key.

AGENT COMMAND   <PY> bootstrap.py --install --verify-key
                <PY> = ANY Python 3.6+ (python3, python, py -3, or WorkBuddy's
                OWN bundled Python by absolute path). Run from the directory
                holding bootstrap.py. ONE command, works with no git on PATH.

STUDENT ACTIONS 1. Paste ONE API key into api-key.txt (line 1, plain text)
                2. Connectors -> Custom Connector -> Trust "hailuo-video"
                3. START A NEW CHAT SESSION
                These three are the ONLY manual steps on a normal machine.
                ONLY if no Python 3.10+ exists anywhere: a one-time Python
                install (bootstrap.py prints the exact command). Never git.

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

### Step 0 — Get the code with NO git, and find ANY Python

**Cold start:** you may have arrived from the §0 kickoff prompt with zero prior
context. **Assume the machine has no `git` and no `python` on PATH.** WorkBuddy
agents can run shell commands; this install of WorkBuddy also ships its own
Python 3.13 and PortableGit, but neither is guaranteed to be on PATH — and the
docs make **no promise** that WorkBuddy will install developer tools for you.
So: never *require* git, and never run a system-level installer without asking.

#### A. Get `bootstrap.py` (one file, stdlib-only, Python 3.6+)

If a clone/extraction already exists in the workspace, `cd` into it — it already
contains `bootstrap.py` (or you can fetch the standalone copy below into its
parent). Otherwise download just that one file into the workspace:

```bash
# macOS / Linux / Git Bash on Windows
curl -fsSL -o bootstrap.py \
  https://raw.githubusercontent.com/vjsyong/hailuo-local-mcp/main/bootstrap.py
```

```powershell
# Windows PowerShell (if curl is unavailable)
Invoke-WebRequest -Uri https://raw.githubusercontent.com/vjsyong/hailuo-local-mcp/main/bootstrap.py -OutFile bootstrap.py
```

`bootstrap.py` downloads and extracts the repo ZIP itself using `urllib` +
`zipfile`. **Do not clone, do not call `tar -xf` on the ZIP** (Git Bash's GNU tar
cannot read ZIP), and do not run `unzip`. If the download is blocked, fetch the
ZIP URL from §0 by hand and set `HAILUO_ZIP` to that local file.

#### B. Find ANY Python able to *run* bootstrap.py (3.6+ is enough)

```bash
python3 --version || python --version || py -3 --version
```

If all of those fail, use WorkBuddy's **own** bundled Python by absolute path:

```bash
# Windows (Git Bash)
ls "$HOME/.workbuddy-ai/binaries/python/versions/"*/python.exe
# Windows (PowerShell)
Get-ChildItem "$env:USERPROFILE\.workbuddy-ai\binaries\python\versions\*\python.exe"
# Windows app bundle (fallback)
"$LOCALAPPDATA/Programs/WorkBuddyAI/resources/vendor/python/python.exe" --version
# macOS / Linux (home bundle, then app bundle)
ls ~/.workbuddy-ai/binaries/python/versions/*/bin/python3 2>/dev/null
"/Applications/WorkBuddy AI.app/Contents/Resources/vendor/python/bin/python3" --version
```

Assign the path you found to `<PY>`. On macOS the stock Xcode `python3` is 3.9 —
**that is fine for running `bootstrap.py`**, which will then find (or report the
need for) a 3.10+ interpreter for the install itself. Do not install git.

#### C. Free read-only probe

```bash
<PY> bootstrap.py --find-python
```

`PYTHON_OK <path>` + `VERSION 3.10+` → go to Step 2. If it prints
`BOOTSTRAP INCOMPLETE: no Python 3.10+`, **stop** and give the student the exact
one-time install command it printed. This is the only case that needs a human
install, and it is the only exception to "the student pastes just one key".
No credit is spent and no config is changed by this probe.

#### D. Orient

`REPO_ROOT` is the directory containing `bootstrap.py` (Step 2 will create
`./hailuo-local-mcp/` from the ZIP if needed). Run `git status --short` **only if
git happens to exist**; a ZIP extraction has no `.git`, which is expected and
harmless (setup simply skips the pre-commit guard). A `--check` exit code of `1`
on a fresh machine is also expected — it means the install has not run yet. Do
not "repair" files by hand.

### Step 1 — Prerequisites gate (STOP if unmet)

| Need | Who provides it | If missing |
|---|---|---|
| The repo | `bootstrap.py` (ZIP download, **no git**) or an existing clone | Use `HAILUO_ZIP` with a local copy of the ZIP |
| Python to *run* bootstrap | any 3.6+ — including macOS 3.9 or WorkBuddy's bundled Python | Follow Step 0B; do not install git |
| Python to *run* setup | 3.10+ found by `--find-python` (PATH, `py` launcher, or WorkBuddy bundled) | The **one** permitted human install; bootstrap prints the exact command |
| PyPI for `mcp==2.3.0`, `httpx==0.28.1` | first-run network | Set `HAILUO_WHEELHOUSE` to a folder of wheels; setup uses `--no-index --find-links` |
| git | **NOT REQUIRED** | Do not install it, do not ask the student to |

* Setup exits `1` with `SETUP INCOMPLETE: Python 3.10+ is required` on an older
  interpreter; `bootstrap.py` normally prevents you from ever getting there.
* **macOS:** there is no `python`, and the Xcode Command Line Tools `python3` is
  **3.9** — too old for setup but fine for bootstrap. If `--find-python` finds no
  3.10+, have the student install Python once:
  `brew install python@3.12` or <https://www.python.org/downloads/macos/>, then
  re-run Step 0C. `xcode-select --install` is only needed if pip must compile a
  wheel.
* **WorkBuddy bundled Python caveat:** when that is the only 3.10+ interpreter,
  `.venv` is based on it. If a WorkBuddy update later replaces that Python,
  re-run `bootstrap.py --install --verify-key` once. Prefer a real system Python
  when one exists.
* `HAILUO_ZIP`, `HAILUO_REPO_DIR`, `HAILUO_PYTHON` and `HAILUO_WHEELHOUSE` are
  **installation path hints, not credentials**. Never put an API key in any of
  them or in any environment variable.
* Never install dependencies globally, never create `.venv` by hand, never edit
  `~/.workbuddy-ai/mcp.json` by hand. `setup_mcp.py` does all of it.

### Step 2 — Run the ONE setup command

```bash
<PY> bootstrap.py --install --verify-key
```

`<PY>` is the interpreter from Step 0B (any 3.6+, including WorkBuddy's bundled
Python by absolute path). Examples:

```bash
python3 bootstrap.py --install --verify-key                 # macOS / Linux
python  bootstrap.py --install --verify-key                 # Windows
"/c/Users/stu/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe" \
    bootstrap.py --install --verify-key                     # no python on PATH
```

`bootstrap.py` (stdlib-only, no git) does this first:

1. Uses the existing clone/extraction, or downloads the GitHub ZIP and extracts
   it with `zipfile` into `./hailuo-local-mcp/` (path-traversal checked).
2. Probes interpreters in order: `HAILUO_PYTHON`, the current one, PATH names,
   the Windows `py` launcher, then WorkBuddy's bundled Python locations. Stops
   at the first usable 3.10+.
3. Invokes `setup_mcp.py --install --verify-key` **with that interpreter** and
   returns its exit code unchanged. Arguments pass through, so
   `bootstrap.py --check` is a read-only status check.

`setup_mcp.py` is **single-pass**: it completes fully even when `api-key.txt`
does not exist yet or still holds the placeholder. In order, it:

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
   edits to `api-key.example.txt` (**skipped** when there is no `.git`, i.e. a
   ZIP install — there is nothing to commit with).
7. With `--verify-key`, makes **one no-cost** TokenHub auth probe. It is skipped
   cleanly if no key has been pasted, and a rejected/inconclusive probe **never
   fails the install**.

Do not pass `--install` twice, do not re-run setup after the key paste, and do
not run `selftest.py` as a "fix" — it is offline verification only.

### Step 3 — Interpret setup output (decision table)

| Exact output fragment | Meaning | Your next action |
|---|---|---|
| `BOOTSTRAP INCOMPLETE: no Python 3.10+ interpreter was found` | No usable Python anywhere on this machine | **Stop.** Give the student the exact one-time install bootstrap printed. This is the only human install; never install git |
| `BOOTSTRAP INCOMPLETE: could not download the repo ZIP` / `not a ZIP` | No network, proxy or captive portal | Fetch the §0 ZIP URL manually and set `HAILUO_ZIP`; or set `HAILUO_REPO_DIR` to an existing extraction |
| `[ok] extracted N files -> ... (no git used)` | ZIP path succeeded, no `.git` present | Normal. Continue; the pre-commit guard will be skipped |
| `PYTHON_OK <path>` / `VERSION 3.10+` | Read-only `--find-python` probe | Use that path as `<PY>` in Step 2 |
| `[!] Using WorkBuddy's bundled Python as the .venv base` | Only a WorkBuddy-supplied Python was available | Normal. Note it: re-run bootstrap once if WorkBuddy later upgrades Python |
| `SETUP INCOMPLETE: Python 3.10+ is required` | Wrong interpreter (only possible if setup was run directly) | Go to Step 1; do not continue |
| `SETUP INCOMPLETE: Could not create .venv` | Missing `venv` module / broken Python | Install a full Python 3.10+; re-run once |
| `SETUP INCOMPLETE: Dependency install failed` | No PyPI / proxy / wheelhouse | Fix network or set `HAILUO_WHEELHOUSE`; re-run |
| `[!!] Ignored legacy environment variables: ...` | Old `TOKENHUB_*` vars are set but ignored | Tell student to unset them; **do not** use them as a key source |
| `[!] Created api-key.txt -- this is the ONLY file you ever edit` | Normal on a fresh install (clone or ZIP) | Continue |
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
9. **Never require git or a system-level install.** Fetch the repo with
   `bootstrap.py` (ZIP + `zipfile`) and use any available Python 3.10+, including
   WorkBuddy's bundled one. Do not install git, do not run `winget`/`brew`/`apt`
   or an OS installer without the student's explicit OK, and do not put a key in
   any `HAILUO_*` path hint. The only permitted human install is Python 3.10+
   when `--find-python` proves none exists anywhere.

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
| `BOOTSTRAP INCOMPLETE: no Python 3.10+` | Give the student the exact one-time install bootstrap printed; then re-run Step 0C. Do **not** install git |
| `command not found: git` | Expected and harmless — bootstrap downloads the ZIP. Never install git for this |
| `tar: This does not look like a tar archive` | Git Bash's GNU tar cannot read ZIP. Let `bootstrap.py` extract it; do not use tar/unzip |
| `SETUP INCOMPLETE: Python 3.10+` (macOS) | Xcode CLT ships 3.9: `brew install python@3.12` or python.org installer, verify with `bootstrap.py --find-python`, re-run Step 2 |
| `command not found: python` | Use `python3`, `py -3`, or WorkBuddy's bundled Python by absolute path (Step 0B). Any 3.6+ can run `bootstrap.py` |
| `.venv` python breaks after a WorkBuddy update | Its base interpreter was replaced; re-run `bootstrap.py --install --verify-key` once |
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
# CANONICAL: one command, no git, no Python on PATH required
<PY> bootstrap.py --install --verify-key

# free read-only interpreter probe (before install, spends nothing)
<PY> bootstrap.py --find-python

# passthrough checks (bootstrap forwards every argument to setup_mcp.py)
<PY> bootstrap.py --check               # read-only: venv / key / both config entries
<PY> bootstrap.py --uninstall          # remove ONLY hailuo-video (with backup)

# direct setup, ONLY when Python 3.10+ is already on PATH
python3 setup_mcp.py --install --verify-key       # macOS / Linux
python  setup_mcp.py --install --verify-key       # Windows
python3 setup_mcp.py                             # dry run: no global install

# no-cost key probe (Windows: .venv/Scripts/python.exe)
.venv/bin/python check_key.py

# offline end-to-end regression suite (zero TokenHub calls, zero credit)
.venv/bin/python selftest.py

# offline classroom install
HAILUO_WHEELHOUSE=/path/to/wheels <PY> bootstrap.py --install --verify-key
HAILUO_ZIP=/path/to/repo.zip       <PY> bootstrap.py --install --verify-key
```

`bootstrap.py` runs on Python 3.6+, downloads/extracts the repo with the stdlib
when there is no clone, finds a 3.10+ interpreter, and returns setup's exit code.
`setup_mcp.py` prints `INSTALL WRITTEN -- activation is NOT complete.` on
success and never claims the connector is live. It exits `1` on an unsupported
Python or a failed dependency install; it may have *created* `api-key.txt`, but it
never overwrites an existing key value or any existing config. `--check` exits
`1` when the install is incomplete. `check_key.py`
exits `0` **only** for `KEY VALID` (HTTP 400). `HAILUO_*` variables are path
hints only — none of them may ever hold a credential.

---

## 7. Platform notes

| | Windows | macOS (Intel / Apple Silicon) | Linux |
|---|---|---|---|
| Setup command | `<PY> bootstrap.py --install --verify-key` | same | same |
| Venv python | `.venv/Scripts/python.exe` | `.venv/bin/python` | `.venv/bin/python` |
| Python prerequisite | 3.10+ (bootstrap accepts 3.6+) | **3.10+ — stock `python3` is 3.9** (fine for bootstrap) | 3.10+ and `python3-venv` |
| Needs git? | **No** | **No** | **No** |
| No Python on PATH | Use WorkBuddy bundled `python.exe` by absolute path | Same, or python.org / Homebrew once | Use `python3` absolute path or install `python3-venv` |
| Config | `~/.workbuddy-ai/mcp.json` (+ `~/.workbuddy/mcp.json` if that folder exists) | same | same |

**Lowest common denominator (no git, no Python on PATH).** WorkBuddy's public
Overview docs do **not** promise to install developer tools, and installing them
needs rights an agent may not have — so this repo does not rely on that. What was
verified on a Windows WorkBuddy install: a bundled Python 3.13
(`~/.workbuddy-ai/binaries/python/versions/<ver>/python.exe`, also
`%LOCALAPPDATA%/Programs/WorkBuddyAI/resources/vendor/python/python.exe`),
PortableGit, Node, `curl.exe` and `C:\Windows\System32\tar.exe` (bsdtar). Git
Bash's `/usr/bin/tar` is GNU tar and **cannot** open a ZIP — which is why
`bootstrap.py` uses `zipfile` instead of any external tool. WorkBuddy therefore
usually needs to install nothing at all: the agent locates its bundled Python and
runs `bootstrap.py`, which fetches the ZIP itself. **The macOS bundled-Python
paths are best-effort guesses** (app-bundle layout was not verifiable from
Windows); confirm with one Mac pilot. If no 3.10+ interpreter exists anywhere,
the student performs exactly one manual Python install — bootstrap prints the
platform-specific command — and never installs git.

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

## 8. For the teacher — distribution and rotation

> Student agents should **not** act on this section.

1. The repo is live at `https://github.com/vjsyong/hailuo-local-mcp.git` and is
   currently **public**, so the §0 kickoff prompt's raw `README.md`,
   `bootstrap.py` and ZIP URLs all work with no sign-in. It holds no credentials,
   only code and docs. **Git is not required on student machines.** If classroom
   policy requires a private repo, change visibility in GitHub Settings **and
   grant every student read access first** — otherwise the raw/ZIP downloads
   fail too; in that case hand out a local ZIP and set `HAILUO_ZIP`. Confirm your
   WorkBuddy build honours external edits to `mcp.json`; if not, students paste
   the block from `mcp.local.json` into the MCP settings UI manually.
2. Give each of the 5 groups **its own single** TokenHub API key via a separate
   channel (LMS, email, in person) — never in the repo, never in an issue.
3. Point students at `README.md` §0 and have them paste that one kickoff prompt.
   It carries the repo, raw runbook, bootstrap and ZIP URLs, so their agent can
   fetch the code **without git** and run the single setup command itself; the
   student pastes only their own key. Do not send extra install instructions —
   that invites agents to improvise.
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
   distributing to all 5 groups. On at least one pilot, remove git from PATH and
   use only WorkBuddy's bundled Python by absolute path — that is the
   lowest-common-denominator case this runbook is written for.

---

## 9. What this is — architecture and security model

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

**One group = one key = one OS account = one repo copy** (clone or ZIP
extraction). Two groups sharing a machine/account will overwrite each other's
connector entry and key file.

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

## 10. Acceptance checklist (agent: confirm before saying "done")

- [ ] `git status --short` shows no secret or runtime file staged (skip entirely
      when the ZIP path was used — there is no `.git`).
- [ ] The install worked **without installing git**; if Python was not on PATH,
      the WorkBuddy bundled interpreter (or `bootstrap.py --find-python`) was used.
- [ ] `bootstrap.py --check` reports install complete and the connector entry in
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

## 11. Files in this repo

| File | Role |
|---|---|
| `README.md` | **This file — §0 student kickoff prompt + the canonical agent runbook** |
| `AGENTS.md` | Extended reference, rationale, teacher notes |
| `bootstrap.py` | **Zero-prerequisite entry point**: no git, no Python on PATH needed. Downloads/extracts the ZIP, finds a 3.10+ interpreter (incl. WorkBuddy's bundled Python), delegates to setup |
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

- **Not git.** Not a system-level install. The repo arrives as a ZIP if needed.
- A Python 3.10+ interpreter *somewhere* — system, `py` launcher, or WorkBuddy's
  own bundled Python. `bootstrap.py` itself runs on any Python 3.6+, so a stock
  macOS 3.9 can drive the install. Only if none exists is a one-time Python
  install needed.
- WorkBuddy with custom MCP connector support and the ability to run shell
  commands (its agent toolset provides this).
- `mcp==2.3.0`, `httpx==0.28.1` (installed into `.venv` automatically).
- One Tencent Cloud TokenHub API key per group.
- Network access to GitHub/codeload for the ZIP, PyPI on the first run (or a
  wheelhouse), and to TokenHub for generation. Offline labs: `HAILUO_ZIP` +
  `HAILUO_WHEELHOUSE`.
