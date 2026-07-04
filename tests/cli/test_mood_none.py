"""Tests for /mood none — clearing mood overlay."""
import pytest
from unittest.mock import MagicMock, patch
import yaml


# ── CLI tests ──────────────────────────────────────────────────────────────

class TestCLIMoodNone:

    def _make_cli(self, moods=None):
        from cli import AlvarezCLI
        cli = AlvarezCLI.__new__(AlvarezCLI)
        cli.moods = moods or {
            "helpful": "You are helpful.",
            "concise": "You are concise.",
        }
        cli.system_prompt = "You are kawaii~"
        cli.agent = MagicMock()
        cli.console = MagicMock()
        return cli

    def test_none_clears_system_prompt(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood none")
        assert cli.system_prompt == ""

    def test_default_clears_system_prompt(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood default")
        assert cli.system_prompt == ""

    def test_neutral_clears_system_prompt(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood neutral")
        assert cli.system_prompt == ""

    def test_none_forces_agent_reinit(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood none")
        assert cli.agent is None

    def test_none_saves_to_config(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True) as mock_save:
            cli._handle_mood_command("/mood none")
        mock_save.assert_called_once_with("agent.system_prompt", "")

    def test_known_mood_still_works(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood helpful")
        assert cli.system_prompt == "You are helpful."

    def test_unknown_mood_shows_none_in_available(self, capsys):
        cli = self._make_cli()
        cli._handle_mood_command("/mood nonexistent")
        output = capsys.readouterr().out
        assert "none" in output.lower()

    def test_list_shows_none_option(self):
        cli = self._make_cli()
        with patch("builtins.print") as mock_print:
            cli._handle_mood_command("/mood")
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "none" in output.lower()


# ── Gateway tests ──────────────────────────────────────────────────────────

class TestGatewayMoodNone:

    def _make_event(self, args=""):
        event = MagicMock()
        event.get_command.return_value = "mood"
        event.get_command_args.return_value = args
        return event

    def _make_runner(self, moods=None):
        from gateway.run import GatewayRunner
        runner = GatewayRunner.__new__(GatewayRunner)
        runner._ephemeral_system_prompt = "You are kawaii~"
        runner.config = {
            "agent": {
                "moods": moods or {"helpful": "You are helpful."}
            }
        }
        return runner

    @pytest.mark.asyncio
    async def test_none_clears_ephemeral_prompt(self, tmp_path):
        runner = self._make_runner()
        config_data = {"agent": {"moods": {"helpful": "You are helpful."}, "system_prompt": "kawaii"}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._alvarez_home", tmp_path):
            event = self._make_event("none")
            result = await runner._handle_mood_command(event)

        assert runner._ephemeral_system_prompt == ""
        assert "cleared" in result.lower()

    @pytest.mark.asyncio
    async def test_default_clears_ephemeral_prompt(self, tmp_path):
        runner = self._make_runner()
        config_data = {"agent": {"moods": {"helpful": "You are helpful."}}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._alvarez_home", tmp_path):
            event = self._make_event("default")
            result = await runner._handle_mood_command(event)

        assert runner._ephemeral_system_prompt == ""

    @pytest.mark.asyncio
    async def test_list_includes_none(self, tmp_path):
        runner = self._make_runner()
        config_data = {"agent": {"moods": {"helpful": "You are helpful."}}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._alvarez_home", tmp_path):
            event = self._make_event("")
            result = await runner._handle_mood_command(event)

        assert "none" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_shows_none_in_available(self, tmp_path):
        runner = self._make_runner()
        config_data = {"agent": {"moods": {"helpful": "You are helpful."}}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        with patch("gateway.run._alvarez_home", tmp_path):
            event = self._make_event("nonexistent")
            result = await runner._handle_mood_command(event)

        assert "none" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_mood_list_uses_profile_display_path(self, tmp_path):
        runner = self._make_runner(moods={})
        (tmp_path / "config.yaml").write_text(yaml.dump({"agent": {"moods": {}}}))

        with patch("gateway.run._alvarez_home", tmp_path), \
             patch("alvarez_constants.display_alvarez_home", return_value="~/.alvarez/profiles/coder"):
            event = self._make_event("")
            result = await runner._handle_mood_command(event)

        assert result == "No moods configured in `~/.alvarez/profiles/coder/config.yaml`"


class TestMoodDictFormat:
    """Test dict-format custom moods with description, tone, style."""

    def _make_cli(self, moods):
        from cli import AlvarezCLI
        cli = AlvarezCLI.__new__(AlvarezCLI)
        cli.moods = moods
        cli.system_prompt = ""
        cli.agent = None
        cli.console = MagicMock()
        return cli

    def test_dict_mood_uses_system_prompt(self):
        cli = self._make_cli({
            "coder": {
                "description": "Expert programmer",
                "system_prompt": "You are an expert programmer.",
                "tone": "technical",
                "style": "concise",
            }
        })
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood coder")
        assert "You are an expert programmer." in cli.system_prompt

    def test_dict_mood_includes_tone(self):
        cli = self._make_cli({
            "coder": {
                "system_prompt": "You are an expert programmer.",
                "tone": "technical and precise",
            }
        })
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood coder")
        assert "Tone: technical and precise" in cli.system_prompt

    def test_dict_mood_includes_style(self):
        cli = self._make_cli({
            "coder": {
                "system_prompt": "You are an expert programmer.",
                "style": "use code examples",
            }
        })
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood coder")
        assert "Style: use code examples" in cli.system_prompt

    def test_string_mood_still_works(self):
        cli = self._make_cli({"helper": "You are helpful."})
        with patch("cli.save_config_value", return_value=True):
            cli._handle_mood_command("/mood helper")
        assert cli.system_prompt == "You are helpful."

    def test_resolve_prompt_dict_no_tone_no_style(self):
        from cli import AlvarezCLI
        result = AlvarezCLI._resolve_mood_prompt({
            "description": "A helper",
            "system_prompt": "You are helpful.",
        })
        assert result == "You are helpful."

    def test_resolve_prompt_string(self):
        from cli import AlvarezCLI
        result = AlvarezCLI._resolve_mood_prompt("You are helpful.")
        assert result == "You are helpful."
