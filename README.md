# Hailuo Video MCP (local, one key per group)

Generate short videos with MiniMax H3 (`minimax-video-h3`) on Tencent Cloud
TokenHub from inside WorkBuddy. This is a **local** MCP server: it runs on your
computer, keeps your finished MP4 in `videos/`, and needs **exactly one**
credential — your group's TokenHub API key.

## Student: 4 steps

1. Clone this repo.
2. Tell your WorkBuddy agent: **"Set up the video MCP in this repo."**
3. Paste your group's **single API key** into `api-key.txt` (line 1, plain text).
   This is the only file you edit.
4. In WorkBuddy: **Connectors → Custom Connector → Trust `hailuo-video`**, then
   **start a new chat session**. Ask: *"Generate a 4 second video of a cat on a
   desk."*

Your agent handles everything else. Before generating, it will run
`check_key.py`, a free key check that creates no video and spends no credit.

- **Never commit `api-key.txt`.** It is gitignored; setup also installs a hook
  that blocks it.
- **Never put a real key in `api-key.example.txt`** — that file is tracked.
- One group = one key = one computer/OS account = one clone.

Full instructions for your agent and for the teacher: **[AGENTS.md](AGENTS.md)**.

## Manual setup (if your agent cannot run it)

```bash
# Windows
python setup_mcp.py --install --verify-key

# macOS / Linux  (Python 3.10+; stock macOS has python3, not python)
python3 setup_mcp.py --install --verify-key
```

### macOS — read this first

**Yes, it runs on macOS (Intel and Apple Silicon).** The only thing that will
actually trip students up is Python: macOS has **no `python`**, and the `python3`
that comes with Xcode Command Line Tools is **Python 3.9**, which is too old.
Setup will refuse it with a clear message. Install 3.10+ once per machine:

```bash
# Option A — Homebrew
brew install python@3.12
python3 --version                 # must print 3.10 or newer

# Option B — official installer: https://www.python.org/downloads/macos/
#            (then check `python3 --version`)

xcode-select --install            # only needed if pip has to compile a wheel
python3 setup_mcp.py --install --verify-key
```

Other Mac-specific notes:

- Edit `api-key.txt` in a **plain-text** editor (VS Code, BBEdit, `nano`), not
  TextEdit in its default Rich Text / smart-quotes mode. A curly-quote or UTF-16
  save is rejected with an explicit error, so a bad paste fails safely instead of
  sending a broken key.
- Config is written to `~/.workbuddy-ai/mcp.json` (and `~/.workbuddy/mcp.json`
  if that folder exists). Setup generates `.venv/bin/python` paths automatically;
  `mcp.local.json` is a paste-ready fallback.
- Apple Silicon is fine: the only compiled dependencies (`pydantic-core`,
  `cryptography`) publish macOS arm64 wheels.
- Paths with spaces are safe (the MCP SDK spawns with an argument array, not a
  shell), but cloning to a simple path like `~/hailuo-local-mcp` is still safest.

Useful commands:

```bash
python3 setup_mcp.py --check        # status of venv, key, connector config
python3 setup_mcp.py --uninstall    # remove only the hailuo-video connector
.venv/bin/python check_key.py       # no-cost key probe (Windows: .venv/Scripts/python.exe)
.venv/bin/python selftest.py        # offline end-to-end test, zero credit
```

First run needs PyPI access. For offline labs, set `HAILUO_WHEELHOUSE` to a
folder of wheels before running setup.

## Tools

| Tool | What it does |
|---|---|
| `video_capabilities` | Model, valid ranges, key status |
| `generate_video` | Submit → poll → download → local `video_path` |
| `submit_video` | Submit only, returns `task_id` |
| `check_video` | Resume a job with its `task_id` |
| `recent_tasks` | Recover a lost `task_id` |

If a result says `resubmit_allowed: false`, the job is already paid for — call
`check_video` with its `task_id`, **never** generate again.

## Requirements

- Python 3.10+ (3.11+ recommended)
- WorkBuddy with custom MCP connector support (verified on builds that read
  `~/.workbuddy-ai/mcp.json`; setup also writes `~/.workbuddy/mcp.json`)
- `mcp==2.3.0`, `httpx==0.28.1` (installed into `.venv` automatically)
- One Tencent Cloud TokenHub API key per group
