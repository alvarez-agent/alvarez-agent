"""install.ps1 must install from the local checkout it is run from.

Windows mirror of ``tests/test_install_sh_local_source.py``.  The repo is
private, so the checkout the user already cloned (with their own credentials)
is the reliable install source.  ``Find-LocalSource`` finds the enclosing
alvarez-agent checkout via the script's own location (``$PSCommandPath``,
captured as ``$InstallerSource``), and ``Install-RepositoryFromLocalSource``
clones it into the managed install dir, re-pointing ``origin`` at the
checkout's real remote so later update runs fetch from GitHub.  ``iex (irm
...)`` invocations have an empty ``$PSCommandPath`` and must fall back to the
GitHub clone URLs -- which must point at alvarez-agent/alvarez-agent, never
the old hermes upstream.

install.ps1 only runs on Windows, so there is no runner to execute it on
Linux/macOS CI -- these are source-level contract tests, following
``test_install_ps1_python_fallback_venv.py``.  The runnable smoke test lives
at ``scripts/tests/test-install-ps1-local-source.ps1``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_INSTALL_PS1 = _SCRIPTS / "install.ps1"
_INSTALL_CMD = _SCRIPTS / "install.cmd"


@pytest.fixture(scope="module")
def source() -> str:
    return _INSTALL_PS1.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cmd_source() -> str:
    return _INSTALL_CMD.read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    """Return the text of a PowerShell ``function <name> { ... }`` block."""
    # \b so "Install-Repository" doesn't match "Install-RepositoryFromLocalSource".
    m = re.search(rf"function {re.escape(name)}\b", source)
    assert m is not None, f"function {name} not found in install.ps1"
    start = m.start()
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace : i + 1]
    raise AssertionError(f"unterminated function body for {name}")


# ---------------------------------------------------------------------------
# URL scrub: nothing may point at the old hermes upstream
# ---------------------------------------------------------------------------


def test_repo_urls_point_at_alvarez(source: str):
    assert '$RepoUrlSsh = "git@github.com:alvarez-agent/alvarez-agent.git"' in source
    assert '$RepoUrlHttps = "https://github.com/alvarez-agent/alvarez-agent.git"' in source


def test_zip_fallback_urls_point_at_alvarez(source: str):
    """The Commit/Tag/Branch archive URLs must all target the alvarez repo."""
    repos = re.findall(r"https://github\.com/([^/\"]+/[^/\"]+)/archive/", source)
    assert repos, "expected ZIP-fallback archive URLs in install.ps1"
    assert set(repos) == {"alvarez-agent/alvarez-agent"}


def test_no_hermes_references_remain_in_ps1(source: str):
    assert "NousResearch" not in source
    assert "hermes-agent.nousresearch.com" not in source


def test_no_hermes_references_remain_in_cmd(cmd_source: str):
    assert "NousResearch" not in cmd_source
    assert "nousresearch" not in cmd_source.lower()


def test_install_cmd_launches_the_adjacent_ps1(cmd_source: str):
    """The CMD wrapper must run the install.ps1 next to it, not a dead URL.

    ``-File "%~dp0install.ps1"`` also gives the PowerShell script a real
    ``$PSCommandPath``, so local-checkout detection works through the wrapper.
    """
    assert '-File "%~dp0install.ps1"' in cmd_source
    assert "irm " not in cmd_source


# ---------------------------------------------------------------------------
# Find-LocalSource
# ---------------------------------------------------------------------------


def test_installer_source_captured_from_pscommandpath(source: str):
    """`iex (irm ...)` leaves $PSCommandPath empty -- detection must key off it."""
    assert '$InstallerSource = "$PSCommandPath"' in source


def test_find_local_source_contract(source: str):
    body = _function_body(source, "Find-LocalSource")
    # Empty source (piped invocation) disables detection.
    assert "IsNullOrWhiteSpace($InstallerSource)" in body
    # The enclosing checkout is found via git, from the script's own dir.
    assert "rev-parse --show-toplevel" in body
    # Only a checkout of THIS repo qualifies.
    assert "'^name = \"alvarez-agent\"'" in body, (
        "Find-LocalSource must verify the checkout's pyproject.toml project name"
    )


def test_find_local_source_tolerates_missing_git(source: str):
    """Detection can run before Stage-Git on a fresh machine -- no git, no throw."""
    body = _function_body(source, "Find-LocalSource")
    assert "Get-Command git -ErrorAction SilentlyContinue" in body


# ---------------------------------------------------------------------------
# Install-RepositoryFromLocalSource
# ---------------------------------------------------------------------------


def test_clone_repoints_origin_at_source_remote(source: str):
    body = _function_body(source, "Install-RepositoryFromLocalSource")
    # Future update runs fetch from origin -- it must be the real remote, not
    # the local path (which the user may delete after installing).
    assert "remote get-url origin" in body
    assert "remote set-url origin $sourceOrigin" in body
    # ...and when the checkout has no remote, warn instead of failing.
    assert "future updates will pull from" in body


def test_clone_does_not_use_depth(source: str):
    """git ignores --depth for local-path clones; passing it just warns."""
    body = _function_body(source, "Install-RepositoryFromLocalSource")
    git_lines = [ln for ln in body.splitlines() if "& git" in ln]
    assert git_lines, "expected git invocations in Install-RepositoryFromLocalSource"
    assert not [ln for ln in git_lines if "--depth" in ln]


def test_clone_follows_source_checkout_branch(source: str):
    """Without an explicit -Branch, install what the checkout has checked out."""
    body = _function_body(source, "Install-RepositoryFromLocalSource")
    explicit_at = body.find("$BranchExplicit")
    assert explicit_at != -1, (
        "Install-RepositoryFromLocalSource must consult $BranchExplicit so an "
        "explicit -Branch wins over the checkout's current branch"
    )
    assert "rev-parse --abbrev-ref HEAD" in body
    # Detached HEAD has no branch name to follow -- fall back to main.
    assert "detached HEAD" in body
    # Downstream stages (update path, completion hints) must see the branch
    # that was actually installed.
    assert "$script:Branch = $srcBranch" in body


def test_explicit_missing_branch_fails_with_hint(source: str):
    body = _function_body(source, "Install-RepositoryFromLocalSource")
    verify_at = body.find("rev-parse --verify --quiet")
    assert verify_at != -1, "the requested branch must be verified in the source checkout"
    assert "not found in local checkout" in body
    assert "-Branch <name>" in body


def test_uncommitted_changes_warn_but_install(source: str):
    body = _function_body(source, "Install-RepositoryFromLocalSource")
    assert "status --porcelain" in body
    assert "uncommitted changes" in body


# ---------------------------------------------------------------------------
# Install-Repository wiring
# ---------------------------------------------------------------------------


def test_local_source_is_preferred_over_github_clone(source: str):
    """The fresh-clone path must consult the local checkout before SSH/HTTPS."""
    body = _function_body(source, "Install-Repository")
    local_at = body.find("Find-LocalSource")
    assert local_at != -1, "Install-Repository must call Find-LocalSource"
    assert "Install-RepositoryFromLocalSource" in body
    ssh_at = body.find("Trying SSH clone")
    assert ssh_at != -1
    assert local_at < ssh_at, (
        "local-checkout detection must run BEFORE the GitHub SSH/HTTPS clone "
        "attempts -- the private repo makes the local checkout the reliable source"
    )


def test_local_source_does_not_shadow_update_path(source: str):
    """An existing valid install still takes the in-place update path."""
    body = _function_body(source, "Install-Repository")
    update_at = body.find("Existing installation found, updating...")
    local_at = body.find("Find-LocalSource")
    assert update_at != -1 and local_at != -1
    assert update_at < local_at, (
        "the update path must be checked before local-source detection so a "
        "managed install is updated in place, never re-cloned over"
    )
