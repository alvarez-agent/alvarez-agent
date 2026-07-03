---
name: alvarez-agent
description: "Configure, extend, or contribute to Alvarez — the trimmed, terminal-first self-improving agent."
version: 3.0.0
author: Alvarez
license: MIT
platforms: [linux, macos, windows]
metadata:
  alvarez:
    tags: [alvarez, setup, configuration, cli, tui, telegram, learning-loop, skills, memory, development]
    related_skills: [claude-code, codex, opencode]
---

# Alvarez Agent

Alvarez is a heavily trimmed fork of the Hermes agent framework — a self-improving AI agent with a terminal-first interface, a persistent learning loop, and one remote channel (Telegram). It is in the same category as Claude Code (Anthropic), Codex (OpenAI), and OpenCode: autonomous coding and task-execution agents that use tool calling to interact with your system. It works with any OpenAI-compatible LLM provider (27 bundled provider plugins: OpenRouter, Anthropic, Google, DeepSeek, xAI, local models, and more) and runs on Linux, macOS, Windows, and WSL.

Current version: **0.1.0** (as of 2026-07-03). Alvarez runs from a local git checkout; it is not published to PyPI or npm and has no hosted docs site.

The design goal of the fork is a "pi agent": keep the critical features that make the agent work, delete everything else. The trim removed ~730k lines — the Electron desktop app, the web dashboard, 19 of 20 messaging platforms, research/training tooling, the docs website, and the Nous Portal / credits / billing integrations are all **gone**. What remains:

- **CLI + Ink TUI** — the main surface: multiline editing, slash-command autocomplete, streaming tool output, interrupt-and-redirect, a 6-skin theme system, optional terminal pet.
- **Self-improving through skills** — Alvarez learns from experience by saving reusable procedures as skill documents (agentskills.io-compatible). Skills accumulate over time; a background curator maintains them.
- **Persistent memory across sessions** — pluggable memory backends (hindsight, honcho, mem0, supermemory, and more) plus FTS5 full-text search over its own past sessions.
- **Telegram gateway** — the one remote channel, with full tool access, DM pairing, voice transcription, and session continuity across CLI ↔ Telegram. The gateway also hosts `api_server` (OpenAI-compatible HTTP API) and `webhook` (inbound events) adapters.
- **~35 toolsets / ~90 tool modules** — files, terminal, browser automation, web search, delegation (subagents), sandboxed code execution, vision, TTS, kanban multi-agent coordination, MCP client/server.
- **Automation** — natural-language cron jobs, webhook-triggered agent runs, a durable kanban work queue.
- **Profiles** — multiple isolated instances with their own config, sessions, skills, and memory.
- **ACP server** — Agent Client Protocol integration for editors (Zed, JetBrains).

**This skill helps you work with Alvarez effectively** — running it, configuring features, spawning additional agent instances, troubleshooting, finding the right commands and settings, and understanding the system when you need to extend it.

## Scope & Verification

This skill is a concise operating guide, not the complete source of truth for every feature. If a feature, command, or setting is not mentioned here, do not treat that absence as evidence that it does not exist. There are no hosted docs — verify against the local repo checkout:

- CLI commands: `uv run alvarez --help`, `uv run alvarez <command> --help`, and `alvarez_cli/main.py`
- Slash commands: `/help` in-session, or `COMMAND_REGISTRY` in `alvarez_cli/commands.py`
- Toolsets: `toolsets.py` at the repo root
- Themes: `alvarez_cli/skin_engine.py`
- Refactor history and what was deleted: `REFACTOR_NOTES.md` at the repo root

The repo checkout lives at `/Users/ken/dev2/hermes-agent` (branch `rebrand-alvarez`).

## Quick Start

There is no installer. Run from the repo checkout with `uv` (builds the `.venv` on first run, Python 3.12):

```bash
cd /Users/ken/dev2/hermes-agent

uv run alvarez                  # interactive TUI (the main surface)
uv run alvarez --cli            # force the plain readline CLI instead

uv run alvarez -z "summarize the git log of this repo"   # one-shot prompt
uv run alvarez -m openrouter/deepseek/deepseek-chat -z "…"  # model override
uv run alvarez -t coding,web -z "…"                      # toolset selection

uv run alvarez setup            # interactive wizard (provider + key + model)
uv run alvarez model            # model/provider picker
uv run alvarez doctor           # config + dependency health check
```

Telegram deps come from an extra: `uv run --extra messaging alvarez gateway run`.

First run: `uv run alvarez setup` (fresh install wizard), or sandbox with `ALVAREZ_HOME=~/alvarez-test uv run alvarez`. The old `~/.hermes` fallback was removed in the separation — copy `config.yaml` and `.env` into `~/.alvarez` by hand if migrating a pre-rebrand install.

The TUI's vendored ink package needs a one-time build: `npm install` at the repo root, then `cd ui-tui/packages/alvarez-ink && npm run build`.

---

## CLI Reference

### Global Flags

```
alvarez [flags] [command]

  --version, -V             Show version
  -z, --oneshot TEXT        One-shot prompt, non-interactive
  -m, --model MODEL         Model override
  --provider PROVIDER       Force provider
  -t, --toolsets LIST       Comma-separated toolsets
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --tui / --cli             Force the Ink TUI or plain CLI
  --yolo                    Skip dangerous-command approval
  --quiet, -Q               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --ignore-rules            Skip project context files, SOUL.md, user config, plugins, MCP
  --safe-mode               Locked-down run
  --pass-session-id         Include session ID in system prompt
```

No subcommand defaults to `chat`. `alvarez chat -q "…"` is equivalent to `-z`. There is also a headless programmatic entry point: `alvarez-agent` (`run_agent.py`), and an ACP entry point `alvarez-acp` for editors.

### Subcommand Map

| Area | Commands |
|---|---|
| Chat | `chat` (default), `-z` one-shot, `--resume` / `--continue` |
| Models | `model`, `moa` (mixture-of-agents), `fallback`, `auth` / `login` / `logout`, `proxy` (OpenAI-compatible local proxy) |
| Learning | `skills`, `bundles`, `curator`, `memory`, `journey`, `sessions`, `insights` |
| Automation | `cron`, `webhook`, `send`, `gateway`, `pairing` |
| Workspace | `project`, `kanban`, `profile`, `hooks`, `lsp` |
| Tooling | `tools`, `mcp`, `computer-use`, `plugins`, `pets` |
| Ops | `setup`, `doctor`, `security`, `status`, `config`, `backup` / `import`, `checkpoints`, `logs`, `dump`, `debug`, `update`, `uninstall`, `version`, `completion`, `prompt-size`, `secrets`, `postinstall` |
| Integration | `acp` (editor protocol server), `mcp serve` |

**Known stale entries (post-trim debt):** a few parser entries survive whose backends were deleted — `slack`, `desktop` / `gui`, `dashboard`, `portal`, and possibly `claw` paths. They fail or no-op if invoked; do not recommend them. `computer-use` still works (its cua-driver backend was kept).

### Configuration

```
alvarez setup [section]      Interactive wizard (model|terminal|gateway|tools|agent)
alvarez model                Interactive model/provider picker
alvarez config               View current config
alvarez config edit          Open config.yaml in $EDITOR
alvarez config set KEY VAL   Set a config value
alvarez config path          Print config.yaml path
alvarez config env-path      Print .env path
alvarez doctor [--fix]       Check dependencies and config
alvarez status [--all]       Show component status
```

Credentials (OAuth + API keys, with pooling) are managed under `alvarez auth`: `add`, `list`, `remove`, `reset`. Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys. `alvarez secrets bitwarden` wires in Bitwarden Secrets Manager as an external secret store.

### Tools & Skills

```
alvarez tools                Interactive tool enable/disable
alvarez tools list           Show all tools and status
alvarez tools enable NAME    Enable a toolset
alvarez tools disable NAME   Disable a toolset

alvarez skills list          List installed skills
alvarez skills search QUERY  Search skill sources
alvarez skills install ID    Install (hub identifier OR a direct https://…/SKILL.md URL)
alvarez skills inspect ID    Preview without installing
alvarez skills config        Enable/disable skills per platform
alvarez skills uninstall N   Remove an installed skill
alvarez skills tap add REPO  Add a GitHub repo as a skill source
alvarez bundles              Skill-group aliases
```

### MCP Servers

```
alvarez mcp serve            Run Alvarez as an MCP server (mcp_serve.py)
alvarez mcp add NAME         Add an MCP server (--url or --command)
alvarez mcp remove NAME      Remove an MCP server
alvarez mcp list             List configured servers
alvarez mcp test NAME        Test connection
alvarez mcp configure NAME   Toggle tool selection
alvarez mcp install NAME     Install from the bundled catalog (alvarez_cli/mcp_catalog.py)
```

How the built-in MCP client connects servers (stdio/HTTP), auto-discovers their tools, exposes them as first-class tools, and handles sampling: `skill_view(name="alvarez-agent", file_path="references/native-mcp.md")`.

### Gateway (Telegram)

```
alvarez gateway status       What's configured / running
alvarez gateway run          Start gateway in the foreground
alvarez gateway install      Install as user service (launchd/systemd)
alvarez gateway start/stop/restart   Control the service
alvarez gateway setup        Configure platforms
```

Telegram is the only messaging platform. Config: `TELEGRAM_BOT_TOKEN` env var or `gateway.platforms.telegram` in `config.yaml`. DM pairing (`alvarez pairing list/approve/revoke`) authorizes users; voice memos are auto-transcribed; sessions continue across CLI ↔ Telegram.

The gateway also hosts two non-messaging adapters:

- **`api_server`** — an OpenAI-compatible HTTP API into the agent (external UIs and scripts can talk to Alvarez as if it were a model endpoint).
- **`webhook`** — inbound event processing; external services POST events that trigger agent runs. Full setup, payload templating, and delivery patterns: `skill_view(name="alvarez-agent", file_path="references/webhooks.md")`.

`alvarez send -p telegram -c <chat> "message"` sends one-off messages (used by cron jobs and scripts).

### Sessions

```
alvarez sessions list        List recent sessions
alvarez sessions browse      Interactive picker
alvarez sessions export OUT  Export to JSONL
alvarez sessions rename ID T Rename a session
alvarez sessions delete ID   Delete a session
alvarez sessions prune       Clean up old sessions (--older-than N days)
alvarez sessions stats       Session store statistics
```

`alvarez insights [--days N]` shows usage analytics; `alvarez journey` renders a timeline of learned skills and memories over time.

### Cron Jobs

```
alvarez cron list            List jobs (--all for disabled)
alvarez cron add SCHED       Create: '30m', 'every 2h', '0 9 * * *', or natural language
alvarez cron edit ID         Edit schedule, prompt, delivery
alvarez cron pause/resume ID Control job state
alvarez cron run ID          Trigger on next tick
alvarez cron remove ID       Delete a job
alvarez cron status          Scheduler status
```

### Webhooks

```
alvarez webhook subscribe N  Create route at /webhooks/<name>
alvarez webhook list         List subscriptions
alvarez webhook remove NAME  Remove a subscription
alvarez webhook test NAME    Send a test POST
```

### Profiles

```
alvarez profile list         List all profiles
alvarez profile create NAME  Create (--clone, --clone-all, --clone-from)
alvarez profile use NAME     Set sticky default
alvarez profile delete NAME  Delete a profile
alvarez profile show NAME    Show details
alvarez profile alias NAME   Manage wrapper scripts
alvarez profile rename A B   Rename a profile
alvarez profile export NAME  Export to tar.gz
alvarez profile import FILE  Import from archive
```

Each profile is `<root>/profiles/<name>` used as its own `ALVAREZ_HOME` (own config, sessions, memory). The gateway and cron spawners propagate `ALVAREZ_HOME` explicitly; a loud stderr warning fires if a non-default profile is sticky-active but a process falls back to the default home.

### Other

```
alvarez kanban <verb>        Multi-agent work-queue board (init/create/list/show/assign/…)
alvarez memory setup/status/off  Memory provider config
alvarez curator <verb>       Skill lifecycle maintenance (status/run/pin/archive/…)
alvarez proxy                OpenAI-compatible local proxy backed by an OAuth provider
alvarez plugins list/install/remove  Plugin management
alvarez completion bash|zsh  Shell completions
alvarez acp                  ACP server (IDE integration)
alvarez pets                 Terminal sprite pet management
```

For the full, authoritative command list run `alvarez --help` (and `alvarez <command> --help`). Plugin-supplied subcommands only appear once their plugin is installed and active.

---

## Slash Commands (In-Session)

Type these during an interactive chat session. The registry of record is `COMMAND_REGISTRY` in `alvarez_cli/commands.py` — every consumer (autocomplete, `/help`, the Telegram menu) derives from it. Run `/help` in-session for the authoritative list.

### Session Control
```
/new (/reset)        Fresh session
/clear               Clear screen + new session (CLI)
/retry               Resend last message
/undo [N]            Back up N user turns and re-prompt
/prompt              Compose your next prompt in $EDITOR
/title [name]        Name the session
/compress            Manually compress context
/stop                Kill background processes
/rollback [N]        Restore filesystem checkpoint
/snapshot [sub]      Create or restore state snapshots of Alvarez config/state (CLI)
/background <prompt> Run prompt in background
/queue <prompt>      Queue for next turn
/steer <prompt>      Inject a message after the next tool call without interrupting
/agents (/tasks)     Show active agents and running tasks
/resume [name]       Resume a named session
/sessions            Browse and resume previous sessions
/branch (/fork)      Branch the current session
/goal [text|sub]     Standing goal Alvarez works on across turns (status/pause/resume/clear)
/subgoal [sub]       Manage extra criteria on the active goal
/moa <prompt>        One prompt through the Mixture-of-Agents preset
/handoff <platform>  Hand the live session off to Telegram (CLI)
/redraw              Force a full UI repaint (CLI)
```

### Configuration
```
/config              Show config (CLI)
/model [name]        Show or change model
/personality [name]  Set personality
/reasoning [level]   Set reasoning (none|minimal|low|medium|high|xhigh|show|hide)
/verbose             Cycle tool progress: off → new → all → verbose
/voice [on|off|tts]  Voice mode
/yolo                Toggle approval bypass
/fast                Toggle priority/fast processing
/busy [sub]          What Enter does while Alvarez is working (queue/steer/interrupt/status)
/indicator [style]   TUI busy-indicator style (kaomoji, emoji, unicode, ascii)
/footer [on|off]     Toggle gateway runtime-metadata footer on final replies
/skin [name]         Change theme (CLI)
/statusbar           Toggle status bar (CLI)
/timestamps          Toggle [HH:MM] timestamps
/codex-runtime       Toggle codex app-server runtime for OpenAI/Codex models
```

### Tools, Skills & Learning
```
/tools               Manage tools (CLI)
/toolsets            List toolsets (CLI)
/skills              Search/install/manage skills
/reload-skills       Re-scan ~/.alvarez/skills/
/reload              Reload .env variables into the running session (CLI)
/reload-mcp          Reload MCP servers
/learn <what>        Learn a reusable skill from anything you describe
/memory              Review pending memory writes / toggle the approval gate
/bundles             List skill bundles (aliases for skill groups)
/journey             Open the learning journey timeline
/curator [sub]       Background skill maintenance (status, run, pin, archive, …)
/cron                Manage cron jobs (CLI)
/suggestions         Review suggested automations (accept/dismiss)
/blueprint           Set up an automation from a blueprint template
/kanban [sub]        Multi-profile collaboration board (tasks, links, comments)
/plugins             List plugins (CLI)
/browser             Open CDP browser connection
/pet, /hatch         Terminal pet: adopt / generate one
```

### Gateway
```
/approve, /deny      Approve/deny a pending command (gateway)
/restart             Restart gateway after draining active runs (gateway)
/sethome             Set current chat as home channel (gateway)
/update              Update Alvarez (gateway)
/topic [sub]         Telegram DM topic sessions (gateway)
/platforms (/gateway) Platform connection status
/platform [sub]      Pause/resume/list a failing gateway platform
```

### Info & Exit
```
/help                Show commands
/commands [page]     Browse all commands (paginated)
/usage               Token usage and rate limits
/insights [days]     Usage analytics
/status              Session, model, token, and context info
/profile             Active profile info
/whoami              Slash-command access level (admin/user)
/history /save /copy /paste /image   Transcript and clipboard helpers (CLI)
/version /debug      Version info / upload debug report
/quit (/exit, /q)    Exit CLI
```

---

## Key Paths & Config

All state lives under **`ALVAREZ_HOME`** (default `~/.alvarez`; `%LOCALAPPDATA%\alvarez` on Windows):

```
~/.alvarez/config.yaml       Main configuration
~/.alvarez/.env              API keys and secrets
~/.alvarez/skills/           User-installed skills
~/.alvarez/plugins/          User-installed plugins
~/.alvarez/skins/            User theme YAMLs
~/.alvarez/sessions/         Transcripts, routing index (FTS5-searchable)
~/.alvarez/state.db          Canonical session store (SQLite + FTS5)
~/.alvarez/checkpoints/      File-change checkpoints
~/.alvarez/profiles/<name>/  Isolated sub-instances (same layout)
~/.alvarez/logs/             Gateway and error logs
~/.alvarez/auth.json         OAuth tokens and credential pools
```

**Legacy compatibility:** removed (2026-07-03) — `~/.alvarez` (or `ALVAREZ_HOME`) only. Migrating from a pre-rebrand install means copying `config.yaml` and `.env` across; hindsight memory carries over via `bank_id: hermes` (see Troubleshooting).

### Config Sections

Edit with `alvarez config edit` or `alvarez config set section.key value`. The full default tree is `DEFAULT_CONFIG` in `alvarez_cli/config.py`.

| Section | Key options |
|---------|-------------|
| `model` | `name`/`default`, `provider`, `base_url`, `api_key`, `context_length` |
| `agent` | `max_turns`, `tool_use_enforcement` |
| `terminal` | `backend` (local/docker/ssh/modal), `cwd`, `timeout`, `home_mode` (auto/real/profile) |
| `compression` | `enabled`, `threshold`, `target_ratio` |
| `display` | `skin`, `interface` (cli/tui), `tool_progress`, `show_reasoning`, `show_cost`, `language` |
| `gateway` | `platforms.telegram` (enabled, token), webhook/api_server settings |
| `stt` / `tts` | voice providers (see Voice section) |
| `memory` | provider selection + provider config (see Learning Loop) |
| `security` | `redact_secrets`, `website_blocklist` |
| `privacy` | `redact_pii` |
| `approvals` | `mode` (manual/smart/off) |
| `delegation` | `model`, `provider`, `max_iterations`, `max_concurrent_children`, `max_spawn_depth` |
| `checkpoints` | `enabled`, `max_snapshots` |
| `curator` | `enabled`, `consolidate` (off by default), `interval_hours`, `stale_after_days` |
| `network` | `force_ipv4` (getaddrinfo patch for broken IPv6 hosts) |

### Environment Variables

| Variable | Purpose |
|---|---|
| `ALVAREZ_HOME` | State directory override (per-profile isolation, Docker) |
| `HERMES_HOME` | Legacy alias, still honored |
| `TELEGRAM_BOT_TOKEN` | Telegram gateway credential |
| `ALVAREZ_TUI_LIGHT` / `ALVAREZ_TUI_THEME` / `ALVAREZ_TUI_BACKGROUND` | TUI light/dark detection overrides |
| `ALVAREZ_YOLO_MODE` | Per-invocation approval bypass |
| `ALVAREZ_NODE_TARGET_MAJOR` | Managed Node major version (default 22) |
| `ALVAREZ_REAL_HOME` | Explicit OS-user home for subprocess HOME repair |

### Providers

27 model-provider plugins under `plugins/model-providers/`: openrouter, anthropic, openai-codex, gemini, deepseek, xai, ollama-cloud, bedrock, azure-foundry, copilot, qwen-oauth, kimi-coding, zai, and more, plus `custom` for any OpenAI-compatible endpoint (vLLM, llama.cpp, ollama). Set via `alvarez model` or `alvarez setup`; common env vars:

| Provider | Auth |
|----------|------|
| OpenRouter | `OPENROUTER_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI Codex | OAuth via `alvarez auth` |
| GitHub Copilot | Copilot OAuth device flow via `alvarez model` (NOT `gh auth login` tokens) |
| Google Gemini | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| xAI / Grok | `XAI_API_KEY` |
| Custom endpoint | `model.base_url` + `model.api_key` in config.yaml |

Note: Hermes-3/4 chat models are detected and warned about — they are not agentic/tool-calling models; pick an agentic model for agent work.

### Toolsets

Enable per-run with `alvarez -t <set,set>` or per-platform with `alvarez tools`. The registry is the `TOOLSETS` dict in `toolsets.py` (repo root); `_ALVAREZ_CORE_TOOLS` is the default bundle most platforms inherit. The 35 surviving sets:

| Group | Toolsets |
|---|---|
| Core work | `file`, `terminal`, `coding` (files+terminal+search+web docs+skills+todo+delegation), `debugging`, `todo`, `clarify`, `safe` (no terminal) |
| Web | `web` (research + extraction), `search` (search only), `browser` (full automation), `x_search` |
| Force multipliers | `delegation` (isolated subagents), `code_execution` (Python scripts calling tools via RPC), `skills`, `memory`, `session_search`, `cronjob`, `kanban`, `context_engine`, `project` |
| Media | `vision`, `video` (analysis), `tts`, `image_gen` / `video_gen` (registries kept; generation provider plugins were trimmed — restore a provider plugin to reactivate) |
| Surfaces | `alvarez-cli`, `alvarez-telegram`, `alvarez-gateway`, `alvarez-webhook`, `alvarez-api-server`, `alvarez-acp`, `alvarez-cron`, `computer_use` |
| Stale stubs | `homeassistant`, `spotify` — backends deleted; entries remain but have no working tools |

Tool changes take effect on `/reset` (new session). They do NOT apply mid-conversation, to preserve prompt caching.

### Themes (skins)

The theme system lives in `alvarez_cli/skin_engine.py`. A skin is ~25 color tokens plus optional branding, spinner faces, and banner art. Switch in-session with `/skin <name>`, persist with `display.skin` in config.yaml, or drop a user YAML at `~/.alvarez/skins/<name>.yaml` (missing keys inherit from `default`).

The six-theme set added in the refactor: `paper` (traditional light), `graphite` (traditional dark), `hypercrush` (magenta/violet on tinted black — the loud one), `terminal-acid` (electric green + cyan), `sunfire` (orange→red on near-black), `deep-reef` (teal + violet on deep navy). Inherited from upstream and still present: `default`, `ares`, `mono`, `slate`, `daylight`, `warm-lightmode`, `poseidon`, `sisyphus`, `charizard`.

---

## The Learning Loop

Alvarez's differentiator: it accumulates capability and context across sessions instead of starting cold. Four legs:

1. **Memory** — `alvarez memory` configures a provider from `plugins/memory/`: **hindsight** (knowledge graph, multi-strategy retrieval, memory banks; cloud or local-embedded), **honcho** (dialectic user modeling), or mem0 / supermemory / byterover / holographic / openviking / retaindb. Modes: `context` (prefetched into the prompt), `tools` (agent queries explicitly), `hybrid`. Note: the hindsight `bank_id` defaults to `"alvarez"`; pre-rebrand banks were `"hermes"` — set `bank_id: hermes` if memory looks empty after upgrading.
2. **Skills** — markdown + YAML-frontmatter documents that teach procedures. The agent can create skills autonomously after complex tasks (`/learn` triggers it explicitly), edits them as it discovers corrections, and the **curator** (`alvarez curator` / `/curator`) does background maintenance: tracks usage, marks idle skills stale, archives (never deletes), keeps a pre-run backup. Pinned skills are exempt from every auto-transition. The aux-model consolidation pass is off by default (`curator.consolidate: true` to opt in) — routine curation costs zero tokens.
3. **Session search** — all conversations are FTS5-indexed under `ALVAREZ_HOME`. The `session_search` toolset gives cross-session recall without a memory provider — one tool, three modes inferred from args: discovery (`query`), scroll (`session_id` + `around_message_id`), browse (no args). Effectively free (no aux LLM).
4. **Cron** — natural-language scheduled jobs run unattended by the gateway and deliver to Telegram or a webhook. Per-job knobs: `skills`, model override, pre-run `script`, `context_from` (chain job outputs), `workdir`, multi-target delivery. Invariants: 3-minute hard interrupt per run, `.tick.lock` prevents duplicate ticks, cron sessions skip memory by default.

A typical composed loop: cron job fires → agent runs with `memory` + `session_search` + task toolsets → does the work (possibly delegating subagents) → persists notable facts → optionally writes/updates a skill → delivers the result to Telegram → the next session recalls all of it.

---

## Project Context Files

Alvarez injects project-level instructions into the system prompt from the working directory. Discovery is **first match wins** — one project context source per session:

| File (priority order) | Discovery |
|---|---|
| `.alvarez.md` / `ALVAREZ.md` | Walks parents up to the git root |
| `AGENTS.md` / `agents.md` | Cwd only |
| `CLAUDE.md` / `claude.md` | Cwd only |
| `.cursorrules` / `.cursor/rules/*.mdc` | Cwd only |

`SOUL.md` (in `$ALVAREZ_HOME`) is independent and always loaded — it sets the agent's identity, not project rules.

- Use `.alvarez.md` for Alvarez-specific rules that inherit from a parent directory (the walk stops at the git root).
- Use `AGENTS.md` when other agents (Codex, Claude Code, OpenCode) will work the same project.
- Don't put project rules in `~/.alvarez/AGENTS.md` — for cross-project context use `SOUL.md` or install a skill.
- Each file is capped at 20,000 characters (head + tail truncation with a `[...truncated...]` marker).
- All context files pass through the threat-pattern scanner; injection-looking content is replaced with a `[BLOCKED: ...]` placeholder (the rest of the file still loads).
- `alvarez --ignore-rules` skips all project context files, `SOUL.md`, user config, plugins, and MCP servers — use it to isolate whether a problem is your setup or Alvarez itself.

---

## Security & Privacy Toggles

Most of these are read at startup — change them from a terminal, then start a fresh session (`/reset` or a new invocation).

- **Secret redaction** (on by default): tool output is scanned for API-key/token-like strings before entering context and logs. `alvarez config set security.redact_secrets false` to disable (debugging only). The value is snapshotted at import time — flipping it mid-session (e.g. via an env var from a tool call) deliberately does NOT take effect for the running process.
- **PII redaction** (off by default): `alvarez config set privacy.redact_pii true` — the gateway hashes user IDs and strips phone numbers before context reaches the model.
- **Command approvals**: `approvals.mode` = `manual` (always prompt, default), `smart` (aux-LLM auto-approves low-risk), `off` (= `--yolo`). Per-invocation bypass: `alvarez --yolo` or `ALVAREZ_YOLO_MODE=1`. YOLO does NOT turn off secret redaction — they are independent.
- **Shell hooks allowlist**: `~/.alvarez/shell-hooks-allowlist.json`, prompted interactively on first use.
- To keep the model away from network/media tools entirely: `alvarez tools`, toggle per-platform, takes effect on next session.

---

## Voice & Transcription

**STT** (voice → text; Telegram voice memos are auto-transcribed). Provider priority: local faster-whisper (`pip install faster-whisper`, free) → Groq Whisper (`GROQ_API_KEY`) → OpenAI Whisper (`VOICE_TOOLS_OPENAI_KEY`) → Mistral Voxtral (`MISTRAL_API_KEY`). Config under `stt:` (`enabled`, `provider`, `local.model`).

**TTS** (text → voice): Edge TTS (free, default), ElevenLabs (`ELEVENLABS_API_KEY`), OpenAI, MiniMax, Mistral, NeuTTS (local). In-session: `/voice on` (voice-to-voice), `/voice tts` (always voice), `/voice off`.

---

## Spawning Additional Alvarez Instances

Run additional Alvarez processes as fully independent subprocesses — separate sessions, tools, and environments.

| | `delegate_task` | Spawning an `alvarez` process |
|-|-----------------|-------------------------------|
| Isolation | Separate conversation, shared process | Fully independent process |
| Duration | Minutes (bounded by parent loop) | Hours/days |
| Tool access | Subset of parent's tools | Full tool access |
| Interactive | No | Yes (PTY mode) |
| Use case | Quick parallel subtasks | Long autonomous missions |

One-shot: `terminal(command="alvarez chat -q '…'", timeout=300)`, or `background=true` for long tasks. Interactive spawning needs a real terminal — use tmux:

```
terminal(command="tmux new-session -d -s agent1 -x 120 -y 40 'alvarez'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t agent1 'Build a FastAPI auth service' Enter", timeout=15)
terminal(command="sleep 20 && tmux capture-pane -t agent1 -p", timeout=5)
terminal(command="tmux send-keys -t agent1 '/exit' Enter && sleep 2 && tmux kill-session -t agent1", timeout=10)
```

Tips: prefer `delegate_task` for quick subtasks; use `-w` (worktree mode) when spawned agents edit code (prevents git conflicts); use `--resume`/`--continue` to attach to prior sessions; for scheduled work use the `cronjob` tool instead of spawning (it handles delivery and retry).

---

## Durable & Background Systems

### Delegation (`delegate_task`)

Spawn a subagent with an isolated context + terminal session. Single (`delegate_task(goal, context, toolsets)`), batch (`tasks=[…]`, parallel, capped by `delegation.max_concurrent_children`), or background (`background=true` returns a handle; the child's result re-enters the conversation as a new turn). Roles: `leaf` (default; cannot re-delegate) vs `orchestrator` (bounded by `delegation.max_spawn_depth`). **Not durable** — a backgrounded child dies with the parent process; for work that must outlive the process use `cronjob` or `terminal(background=True, notify_on_complete=True)`.

### Cron

Durable scheduler (`cron/jobs.py` + `cron/scheduler.py`, backend `plugins/cron_providers/chronos`). Drive via the `cronjob` tool, `alvarez cron`, or `/cron`. See the Learning Loop section for schedules, per-job knobs, and invariants.

### Curator

Skill lifecycle maintenance — `alvarez curator status|run|pause|resume|pin|unpin|archive|restore|prune|backup|rollback`, mirrored by `/curator`. Only touches skills with `created_by: "agent"` provenance; bundled and hub-installed skills are off-limits. Never deletes — max destructive action is archive. Usage telemetry sidecar: `~/.alvarez/skills/.usage.json`.

### Kanban

Durable SQLite board for multi-profile / multi-worker collaboration. Users drive it via `alvarez kanban <verb>` (`init`, `create`, `list`, `show`, `assign`, `link`, `comment`, `complete`, `block`, `archive`, `tail`, …). Dispatcher-spawned workers get a focused `kanban_*` toolset gated by `ALVAREZ_KANBAN_TASK`; the dispatcher runs inside the gateway by default (`kanban.dispatch_in_gateway: true`) — reclaims stale claims, promotes ready tasks, atomically claims, spawns assigned profiles, and auto-blocks after `failure_limit` consecutive spawn failures. Board is the hard isolation boundary (`ALVAREZ_KANBAN_BOARD` pinned in worker env). The kanban core survived the trim; only its web-dashboard UI was deleted.

---

## Troubleshooting

### Model/provider issues
1. `alvarez doctor` — check config and dependencies
2. `alvarez auth` — re-authenticate OAuth providers (or `alvarez auth add <provider>`)
3. Check `.env` has the right API key
4. **Copilot 403**: `gh auth login` tokens do NOT work for the Copilot API — use the Copilot OAuth device flow via `alvarez model` → GitHub Copilot.

### Changes not taking effect
- Tools/skills: `/reset` starts a new session with the updated toolset
- Config changes: in gateway `/restart`; in CLI exit and relaunch
- Code changes: restart the CLI or gateway process

### Tool not available
1. `alvarez tools` — check the toolset is enabled for your platform
2. Some tools need env vars (check `.env`); tools with unmet requirements are hidden
3. `/reset` after enabling

### Skills not showing
1. `alvarez skills list` — verify installed
2. `alvarez skills config` — check platform enablement
3. Load explicitly: `/skill name` or `alvarez -s name`

### Gateway issues
Check logs first: `grep -i "failed to send\|error" ~/.alvarez/logs/gateway.log | tail -20`
- Gateway dies on SSH logout: `sudo loginctl enable-linger $USER`
- Gateway dies on WSL2 close: WSL2 needs `systemd=true` in `/etc/wsl.conf`; without it the gateway falls back to `nohup` and dies with the session
- Crash loop: `systemctl --user reset-failed alvarez-gateway`

### Voice not working
1. `stt.enabled: true` in config.yaml
2. `pip install faster-whisper` or set a provider API key
3. Gateway: `/restart`; CLI: relaunch

### Auxiliary models not working
If auxiliary tasks (vision, compression, session_search summaries) fail silently, the `auto` provider can't find a backend. Set `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`, or configure explicitly:
```bash
alvarez config set auxiliary.vision.provider <provider>
alvarez config set auxiliary.vision.model <model>
```

### Memory looks empty after the rename
Pre-rebrand hindsight banks were named `hermes`; the default is now `alvarez`. Set `bank_id: hermes` under the memory provider config.

### Windows quirks
- **Alt+Enter doesn't insert a newline** (Windows Terminal grabs it) — use Ctrl+Enter.
- **HTTP 400 "No models provided" on first run** — config.yaml saved with a UTF-8 BOM (Notepad). Re-save without BOM; `alvarez config edit` writes correctly.
- **WinError 10106 in `execute_code`** — the env scrubber dropped `SYSTEMROOT`; covered by `_WINDOWS_ESSENTIAL_ENV_VARS` in `tools/code_execution_tool.py`.
- Forward slashes (`C:/Users/...`) work in every Alvarez tool — prefer them.

---

## Where to Find Things

| Looking for... | Location |
|----------------|----------|
| Config options | `alvarez config edit`; defaults in `alvarez_cli/config.py` (`DEFAULT_CONFIG`) |
| Available tools | `alvarez tools list`; registry in `tools/registry.py`, grouping in `toolsets.py` |
| Slash commands | `/help` in session; registry in `alvarez_cli/commands.py` |
| Skills | `alvarez skills list`; bundled under `skills/` and `optional-skills/` in the repo |
| Provider setup | `alvarez model`; plugins under `plugins/model-providers/` |
| Telegram setup | `alvarez gateway setup`; adapter under `plugins/platforms/telegram/` |
| MCP servers | `alvarez mcp list`; client in `tools/mcp_tool.py`, catalog in `alvarez_cli/mcp_catalog.py` |
| Themes | `/skin`; engine in `alvarez_cli/skin_engine.py` |
| Profiles | `alvarez profile list` |
| Cron jobs | `alvarez cron list`; scheduler in `cron/` |
| Memory | `alvarez memory status`; providers under `plugins/memory/` |
| Gateway logs | `~/.alvarez/logs/gateway.log` |
| Session files | `alvarez sessions browse` (reads `state.db`) |
| What was deleted in the trim & how to restore it | `REFACTOR_NOTES.md` in the repo root |

---

## Contributor Quick Reference

### Project Layout

```
/Users/ken/dev2/hermes-agent      branch: rebrand-alvarez
├── agent/               core loop, prompt builder, context engines, pet, i18n
├── alvarez_cli/         CLI (main.py), config, skin engine, kanban, sessions
│   ├── commands.py      slash command registry (CommandDef)
│   ├── config.py        DEFAULT_CONFIG, env var definitions
│   └── main.py          CLI entry point and argparse
├── gateway/             telegram/webhook/api-server adapters, authz, delivery
├── tui_gateway/         Python side of the TUI bridge
├── ui-tui/              TypeScript Ink TUI (+ vendored alvarez-ink package)
├── tools/               ~90 tool modules; registry.py
├── toolsets.py          toolset registry (root)
├── plugins/             memory, browser, web, model-providers, telegram, cron
├── skills/ optional-skills/ optional-mcps/
├── cron/ acp_adapter/ providers/
├── run_agent.py cli.py mcp_serve.py model_tools.py
├── tests/               pytest suite (run via scripts/run_tests.sh)
└── REFACTOR_NOTES.md    working doc + change log (append every change)
```

Config: `~/.alvarez/config.yaml` (settings), `~/.alvarez/.env` (API keys) — both under `$ALVAREZ_HOME` when set.

### Adding a Tool

Two files. Auto-discovery imports any `tools/*.py` with a top-level `registry.register()` call, but a tool is only *exposed* once its name appears in a toolset.

**1. Create `tools/your_tool.py`:**
```python
import json, os
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("EXAMPLE_API_KEY"))

def example_tool(param: str, task_id: str = None) -> str:
    return json.dumps({"success": True, "data": "..."})

registry.register(
    name="example_tool",
    toolset="example",
    schema={"name": "example_tool", "description": "...", "parameters": {...}},
    handler=lambda args, **kw: example_tool(
        param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=check_requirements,
    requires_env=["EXAMPLE_API_KEY"],
)
```

**2. Wire it into a toolset in `toolsets.py`** — add the name to `_ALVAREZ_CORE_TOOLS` (every platform) or to a specific toolset.

All handlers must return JSON strings. Use `get_alvarez_home()` (from `alvarez_constants`) for paths, never hardcode `~/.alvarez`. For custom/local-only tools, write a plugin in `~/.alvarez/plugins/` instead of editing core — plugin discovery is a directory scan of `plugin.yaml` manifests.

### Adding a Slash Command

1. Add a `CommandDef` to `COMMAND_REGISTRY` in `alvarez_cli/commands.py`
2. Add a handler in `cli.py` → `process_command()`
3. (Optional) Add a gateway handler in `gateway/run.py`

All consumers (help text, autocomplete, Telegram menu) derive from the central registry automatically.

### Testing

- **Python ≥3.10 required**; use `uv run …` (manages the `.venv`, Python 3.12).
- Targeted: `uv run --with pytest,pytest-asyncio python -m pytest tests/alvarez_cli/test_skin_engine.py -q`
- Full suite MUST be per-file isolated: `scripts/run_tests.sh` (one pytest process per file). A serial single-process run cross-pollutes module state and produces ~1,500 bogus failures. The isolated baseline has ~60 environment-specific failures that pre-date the refactor — compare against baseline, don't chase them.
- TUI: `cd ui-tui && npm test` (vitest); TS binaries are hoisted to the repo-root `node_modules/.bin`. The vendored `ui-tui/packages/alvarez-ink` needs a one-time `npm run build`.
- Tests auto-redirect `ALVAREZ_HOME` to temp dirs — never touch real `~/.alvarez/`.

### Key Rules

- **Never break prompt caching** — don't change context, tools, or the system prompt mid-conversation
- **Message role alternation** — never two assistant or two user messages in a row
- Use `get_alvarez_home()` for all paths (profile-safe)
- Config values go in `config.yaml`, secrets go in `.env`
- New tools need a `check_fn` so they only appear when requirements are met
- Append every refactor change to the `REFACTOR_NOTES.md` change log (newest first)
- Keep-as-hermes list (never rename): Hermes model IDs, vLLM's `--tool-call-parser hermes`, `hermes-0day`
