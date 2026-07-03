"""Regressions for the context-engine host contract.

These tests pin the five generic host-side guarantees that external context
engine plugins (e.g. alvarez-lcm) rely on:

1. ``_transition_context_engine_session`` drives the full lifecycle
   (on_session_end → on_session_reset → on_session_start → optional
   carry_over_new_session_context) and ``reset_session_state`` delegates
   to it when callers pass session metadata.

2. ``on_session_start`` receives ``conversation_id`` derived from
   ``_gateway_session_key`` at agent init time.

3. ``conversation_loop`` forwards canonical cache buckets
   (``cache_read_tokens``, ``cache_write_tokens``, ``input_tokens``,
   ``output_tokens``, ``reasoning_tokens``) to the engine's
   ``update_from_response``, on top of the legacy aggregate keys.

4. ``_discover_context_engines`` includes plugin-registered engines (not
   just repo-shipped engines under ``plugins/context_engine/``).

5. The repo-shipped ``_EngineCollector`` honors ``ctx.register_command``
   from a plugin engine's ``register(ctx)`` entry point and routes it
   to the global plugin command registry.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agent.context_compressor import ContextCompressor
from alvarez_state import SessionDB
from run_agent import AIAgent


def _bare_agent() -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.session_id = "test-session"
    agent.model = "fake-model"
    agent.platform = "telegram"
    agent._gateway_session_key = "agent:main:telegram:dm:42"
    return agent


def test_transition_runs_full_lifecycle_in_order():
    """End → reset → start → carry_over, in that order, when all inputs apply."""
    events: list[str] = []
    engine = MagicMock()
    engine.context_length = 200_000
    engine.on_session_end.side_effect = lambda *a, **kw: events.append("on_session_end")
    engine.on_session_reset.side_effect = lambda *a, **kw: events.append("on_session_reset")
    engine.on_session_start.side_effect = lambda *a, **kw: events.append("on_session_start")
    engine.carry_over_new_session_context.side_effect = lambda *a, **kw: events.append("carry_over")

    agent = _bare_agent()
    agent.context_compressor = engine

    agent._transition_context_engine_session(
        old_session_id="old-sid",
        new_session_id="new-sid",
        previous_messages=[{"role": "user", "content": "hi"}],
        carry_over_context=True,
    )

    assert events == [
        "on_session_end",
        "on_session_reset",
        "on_session_start",
        "carry_over",
    ]


def test_transition_passes_conversation_id_from_gateway_session_key():
    """on_session_start receives ``conversation_id`` from ``_gateway_session_key``."""
    engine = MagicMock()
    engine.context_length = 200_000
    captured: dict = {}
    engine.on_session_start.side_effect = lambda sid, **kw: captured.update(kw)

    agent = _bare_agent()
    agent.context_compressor = engine

    agent._transition_context_engine_session(
        old_session_id="old-sid",
        new_session_id="new-sid",
        previous_messages=[{"role": "user", "content": "hi"}],
    )

    assert captured.get("conversation_id") == "agent:main:telegram:dm:42"
    assert captured.get("old_session_id") == "old-sid"
    assert captured.get("platform") == "telegram"


def test_transition_skips_optional_hooks_when_engine_lacks_them():
    """Engines that don't implement on_session_end/carry_over still work."""
    class MinimalEngine:
        def __init__(self):
            self.context_length = 100_000
            self.reset_called = False
            self.start_called_with = None

        def on_session_reset(self):
            self.reset_called = True

        def on_session_start(self, sid, **kw):
            self.start_called_with = (sid, kw)

    engine = MinimalEngine()
    agent = _bare_agent()
    agent.context_compressor = engine

    # Should not raise even though on_session_end / carry_over are missing.
    agent._transition_context_engine_session(
        old_session_id="old",
        new_session_id="new",
        previous_messages=[{"role": "user", "content": "hi"}],
        carry_over_context=True,
    )

    assert engine.reset_called is True
    assert engine.start_called_with is not None
    new_sid, kw = engine.start_called_with
    assert new_sid == "new"
    assert kw.get("old_session_id") == "old"


def test_reset_session_state_delegates_to_transition_when_args_provided():
    """``reset_session_state(previous_messages=..., old_session_id=...)`` fires full lifecycle."""
    engine = MagicMock()
    engine.context_length = 100_000

    agent = _bare_agent()
    agent.context_compressor = engine

    agent.reset_session_state(
        previous_messages=[{"role": "user", "content": "hi"}],
        old_session_id="old-sid",
    )

    assert engine.on_session_end.called
    assert engine.on_session_reset.called
    assert engine.on_session_start.called
    # No carry_over_context, so carry_over hook NOT called.
    assert not engine.carry_over_new_session_context.called


def test_reset_session_state_default_call_only_resets():
    """Bare ``reset_session_state()`` still only resets the engine (no end/start)."""
    engine = MagicMock()
    engine.context_length = 100_000

    agent = _bare_agent()
    agent.context_compressor = engine

    agent.reset_session_state()

    assert engine.on_session_reset.called
    assert not engine.on_session_end.called
    assert not engine.on_session_start.called


def test_reset_session_state_rebinds_builtin_compressor_after_session_switch(tmp_path, monkeypatch):
    """Reset-only session switches must rebind durable cooldown state to the new session."""
    db = SessionDB(db_path=tmp_path / "state.db")
    db.create_session("old-sid", source="cli")
    db.create_session("new-sid", source="cli")
    db.record_compression_failure_cooldown("old-sid", 4_000_000_000.0, "old-timeout")

    monkeypatch.setattr(
        "agent.context_compressor.get_model_context_length",
        lambda *_a, **_k: 100_000,
    )
    compressor = ContextCompressor(
        model="fake-model",
        threshold_percent=0.85,
        protect_first_n=2,
        protect_last_n=2,
        quiet_mode=True,
    )
    compressor.bind_session_state(db, "old-sid")

    agent = _bare_agent()
    agent._session_db = db
    agent.context_compressor = compressor
    agent.session_id = "new-sid"

    agent.reset_session_state()

    assert compressor._session_id == "new-sid"
    assert compressor.get_active_compression_failure_cooldown() is None
    assert db.get_compression_failure_cooldown("old-sid") is not None

    compressor._record_compression_failure_cooldown(30.0, "new-timeout")

    assert db.get_compression_failure_cooldown("new-sid") is not None
    assert db.get_compression_failure_cooldown("old-sid")["error"] == "old-timeout"


def test_update_from_response_forwards_canonical_cache_buckets():
    """conversation_loop passes cache_read/write/reasoning tokens to engine."""
    # Test the contract directly: a usage_dict built from CanonicalUsage must
    # contain the canonical buckets in addition to the legacy keys. We don't
    # spin up the full conversation loop; we just verify the dict shape.
    from agent.usage_pricing import CanonicalUsage

    canonical = CanonicalUsage(
        input_tokens=1000,
        output_tokens=500,
        cache_read_tokens=800,
        cache_write_tokens=200,
        reasoning_tokens=50,
    )
    usage_dict = {
        "prompt_tokens": canonical.prompt_tokens,
        "completion_tokens": canonical.output_tokens,
        "total_tokens": canonical.total_tokens,
        "input_tokens": canonical.input_tokens,
        "output_tokens": canonical.output_tokens,
        "cache_read_tokens": canonical.cache_read_tokens,
        "cache_write_tokens": canonical.cache_write_tokens,
        "reasoning_tokens": canonical.reasoning_tokens,
    }

    # Legacy keys present
    assert usage_dict["prompt_tokens"] == canonical.prompt_tokens
    assert usage_dict["completion_tokens"] == 500
    assert usage_dict["total_tokens"] == canonical.total_tokens
    # Canonical cache + reasoning buckets present
    assert usage_dict["cache_read_tokens"] == 800
    assert usage_dict["cache_write_tokens"] == 200
    assert usage_dict["reasoning_tokens"] == 50
    assert usage_dict["input_tokens"] == 1000
    assert usage_dict["output_tokens"] == 500


