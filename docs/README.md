# Alvarez Agent documentation

Repo-level references:

- [AGENTS.md](../AGENTS.md) — architecture and design philosophy
- [CONTRIBUTING.md](../CONTRIBUTING.md) — development setup, code style, PR process
- [SECURITY.md](../SECURITY.md) — trust model and vulnerability reporting

Topic docs in this directory:

- [session-lifecycle.md](session-lifecycle.md) — gateway session model and lifecycle
- [security/network-egress-isolation.md](security/network-egress-isolation.md) — Docker network egress isolation
- [kanban/multi-gateway.md](kanban/multi-gateway.md) — running multiple gateway processes
- [middleware/README.md](middleware/README.md) — plugin middleware contract (request/execution rewriting)
- [observability/README.md](observability/README.md) — plugin observer-hook contract (telemetry)
- [relay-connector-contract.md](relay-connector-contract.md) — experimental gateway ↔ connector protocol

Elsewhere in the repo:

- [ui-tui/README.md](../ui-tui/README.md) — React + Ink terminal UI architecture
- [gateway/platforms/ADDING_A_PLATFORM.md](../gateway/platforms/ADDING_A_PLATFORM.md) — adding a messaging platform
- [.env.example](../.env.example) and [cli-config.yaml.example](../cli-config.yaml.example) — configuration reference
