"""Fixtures shared across alvarez_cli kanban tests."""

from __future__ import annotations

import pytest

# Shared skip markers for the disabled `alvarez update` channel. Defined once
# here (rather than copy-pasted per test file) so re-enabling the channel is a
# single-place change instead of a hunt across every file that skipped its
# tests. Two independent disable points exist — cmd_update and the passive
# check — so there are two markers, not one.
update_disabled = pytest.mark.skip(
    reason="`alvarez update` is disabled in the Alvarez fork — see cmd_update in alvarez_cli/main.py"
)
passive_update_check_disabled = pytest.mark.skip(
    reason="passive update check is disabled in the Alvarez fork — see check_for_updates in alvarez_cli/banner.py"
)


@pytest.fixture
def all_assignees_spawnable(monkeypatch):
    """Pretend every assignee maps to a real Alvarez profile.

    Most dispatcher tests use synthetic assignees ("alice", "bob") that
    don't correspond to actual profile directories on disk. Without this
    patch, the dispatcher's profile-exists guard (PR #20105) routes
    those tasks into ``skipped_nonspawnable`` instead of spawning, which
    would break tests that assert spawn behavior.
    """
    from alvarez_cli import profiles
    monkeypatch.setattr(profiles, "profile_exists", lambda name: True)


@pytest.fixture(autouse=True)
def _suppress_concurrent_alvarez_gate(request, monkeypatch):
    """Default ``_detect_concurrent_alvarez_instances`` to ``[]`` for every test.

    The Windows update path now refuses to proceed when another
    ``alvarez.exe`` is detected (issue #26670). On a developer's Windows
    machine running the test suite via ``alvarez`` itself, this would
    flag the running agent as a concurrent instance and abort every
    ``cmd_update`` test. Tests that want to exercise the gate explicitly
    re-patch ``_detect_concurrent_alvarez_instances`` with their own
    return value — autouse here gives a clean default without touching
    the rest of the suite.

    Tests that need to call the REAL function (e.g. unit tests for the
    helper itself) opt out with ``@pytest.mark.real_concurrent_gate``.
    """
    if request.node.get_closest_marker("real_concurrent_gate"):
        return
    try:
        from alvarez_cli import main as _cli_main
    except Exception:
        return
    # raising=False: under pytest's per-test spawn isolation, a concurrent
    # xdist worker importing a module that transitively touches alvarez_cli.main
    # can briefly expose a partially-initialized module object here — one where
    # _detect_concurrent_alvarez_instances isn't defined yet. A bare setattr
    # would raise AttributeError and error the (unrelated) test. The attribute
    # always exists once main.py finishes importing, so a no-op when it's
    # transiently absent is the correct, race-free default.
    monkeypatch.setattr(
        _cli_main,
        "_detect_concurrent_alvarez_instances",
        lambda *_a, **_k: [],
        raising=False,
    )
