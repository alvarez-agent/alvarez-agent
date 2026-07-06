# Rebrand + Strip-Down — Notes & First-Pass Plan

Informal working doc. Not a spec, just enough to start cutting.

## Change log

Running record of refactor changes as they land. Newest first.

### 2026-07-05 — CI cleanup: catch up the stale test suite (Workstream B)

Finished the strip-down test catch-up the earlier "tests: catch up" commit
started. ~40 files triaged; each failure was run and confirmed before acting
(delete only when the code/dir under test is gone; update the assertion when
surviving code just lost Nous branding; skip when the feature is disabled).

- **Deleted (dir/feature gone):** desktop/electron tests
  (`test_desktop_electron_pin`, `test_desktop_mac_entitlements`,
  `test_assistant_ui_tap_compat`), `test_release_acp_registry`
  (acp_registry + scripts/release.py gone), `test_gateway_platform_gating`
  (matrix/discord/slack), `test_windows_native_docs` (website/ docs). Plus
  targeted single-test/class deletions for removed Nous surfaces (portal
  pricing, credits, self-provision device-code, provider tables/profiles,
  vision backend, prompt-cache portal path) and the removed docs-site
  blueprint generator.
- **Updated (surviving code, stale assertion):** rebrand fixes — banner
  `NOUS ALVAREZ`→`ALVAREZ`, computer_use session-id prefix length
  (`hermes-`=7 → `alvarez-`=8), gateway-restart legacy `hermes` case,
  OpenRouter attribution `HTTP-Referer`→`X-Title`, managed tool-gateway
  message, turn-retry field set, xurl skill test (dropped deleted docs
  mirror), packaging-metadata (dropped removed `web` extra), provider-dir
  floor 28→27 (removed empty `plugins/model-providers/nous/`), setup gateway
  tests (removed matrix pre-config → bluebubbles).
- **Skipped (feature disabled, not removed):** the remaining `alvarez update`
  / passive-update-check tests, via the same `@update_disabled` marker the
  earlier catch-up used (`test_cmd_update_docker`, `test_update_autostash`,
  `test_update_check`, `test_update_concurrent_quarantine`).
- **Source fixes (not just tests):** pruned 4 phantom entries
  (`dashboard`, `serve`, `whatsapp`, `whatsapp-cloud`) from
  `main.py:_BUILTIN_SUBCOMMANDS` — the tests were correctly flagging stale
  source.

**Surfaced, NOT papered over — genuine source bugs from an incomplete Nous
removal (16 tests left failing on purpose):**
- `agent/credential_pool.py:216` — `PooledCredential.runtime_api_key` (nous
  branch) calls the deleted `alvarez_cli.auth._nous_invoke_jwt_is_usable`.
  Fails 2 tests in `test_credential_pool.py`.
- `alvarez_cli.auth.resolve_nous_access_token` is imported by live code
  (`gateway/relay/__init__.py:492`, `alvarez_cli/gateway_enroll.py:148,184`,
  `plugins/cron_providers/chronos/_nas_client.py:45`) but **defined nowhere**
  — lazy imports inside function bodies, so it only breaks when called
  (relay self-provision swallows the ImportError → silent no-op). Fails 3
  tests in `test_relay_multiplatform.py` + 11 in `test_self_provision.py`.
  Decision needed (Ken): finish removing the Nous provisioning path (relay
  self-provision, gateway enroll, chronos NAS auth + these tests) OR restore
  the two missing symbols in `auth.py`.
- Minor: banner constants half-renamed in source — `_OFFICIAL_REPO_CANONICAL`
  → alvarez, `_UPSTREAM_REPO_URL` (`banner.py:122`) still `hermes-agent`.

Pre-existing order-dependent flakes left as-is (all fail on a clean
`784eec906` too, not part of this cleanup):
`test_projects_rpc.py::test_discover_repos_from_full_history`,
`test_subagent_child_mirror.py::test_prompt_submit_rejected_while_child_run_active`,
and `test_api_key_providers.py::TestZaiEndpointAutoDetect::test_probe_success_returns_detected_url`
(passes in isolation; a preceding `tests/agent/*` test leaves a cached zai
endpoint — confirmed pre-existing on base).

Verification: the ~40 touched files run together give 833 passed / 28 skipped
/ 3 failed, where the 3 are the 2 credential_pool REAL_BUGs above + the zai
flake. The relay REAL_BUG pair adds 14 more (3 + 11), untouched.

### 2026-07-05 — CI cleanup: prune dead workflow jobs (Workstream A)

CI was red across the board since the initial public commit — leftover from
the Phase 3 strip-down, not from recent feature work. First pass removes CI
workflow jobs that reference deleted dirs (`apps/`, `web/`, `docs-site/`,
`website/`):

- **`typecheck.yml`**: matrix reduced `[ui-tui, web, apps/bootstrap-installer,
  apps/desktop, apps/shared]` → `[ui-tui]` (only survivor); dropped the
  "Build desktop app" job (`npm run --prefix apps/desktop build` — dir gone).
- **`docs-site-checks.yml`**: deleted (built the removed Docusaurus site);
  removed its `docs-site` job from `ci.yml` and the `- docs-site` entry in
  `all-checks-pass` `needs:`.
- **Dead website-docs pipeline deleted** (`deploy-site.yml`, `skills-index.yml`,
  `skills-index-freshness.yml`): all three built/deployed/watched the removed
  `website/` Docusaurus site and were hard-gated to `NousResearch/hermes-agent`
  — they only ever skip in this fork.
- **`osv-scanner.yml`**: dropped the `--lockfile=website/package-lock.json` arg
  (file gone). The scanner core already passed; its remaining red is unrelated
  (`Upload to code-scanning` needs GitHub Advanced Security enabled on the repo
  — a settings issue, not a code one).

### 2026-07-04 — personalities → moods, Alvarez mood set

SOUL.md is the identity now; the overlays are *moods* — registers layered on
top of it (ephemeral_system_prompt composes additively with the cached SOUL.md
prompt, so no loader changes). Renames: `agent.personalities` → `agent.moods`,
`display.personality` → `display.mood`, `/personality` → `/mood` (CLI routing +
kaomoji handler, gateway async handler, TUI server config.set/getter/session
key/helpers, ui-tui session.ts + slashParity, locales `personality:` → `mood:`
in all 16 files with en fully rewritten). Migration v33→34 renames the keys,
entries preserved. The 14 stock upstream personas (catgirl, pirate, uwu…) are
replaced by 8 Alvarez moods shipped in DEFAULT_CONFIG.agent.moods — creative
🎨, ceo 💼, curious 🔬, founder 🚀, focused 🎯, mentor 🌱, investigative 🔍,
zen 🍃 — dict
format, single source of truth (cli.py's inline defaults now import from it;
upstream's top-level DEFAULT_CONFIG["personalities"] was dead — it sat outside
the agent section). Ken's live config: migrated, stock block dropped (all 14
matched stock, none custom), active 'creative' carried over to the new creative
mood prompt. Tests: test_personality_none.py → test_mood_none.py, new
test_mood_migration.py; ~780 pass, only pre-existing order-dependent flakes
remain (test_projects_rpc, test_subagent_child_mirror — fail on clean tree
too). ui-tui rebuilt.

### 2026-07-03 — hypercrush skin: readable dim text

`banner_dim`/`session_border` #55507A (~33% luminance, then dimmed again by
banner.py's `[dim]` markup) → #9A94C9 (~58%) — same treatment sunfire got.
Fixes unreadable toolset/category labels and the session line in the banner.

### 2026-07-03 — test suite caught up with the platform strip-down (12 failures)

Tests still assuming the multi-platform world, sorted per test:

- **Deleted** (covered removed platforms): `test_tools_config.py` —
  homeassistant-platform, whatsapp-includes-web, feishu-doc-and-drive tests;
  `test_setup_openclaw_migration.py` — WHATSAPP_ENABLED gateway summary test.
- **Updated to Telegram-only expectations**: `TestPlatformToolsetConsistency`
  now checks the surviving platforms ({cli, telegram, webhook, api_server,
  cron} — the PLATFORMS registry intentionally still lists stripped platforms
  for legacy-config migration) and asserts `alvarez-gateway` includes exactly
  `{alvarez-telegram, alvarez-webhook}`; the openclaw gateway-summary test now
  asserts a leftover DISCORD_BOT_TOKEN does *not* resurface Discord.
- **Skipped, not deleted** (`test_cmd_update.py`, `test_update_yes_flag.py`,
  17 tests): they fail because `alvarez update` is disabled (exit 1, no
  upstream channel), not because of platforms. Marked skip with a pointer at
  cmd_update's re-enable note; new `test_update_is_disabled_in_fork` covers
  the disabled behavior itself.
- **Fixed two order-dependent tests** (failed only in full-suite runs):
  `test_goals.py` fixture now pins `alvarez_state.DEFAULT_DB_PATH` (frozen at
  import time, so goals tests had been writing into the real
  ~/.alvarez/state.db — leaked rows cleaned out); the tools_config
  composite-recovery test's fake composite now lists `read_terminal`/
  `close_terminal`, which importing model_tools adds to the `terminal`
  toolset.

### 2026-07-03 — config migration scrubs retired toolsets ("Unknown toolsets: messaging")

Old/imported configs still list toolsets removed in the strip-down
(`messaging`, plus the `hermes-discord/-slack/-signal/-whatsapp/-qqbot/
-homeassistant` platform toolsets), which warned "Unknown toolsets" at every
startup. New `REMOVED_TOOLSETS` in toolsets.py; migrate_config() (always-run
section, alvarez_cli/config.py) drops those names from `platform_toolsets`,
deleting a platform entry entirely when all of its toolsets were retired
(user-set empty lists are left alone). `_config_version` bumped 32 → 33 so
existing installs migrate on next update/startup. Verified on Ken's live
config (backup taken): scrub is idempotent, zero invalid toolsets remain.
Known issue: 10 pre-existing test failures from strip-down leftovers
(tests still referencing removed platforms) — unrelated, tracked separately.

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
