"""install.sh must install from the local checkout it is run from.

The repo is private, so the checkout the user already cloned (with their own
credentials) is the reliable install source. ``detect_local_source()`` finds
the enclosing alvarez-agent checkout via the script's own location, and
``clone_from_local_source()`` clones it into the managed install dir,
re-pointing ``origin`` at the checkout's real remote so later update runs
fetch from GitHub. Piped invocations (``curl | bash``) have an empty
``BASH_SOURCE`` and must fall back to the GitHub clone URLs — which must
point at alvarez-agent/alvarez-agent, never the old hermes upstream.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="needs git and bash",
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _extract_function(name: str) -> str:
    text = INSTALL_SH.read_text()
    m = re.search(rf"^{re.escape(name)}\(\) \{{\n.*?\n\}}", text, re.DOTALL | re.MULTILINE)
    assert m is not None, f"{name}() not found in install.sh"
    return m.group(0)


LOG_STUBS = (
    'log_info() { echo "INFO: $*"; }\n'
    'log_warn() { echo "WARN: $*"; }\n'
    'log_error() { echo "ERROR: $*"; }\n'
    'log_success() { echo "OK: $*"; }\n'
)


def _make_source_checkout(tmp_path: Path, *, origin: str | None, name: str = "alvarez-agent") -> Path:
    """A minimal stand-in for the repo checkout a user just cloned."""
    src = tmp_path / "checkout"
    scripts = src / "scripts"
    scripts.mkdir(parents=True)
    (src / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.0.1"\n')
    shutil.copy(INSTALL_SH, scripts / "install.sh")
    _git(src, "init", "-b", "main")
    _git(src, "add", "-A")
    _git(src, "commit", "-m", "init")
    if origin is not None:
        _git(src, "remote", "add", "origin", origin)
    return src


# ---------------------------------------------------------------------------
# URL scrub: nothing may point at the old hermes upstream
# ---------------------------------------------------------------------------


def test_repo_urls_point_at_alvarez() -> None:
    text = INSTALL_SH.read_text()
    assert 'REPO_URL_SSH="git@github.com:alvarez-agent/alvarez-agent.git"' in text
    assert 'REPO_URL_HTTPS="https://github.com/alvarez-agent/alvarez-agent.git"' in text


def test_no_hermes_references_remain() -> None:
    text = INSTALL_SH.read_text()
    assert "NousResearch" not in text
    assert "hermes-agent.nousresearch.com" not in text


# ---------------------------------------------------------------------------
# detect_local_source
# ---------------------------------------------------------------------------


def _run_detect(installer_source: str) -> str:
    block = _extract_function("detect_local_source")
    script = (
        f"{LOG_STUBS}"
        f"INSTALLER_SOURCE={shlex.quote(installer_source)}\n"
        'LOCAL_SOURCE=""\n'
        f"{block}\n"
        "detect_local_source || true\n"
        'printf "%s" "$LOCAL_SOURCE"\n'
    )
    res = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return res.stdout


def test_detects_enclosing_checkout(tmp_path: Path) -> None:
    src = _make_source_checkout(tmp_path, origin=None)
    detected = _run_detect(str(src / "scripts" / "install.sh"))
    assert Path(detected).resolve() == src.resolve()


def test_empty_installer_source_disables_detection(tmp_path: Path) -> None:
    # curl | bash and bash -s leave BASH_SOURCE empty — detection must no-op.
    assert _run_detect("") == ""


def test_wrong_project_name_is_rejected(tmp_path: Path) -> None:
    src = _make_source_checkout(tmp_path, origin=None, name="some-other-project")
    assert _run_detect(str(src / "scripts" / "install.sh")) == ""


def test_script_outside_git_repo_is_rejected(tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir()
    script = loose / "install.sh"
    shutil.copy(INSTALL_SH, script)
    assert _run_detect(str(script)) == ""


def test_piped_manifest_mode_still_works() -> None:
    """Regression: the top-level detection call must not break piped runs."""
    res = subprocess.run(
        ["bash", "-s", "--", "--manifest"],
        stdin=INSTALL_SH.open("rb"),
        capture_output=True,
        text=True,
        cwd="/",
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip().startswith('{"protocol_version"')


# ---------------------------------------------------------------------------
# clone_from_local_source
# ---------------------------------------------------------------------------


def _run_clone(
    source: Path,
    install_dir: Path,
    *,
    branch: str = "main",
    branch_explicit: bool = False,
) -> subprocess.CompletedProcess:
    block = _extract_function("clone_from_local_source")
    script = (
        f"{LOG_STUBS}"
        f"LOCAL_SOURCE={shlex.quote(str(source))}\n"
        f"INSTALL_DIR={shlex.quote(str(install_dir))}\n"
        f"BRANCH={shlex.quote(branch)}\n"
        f"BRANCH_EXPLICIT={'true' if branch_explicit else 'false'}\n"
        f"{block}\n"
        "clone_from_local_source\n"
        'printf "BRANCH_AFTER=%s" "$BRANCH"\n'
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def _origin_of(repo: Path) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _head_of(repo: Path) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def test_clone_repoints_origin_at_source_remote(tmp_path: Path) -> None:
    fake_origin = "https://github.com/alvarez-agent/alvarez-agent.git"
    src = _make_source_checkout(tmp_path, origin=fake_origin)
    install_dir = tmp_path / "managed"

    res = _run_clone(src, install_dir)
    assert res.returncode == 0, res.stderr
    assert install_dir.is_dir()
    assert _head_of(install_dir) == _head_of(src)
    # Future update runs fetch from origin — it must be the real remote, not
    # the local path (which the user may delete after installing).
    assert _origin_of(install_dir) == fake_origin


def test_clone_without_source_remote_keeps_local_path(tmp_path: Path) -> None:
    src = _make_source_checkout(tmp_path, origin=None)
    install_dir = tmp_path / "managed"

    res = _run_clone(src, install_dir)
    assert res.returncode == 0, res.stderr
    assert _origin_of(install_dir) == str(src)
    assert "WARN" in res.stdout  # updates-from-local-path warning


def test_clone_uses_source_checkout_branch(tmp_path: Path) -> None:
    src = _make_source_checkout(tmp_path, origin=None)
    _git(src, "checkout", "-b", "feature/fresh-install")
    (src / "extra.txt").write_text("x")
    _git(src, "add", "-A")
    _git(src, "commit", "-m", "feature commit")
    install_dir = tmp_path / "managed"

    res = _run_clone(src, install_dir)  # BRANCH=main, not explicit
    assert res.returncode == 0, res.stderr
    assert _head_of(install_dir) == _head_of(src)
    assert (install_dir / "extra.txt").exists()
    assert "BRANCH_AFTER=feature/fresh-install" in res.stdout


def test_explicit_missing_branch_fails_with_hint(tmp_path: Path) -> None:
    src = _make_source_checkout(tmp_path, origin=None)
    install_dir = tmp_path / "managed"

    res = _run_clone(src, install_dir, branch="no-such-branch", branch_explicit=True)
    assert res.returncode != 0
    assert "not found in local checkout" in res.stdout
    assert not install_dir.exists()


def test_uncommitted_changes_warn_but_install(tmp_path: Path) -> None:
    src = _make_source_checkout(tmp_path, origin=None)
    (src / "dirty.txt").write_text("uncommitted")
    install_dir = tmp_path / "managed"

    res = _run_clone(src, install_dir)
    assert res.returncode == 0, res.stderr
    assert "uncommitted changes" in res.stdout
    assert not (install_dir / "dirty.txt").exists()
