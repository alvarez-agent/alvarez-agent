<p align="center">
  <img src="assets/banner.png" alt="Alvarez" width="100%">
</p>

# Alvarez Agent ☤
<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.11%E2%80%933.13-blue?style=for-the-badge" alt="Python 3.11–3.13"></a>
</p>

**A self-improving AI agent** (a fork of Nous Research's hermes-agent). Alvarez has a built-in learning loop: it creates skills from experience, improves them during use, curates its own memory, searches its past conversations, and builds a deepening model of who you are across sessions. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that hibernates when idle — and talk to it from Telegram or the terminal while it works on a cloud VM.

Use any model you want — 27 provider plugins cover OpenRouter, OpenAI, Anthropic, Gemini, xAI, DeepSeek, Ollama, Bedrock, and your own endpoint. Switch with `alvarez model` — no code changes, no lock-in.

<table>
<tr><td><b>Two terminal UIs</b></td><td>A default CLI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output — plus a full-screen TUI (<code>alvarez --tui</code>, see <a href="ui-tui/README.md">ui-tui</a>).</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. Pluggable memory backends — 8 providers, including <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling and mem0. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Telegram and the terminal</b></td><td>A Telegram gateway with voice-memo transcription (local faster-whisper by default; OpenAI or Groq optional), plus webhook and API adapters. The platform layer is a plugin architecture — see <a href="gateway/platforms/ADDING_A_PLATFORM.md">Adding a Platform</a> to bring your own.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with a blueprint catalog. Daily reports, nightly backups, weekly audits — described in natural language, running unattended, delivered to Telegram or the terminal.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Six terminal backends — local, Docker, SSH, Singularity, Modal, and Daytona. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions.</td></tr>
<tr><td><b>Skills and plugins</b></td><td>72 built-in skills and 101 more in <a href="optional-skills">optional-skills</a>. Plugins for model providers (27), memory backends (8), web search (8), and browsers.</td></tr>
<tr><td><b>Speaks the protocols</b></td><td>MCP client <i>and</i> server (<code>alvarez mcp serve</code> exposes your conversations over MCP), ACP server for editors like Zed (<code>alvarez acp</code>), and an OpenAI-compatible proxy (<code>alvarez proxy</code>).</td></tr>
</table>

---

## Quick Install

### Linux, macOS, WSL2

```bash
git clone https://github.com/alvarez-agent/alvarez-agent.git
cd alvarez-agent
bash scripts/install.sh
```

The installer clones this checkout into the managed install at `~/.alvarez/alvarez-agent` and points it at your origin — keep your clone for development or delete it afterwards. It manages its own copies of uv, Python 3.11, and Node.js; nothing is installed globally.

Prefer a one-liner? Piped mode clones from GitHub instead of a local checkout:

```bash
curl -LsSf https://raw.githubusercontent.com/alvarez-agent/alvarez-agent/main/scripts/install.sh | bash
```

### Android (Termux)

Use the same clone-and-install commands as Linux. The installer detects Termux and switches to `pkg`-provided Python with a curated `.[termux]` dependency set (pinned in [constraints-termux.txt](constraints-termux.txt)) — the full `.[all]` extra pulls voice dependencies that don't build on Android.

### Windows (native, PowerShell)

Native Windows runs Alvarez without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux path above works there too.

```powershell
git clone https://github.com/alvarez-agent/alvarez-agent.git
cd alvarez-agent
scripts\install.ps1
```

The installer sets up everything under `%LOCALAPPDATA%\alvarez`: uv, Python 3.11, Node.js, ripgrep, and ffmpeg. If you have Git installed it uses that; otherwise it downloads a portable Git (PortableGit, unpacked inside the install directory — no admin rights, completely isolated from any system Git) so Alvarez can run shell commands through its bundled Git Bash.

### After installation

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
alvarez             # start chatting!
```

---

## Other ways to run

**Docker** — builds the image locally and runs the gateway plus the dashboard (bound to localhost), with state mounted from `~/.alvarez`:

```bash
ALVAREZ_UID=$(id -u) ALVAREZ_GID=$(id -g) docker compose up -d --build
```

To lock down what a containerized agent can reach on the network, see [network egress isolation](docs/security/network-egress-isolation.md).

**Nix** — the [flake](flake.nix) ships package variants (`default`/`full`, `minimal`, `tui`, `web`, `desktop`), a dev shell, and a NixOS module:

```bash
nix run .            # from a checkout — or: nix run .#minimal
nix develop          # dev shell (direnv users get it automatically via .envrc)
```

For declarative deployment, the NixOS module is `services.alvarez-agent` (see [nix/](nix)).

---

## Getting Started

```bash
alvarez              # Interactive CLI — start a conversation
alvarez --tui        # Full-screen terminal UI
alvarez setup        # Setup wizard — model, keys, tools, gateway in one pass
alvarez model        # Choose your LLM provider and model
alvarez gateway      # Start the messaging gateway (Telegram)
alvarez doctor       # Diagnose any issues
```

### Beyond chat

A sampling of the roughly 50 subcommands:

```bash
alvarez skills       # Browse and install skills (72 built-in, 101 optional)
alvarez cron         # Scheduled automations in natural language
alvarez kanban       # Agent task board (see also: alvarez project)
alvarez mcp          # Connect MCP servers — or expose Alvarez as one (mcp serve)
alvarez acp          # Run as an ACP server for editors like Zed
alvarez proxy        # OpenAI-compatible proxy over OAuth providers
alvarez profile      # Run multiple isolated instances side by side
alvarez security     # Supply-chain audit (OSV.dev) of the venv, plugins, MCP servers
alvarez soul         # Edit the SOUL.md persona
alvarez backup       # Back up your Alvarez home (restore with: alvarez import)
```

Run `alvarez --help` for the full list. CLI approval prompts are localized into 16 languages.

---

## CLI vs Messaging Quick Reference

Alvarez has two entry points: start the terminal UI with `alvarez`, or run the gateway and talk to it from Telegram. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action                         | CLI                                           | Messaging platforms                                                              |
| ------------------------------ | ---------------------------------------------- | -------------------------------------------------------------------------------- |
| Start chatting                 | `alvarez`                                      | Run `alvarez gateway setup` + `alvarez gateway start`, then send the bot a message |
| Start fresh conversation       | `/new` or `/reset`                            | `/new` or `/reset`                                                               |
| Change model                   | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| Set a mood                     | `/mood [name]`                                | `/mood [name]`                                                                   |
| Retry or undo the last turn    | `/retry`, `/undo`                             | `/retry`, `/undo`                                                                |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]`                                        |
| Browse skills                  | `/skills` or `/<skill-name>`                  | `/<skill-name>`                                                                  |
| Interrupt current work         | `Ctrl+C` or send a new message                | `/stop` or send a new message                                                    |
| Platform-specific status       | `/platforms`                                  | `/status`, `/sethome`                                                            |

For everything else: `alvarez --help` in the shell, `/help` inside any conversation.

---

## Configuration

`alvarez setup` walks through everything interactively; `alvarez config set` changes individual values. The full reference is in the annotated examples: [.env.example](.env.example) for environment variables and [cli-config.yaml.example](cli-config.yaml.example) for YAML config keys.

---

## Updating

`alvarez update` is disabled in this fork — there's no release channel yet. Update by pulling the managed checkout and re-running the installer:

```bash
cd ~/.alvarez/alvarez-agent
git pull
bash scripts/install.sh
```

---

## Migrating from OpenClaw

If you're coming from OpenClaw, Alvarez can import your settings, memories, skills, and API keys. The setup wizard (`alvarez setup`) detects `~/.openclaw` automatically and offers to migrate; you can also run it anytime:

```bash
alvarez claw migrate              # Interactive migration (full preset)
alvarez claw migrate --dry-run    # Preview what would be migrated
alvarez claw migrate --preset user-data   # Migrate without secrets
alvarez claw migrate --overwrite  # Overwrite existing conflicts
```

It imports SOUL.md, memories, skills, command allowlists, messaging settings, and allowlisted API keys — see `alvarez claw migrate --help` for details, or use the `openclaw-migration` skill for an agent-guided migration.

---

## Security

[SECURITY.md](SECURITY.md) covers the trust model and the one load-bearing security boundary (terminal execution), plus how to report vulnerabilities. For containerized deployments, [network egress isolation](docs/security/network-egress-isolation.md) shows how to limit what the agent can reach. Audit your install's supply chain anytime with `alvarez security`.

---

## Documentation

Architecture and design philosophy live in [AGENTS.md](AGENTS.md); the contributor guide is [CONTRIBUTING.md](CONTRIBUTING.md). Topic docs — gateway session lifecycle, Docker hardening, plugin extension points, and more — are indexed in [docs/](docs/README.md).

---

## Troubleshooting

### Windows Defender or antivirus flags `uv.exe` as malware

If your antivirus quarantines `uv.exe` from `%LOCALAPPDATA%\alvarez\bin`, this is a **false positive**: the file is Astral's [uv](https://github.com/astral-sh/uv), the Python package manager Alvarez bundles. ML-based engines commonly flag unsigned Rust binaries that download packages — see the upstream reports: [astral-sh/uv#13553](https://github.com/astral-sh/uv/issues/13553), [astral-sh/uv#15011](https://github.com/astral-sh/uv/issues/15011), [astral-sh/uv#10079](https://github.com/astral-sh/uv/issues/10079).

To whitelist it, exclude the **folder**, not the file hash — Alvarez updates uv and the hash changes every version. For Windows Defender (PowerShell as Admin):

```powershell
Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\alvarez\bin"
```

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and PR process.

Quick start for contributors — use the standard installer, then work from the
full git checkout it creates at `$ALVAREZ_HOME/alvarez-agent` (usually
`~/.alvarez/alvarez-agent`). This matches the layout used by the managed venv,
lazy dependencies, gateway, and docs tooling.

```bash
git clone https://github.com/alvarez-agent/alvarez-agent.git
cd alvarez-agent
bash scripts/install.sh
cd "${ALVAREZ_HOME:-$HOME/.alvarez}/alvarez-agent"
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

Manual clone fallback (for throwaway clones/CI where you intentionally do not
want the managed install layout):

Create the venv outside the cloned source tree — a venv inside the directory
the agent operates from can be wiped by a relative-path command the agent runs
against its own checkout, destroying the running runtime mid-session.

```bash
git clone https://github.com/alvarez-agent/alvarez-agent.git
cd alvarez-agent
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv ~/.alvarez/venvs/alvarez-dev --python 3.11
source ~/.alvarez/venvs/alvarez-dev/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

---

## Community

- 📚 [Skills Hub](https://agentskills.io)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server for Alvarez and other MCP hosts, with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [AlvarezClaw](https://github.com/AaronWong1999/alvarezclaw) — Community WeChat bridge: Run Alvarez Agent and OpenClaw on the same WeChat account.

---

## License

MIT — see [LICENSE](LICENSE).

Forked from hermes-agent, originally built by Nous Research.
