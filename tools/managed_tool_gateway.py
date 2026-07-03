"""Managed-tool gateway shims — the hosted gateway was removed (hermes separation, 2026-07-03).

ponytail: dead-None/False shims. ~20 tool modules (web, tts, transcription,
terminal/modal, browser, image…) resolve their backend through these helpers
and fall back to bring-your-own-key paths when the gateway is absent. Keeping
the API surface as inert stubs is a far smaller diff than editing every call
site; delete the module (and all callers) only if the managed path is never
coming back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ManagedToolGatewayConfig:
    vendor: str
    gateway_origin: str
    nous_user_token: str
    managed_mode: bool


def build_vendor_gateway_url(vendor: str) -> str:
    """Gateway removed — no origin to build."""
    return ""


def peek_nous_access_token() -> Optional[str]:
    """Gateway removed — there is never a token."""
    return None


def read_nous_access_token() -> Optional[str]:
    """Gateway removed — there is never a token."""
    return None


def resolve_managed_tool_gateway(
    vendor: str,
    gateway_builder: Optional[Callable[[str], str]] = None,
    token_reader: Optional[Callable[[], Optional[str]]] = None,
) -> Optional[ManagedToolGatewayConfig]:
    """Gateway removed — managed config never resolves."""
    return None


def is_managed_tool_gateway_ready(
    vendor: str,
    gateway_builder: Optional[Callable[[str], str]] = None,
    token_reader: Optional[Callable[[], Optional[str]]] = None,
) -> bool:
    """Gateway removed — never ready."""
    return False
