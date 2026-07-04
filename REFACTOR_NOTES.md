# Rebrand + Strip-Down — Notes & First-Pass Plan

Informal working doc. Not a spec, just enough to start cutting.

## Change log

Running record of refactor changes as they land. Newest first.

### 2026-07-03 — Telegram auto-setup gated on onboarding URL + magenta prompts

Field-test fixes from Ken's setup run. (1) The setup wizard offered "Automatic
(recommended)" Telegram QR onboarding, but this fork has no hosted onboarding
service (`DEFAULT_API_URL = ""` in alvarez_cli/telegram_managed_bot.py), so it
always failed with a misleading "check your network". Added
`onboarding_service_configured()` to telegram_managed_bot.py; setup.py
(`_telegram_auto_available()`) and gateway.py's channel flow now skip the
automatic option entirely unless `TELEGRAM_ONBOARDING_URL` is set, and
`auto_setup_telegram_bot_result()` prints an accurate "no service configured"
message if reached anyway. (2) Interactive prompt/header color switched from
yellow to brand magenta: `prompt`/`prompt_yes_no`/`prompt_choice` fallback in
setup.py, `prompt`/`print_header` in cli_output.py. Warnings stay yellow.

### 2026-07-03 — `alvarez soul`: personality swap command

New `alvarez soul` subcommand (alvarez_cli/soul.py, wired in main.py next to
`pets`, added to `_BUILTIN_SUBCOMMANDS`). Manages named SOUL.md variants in
`$ALVAREZ_HOME/souls/*.md`: `show` (default), `list` (* = active), `save
<name> [--force]`, `use <name>`, `delete <name>`. `use` auto-stashes an
unsaved live SOUL.md to `souls/_previous.md` so nothing is lost. No loader
changes needed — SOUL.md is already re-read every message, so switches are
immediate. Tests: tests/alvarez_cli/test_soul.py (5, passing).

### 2026-07-03 — change-list round 1: full Nous/hermes separation + field-test fixes

Executed `mailbox/Alvarez Change List.md` (projects wiki). Version is now
**v0.1.0 (2026.7.3)** (`alvarez_cli/__init__.py`, pyproject.toml).

**Field-test fixes (items 1, 2):**
- Banner/TUI show the real provider after the model name instead of the
  hard-coded "Nous Research" (banner.py provider_str; branding.tsx uses
  `info.provider`, already in the tui_gateway payload — added to SessionInfo).
  Taglines: "Alvarez · wire in, dive deep"; `⚕ NOUS ALVAREZ` → `ALVAREZ`.
- sunfire skin: `banner_dim`/`session_border` #7A3511 (~28% luminance,
  unreadable + further dimmed by Rich `[dim]`) → #CE7B3E (~60%), same
  treatment the gold theme's muted got; `status_bar_dim` → #C08558.

**Full separation (items 3, 4)** — everything Nous/hermes deleted except
three externally-controlled strings: the Hermes model-ID regex
(model_switch.py), vLLM `--tool-call-parser hermes`, and `hermes-0day`
(literal IOC in mcp_security.py scanning user configs for a real June 2026
campaign — renaming breaks detection). Deleted:
- Modules: agent/{account_usage Nous half, credits_tracker, billing_view,
  portal_tags, nous_rate_guard}, alvarez_cli/{nous_account, nous_billing,
  nous_auth_keepalive, nous_subscription portal half, diagnostics_upload,
  portal_cli}, plugins/model-providers/nous/, acp_registry/,
  packaging/homebrew/, scripts/{release,contributor_audit}.py,
  alvarez-already-has-routines.md.
- Features: /credits + /billing (CLI ~750 lines, gateway handlers, TUI
  overlay + slash commands + billing RPCs ~250 lines, command registry,
  16 locale files), Nous Portal OAuth/JWT/agent-key stack in auth.py,
  Nous auxiliary/fallback client (−1,093 lines in auxiliary_client.py),
  Nous entitlement/401/rate-guard retry paths in conversation_loop,
  credits notices spine producers (generic AgentNotice type moved to new
  agent/notices.py), portal model recommendations (models.py), managed
  Nous tool gateway (tool_backend_helpers + managed_tool_gateway are now
  dead-False/None shims — ~20 tool modules degrade to BYO keys; delete the
  shims only if a managed backend returns), Nous rows in the tools picker,
  `alvarez portal` + `alvarez debug share --nous` commands, HERMES_HOME /
  populated-`~/.hermes` fallback (alvarez_constants — ALVAREZ_HOME only).
- **`alvarez update` + the update check are disabled** (early returns with
  re-enable notes): every download path pointed at NousResearch/hermes-agent
  and would have overwritten the fork. The `upstream` git remote is removed.
- All nousresearch.com / github.com/NousResearch / dead docs-site URLs
  swept from code, help text, README/CONTRIBUTING/AGENTS/SECURITY (model
  slugs like `nousresearch/hermes-4-405b` in godmode kept — provider IDs).
- skills/autonomous-ai-agents/alvarez-agent rewritten 1,111 → 695 lines
  against the trimmed reality (it's the agent's own self-reference).

**Item 5:** `/alvarez-agent` verified — it's the bundled self-doc skill
surfaced as a slash command (renamed from upstream's hermes-agent skill).
Repo is not on GitHub; its only remote was upstream, now removed.

**Item 6 (~19K first-message tokens):** `~/.alvarez/config.yaml` listed the
stale `hermes-cli` toolset → fixed to `alvarez-cli`. Measured from a neutral
cwd: 14.9 KB system prompt + 56.6 KB tool schemas (34 tools) ≈ 18.3K tokens.
Biggest per-toolset schema costs: delegation 7.5 KB, terminal 6.8 KB,
browser 6.2 KB, session_search 5.8 KB, file 5.8 KB, skills 5.2 KB,
computer_use 5.1 KB. Further trim = `disabled_toolsets` in config (Ken's
call; numbers in the mailbox answer).

**Verification:** collection gate 29,919 tests / 0 errors; touched-area
suites green in per-file runs (~1,100 python tests + 255 auxiliary);
`tsc --noEmit` clean; vitest 1,074 passed / 3 pre-existing failures
(2 statusRule + 1 virtualHeights, all fail on untouched files at HEAD);
`alvarez --version` → v0.1.0 (2026.7.3); prompt-size runs clean.
Deliberate skips: setup.py's inert `managed_by_nous` feature gates stay
(always-False against the neutered nous_subscription API); stale comments
mentioning removed Nous rows in tools_config; `NousSubscriptionFeatures`
class names kept to avoid a rename cascade — all debt for the stale-CLI
cleanup pass.

### 2026-07-02 — field-test fixes round 2: hero art, update-nag cache, token cost

- New hero graphic: braindance visor (braille art, "wire in, dive deep")
  replaces the caduceus in ALVAREZ_CADUCEUS (banner.py, cli.py, gold) and
  as hypercrush's banner_hero (magenta/violet).
- "422 commits behind" persisted after the remote rename because
  check_for_updates() caches for 6h in <home>/.update_check — cleared both
  homes' caches; check now returns None.
- 37K tokens for "hi" explained via `alvarez prompt-size`: 71.6KB was the
  repo's own AGENTS.md injected as cwd context (launched from inside the
  repo — launch elsewhere and it disappears); 56.6KB is 34 tool schemas
  (trim default toolsets for the pi profile); only ~18KB is identity.

### 2026-07-02 — field-test fixes: ALVAREZ wordmark, upstream remote

First launch of the base surfaced rename leftovers the grep pass couldn't
catch:
- The TUI banner still read HERMES-AGENT — it's ANSI-Shadow ASCII *art*
  (drawn letters), immune to find/replace. `ALVAREZ_AGENT_LOGO` in
  `alvarez_cli/banner.py` + `cli.py` now spells ALVAREZ (gold fallback);
  the `hypercrush` skin got its own magenta→violet wordmark.
- The "N commits behind — run alvarez update" nag counted against
  `origin/main`, which was still NousResearch/hermes-agent; `alvarez
  update` would have pulled upstream hermes over the fork. Remote renamed
  `origin` → `upstream` (fetch deliberately, never auto-track).
- User-home split: `~/.alvarez` created with only config.yaml + .env
  copied from `~/.hermes` (keys/model carry over; plugins, skills,
  sessions stay behind). The legacy fallback now never fires on this
  machine. Note: MCP servers and memory-provider settings ride in
  config.yaml — prune there if the base should start leaner.

### 2026-07-02 — Phase 3: pi-agent strip-down (~650k lines deleted)

Goal per Ken: keep the critical features that make Alvarez work, trim to a
minimal "pi agent". Profile: **CLI/TUI + Telegram, no GUI apps, no research
tooling, essential plugins only.**

Deleted:
- Research/training tooling (batch_runner, trajectory_compressor,
  mini_swe_runner, toolset_distributions, datagen configs), docs website,
  infographic, README translations
- Electron desktop (apps/), web dashboard (web/ + alvarez_cli/web_server.py
  + dashboard_auth + dashboard/serve CLI commands + pty bridges + [web] extra)
- 19 messaging platforms (kept telegram): plugin dirs, built-in
  signal/whatsapp/weixin/bluebubbles/qqbot/yuanbao/msgraph adapters, send
  paths, setup wizards, env-override config blocks, whatsapp/whatsapp-cloud
  CLI commands, platform tool modules + toolsets + pyproject extras
- Plugins: image_gen, video_gen, kanban-dashboard, spotify, google_meet,
  observability, context_engine, teams_pipeline, achievements
- ~165 test files deleted + 64 surgically edited to match

Kept deliberately (the load-bearing list):
- **plugins/web (web search providers)** — initially cut by mistake
  (misread as dashboard code), restored; a pi agent needs web search
- **Core kanban** (alvarez_cli/kanban*, tools/kanban_tools,
  gateway/kanban_watchers) — the agent's task system; only the dashboard
  UI plugin died
- **Platform enum intact** in gateway/config.py — 87 comparison sites
  across authz/session/slash-commands reference members; dead labels are
  the cheapest shim (ponytail: delete later only if it ever matters)
- **whatsapp_identity.py** — generic authz allowlist parsing
- **api_server + webhook adapters** — infrastructure, not messaging
- **agent/pet** (TUI sprite pet), **image/video gen core registries**
  (providers gone; degrade gracefully), **locales/** (runtime i18n)
- Learning loop untouched: memory, skills, session search, cron

Verified: full-suite collection clean (30,180 tests, 0 errors, baseline had
114); per-file-isolated run introduces zero new failures vs baseline;
251/251 on web/config/registry slices; gateway config loads telegram-only;
alvarez CLI + gateway status + TUI skins + run_agent all work; TUI tsc
clean; npm lockfile regenerated (828 packages dropped).

Known debt: `alvarez update` web-UI build steps may reference removed
paths (unverified); Platform enum + authz code retain dead platform
branches by design.

### 2026-07-02 — Phase 1: hermes → alvarez mechanical rebrand

Name locked in: **Alvarez** (nod to Judy Alvarez, Cyberpunk 2077 — surname
only, no character likeness). `alvarez` + `alvarez-agent` confirmed free on
PyPI and npm at decision time; grab them before publishing.

On branch `rebrand-alvarez`: 828 tracked paths renamed, case-aware content
replace across 3,534 files, lockfiles regenerated (npm + uv). CLI
entrypoints are now `alvarez` / `alvarez-agent` / `alvarez-acp`; Electron is
`com.nousresearch.alvarez` / product "Alvarez".

Deliberately KEPT as "hermes" (do not re-rename):
- Hermes model IDs & families (Hermes-3/4, Nous Hermes, `nous/hermes-test`)
  and the model-detection regex in `alvarez_cli/model_switch.py`
- vLLM's `--tool-call-parser hermes` (external flag value)
- `hermes-0day` (historical incident name), `nous-hermes-agent` (Portal
  product id)
- Live URLs: `hermes-agent.nousresearch.com`, `github.com/NousResearch/
  hermes-agent` — re-point when the new domain/repo exists (grep for
  `nousresearch.com` then)

Legacy compat (in `alvarez_constants.py`): `HERMES_HOME` env still honored;
a populated `~/.hermes` is reused when `~/.alvarez` doesn't exist — existing
installs keep their data with no migration.

Known upgrade caveats:
- Desktop/web localStorage keys renamed → theme/font prefs reset once.
- Hindsight memory: installs that never persisted `bank_id` in config now
  default to bank "alvarez"; if memory looks empty, set `bank_id: hermes`.

Verified: `run_agent.py --help` + `alvarez --version` work; web/desktop/
ui-tui tsc clean; skin + banner + model-detection suites pass; desktop
52/52 theme tests; ui-tui 1,098 pass (3 failures pre-exist on baseline);
web dashboard boots as "Alvarez Agent". Full Python suite: 262 failures vs
261 on the pre-rename baseline commit — same files, pass in isolation;
pre-existing parallel-run flakiness, not rename fallout.

### 2026-07-02 — Phase 2: six new themes on all three surfaces

Discovery: the theme *mechanism* already existed everywhere (CLI skin engine
→ TUI via gateway `skin.changed`, web preset registry + picker, desktop
preset registry + picker). Phase 2 reduced to adding 6 palettes to 3
registries — no new infrastructure built.

Themes (same names on every surface): `paper` (traditional light),
`graphite` (traditional dark), `hypercrush` (magenta/violet on `#1a1a24`),
`terminal-acid` (green/cyan CRT), `sunfire` (orange/red), `deep-reef`
(teal/violet on navy).

Files changed:
- `alvarez_cli/skin_engine.py` — 6 skins in `_BUILTIN_SKINS`, colors only;
  spinner/branding/banners inherit from `default` via the existing merge.
  Covers CLI + TUI with zero TS changes (`/skin hypercrush` or
  `display.skin` in config.yaml).
- `web/src/themes/presets.ts` + `alvarez_cli/web_server.py`
  (`_BUILTIN_DASHBOARD_THEMES`) — 6 dashboard themes; the two lists must
  stay in sync.
- `apps/desktop/src/themes/presets.ts` — 6 desktop themes; settings picker
  enumerates the registry automatically.

Verified: skins load with inherited branding (33/33 skin-engine tests),
web + desktop `tsc --noEmit` clean, 52/52 desktop theme tests, live check
in the web dashboard (picker shows all 14, Hypercrush bg renders `#1a1a24`).

Skipped (deliberate): hatch/scanline decorative textures and gradient
headers — add if a theme feels flat in use. Existing themes untouched;
pruning old skins belongs with the Phase 1 rebrand.

## Where things stand today

- Monorepo: Python core (`/agent`, 112 files) + Node/TS (`web/`, `apps/desktop/`, `ui-tui/`).
- "Alvarez" shows up ~36k times across ~1000 files. Most of it is low-risk
  (env vars, `~/.alvarez/` paths, package names) — mechanical rename.
  Medium-risk spots: hardcoded `"alvarez"` default agent IDs in memory
  backends, Slack slash-command matching, system-prompt self-reference text,
  Electron `appId`/installer config, CLI entrypoints (`alvarez`, `alvarez-agent`,
  `alvarez-acp`).
- Skills: directory-scanned (`/skills/` + `/plugins/*`), YAML frontmatter
  (`SKILL.md`), no hardcoded IDs elsewhere. Swapping bundled skills should be
  a pure add/delete of directories — this is the easy part.
- Dev servers exist and hot-reload for all three frontends:
  - `web/` → `npm run dev` (Vite)
  - `apps/desktop/` → `npm run dev` (Vite renderer + Electron concurrently)
  - `ui-tui/` → `npm run dev` (tsx --watch)
  - Python core has no hot-reload; restart `python run_agent.py` after edits.
- Full Rust rewrite: not worth it right now. The ML/provider SDK ecosystem
  is Python-first, and the payoff (perf, single binary) doesn't matter much
  for something that's I/O-bound on LLM API calls. Revisit only if there's a
  concrete distribution reason (e.g. single static binary requirement).

## Goal

Rebrand only — keep all existing functionality. Look should go "over the
top" in the Charm Hypercrush direction (see screenshot: bold blocky ASCII
wordmark, neon magenta/purple gradient, angled hatch banner, terminal-native
feel). Needs a **theme system**, not a single new palette:

- 2 traditional themes: one light, one dark
- 4 vibrant themes: neon/gradient, Hypercrush-style

Then, separately: swap out most bundled skills for a different set.

## First-pass plan

### Phase 0 — Scope the name & assets
- Pick the new name, check it's not squatted as an npm/PyPI package name if
  you care about publishing.
- New wordmark/logo, new icon set (replace `apps/desktop/assets/icon.*`).
- Decide on primary neon color pair for the "loud" identity (Hypercrush uses
  magenta → violet gradient over black + blue diagonal hatch).

### Phase 1 — Rebrand mechanics (find/replace, low creativity, high tedium)
1. Central constants: `alvarez_constants.py` (or equivalent) — rename
   `ALVAREZ_HOME` env var, `~/.alvarez/` default path, default agent/bank IDs.
2. `package.json` names/bins across root, `web/`, `apps/desktop/`, `ui-tui/`.
3. CLI console scripts (`alvarez`, `alvarez-agent`, `alvarez-acp`) → new names.
4. Electron `appId`, product name, installer/DMG strings
   (`apps/desktop/package.json` build config).
5. System prompt self-reference text (`system_prompt.py`, `learn_prompt.py`)
   — the agent's own name when it talks about itself.
6. README/docs, domain references, Slack slash-command name check.
7. Grep for leftover `"alvarez"` / `"Alvarez"` string literals as a final pass;
   don't expect one clean regex given ~1000 files, budget a review pass.

Sanity check after this phase: fresh install + `run_agent.py --help` +
each dev server boots without errors.

### Phase 2 — Theme system (the actual design work)
This is new, not just restyling — need a mechanism to switch between 6
themes across web, desktop, and TUI (TUI is more limited — 256-color/ANSI
territory, can't do gradients the same way).

- Define a theme as a small token set: background, surface, primary accent,
  secondary accent, text, muted text, success/error/warn. Keep it flat —
  don't build a full design-token pipeline for 6 themes.
- Web/desktop (CSS): CSS custom properties + a `data-theme` attribute on
  `<html>`, one stylesheet block per theme. No need for a JS theming
  library — this is exactly what CSS variables are for.
- TUI: whatever the current TUI styling approach is (likely chalk/ink
  styles) — map the same token set to ANSI-safe colors, accept less
  gradient fidelity there.
- Vibrant themes: treat as literal reskins of the Hypercrush look —
  black/near-black background, diagonal hatch or scanline texture as an
  optional decorative accent, bold blocky type for headers. Four distinct
  vibes, not four shades of the same neon:
  1. **Hypercrush** (baseline) — magenta → violet gradient, black bg, blue
     hatch accent. The "loud default."
  2. **Terminal Acid** — cyan/electric-green on black, CRT/scanline feel,
     hacker-green energy rather than pink.
  3. **Sunfire** — orange → red gradient on near-black, warm/aggressive,
     reads more "alert/energy" than "cyberpunk."
  4. **Deep Reef** — teal/blue → violet gradient on deep navy (not pure
     black), calmer than the other three but still saturated — the
     "vibrant but not assaulting your eyes at 2am" option.
- Traditional themes: one conventional light (white/near-white bg, dark
  text, restrained accent) and one conventional dark (standard dark-mode
  gray, not neon) — these are the "boring and it's fine" options for people
  who just want to read text.
- Persist theme choice per-user (existing settings/config file, don't invent
  a new storage layer).
- Background: `#1a1a24` (tinted dark indigo-gray, not pure black) — chosen
  over pure black `#000000` per the "background enabled" Hypercrush
  screenshot. Use as the `--bg` token for the dark/vibrant themes.

### Phase 3 — Skill swap
- Bundled skill removal is low-risk: delete directories under `/skills/`
  and unwanted categories under `/plugins/*`.
- Exception to check before deleting: `/plugins/alvarez-achievements` is
  wired into desktop UI — if cut, the UI feature referencing it needs
  removal too, not just the plugin folder.
- Delete matching test directories under `/tests/plugins/` and
  `/tests/tools/` for anything removed (some have hardcoded path strings
  like `/opt/alvarez/bin/alvarez` — will need updating regardless of what
  survives).
- Author new bundled skills last, once the rest of the app boots — no
  reason to design new skills before confirming the host still works.
- Update gateway config wherever it enumerates platforms/skills so it
  doesn't try to init something that's gone.

### Phase 4 — Pass over the whole thing
- Full grep for old name, one more time.
- Boot all three dev servers + Python core, click through each theme,
  confirm skill list matches the new set.
- Regression pass on whatever functionality phase 3 touched (gateway startup
  in particular — it errors if config references a removed platform).

## Order-of-operations note

Rebrand mechanics (Phase 1) and skill swap (Phase 3) are independent —
could be done in parallel by two people, or interleaved in either order.
Theme system (Phase 2) is the one with actual design decisions to make
first (name the 6 palettes concretely) before touching code.
