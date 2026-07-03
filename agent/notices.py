"""Driver-agnostic out-of-band agent notices.

The agent fires these via ``AIAgent.notice_callback`` (and clears them via
``notice_clear_callback``); each driver renders them its own way — the TUI as
a status-bar override, the CLI as a console line, messaging platforms as a
plain line. Extracted from the deleted credits tracker (hermes separation,
2026-07-03): the credits producers are gone, but the spine and this type are
generic and stay for future producers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AgentNotice:
    text: str
    level: str = "info"            # info | warn | error | success
    kind: str = "sticky"           # sticky | ttl
    ttl_ms: Optional[int] = None   # honored only when kind == "ttl"
    key: Optional[str] = None      # dedupe / fired-once-latch / clear key
    id: Optional[str] = None
