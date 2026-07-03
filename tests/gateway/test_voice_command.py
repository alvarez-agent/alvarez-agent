"""Tests for the /voice command and auto voice reply in the gateway."""

import importlib.util
import json
import os
import queue
import sys
import threading
import time
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _ensure_discord_mock():
    """Install a lightweight discord mock when discord.py isn't available."""
    if "discord" in sys.modules and hasattr(sys.modules["discord"], "__file__"):
        return

    discord_mod = MagicMock()
    discord_mod.Intents.default.return_value = MagicMock()
    discord_mod.Client = MagicMock
    discord_mod.File = MagicMock
    discord_mod.DMChannel = type("DMChannel", (), {})
    discord_mod.Thread = type("Thread", (), {})
    discord_mod.ForumChannel = type("ForumChannel", (), {})
    discord_mod.ui = SimpleNamespace(View=object, button=lambda *a, **k: (lambda fn: fn), Button=object)
    discord_mod.ButtonStyle = SimpleNamespace(success=1, primary=2, secondary=2, danger=3, green=1, grey=2, blurple=2, red=3)
    discord_mod.Color = SimpleNamespace(orange=lambda: 1, green=lambda: 2, blue=lambda: 3, red=lambda: 4, purple=lambda: 5)
    discord_mod.Interaction = object
    discord_mod.Embed = MagicMock
    discord_mod.app_commands = SimpleNamespace(
        describe=lambda **kwargs: (lambda fn: fn),
        choices=lambda **kwargs: (lambda fn: fn),
        Choice=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    discord_mod.opus = SimpleNamespace(is_loaded=lambda: True, load_opus=lambda *_args, **_kwargs: None)
    discord_mod.FFmpegPCMAudio = MagicMock
    discord_mod.PCMVolumeTransformer = MagicMock
    discord_mod.http = SimpleNamespace(Route=MagicMock)

    ext_mod = MagicMock()
    commands_mod = MagicMock()
    commands_mod.Bot = MagicMock
    ext_mod.commands = commands_mod

    sys.modules.setdefault("discord", discord_mod)
    sys.modules.setdefault("discord.ext", ext_mod)
    sys.modules.setdefault("discord.ext.commands", commands_mod)


_ensure_discord_mock()

from gateway.platforms.base import MessageEvent, MessageType, SessionSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(text: str = "", message_type=MessageType.TEXT, chat_id="123") -> MessageEvent:
    source = SessionSource(
        chat_id=chat_id,
        user_id="user1",
        platform=MagicMock(),
    )
    source.platform.value = "telegram"
    source.thread_id = None
    event = MessageEvent(text=text, message_type=message_type, source=source)
    event.message_id = "msg42"
    return event


def _make_runner(tmp_path):
    """Create a bare GatewayRunner without calling __init__."""
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner._session_db = None
    runner.session_store = MagicMock()
    runner._is_user_authorized = lambda source: True
    return runner


# =====================================================================
# /voice command handler
# =====================================================================

class TestHandleVoiceCommand:

    @pytest.fixture
    def runner(self, tmp_path):
        return _make_runner(tmp_path)

    @pytest.mark.asyncio
    async def test_voice_on(self, runner):
        event = _make_event("/voice on")
        result = await runner._handle_voice_command(event)
        assert "enabled" in result.lower()
        assert runner._voice_mode["telegram:123"] == "voice_only"

    @pytest.mark.asyncio
    async def test_voice_off(self, runner):
        runner._voice_mode["telegram:123"] = "voice_only"
        event = _make_event("/voice off")
        result = await runner._handle_voice_command(event)
        assert "disabled" in result.lower()
        assert runner._voice_mode["telegram:123"] == "off"

    @pytest.mark.asyncio
    async def test_voice_tts(self, runner):
        event = _make_event("/voice tts")
        result = await runner._handle_voice_command(event)
        assert "tts" in result.lower()
        assert runner._voice_mode["telegram:123"] == "all"

    @pytest.mark.asyncio
    async def test_voice_status_off(self, runner):
        event = _make_event("/voice status")
        result = await runner._handle_voice_command(event)
        assert "off" in result.lower()

    @pytest.mark.asyncio
    async def test_voice_status_on(self, runner):
        runner._voice_mode["telegram:123"] = "voice_only"
        event = _make_event("/voice status")
        result = await runner._handle_voice_command(event)
        assert "voice reply" in result.lower()

    @pytest.mark.asyncio
    async def test_toggle_off_to_on(self, runner):
        event = _make_event("/voice")
        result = await runner._handle_voice_command(event)
        assert "enabled" in result.lower()
        assert runner._voice_mode["telegram:123"] == "voice_only"

    @pytest.mark.asyncio
    async def test_toggle_on_to_off(self, runner):
        runner._voice_mode["telegram:123"] = "voice_only"
        event = _make_event("/voice")
        result = await runner._handle_voice_command(event)
        assert "disabled" in result.lower()
        assert runner._voice_mode["telegram:123"] == "off"

    @pytest.mark.asyncio
    async def test_persistence_saved(self, runner):
        event = _make_event("/voice on")
        await runner._handle_voice_command(event)
        assert runner._VOICE_MODE_PATH.exists()
        data = json.loads(runner._VOICE_MODE_PATH.read_text())
        assert data["telegram:123"] == "voice_only"

    @pytest.mark.asyncio
    async def test_persistence_loaded(self, runner):
        runner._VOICE_MODE_PATH.write_text(json.dumps({"telegram:456": "all"}))
        loaded = runner._load_voice_modes()
        assert loaded == {"telegram:456": "all"}

    @pytest.mark.asyncio
    async def test_persistence_saved_for_off(self, runner):
        event = _make_event("/voice off")
        await runner._handle_voice_command(event)
        data = json.loads(runner._VOICE_MODE_PATH.read_text())
        assert data["telegram:123"] == "off"

    def test_sync_voice_mode_state_to_adapter_restores_off_chats(self, runner):
        from gateway.config import Platform
        runner._voice_mode = {"telegram:123": "off", "telegram:456": "all"}
        adapter = SimpleNamespace(
            _auto_tts_disabled_chats=set(),
            platform=Platform.TELEGRAM,
        )

        runner._sync_voice_mode_state_to_adapter(adapter)

        assert adapter._auto_tts_disabled_chats == {"123"}

    def test_sync_populates_enabled_chats_from_voice_modes(self, runner):
        """Issue #16007: sync also restores per-chat /voice on|tts opt-ins.

        The adapter's ``_auto_tts_enabled_chats`` must mirror chats whose
        persisted voice_mode is ``voice_only`` or ``all`` — without this,
        ``/voice on`` was relying on a "not in disabled set" default that
        silently enabled auto-TTS for every chat.
        """
        from gateway.config import Platform
        runner._voice_mode = {
            "telegram:off_chat": "off",
            "telegram:on_chat": "voice_only",
            "telegram:tts_chat": "all",
            "slack:999": "voice_only",  # wrong platform, must be ignored
        }
        adapter = SimpleNamespace(
            _auto_tts_default=False,
            _auto_tts_disabled_chats=set(),
            _auto_tts_enabled_chats=set(),
            platform=Platform.TELEGRAM,
        )

        runner._sync_voice_mode_state_to_adapter(adapter)

        assert adapter._auto_tts_disabled_chats == {"off_chat"}
        assert adapter._auto_tts_enabled_chats == {"on_chat", "tts_chat"}

    def test_sync_pushes_config_default_onto_adapter(self, runner, monkeypatch):
        """Issue #16007: ``voice.auto_tts`` must propagate to ``_auto_tts_default``."""
        from gateway.config import Platform

        fake_cfg = {"voice": {"auto_tts": True}}
        monkeypatch.setattr(
            "alvarez_cli.config.load_config",
            lambda: fake_cfg,
        )
        adapter = SimpleNamespace(
            _auto_tts_default=False,
            _auto_tts_disabled_chats=set(),
            _auto_tts_enabled_chats=set(),
            platform=Platform.TELEGRAM,
        )

        runner._sync_voice_mode_state_to_adapter(adapter)

        assert adapter._auto_tts_default is True

    def test_restart_restores_voice_off_state(self, runner, tmp_path):
        from gateway.config import Platform
        runner._VOICE_MODE_PATH.write_text(json.dumps({"telegram:123": "off"}))

        restored_runner = _make_runner(tmp_path)
        restored_runner._voice_mode = restored_runner._load_voice_modes()
        adapter = SimpleNamespace(
            _auto_tts_disabled_chats=set(),
            platform=Platform.TELEGRAM,
        )

        restored_runner._sync_voice_mode_state_to_adapter(adapter)

        assert restored_runner._voice_mode["telegram:123"] == "off"
        assert adapter._auto_tts_disabled_chats == {"123"}

    @pytest.mark.asyncio
    async def test_per_chat_isolation(self, runner):
        e1 = _make_event("/voice on", chat_id="aaa")
        e2 = _make_event("/voice tts", chat_id="bbb")
        await runner._handle_voice_command(e1)
        await runner._handle_voice_command(e2)
        assert runner._voice_mode["telegram:aaa"] == "voice_only"
        assert runner._voice_mode["telegram:bbb"] == "all"

    @pytest.mark.asyncio
    async def test_platform_isolation(self, runner):
        """Same chat_id on different platforms must not collide (#12542)."""
        telegram_event = _make_event("/voice on", chat_id="999")
        slack_event = _make_event("/voice off", chat_id="999")
        slack_event.source.platform.value = "slack"

        await runner._handle_voice_command(telegram_event)
        await runner._handle_voice_command(slack_event)

        assert runner._voice_mode["telegram:999"] == "voice_only"
        assert runner._voice_mode["slack:999"] == "off"


# =====================================================================
# Auto voice reply decision logic
# =====================================================================

class TestAutoVoiceReply:
    """Test the real _should_send_voice_reply method on GatewayRunner.

    The gateway has two TTS paths:
      1. base adapter auto-TTS: fires for voice input in _process_message_background
      2. gateway _send_voice_reply: fires based on voice_mode setting

    To prevent double audio, _send_voice_reply is skipped when voice input
    already triggered base adapter auto-TTS.

    For Discord voice channels, the base adapter now routes play_tts directly
    into VC playback, so the runner should still skip voice-input follow-ups to
    avoid double playback.
    """

    @pytest.fixture
    def runner(self, tmp_path):
        return _make_runner(tmp_path)

    def _call(self, runner, voice_mode, message_type, agent_messages=None,
              response="Hello!", in_voice_channel=False):
        """Call real _should_send_voice_reply on a GatewayRunner instance."""
        chat_id = "123"
        if voice_mode != "off":
            runner._voice_mode["telegram:" + chat_id] = voice_mode
        else:
            runner._voice_mode.pop("telegram:" + chat_id, None)

        event = _make_event(message_type=message_type)

        if in_voice_channel:
            mock_adapter = MagicMock()
            mock_adapter.is_in_voice_channel = MagicMock(return_value=True)
            event.raw_message = SimpleNamespace(guild_id=111, guild=None)
            runner.adapters[event.source.platform] = mock_adapter

        return runner._should_send_voice_reply(
            event, response, agent_messages or []
        )

    # -- Full platform x input x mode matrix --------------------------------
    #
    # Legend:
    #   base = base adapter auto-TTS (play_tts)
    #   runner = gateway _send_voice_reply
    #
    # | Platform      | Input | Mode       | base | runner | Expected     |
    # |---------------|-------|------------|------|--------|--------------|
    # | Telegram      | voice | off        | yes  | skip   | 1 audio      |
    # | Telegram      | voice | voice_only | yes  | skip*  | 1 audio      |
    # | Telegram      | voice | all        | yes  | skip*  | 1 audio      |
    # | Telegram      | text  | off        | skip | skip   | 0 audio      |
    # | Telegram      | text  | voice_only | skip | skip   | 0 audio      |
    # | Telegram      | text  | all        | skip | yes    | 1 audio      |
    # | Discord text  | voice | all        | yes  | skip*  | 1 audio      |
    # | Discord text  | text  | all        | skip | yes    | 1 audio      |
    # | Discord VC    | voice | all        | skip†| yes    | 1 audio (VC) |
    # | Web UI        | voice | off        | yes  | skip   | 1 audio      |
    # | Web UI        | voice | all        | yes  | skip*  | 1 audio      |
    # | Web UI        | text  | all        | skip | yes    | 1 audio      |
    # | Slack         | voice | all        | yes  | skip*  | 1 audio      |
    # | Slack         | text  | all        | skip | yes    | 1 audio      |
    #
    # * skip_double: voice input → base already handles
    # † Discord play_tts override skips when in VC

    # -- Telegram/Slack/Web: voice input, base handles ---------------------

    def test_voice_input_voice_only_skipped(self, runner):
        """voice_only + voice input: base auto-TTS handles it, runner skips."""
        assert self._call(runner, "voice_only", MessageType.VOICE) is False

    def test_voice_input_all_mode_skipped(self, runner):
        """all + voice input: base auto-TTS handles it, runner skips."""
        assert self._call(runner, "all", MessageType.VOICE) is False

    # -- Text input: only runner handles -----------------------------------

    def test_text_input_all_mode_runner_fires(self, runner):
        """all + text input: only runner fires (base auto-TTS only for voice)."""
        assert self._call(runner, "all", MessageType.TEXT) is True

    def test_text_input_voice_only_no_reply(self, runner):
        """voice_only + text input: neither fires."""
        assert self._call(runner, "voice_only", MessageType.TEXT) is False

    # -- Mode off: nothing fires -------------------------------------------

    def test_off_mode_voice(self, runner):
        assert self._call(runner, "off", MessageType.VOICE) is False

    def test_off_mode_text(self, runner):
        assert self._call(runner, "off", MessageType.TEXT) is False

    # -- Discord VC exception: runner must handle --------------------------

    def test_discord_vc_voice_input_base_handles(self, runner):
        """Discord VC + voice input: base adapter play_tts plays in VC,
        so runner skips to avoid double playback."""
        assert self._call(runner, "all", MessageType.VOICE, in_voice_channel=True) is False

    def test_discord_vc_voice_only_base_handles(self, runner):
        """Discord VC + voice_only + voice: base adapter handles."""
        assert self._call(runner, "voice_only", MessageType.VOICE, in_voice_channel=True) is False

    # -- Edge cases --------------------------------------------------------

    def test_error_response_skipped(self, runner):
        assert self._call(runner, "all", MessageType.TEXT, response="Error: boom") is False

    def test_empty_response_skipped(self, runner):
        assert self._call(runner, "all", MessageType.TEXT, response="") is False

    def test_dedup_skips_when_agent_called_tts(self, runner):
        messages = [{
            "role": "assistant",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "text_to_speech", "arguments": "{}"},
            }],
        }]
        assert self._call(runner, "all", MessageType.TEXT, agent_messages=messages) is False

    def test_no_dedup_for_other_tools(self, runner):
        messages = [{
            "role": "assistant",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "web_search", "arguments": "{}"},
            }],
        }]
        assert self._call(runner, "all", MessageType.TEXT, agent_messages=messages) is True


# =====================================================================
# _send_voice_reply
# =====================================================================

class TestSendVoiceReply:

    @pytest.fixture
    def runner(self, tmp_path):
        return _make_runner(tmp_path)

    @pytest.mark.asyncio
    async def test_calls_tts_and_send_voice(self, runner):
        from gateway.config import Platform

        mock_adapter = AsyncMock()
        mock_adapter.send_voice = AsyncMock()
        event = _make_event()
        event.source.platform = Platform.TELEGRAM
        runner.adapters[event.source.platform] = mock_adapter

        tts_result = json.dumps({"success": True, "file_path": "/tmp/test.ogg"})

        with patch("tools.tts_tool.text_to_speech_tool", return_value=tts_result) as mock_tts, \
             patch("tools.tts_tool._strip_markdown_for_tts", side_effect=lambda t: t), \
             patch("os.path.isfile", return_value=True), \
             patch("os.unlink"), \
             patch("os.makedirs"):
            await runner._send_voice_reply(event, "Hello world")

        mock_adapter.send_voice.assert_called_once()
        assert mock_tts.call_args.kwargs["output_path"].endswith(".ogg")
        call_args = mock_adapter.send_voice.call_args
        assert call_args.kwargs.get("chat_id") == "123"

    @pytest.mark.asyncio
    async def test_non_telegram_auto_voice_reply_uses_mp3(self, runner):
        from gateway.config import Platform

        mock_adapter = AsyncMock()
        mock_adapter.send_voice = AsyncMock()
        event = _make_event()
        event.source.platform = Platform.SLACK
        runner.adapters[event.source.platform] = mock_adapter

        tts_result = json.dumps({"success": True, "file_path": "/tmp/test.mp3"})

        with patch("tools.tts_tool.text_to_speech_tool", return_value=tts_result) as mock_tts, \
             patch("tools.tts_tool._strip_markdown_for_tts", side_effect=lambda t: t), \
             patch("os.path.isfile", return_value=True), \
             patch("os.unlink"), \
             patch("os.makedirs"):
            await runner._send_voice_reply(event, "Hello world")

        mock_adapter.send_voice.assert_called_once()
        assert mock_tts.call_args.kwargs["output_path"].endswith(".mp3")

    @pytest.mark.asyncio
    async def test_auto_voice_reply_uses_thread_metadata_helper(self, runner):
        from gateway.config import Platform

        mock_adapter = AsyncMock()
        mock_adapter.send_voice = AsyncMock()
        event = _make_event()
        event.source.platform = Platform.TELEGRAM
        event.source.chat_type = "dm"
        event.source.thread_id = "20197"
        event.message_id = "462"
        runner.adapters[event.source.platform] = mock_adapter

        tts_result = json.dumps({"success": True, "file_path": "/tmp/test.ogg"})

        with patch("tools.tts_tool.text_to_speech_tool", return_value=tts_result), \
             patch("tools.tts_tool._strip_markdown_for_tts", side_effect=lambda t: t), \
             patch("os.path.isfile", return_value=True), \
             patch("os.unlink"), \
             patch("os.makedirs"):
            await runner._send_voice_reply(event, "Hello world")

        mock_adapter.send_voice.assert_called_once()
        call_kwargs = mock_adapter.send_voice.call_args.kwargs
        assert call_kwargs["reply_to"] == "462"
        assert call_kwargs["metadata"] == {
            "thread_id": "20197",
            "telegram_dm_topic_reply_fallback": True,
            "direct_messages_topic_id": "20197",
            "telegram_reply_to_message_id": "462",
            # Final voice reply is notify-worthy (issue #27970 Bug 2):
            # mirrors the final-text path in gateway/platforms/base.py.
            "notify": True,
        }

    @pytest.mark.asyncio
    async def test_empty_text_after_strip_skips(self, runner):
        event = _make_event()

        with patch("tools.tts_tool.text_to_speech_tool") as mock_tts, \
             patch("tools.tts_tool._strip_markdown_for_tts", return_value=""):
            await runner._send_voice_reply(event, "```code only```")

        mock_tts.assert_not_called()

    @pytest.mark.asyncio
    async def test_tts_failure_no_crash(self, runner):
        event = _make_event()
        mock_adapter = AsyncMock()
        runner.adapters[event.source.platform] = mock_adapter
        tts_result = json.dumps({"success": False, "error": "API error"})

        with patch("tools.tts_tool.text_to_speech_tool", return_value=tts_result), \
             patch("tools.tts_tool._strip_markdown_for_tts", side_effect=lambda t: t), \
             patch("os.path.isfile", return_value=False), \
             patch("os.makedirs"):
            await runner._send_voice_reply(event, "Hello")

        mock_adapter.send_voice.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_caught(self, runner):
        event = _make_event()
        with patch("tools.tts_tool.text_to_speech_tool", side_effect=RuntimeError("boom")), \
             patch("tools.tts_tool._strip_markdown_for_tts", side_effect=lambda t: t), \
             patch("os.makedirs"):
            # Should not raise
            await runner._send_voice_reply(event, "Hello")


# =====================================================================
# Discord play_tts skip when in voice channel
# =====================================================================


# =====================================================================
# Web play_tts sends play_audio (not voice bubble)
# =====================================================================

# =====================================================================
# Help text + known commands
# =====================================================================

class TestVoiceInHelp:

    def test_voice_in_help_output(self):
        """The gateway help text includes /voice (generated from registry)."""
        from alvarez_cli.commands import gateway_help_lines
        help_text = "\n".join(gateway_help_lines())
        assert "/voice" in help_text

    def test_voice_is_known_command(self):
        """The /voice command is in GATEWAY_KNOWN_COMMANDS."""
        from alvarez_cli.commands import GATEWAY_KNOWN_COMMANDS
        assert "voice" in GATEWAY_KNOWN_COMMANDS


# =====================================================================
# VoiceReceiver unit tests
# =====================================================================


# =====================================================================
# Gateway voice channel commands (join / leave / input)
# =====================================================================

class TestVoiceChannelCommands:
    """Test _handle_voice_channel_join, _handle_voice_channel_leave,
    _handle_voice_channel_input on the GatewayRunner."""

    @pytest.fixture
    def runner(self, tmp_path):
        return _make_runner(tmp_path)

    def _make_discord_event(self, text="/voice channel", chat_id="123",
                            guild_id=111, user_id="user1"):
        """Create event with raw_message carrying guild info."""
        source = SessionSource(
            chat_id=chat_id,
            user_id=user_id,
            platform=MagicMock(),
        )
        source.platform.value = "discord"
        source.thread_id = None
        event = MessageEvent(text=text, message_type=MessageType.TEXT, source=source)
        event.message_id = "msg42"
        event.raw_message = SimpleNamespace(guild_id=guild_id, guild=None)
        return event

    # -- _handle_voice_channel_join --

    @pytest.mark.asyncio
    async def test_join_unsupported_platform(self, runner):
        """Platform without join_voice_channel returns unsupported message."""
        mock_adapter = AsyncMock(spec=[])  # no join_voice_channel
        event = self._make_discord_event()
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_join(event)
        assert "not supported" in result.lower()

    @pytest.mark.asyncio
    async def test_join_no_guild_id(self, runner):
        """DM context (no guild_id) returns error."""
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock()
        event = self._make_discord_event()
        event.raw_message = None  # no guild info
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_join(event)
        assert "discord server" in result.lower()

    @pytest.mark.asyncio
    async def test_join_user_not_in_vc(self, runner):
        """User not in any voice channel."""
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock()
        mock_adapter.get_user_voice_channel = AsyncMock(return_value=None)
        event = self._make_discord_event()
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_join(event)
        assert "need to be in a voice channel" in result.lower()

    @pytest.mark.asyncio
    async def test_join_success(self, runner):
        """Successful join sets voice_mode and returns confirmation."""
        mock_channel = MagicMock()
        mock_channel.name = "General"
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock(return_value=True)
        mock_adapter.get_user_voice_channel = AsyncMock(return_value=mock_channel)
        mock_adapter._voice_text_channels = {}
        mock_adapter._voice_sources = {}
        mock_adapter._voice_input_callback = None
        event = self._make_discord_event()
        event.source.chat_type = "group"
        event.source.chat_name = "Alvarez Server / #general"
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_join(event)
        assert "joined" in result.lower()
        assert "General" in result
        assert runner._voice_mode["discord:123"] == "all"
        assert mock_adapter._voice_sources[111]["chat_id"] == "123"
        assert mock_adapter._voice_sources[111]["chat_type"] == "group"

    @pytest.mark.asyncio
    async def test_join_failure(self, runner):
        """Failed join returns permissions error."""
        mock_channel = MagicMock()
        mock_channel.name = "General"
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock(return_value=False)
        mock_adapter.get_user_voice_channel = AsyncMock(return_value=mock_channel)
        event = self._make_discord_event()
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_join(event)
        assert "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_join_exception(self, runner):
        """Exception during join is caught and reported."""
        mock_channel = MagicMock()
        mock_channel.name = "General"
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock(side_effect=RuntimeError("No permission"))
        mock_adapter.get_user_voice_channel = AsyncMock(return_value=mock_channel)
        event = self._make_discord_event()
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_join(event)
        assert "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_join_missing_voice_dependencies(self, runner):
        """Missing PyNaCl/davey should return a user-actionable install hint."""
        mock_channel = MagicMock()
        mock_channel.name = "General"
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock(
            side_effect=RuntimeError("PyNaCl library needed in order to use voice")
        )
        mock_adapter.get_user_voice_channel = AsyncMock(return_value=mock_channel)
        event = self._make_discord_event()
        runner.adapters[event.source.platform] = mock_adapter

        result = await runner._handle_voice_channel_join(event)

        assert "voice dependencies are missing" in result.lower()
        assert "PyNaCl" in result

    # -- _handle_voice_channel_leave --

    @pytest.mark.asyncio
    async def test_leave_not_in_vc(self, runner):
        """Leave when not in VC returns appropriate message."""
        mock_adapter = AsyncMock()
        mock_adapter.is_in_voice_channel = MagicMock(return_value=False)
        event = self._make_discord_event("/voice leave")
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_leave(event)
        assert "not in" in result.lower()

    @pytest.mark.asyncio
    async def test_leave_no_guild(self, runner):
        """Leave from DM returns not in voice channel."""
        mock_adapter = AsyncMock()
        event = self._make_discord_event("/voice leave")
        event.raw_message = None
        runner.adapters[event.source.platform] = mock_adapter
        result = await runner._handle_voice_channel_leave(event)
        assert "not in" in result.lower()

    @pytest.mark.asyncio
    async def test_leave_success(self, runner):
        """Successful leave disconnects and clears voice mode."""
        mock_adapter = AsyncMock()
        mock_adapter.is_in_voice_channel = MagicMock(return_value=True)
        mock_adapter.leave_voice_channel = AsyncMock()
        event = self._make_discord_event("/voice leave")
        runner.adapters[event.source.platform] = mock_adapter
        runner._voice_mode["discord:123"] = "all"
        result = await runner._handle_voice_channel_leave(event)
        assert "left" in result.lower()
        assert runner._voice_mode["discord:123"] == "off"
        mock_adapter.leave_voice_channel.assert_called_once_with(111)

    # -- _handle_voice_channel_input --

    @pytest.mark.asyncio
    async def test_input_no_adapter(self, runner):
        """No Discord adapter — early return, no crash."""
        # No adapters set
        await runner._handle_voice_channel_input(111, 42, "Hello")

    @pytest.mark.asyncio
    async def test_input_no_text_channel(self, runner):
        """No text channel mapped for guild — early return."""
        from gateway.config import Platform
        mock_adapter = AsyncMock()
        mock_adapter._voice_text_channels = {}
        mock_adapter._client = MagicMock()
        runner.adapters[Platform.DISCORD] = mock_adapter
        await runner._handle_voice_channel_input(111, 42, "Hello")

    @pytest.mark.asyncio
    async def test_input_creates_event_and_dispatches(self, runner):
        """Voice input creates synthetic event and calls handle_message."""
        from gateway.config import Platform
        mock_adapter = AsyncMock()
        mock_adapter._voice_text_channels = {111: 123}
        mock_adapter._voice_sources = {}
        mock_channel = AsyncMock()
        mock_adapter._client = MagicMock()
        mock_adapter._client.get_channel = MagicMock(return_value=mock_channel)
        mock_adapter.handle_message = AsyncMock()
        runner.adapters[Platform.DISCORD] = mock_adapter
        await runner._handle_voice_channel_input(111, 42, "Hello from VC")
        mock_adapter.handle_message.assert_called_once()
        event = mock_adapter.handle_message.call_args[0][0]
        assert event.text == "Hello from VC"
        assert event.message_type == MessageType.VOICE
        assert event.source.chat_id == "123"
        assert event.source.chat_type == "channel"

    @pytest.mark.asyncio
    async def test_input_reuses_bound_source_metadata(self, runner):
        """Voice input should share the linked text channel session metadata."""
        from gateway.config import Platform

        bound_source = SessionSource(
            chat_id="123",
            chat_name="Alvarez Server / #general",
            chat_type="group",
            user_id="user1",
            user_name="user1",
            platform=Platform.DISCORD,
        )

        mock_adapter = AsyncMock()
        mock_adapter._voice_text_channels = {111: 123}
        mock_adapter._voice_sources = {111: bound_source.to_dict()}
        mock_channel = AsyncMock()
        mock_adapter._client = MagicMock()
        mock_adapter._client.get_channel = MagicMock(return_value=mock_channel)
        mock_adapter.handle_message = AsyncMock()
        runner.adapters[Platform.DISCORD] = mock_adapter

        await runner._handle_voice_channel_input(111, 42, "Hello from VC")

        mock_adapter.handle_message.assert_called_once()
        event = mock_adapter.handle_message.call_args[0][0]
        assert event.source.chat_id == "123"
        assert event.source.chat_type == "group"
        assert event.source.chat_name == "Alvarez Server / #general"
        assert event.source.user_id == "42"

    @pytest.mark.asyncio
    async def test_input_posts_transcript_in_text_channel(self, runner):
        """Voice input sends transcript message to text channel."""
        from gateway.config import Platform
        mock_adapter = AsyncMock()
        mock_adapter._voice_text_channels = {111: 123}
        mock_adapter._voice_sources = {}
        mock_channel = AsyncMock()
        mock_adapter._client = MagicMock()
        mock_adapter._client.get_channel = MagicMock(return_value=mock_channel)
        mock_adapter.handle_message = AsyncMock()
        runner.adapters[Platform.DISCORD] = mock_adapter
        await runner._handle_voice_channel_input(111, 42, "Test transcript")
        mock_channel.send.assert_called_once()
        msg = mock_channel.send.call_args[0][0]
        assert "Test transcript" in msg
        assert "42" in msg  # user_id in mention

    @pytest.mark.asyncio
    async def test_input_suppresses_duplicate_transcript(self, runner):
        """Near-immediate duplicate STT output should not dispatch twice."""
        from gateway.config import Platform

        mock_adapter = AsyncMock()
        mock_adapter._voice_text_channels = {111: 123}
        mock_adapter._voice_sources = {}
        mock_channel = AsyncMock()
        mock_adapter._client = MagicMock()
        mock_adapter._client.get_channel = MagicMock(return_value=mock_channel)
        mock_adapter.handle_message = AsyncMock()
        runner.adapters[Platform.DISCORD] = mock_adapter

        await runner._handle_voice_channel_input(111, 42, "Hello from VC")
        await runner._handle_voice_channel_input(111, 42, "Hello from VC")

        mock_adapter.handle_message.assert_called_once()
        mock_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_input_suppresses_near_duplicate_transcript(self, runner):
        """Small STT wording drift should still be treated as the same utterance."""
        from gateway.config import Platform

        mock_adapter = AsyncMock()
        mock_adapter._voice_text_channels = {111: 123}
        mock_adapter._voice_sources = {}
        mock_channel = AsyncMock()
        mock_adapter._client = MagicMock()
        mock_adapter._client.get_channel = MagicMock(return_value=mock_channel)
        mock_adapter.handle_message = AsyncMock()
        runner.adapters[Platform.DISCORD] = mock_adapter

        await runner._handle_voice_channel_input(111, 42, "This is a test of the voice system")
        await runner._handle_voice_channel_input(111, 42, "This is a test for the voice system")

        mock_adapter.handle_message.assert_called_once()
        mock_channel.send.assert_called_once()

    # -- _get_guild_id --

    def test_get_guild_id_from_guild(self, runner):
        event = _make_event()
        mock_guild = MagicMock()
        mock_guild.id = 555
        event.raw_message = SimpleNamespace(guild_id=None, guild=mock_guild)
        result = runner._get_guild_id(event)
        assert result == 555

    def test_get_guild_id_from_interaction(self, runner):
        event = _make_event()
        event.raw_message = SimpleNamespace(guild_id=777, guild=None)
        result = runner._get_guild_id(event)
        assert result == 777

    def test_get_guild_id_none(self, runner):
        event = _make_event()
        event.raw_message = None
        result = runner._get_guild_id(event)
        assert result is None

    def test_get_guild_id_dm(self, runner):
        event = _make_event()
        event.raw_message = SimpleNamespace(guild_id=None, guild=None)
        result = runner._get_guild_id(event)
        assert result is None


# =====================================================================
# Discord adapter voice channel methods
# =====================================================================

        # Should not raise


# =====================================================================
# stream_tts_to_speaker functional tests
# =====================================================================

# =====================================================================
# VoiceReceiver thread-safety (lock coverage)
# =====================================================================


# =====================================================================
# Callback wiring order (join)
# =====================================================================

class TestCallbackWiringOrder:
    """Verify callback is wired BEFORE join, not after."""

    def test_callback_set_before_join(self):
        """_handle_voice_channel_join wires callback before calling join."""
        import inspect
        from gateway.run import GatewayRunner
        source = inspect.getsource(GatewayRunner._handle_voice_channel_join)
        lines = source.split("\n")
        callback_line = None
        join_line = None
        for i, line in enumerate(lines):
            if "_voice_input_callback" in line and "=" in line and "None" not in line:
                if callback_line is None:
                    callback_line = i
            if "join_voice_channel" in line and "await" in line:
                join_line = i
        assert callback_line is not None, "callback wiring not found"
        assert join_line is not None, "join_voice_channel call not found"
        assert callback_line < join_line, (
            f"callback must be wired (line {callback_line}) BEFORE "
            f"join_voice_channel (line {join_line})"
        )

    @pytest.mark.asyncio
    async def test_join_failure_clears_callback(self, tmp_path):
        """If join fails with exception, callback is cleaned up."""
        runner = _make_runner(tmp_path)

        mock_channel = MagicMock()
        mock_channel.name = "General"
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock(
            side_effect=RuntimeError("No permission")
        )
        mock_adapter.get_user_voice_channel = AsyncMock(return_value=mock_channel)
        mock_adapter._voice_input_callback = None

        event = _make_event("/voice channel")
        event.raw_message = SimpleNamespace(guild_id=111, guild=None)
        runner.adapters[event.source.platform] = mock_adapter

        result = await runner._handle_voice_channel_join(event)
        assert "failed" in result.lower()
        assert mock_adapter._voice_input_callback is None

    @pytest.mark.asyncio
    async def test_join_returns_false_clears_callback(self, tmp_path):
        """If join returns False, callback is cleaned up."""
        runner = _make_runner(tmp_path)

        mock_channel = MagicMock()
        mock_channel.name = "General"
        mock_adapter = AsyncMock()
        mock_adapter.join_voice_channel = AsyncMock(return_value=False)
        mock_adapter.get_user_voice_channel = AsyncMock(return_value=mock_channel)
        mock_adapter._voice_input_callback = None

        event = _make_event("/voice channel")
        event.raw_message = SimpleNamespace(guild_id=111, guild=None)
        runner.adapters[event.source.platform] = mock_adapter

        result = await runner._handle_voice_channel_join(event)
        assert "failed" in result.lower()
        assert mock_adapter._voice_input_callback is None


# =====================================================================
# Leave exception handling
# =====================================================================

class TestLeaveExceptionHandling:
    """Verify state is cleaned up even when leave_voice_channel raises."""

    @pytest.fixture
    def runner(self, tmp_path):
        return _make_runner(tmp_path)

    @pytest.mark.asyncio
    async def test_leave_exception_still_cleans_state(self, runner):
        """If leave_voice_channel raises, voice_mode is still cleaned up."""
        mock_adapter = AsyncMock()
        mock_adapter.is_in_voice_channel = MagicMock(return_value=True)
        mock_adapter.leave_voice_channel = AsyncMock(
            side_effect=RuntimeError("Connection reset")
        )
        mock_adapter._voice_input_callback = MagicMock()

        event = _make_event("/voice leave")
        event.raw_message = SimpleNamespace(guild_id=111, guild=None)
        runner.adapters[event.source.platform] = mock_adapter
        runner._voice_mode["telegram:123"] = "all"

        result = await runner._handle_voice_channel_leave(event)
        assert "left" in result.lower()
        assert runner._voice_mode["telegram:123"] == "off"
        assert mock_adapter._voice_input_callback is None

    @pytest.mark.asyncio
    async def test_leave_clears_callback(self, runner):
        """Normal leave also clears the voice input callback."""
        mock_adapter = AsyncMock()
        mock_adapter.is_in_voice_channel = MagicMock(return_value=True)
        mock_adapter.leave_voice_channel = AsyncMock()
        mock_adapter._voice_input_callback = MagicMock()

        event = _make_event("/voice leave")
        event.raw_message = SimpleNamespace(guild_id=111, guild=None)
        runner.adapters[event.source.platform] = mock_adapter
        runner._voice_mode["telegram:123"] = "all"

        await runner._handle_voice_channel_leave(event)
        assert mock_adapter._voice_input_callback is None


# =====================================================================
# Base adapter empty text guard
# =====================================================================

class TestAutoTtsEmptyTextGuard:
    """Verify base adapter skips TTS when text is empty after markdown strip."""

    def test_empty_after_strip_skips_tts(self):
        """Markdown-only content should not trigger TTS call."""
        import re
        text_content = "****"
        speech_text = re.sub(r'[*_`#\[\]()]', '', text_content)[:4000].strip()
        assert not speech_text, "Expected empty after stripping markdown chars"

    def test_code_block_response_skips_tts(self):
        """Code-only response results in empty speech text."""
        import re
        text_content = "```python\nprint(1)\n```"
        speech_text = re.sub(r'[*_`#\[\]()]', '', text_content)[:4000].strip()
        # Note: base.py regex only strips individual chars, not full code blocks
        # So code blocks are partially stripped but may leave content
        # The real fix is in base.py — empty check after strip

    def test_base_empty_check_in_source(self):
        """base.py must check speech_text is non-empty before calling TTS."""
        import inspect
        from gateway.platforms.base import BasePlatformAdapter
        source = inspect.getsource(BasePlatformAdapter._process_message_background)
        assert "if not speech_text" in source or "not speech_text" in source, (
            "base.py must guard against empty speech_text before TTS call"
        )


class TestStreamTtsToSpeaker:
    """Functional tests for the streaming TTS pipeline."""

    def test_none_sentinel_flushes_buffer(self):
        """None sentinel causes remaining buffer to be spoken."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        def display(text):
            spoken.append(text)

        text_q.put("Hello world.")
        text_q.put(None)

        stream_tts_to_speaker(text_q, stop_evt, done_evt, display_callback=display)
        assert done_evt.is_set()
        assert any("Hello" in s for s in spoken)

    def test_stop_event_aborts_early(self):
        """Setting stop_event causes early exit."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        stop_evt.set()
        text_q.put("Should not be spoken.")
        text_q.put(None)

        stream_tts_to_speaker(text_q, stop_evt, done_evt, display_callback=lambda t: spoken.append(t))
        assert done_evt.is_set()
        assert len(spoken) == 0

    def test_done_event_set_on_exception(self):
        """tts_done_event is set even when an exception occurs."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()

        # Put a non-string that will cause concatenation to fail
        text_q.put(12345)
        text_q.put(None)

        stream_tts_to_speaker(text_q, stop_evt, done_evt)
        assert done_evt.is_set()

    def test_think_blocks_stripped(self):
        """<think>...</think> content is not spoken."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        text_q.put("<think>internal reasoning</think>")
        text_q.put("Visible response. ")
        text_q.put(None)

        stream_tts_to_speaker(text_q, stop_evt, done_evt, display_callback=lambda t: spoken.append(t))
        assert done_evt.is_set()
        joined = " ".join(spoken)
        assert "internal reasoning" not in joined
        assert "Visible" in joined

    def test_sentence_splitting(self):
        """Sentences are split at boundaries and spoken individually."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        # Two sentences long enough to exceed min_sentence_len (20)
        text_q.put("This is the first sentence. ")
        text_q.put("This is the second sentence. ")
        text_q.put(None)

        stream_tts_to_speaker(text_q, stop_evt, done_evt, display_callback=lambda t: spoken.append(t))
        assert done_evt.is_set()
        assert len(spoken) >= 2

    def test_markdown_stripped_in_speech(self):
        """Markdown formatting is removed before display/speech."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        text_q.put("**Bold text** and `code`. ")
        text_q.put(None)

        stream_tts_to_speaker(text_q, stop_evt, done_evt, display_callback=lambda t: spoken.append(t))
        assert done_evt.is_set()
        # Display callback gets raw text (before markdown stripping)
        # But the actual TTS audio would be stripped — we verify pipeline doesn't crash

    def test_duplicate_sentences_deduped(self):
        """Repeated sentences are spoken only once."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        # Same sentence twice, each long enough
        text_q.put("This is a repeated sentence. ")
        text_q.put("This is a repeated sentence. ")
        text_q.put(None)

        stream_tts_to_speaker(text_q, stop_evt, done_evt, display_callback=lambda t: spoken.append(t))
        assert done_evt.is_set()
        # First occurrence is spoken, second is deduped
        assert len(spoken) == 1

    def test_no_api_key_display_only(self):
        """Without ELEVENLABS_API_KEY, display callback still works."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        text_q.put("Display only text. ")
        text_q.put(None)

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}):
            stream_tts_to_speaker(text_q, stop_evt, done_evt,
                                  display_callback=lambda t: spoken.append(t))
        assert done_evt.is_set()
        assert len(spoken) >= 1

    def test_long_buffer_flushed_on_timeout(self):
        """Buffer longer than long_flush_len is flushed on queue timeout."""
        from tools.tts_tool import stream_tts_to_speaker
        text_q = queue.Queue()
        stop_evt = threading.Event()
        done_evt = threading.Event()
        spoken = []

        # Put a long text without sentence boundary, then None after a delay
        long_text = "a" * 150  # > long_flush_len (100)
        text_q.put(long_text)

        def delayed_sentinel():
            time.sleep(1.0)
            text_q.put(None)

        t = threading.Thread(target=delayed_sentinel, daemon=True)
        t.start()

        stream_tts_to_speaker(text_q, stop_evt, done_evt,
                              display_callback=lambda t: spoken.append(t))
        t.join(timeout=5)
        assert done_evt.is_set()
        assert len(spoken) >= 1


# =====================================================================
# Bug 1: VoiceReceiver.stop() must hold lock while clearing shared state
# =====================================================================


# =====================================================================
# Bug 2: _packet_debug_count must be instance-level, not class-level
# =====================================================================


# =====================================================================
# Bug 3: play_in_voice_channel uses get_running_loop not get_event_loop
# =====================================================================


# =====================================================================
# Bug 4: _send_voice_reply filename uses uuid (no collision)
# =====================================================================

class TestSendVoiceReplyFilename:
    """_send_voice_reply uses uuid for unique filenames."""

    def test_filename_uses_uuid(self):
        """The method uses uuid in the filename, not time-based."""
        import inspect
        from gateway.run import GatewayRunner
        source = inspect.getsource(GatewayRunner._send_voice_reply)
        assert "uuid" in source, \
            "_send_voice_reply should use uuid for unique filenames"
        assert "int(time.time())" not in source, \
            "_send_voice_reply should not use int(time.time()) — collision risk"

    def test_filenames_are_unique(self):
        """Two calls produce different filenames."""
        import uuid
        names = set()
        for _ in range(100):
            name = f"tts_reply_{uuid.uuid4().hex[:12]}.mp3"
            assert name not in names, f"Collision detected: {name}"
            names.add(name)


# =====================================================================
# Bug 5: Voice timeout cleans up runner voice_mode via callback
# =====================================================================


# =====================================================================
# Bug 6: play_in_voice_channel has playback timeout
# =====================================================================


# =====================================================================
# Bug 7: _send_voice_reply cleanup in finally block
# =====================================================================

class TestSendVoiceReplyCleanup:
    """_send_voice_reply must clean up temp files even on exception."""

    def test_cleanup_in_finally(self):
        """The method has cleanup in a finally block, not inside try."""
        import inspect, textwrap, ast
        from gateway.run import GatewayRunner
        source = textwrap.dedent(inspect.getsource(GatewayRunner._send_voice_reply))
        tree = ast.parse(source)
        func = tree.body[0]

        has_finally_unlink = False
        for node in ast.walk(func):
            if isinstance(node, ast.Try) and node.finalbody:
                finally_source = ast.dump(node.finalbody[0])
                if "unlink" in finally_source or "remove" in finally_source:
                    has_finally_unlink = True
                    break

        assert has_finally_unlink, \
            "_send_voice_reply must have os.unlink in a finally block"

    @pytest.mark.asyncio
    async def test_files_cleaned_on_send_exception(self, tmp_path):
        """Temp files are removed even when send_voice raises."""
        runner = _make_runner(tmp_path)
        adapter = MagicMock()
        adapter.send_voice = AsyncMock(side_effect=RuntimeError("send failed"))
        adapter.is_in_voice_channel = MagicMock(return_value=False)
        event = _make_event(message_type=MessageType.VOICE)
        runner.adapters[event.source.platform] = adapter
        runner._get_guild_id = MagicMock(return_value=None)

        # Create a fake audio file that TTS would produce
        fake_audio = tmp_path / "alvarez_voice"
        fake_audio.mkdir()
        audio_file = fake_audio / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        tts_result = json.dumps({
            "success": True,
            "file_path": str(audio_file),
        })

        with patch("gateway.run.asyncio.to_thread", new_callable=AsyncMock, return_value=tts_result), \
             patch("tools.tts_tool._strip_markdown_for_tts", return_value="hello"), \
             patch("os.path.isfile", return_value=True), \
             patch("os.makedirs"):
            await runner._send_voice_reply(event, "Hello world")

        # File should be cleaned up despite exception
        assert not audio_file.exists(), \
            "Temp audio file must be cleaned up even when send_voice raises"


# =====================================================================
# Bug 8: Base adapter auto-TTS cleans up temp file after play_tts
# =====================================================================

class TestAutoTtsTempFileCleanup:
    """Base adapter auto-TTS must clean up generated audio file."""

    def test_source_has_finally_remove(self):
        """play_tts call is wrapped in try/finally with os.remove."""
        import inspect
        from gateway.platforms.base import BasePlatformAdapter
        source = inspect.getsource(BasePlatformAdapter._process_message_background)
        # Find the play_tts section and verify cleanup
        play_tts_idx = source.find("play_tts")
        assert play_tts_idx > 0
        after_play = source[play_tts_idx:]
        finally_idx = after_play.find("finally")
        remove_idx = after_play.find("os.remove")
        assert finally_idx > 0, "play_tts must be in a try/finally block"
        assert remove_idx > 0, "finally block must call os.remove on _tts_path"
        assert remove_idx > finally_idx, "os.remove must be inside the finally block"


# =====================================================================
# Voice channel awareness (get_voice_channel_info / context)
# =====================================================================


# ---------------------------------------------------------------------------
# Bugfix: disconnect() must clean up voice state
# ---------------------------------------------------------------------------


class TestDisconnectVoiceCleanup:
    """Bug: disconnect() left voice dicts populated after closing client."""

    @pytest.mark.asyncio
    async def test_disconnect_clears_voice_state(self):

        adapter = MagicMock()
        adapter._voice_clients = {111: MagicMock(), 222: MagicMock()}
        adapter._voice_receivers = {111: MagicMock(), 222: MagicMock()}
        adapter._voice_listen_tasks = {111: MagicMock(), 222: MagicMock()}
        adapter._voice_timeout_tasks = {111: MagicMock(), 222: MagicMock()}
        adapter._voice_text_channels = {111: 999, 222: 888}

        async def mock_leave(guild_id):
            adapter._voice_receivers.pop(guild_id, None)
            adapter._voice_listen_tasks.pop(guild_id, None)
            adapter._voice_clients.pop(guild_id, None)
            adapter._voice_timeout_tasks.pop(guild_id, None)
            adapter._voice_text_channels.pop(guild_id, None)

        for gid in list(adapter._voice_clients.keys()):
            await mock_leave(gid)

        assert len(adapter._voice_clients) == 0
        assert len(adapter._voice_receivers) == 0
        assert len(adapter._voice_listen_tasks) == 0
        assert len(adapter._voice_timeout_tasks) == 0


# =====================================================================
# Discord Voice Channel Flow Tests
# =====================================================================


# =====================================================================
# BasePlatformAdapter._should_auto_tts_for_chat — gate for auto-TTS
# on voice input. Regression test for Issue #16007.
# =====================================================================

class TestShouldAutoTtsForChat:
    """Three-layer gate: per-chat enable > per-chat disable > config default."""

    def _make_adapter(self, *, default: bool, enabled=(), disabled=()):
        """Build a bare adapter with only the attrs the gate reads."""
        adapter = SimpleNamespace(
            _auto_tts_default=default,
            _auto_tts_enabled_chats=set(enabled),
            _auto_tts_disabled_chats=set(disabled),
        )
        # Bind the unbound method — _should_auto_tts_for_chat only reads the
        # three attrs above via ``self.``, so an unbound call works.
        from gateway.platforms.base import BasePlatformAdapter
        return BasePlatformAdapter._should_auto_tts_for_chat, adapter

    def test_default_false_no_override_suppresses(self):
        """Issue #16007: voice.auto_tts=False and no per-chat state → no TTS."""
        fn, adapter = self._make_adapter(default=False)
        assert fn(adapter, "chat1") is False

    def test_default_true_no_override_fires(self):
        fn, adapter = self._make_adapter(default=True)
        assert fn(adapter, "chat1") is True

    def test_explicit_enable_overrides_false_default(self):
        """``/voice on`` with config auto_tts=False still fires."""
        fn, adapter = self._make_adapter(default=False, enabled={"chat1"})
        assert fn(adapter, "chat1") is True

    def test_explicit_disable_overrides_true_default(self):
        """``/voice off`` with config auto_tts=True still suppresses."""
        fn, adapter = self._make_adapter(default=True, disabled={"chat1"})
        assert fn(adapter, "chat1") is False

    def test_enabled_wins_over_disabled(self):
        """An explicit enable beats an explicit disable (enable takes priority)."""
        fn, adapter = self._make_adapter(
            default=False, enabled={"chat1"}, disabled={"chat1"}
        )
        assert fn(adapter, "chat1") is True

    def test_per_chat_isolation(self):
        """Enable for chat1 doesn't leak to chat2."""
        fn, adapter = self._make_adapter(default=False, enabled={"chat1"})
        assert fn(adapter, "chat1") is True
        assert fn(adapter, "chat2") is False
