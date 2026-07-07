from unittest.mock import patch

from alvarez_cli.config import (
    format_managed_message,
    get_managed_system,
    recommended_update_command,
)
from tools.skills_hub import OptionalSkillSource


def test_get_managed_system_homebrew(monkeypatch):
    monkeypatch.setenv("ALVAREZ_MANAGED", "homebrew")

    assert get_managed_system() == "Homebrew"
    assert recommended_update_command() == "brew upgrade alvarez-agent"


def test_format_managed_message_homebrew(monkeypatch):
    monkeypatch.setenv("ALVAREZ_MANAGED", "homebrew")

    message = format_managed_message("update Alvarez Agent")

    assert "managed by Homebrew" in message
    assert "brew upgrade alvarez-agent" in message


def test_recommended_update_command_defaults_to_alvarez_update(monkeypatch):
    monkeypatch.delenv("ALVAREZ_MANAGED", raising=False)

    # Also short-circuit the .managed marker path — CI runners may have an
    # ambient ~/.alvarez/.managed if a prior test left ALVAREZ_HOME pointing
    # somewhere with that marker, which would make get_managed_update_command()
    # return "Update your Nix flake input ..." instead of falling through to
    # detect_install_method().
    with patch("alvarez_cli.config.get_managed_update_command", return_value=None), \
         patch("alvarez_cli.config.detect_install_method", return_value="git"):
        assert recommended_update_command() == "alvarez update"


def test_optional_skill_source_honors_env_override(monkeypatch, tmp_path):
    optional_dir = tmp_path / "optional-skills"
    optional_dir.mkdir()
    monkeypatch.setenv("ALVAREZ_OPTIONAL_SKILLS", str(optional_dir))

    source = OptionalSkillSource()

    assert source._optional_dir == optional_dir
