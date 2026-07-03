"""Tests for tools/send_message_tool.py."""

import asyncio
import json
import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# python-telegram-bot is an optional dep — skip the entire module when
# it isn't installed (e.g. CI bare env). Tests that patch telegram.Bot
# or call _send_telegram need it; tests for other platforms don't but
# keeping the whole file consistent is simpler.
_HAS_TELEGRAM = pytest.importorskip("telegram", reason="python-telegram-bot not installed") is not None


from gateway.config import Platform
from tools.send_message_tool import (
    _is_telegram_thread_not_found,
    _parse_target_ref,
    _send_telegram,
    _send_to_platform,
    send_message_tool,
)


def _run_async_immediately(coro):
    return asyncio.run(coro)


def _make_config():
    telegram_cfg = SimpleNamespace(enabled=True, token="***", extra={})
    return SimpleNamespace(
        platforms={Platform.TELEGRAM: telegram_cfg},
        get_home_channel=lambda _platform: None,
    ), telegram_cfg


def _install_telegram_mock(monkeypatch, bot):
    parse_mode = SimpleNamespace(MARKDOWN_V2="MarkdownV2", HTML="HTML")
    constants_mod = SimpleNamespace(ParseMode=parse_mode)
    # MessageEntity needed by #27865 mention-detection path; tests don't
    # inspect it but the import must succeed.
    _MessageEntity = lambda **_kw: SimpleNamespace(**_kw)
    telegram_mod = SimpleNamespace(Bot=lambda token: bot, MessageEntity=_MessageEntity, constants=constants_mod)
    monkeypatch.setitem(sys.modules, "telegram", telegram_mod)
    monkeypatch.setitem(sys.modules, "telegram.constants", constants_mod)


class TestSendMessageTool:


    def test_cron_duplicate_target_is_skipped_and_explained(self):
        home = SimpleNamespace(chat_id="-1001")
        config, _telegram_cfg = _make_config()
        config.get_home_channel = lambda _platform: home

        with patch.dict(
            os.environ,
            {
                "ALVAREZ_CRON_AUTO_DELIVER_PLATFORM": "telegram",
                "ALVAREZ_CRON_AUTO_DELIVER_CHAT_ID": "-1001",
            },
            clear=False,
        ), \
             patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True) as mirror_mock:
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        assert result["skipped"] is True
        assert result["reason"] == "cron_auto_delivery_duplicate_target"
        assert "final response" in result["note"]
        send_mock.assert_not_awaited()
        mirror_mock.assert_not_called()

    def test_resolved_telegram_topic_name_preserves_thread_id(self):
        config, telegram_cfg = _make_config()

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("gateway.channel_directory.resolve_channel_name", return_value="-1001:17585"), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:Coaching Chat / topic 17585",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        send_mock.assert_awaited_once_with(
            Platform.TELEGRAM,
            telegram_cfg,
            "-1001",
            "hello",
            thread_id="17585",
            media_files=[],
            force_document=False,
        )

    def test_display_label_target_resolves_via_channel_directory(self, tmp_path):
        config, telegram_cfg = _make_config()
        cache_file = tmp_path / "channel_directory.json"
        cache_file.write_text(json.dumps({
            "updated_at": "2026-01-01T00:00:00",
            "platforms": {
                "telegram": [
                    {"id": "-1001:17585", "name": "Coaching Chat / topic 17585", "type": "group"}
                ]
            },
        }))

        with patch("gateway.channel_directory.DIRECTORY_PATH", cache_file), \
             patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:Coaching Chat / topic 17585 (group)",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        send_mock.assert_awaited_once_with(
            Platform.TELEGRAM,
            telegram_cfg,
            "-1001",
            "hello",
            thread_id="17585",
            media_files=[],
            force_document=False,
        )

    def test_resolved_slack_thread_name_preserves_thread_id(self):
        slack_cfg = SimpleNamespace(enabled=True, token="xoxb-test", extra={})
        config = SimpleNamespace(
            platforms={Platform.SLACK: slack_cfg},
            get_home_channel=lambda _platform: None,
        )

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("gateway.channel_directory.resolve_channel_name", return_value="C123ABCDEF:171.000001"), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "slack:ops / topic 171.000001",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        send_mock.assert_awaited_once_with(
            Platform.SLACK,
            slack_cfg,
            "C123ABCDEF",
            "hello",
            thread_id="171.000001",
            media_files=[],
            force_document=False,
        )

    def test_resolved_matrix_thread_name_preserves_thread_id(self):
        matrix_cfg = SimpleNamespace(
            enabled=True,
            token="tok",
            extra={"homeserver": "https://matrix.example.com"},
        )
        config = SimpleNamespace(
            platforms={Platform.MATRIX: matrix_cfg},
            get_home_channel=lambda _platform: None,
        )

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch(
                 "gateway.channel_directory.resolve_channel_name",
                 return_value="!roomid:matrix.example.org:$thread123:matrix.example.org",
             ), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "matrix:Ops / topic $thread123",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        send_mock.assert_awaited_once_with(
            Platform.MATRIX,
            matrix_cfg,
            "!roomid:matrix.example.org",
            "hello",
            thread_id="$thread123:matrix.example.org",
            media_files=[],
            force_document=False,
        )

    def test_mirror_receives_current_session_user_id(self):
        config, _telegram_cfg = _make_config()

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})), \
             patch("gateway.session_context.get_session_env") as get_session_env_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True) as mirror_mock:
            get_session_env_mock.side_effect = lambda name, default="": {
                "ALVAREZ_SESSION_PLATFORM": "telegram",
                "ALVAREZ_SESSION_USER_ID": "user-123",
            }.get(name, default)
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:12345",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        mirror_mock.assert_called_once_with(
            "telegram",
            "12345",
            "hello",
            source_label="telegram",
            thread_id=None,
            user_id="user-123",
        )

    def test_media_tag_outside_allowed_roots_is_not_sent(self, tmp_path, monkeypatch):
        # This test exercises the strict-allowlist path; force strict mode on
        # and disable recency trust so the freshly-written tmp_path file is
        # not auto-accepted by the trust window. (Recency trust is covered
        # in test_platform_base.py. The public default flipped to non-strict
        # in 2026-05; this test pins strict on explicitly.)
        monkeypatch.setenv("ALVAREZ_MEDIA_DELIVERY_STRICT", "1")
        monkeypatch.setenv("ALVAREZ_MEDIA_TRUST_RECENT_FILES", "0")
        config, telegram_cfg = _make_config()
        secret = tmp_path / "secret.pdf"
        secret.write_bytes(b"%PDF secret")

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:12345",
                        "message": f"hello\nMEDIA:{secret}",
                    }
                )
            )

        assert result["success"] is True
        send_mock.assert_awaited_once_with(
            Platform.TELEGRAM,
            telegram_cfg,
            "12345",
            "hello",
            thread_id=None,
            media_files=[],
            force_document=False,
        )

    def test_top_level_send_failure_redacts_query_token(self):
        config, _telegram_cfg = _make_config()
        leaked = "very-secret-query-token-123456"

        def _raise_and_close(coro):
            coro.close()
            raise RuntimeError(
                f"transport error: https://api.example.com/send?access_token={leaked}"
            )

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_raise_and_close):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:-1001",
                        "message": "hello",
                    }
                )
            )

        assert "error" in result
        assert leaked not in result["error"]
        assert "access_token=***" in result["error"]


class TestSendTelegramMediaDelivery:
    def test_sends_text_then_photo_for_media_tag(self, tmp_path, monkeypatch):
        image_path = tmp_path / "photo.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
        bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=2))
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "Hello there",
                media_files=[(str(image_path), False)],
            )
        )

        assert result["success"] is True
        assert result["message_id"] == "2"
        bot.send_message.assert_awaited_once()
        bot.send_photo.assert_awaited_once()
        sent_text = bot.send_message.await_args.kwargs["text"]
        assert "MEDIA:" not in sent_text
        assert sent_text == "Hello there"

    def test_sends_voice_for_ogg_with_voice_directive(self, tmp_path, monkeypatch):
        voice_path = tmp_path / "voice.ogg"
        voice_path.write_bytes(b"OggS" + b"\x00" * 32)

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock(return_value=SimpleNamespace(message_id=7))
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "",
                media_files=[(str(voice_path), True)],
            )
        )

        assert result["success"] is True
        bot.send_voice.assert_awaited_once()
        bot.send_audio.assert_not_awaited()
        bot.send_message.assert_not_awaited()

    def test_sends_audio_for_mp3(self, tmp_path, monkeypatch):
        audio_path = tmp_path / "clip.mp3"
        audio_path.write_bytes(b"ID3" + b"\x00" * 32)

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock(return_value=SimpleNamespace(message_id=8))
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "",
                media_files=[(str(audio_path), False)],
            )
        )

        assert result["success"] is True
        bot.send_audio.assert_awaited_once()
        bot.send_voice.assert_not_awaited()

    def test_missing_media_returns_error_without_leaking_raw_tag(self, monkeypatch):
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "",
                media_files=[("/tmp/does-not-exist.png", False)],
            )
        )

        assert "error" in result
        assert "No deliverable text or media remained" in result["error"]
        bot.send_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Regression: long messages are chunked before platform dispatch
# ---------------------------------------------------------------------------


class TestSendToPlatformChunking:


    def test_telegram_markdown_expansion_is_chunked_before_send(self, monkeypatch):
        """Telegram chunking must account for MarkdownV2 escaping expansion.

        A raw message under 4096 UTF-16 units can inflate past the limit once
        MarkdownV2-escaped (each `!`/`.`/`-` becomes `\\!`/`\\.`/`\\-`). The
        send path must chunk the *formatted* text so no single send exceeds
        4096 (issue #28557).
        """
        from gateway.platforms.base import utf16_len

        send_lengths = []

        async def fake_send_message(**kwargs):
            text = kwargs["text"]
            send_lengths.append(utf16_len(text))
            if utf16_len(text) > 4096:
                raise Exception("Message is too long")
            return SimpleNamespace(message_id=len(send_lengths))

        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=fake_send_message)
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_to_platform(
                Platform.TELEGRAM,
                SimpleNamespace(enabled=True, token="tok", extra={}),
                "123",
                "!" * 4096,  # raw 4096 -> ~8192 after MarkdownV2 escaping
            )
        )

        assert result["success"] is True
        assert bot.send_message.await_count >= 2
        assert max(send_lengths) <= 4096

    def test_telegram_media_attaches_after_long_text_chunks(self, tmp_path, monkeypatch):
        """Long text is split into multiple chunks, then media is attached."""
        image_path = tmp_path / "photo.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
        bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=2))
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        long_msg = "word " * 2000  # ~10000 chars, well over Telegram's 4096 limit
        result = asyncio.run(
            _send_to_platform(
                Platform.TELEGRAM,
                SimpleNamespace(enabled=True, token="tok", extra={}),
                "123",
                long_msg,
                media_files=[(str(image_path), False)],
            )
        )

        assert result["success"] is True
        assert bot.send_message.await_count >= 3
        bot.send_photo.assert_awaited_once()


# ---------------------------------------------------------------------------
# HTML auto-detection in Telegram send
# ---------------------------------------------------------------------------


class TestSendTelegramHtmlDetection:
    """Verify that messages containing HTML tags are sent with parse_mode=HTML
    and that plain / markdown messages use MarkdownV2."""

    def _make_bot(self):
        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        return bot

    def test_html_message_uses_html_parse_mode(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(
            _send_telegram("tok", "123", "<b>Hello</b> world")
        )

        bot.send_message.assert_awaited_once()
        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "HTML"
        assert kwargs["text"] == "<b>Hello</b> world"

    def test_plain_text_uses_markdown_v2(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(
            _send_telegram("tok", "123", "Just plain text, no tags")
        )

        bot.send_message.assert_awaited_once()
        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "MarkdownV2"

    def test_disable_link_previews_sets_disable_web_page_preview(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(
            _send_telegram("tok", "123", "https://example.com", disable_link_previews=True)
        )

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["disable_web_page_preview"] is True

    def test_html_with_code_and_pre_tags(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        html = "<pre>code block</pre> and <code>inline</code>"
        asyncio.run(_send_telegram("tok", "123", html))

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "HTML"

    def test_closing_tag_detected(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "123", "text </div> more"))

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "HTML"

    def test_angle_brackets_in_math_not_detected(self, monkeypatch):
        """Expressions like 'x < 5' or '3 > 2' should not trigger HTML mode."""
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "123", "if x < 5 then y > 2"))

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "MarkdownV2"

    def test_html_parse_failure_falls_back_to_plain(self, monkeypatch):
        """If Telegram rejects the HTML, fall back to plain text."""
        bot = self._make_bot()
        bot.send_message = AsyncMock(
            side_effect=[
                Exception("Bad Request: can't parse entities: unsupported html tag"),
                SimpleNamespace(message_id=2),  # plain fallback succeeds
            ]
        )
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram("tok", "123", "<invalid>broken html</invalid>")
        )

        assert result["success"] is True
        assert bot.send_message.await_count == 2
        second_call = bot.send_message.await_args_list[1].kwargs
        assert second_call["parse_mode"] is None

    def test_transient_bad_gateway_retries_text_send(self, monkeypatch):
        bot = self._make_bot()
        bot.send_message = AsyncMock(
            side_effect=[
                Exception("502 Bad Gateway"),
                SimpleNamespace(message_id=2),
            ]
        )
        _install_telegram_mock(monkeypatch, bot)

        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = asyncio.run(_send_telegram("tok", "123", "hello"))

        assert result["success"] is True
        assert bot.send_message.await_count == 2
        sleep_mock.assert_awaited_once()


class TestSendTelegramThreadIdMapping:
    """General-topic mapping in _send_telegram (issue #22267).

    Telegram forum supergroups address the General topic as
    ``message_thread_id="1"`` on incoming updates, but the Bot API rejects
    sends with ``message_thread_id=1`` ("Message thread not found"). The
    gateway adapter's ``_message_thread_id_for_send`` helper maps "1" to
    ``None`` for that reason; the standalone ``_send_telegram`` helper used
    by the ``send_message`` tool needs the same mapping.
    """

    def _make_bot(self):
        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
        return bot

    def test_general_topic_thread_id_omitted(self, monkeypatch):
        """thread_id="1" must be dropped before calling the Bot API."""
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "-1001234567890", "hello", thread_id="1"))

        bot.send_message.assert_awaited_once()
        kwargs = bot.send_message.await_args.kwargs
        assert "message_thread_id" not in kwargs

    def test_non_general_topic_thread_id_preserved(self, monkeypatch):
        """Real forum-topic thread ids (>1) still pass through as ints."""
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "-1001234567890", "hello", thread_id="17585"))

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["message_thread_id"] == 17585

    def test_no_thread_id_no_kwarg(self, monkeypatch):
        """With no thread_id, message_thread_id must not appear in kwargs."""
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "-1001234567890", "hello"))

        kwargs = bot.send_message.await_args.kwargs
        assert "message_thread_id" not in kwargs

    def test_general_topic_thread_id_int_input_also_dropped(self, monkeypatch):
        """thread_id passed as the int 1 (not str) must still be dropped."""
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "-1001234567890", "hello", thread_id=1))

        kwargs = bot.send_message.await_args.kwargs
        assert "message_thread_id" not in kwargs

    def test_thread_not_found_retries_without_message_thread_id(self, monkeypatch):
        """When send_message raises "thread not found", retry without thread_id (#27012)."""
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        # First call raises thread-not-found, second succeeds
        bot.send_message = AsyncMock(side_effect=[
            Exception("Bad Request: message thread not found"),
            SimpleNamespace(message_id=2),
        ])

        asyncio.run(
            _send_telegram("tok", "-1001234567890", "hello", thread_id="17585")
        )

        assert bot.send_message.await_count == 2
        # First call: should include message_thread_id=17585
        call1_kwargs = bot.send_message.await_args_list[0].kwargs
        assert call1_kwargs["message_thread_id"] == 17585
        # Second call (retry): should NOT include message_thread_id
        call2_kwargs = bot.send_message.await_args_list[1].kwargs
        assert "message_thread_id" not in call2_kwargs

    def test_thread_not_found_for_media_retries_without_message_thread_id(self, monkeypatch, tmp_path):
        """Media send with stale thread_id retries without it (#27012)."""
        bot = self._make_bot()
        # Mock send_document to fail with thread-not-found, then succeed
        bot.send_document = AsyncMock(side_effect=[
            Exception("Bad Request: message thread not found"),
            SimpleNamespace(message_id=3),
        ])
        _install_telegram_mock(monkeypatch, bot)

        # Create a test file
        test_file = tmp_path / "doc.txt"
        test_file.write_text("test content")

        asyncio.run(
            _send_telegram(
                "tok", "-1001234567890", "",
                media_files=[(str(test_file), False)],
                thread_id="17585",
            )
        )

        assert bot.send_document.await_count == 2
        # First call: should include message_thread_id=17585
        call1_kwargs = bot.send_document.await_args_list[0].kwargs
        assert call1_kwargs["message_thread_id"] == 17585
        # Second call (retry): should NOT include message_thread_id
        call2_kwargs = bot.send_document.await_args_list[1].kwargs
        assert "message_thread_id" not in call2_kwargs


# ---------------------------------------------------------------------------
# Tests for Discord thread_id support
# ---------------------------------------------------------------------------


class TestParseTargetRefDiscord:
    """_parse_target_ref correctly extracts chat_id and thread_id for Discord."""

    def test_discord_chat_id_with_thread_id(self):
        """discord:chat_id:thread_id returns both values."""
        chat_id, thread_id, is_explicit = _parse_target_ref("discord", "-1001234567890:17585")
        assert chat_id == "-1001234567890"
        assert thread_id == "17585"
        assert is_explicit is True

    def test_discord_chat_id_without_thread_id(self):
        """discord:chat_id returns None for thread_id."""
        chat_id, thread_id, is_explicit = _parse_target_ref("discord", "9876543210")
        assert chat_id == "9876543210"
        assert thread_id is None
        assert is_explicit is True

    def test_discord_large_snowflake_without_thread(self):
        """Large Discord snowflake IDs work without thread."""
        chat_id, thread_id, is_explicit = _parse_target_ref("discord", "1003724596514")
        assert chat_id == "1003724596514"
        assert thread_id is None
        assert is_explicit is True

    def test_discord_channel_with_thread(self):
        """Full Discord format: channel:thread."""
        chat_id, thread_id, is_explicit = _parse_target_ref("discord", "1003724596514:99999")
        assert chat_id == "1003724596514"
        assert thread_id == "99999"
        assert is_explicit is True

    def test_discord_whitespace_is_stripped(self):
        """Whitespace around Discord targets is stripped."""
        chat_id, thread_id, is_explicit = _parse_target_ref("discord", "  123456:789  ")
        assert chat_id == "123456"
        assert thread_id == "789"
        assert is_explicit is True


class TestParseTargetRefMatrix:
    """_parse_target_ref correctly handles Matrix room IDs and user MXIDs."""

    def test_matrix_thread_target_is_explicit(self):
        """Session-derived Matrix thread targets round-trip as room + event id."""
        chat_id, thread_id, is_explicit = _parse_target_ref(
            "matrix",
            "!HLOQwxYGgFPMPJUSNR:matrix.org:$thread123:matrix.org",
        )
        assert chat_id == "!HLOQwxYGgFPMPJUSNR:matrix.org"
        assert thread_id == "$thread123:matrix.org"
        assert is_explicit is True

    def test_matrix_room_id_is_explicit(self):
        """Matrix room IDs (!) are recognized as explicit targets."""
        chat_id, thread_id, is_explicit = _parse_target_ref("matrix", "!HLOQwxYGgFPMPJUSNR:matrix.org")
        assert chat_id == "!HLOQwxYGgFPMPJUSNR:matrix.org"
        assert thread_id is None
        assert is_explicit is True

    def test_matrix_user_mxid_is_explicit(self):
        """Matrix user MXIDs (@) are recognized as explicit targets."""
        chat_id, thread_id, is_explicit = _parse_target_ref("matrix", "@alvarez:matrix.org")
        assert chat_id == "@alvarez:matrix.org"
        assert thread_id is None
        assert is_explicit is True

    def test_matrix_alias_is_not_explicit(self):
        """Matrix room aliases (#) are NOT explicit — they need resolution."""
        chat_id, thread_id, is_explicit = _parse_target_ref("matrix", "#general:matrix.org")
        assert chat_id is None
        assert is_explicit is False

    def test_matrix_prefix_only_matches_matrix_platform(self):
        """! and @ prefixes are only treated as explicit for the matrix platform."""
        chat_id, _, is_explicit = _parse_target_ref("telegram", "!something")
        assert is_explicit is False

        chat_id, _, is_explicit = _parse_target_ref("discord", "@someone")
        assert is_explicit is False


class TestParseTargetRefE164:
    """_parse_target_ref accepts E.164 phone numbers for phone-based platforms."""

    def test_signal_e164_preserves_plus_prefix(self):
        """signal:+E164 is explicit and preserves the leading '+' for signal-cli."""
        chat_id, thread_id, is_explicit = _parse_target_ref("signal", "+41791234567")
        assert chat_id == "+41791234567"
        assert thread_id is None
        assert is_explicit is True

    def test_signal_group_target_is_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref("signal", "  group:abc123  ")
        assert chat_id == "group:abc123"
        assert thread_id is None
        assert is_explicit is True

    def test_empty_signal_group_target_is_not_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref("signal", "  group:  ")
        assert chat_id is None
        assert thread_id is None
        assert is_explicit is False

    def test_sms_e164_is_explicit(self):
        chat_id, _, is_explicit = _parse_target_ref("sms", "+15551234567")
        assert chat_id == "+15551234567"
        assert is_explicit is True

    def test_whatsapp_e164_is_explicit(self):
        chat_id, _, is_explicit = _parse_target_ref("whatsapp", "+15551234567")
        assert chat_id == "+15551234567"
        assert is_explicit is True

    def test_photon_e164_is_explicit(self):
        chat_id, _, is_explicit = _parse_target_ref("photon", "+15551234567")
        assert chat_id == "+15551234567"
        assert is_explicit is True

    def test_signal_bare_digits_still_work(self):
        """Bare digit strings continue to match the generic numeric branch."""
        chat_id, _, is_explicit = _parse_target_ref("signal", "15551234567")
        assert chat_id == "15551234567"
        assert is_explicit is True

    def test_signal_invalid_e164_rejected(self):
        """Too-short, too-long, and non-numeric E.164 strings are not explicit."""
        assert _parse_target_ref("signal", "+123")[2] is False
        assert _parse_target_ref("signal", "+1234567890123456")[2] is False
        assert _parse_target_ref("signal", "+12abc4567890")[2] is False
        assert _parse_target_ref("signal", "+")[2] is False

    def test_e164_prefix_only_matches_phone_platforms(self):
        """'+' prefix must NOT be treated as explicit for non-phone platforms."""
        assert _parse_target_ref("telegram", "+15551234567")[2] is False
        assert _parse_target_ref("discord", "+15551234567")[2] is False
        assert _parse_target_ref("matrix", "+15551234567")[2] is False


class TestParseTargetRefWhatsAppJID:
    """_parse_target_ref accepts native WhatsApp JIDs as explicit targets.

    Regression: group JIDs (``<id>@g.us``) and linked-identity JIDs
    (``<id>@lid``) matched no branch and fell through to home-channel
    resolution, so ``send_message(target="whatsapp:<group-jid>")`` silently
    delivered to the configured home DM instead of the requested group.
    """

    def test_group_jid_is_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref(
            "whatsapp", "120363408391911677@g.us"
        )
        assert chat_id == "120363408391911677@g.us"
        assert thread_id is None
        assert is_explicit is True

    def test_user_jid_is_explicit(self):
        chat_id, _, is_explicit = _parse_target_ref(
            "whatsapp", "19255551234@s.whatsapp.net"
        )
        assert chat_id == "19255551234@s.whatsapp.net"
        assert is_explicit is True

    def test_lid_jid_is_explicit(self):
        chat_id, _, is_explicit = _parse_target_ref(
            "whatsapp", "149606612619433@lid"
        )
        assert chat_id == "149606612619433@lid"
        assert is_explicit is True

    def test_broadcast_and_newsletter_jids_are_explicit(self):
        assert _parse_target_ref("whatsapp", "status@broadcast")[2] is True
        assert _parse_target_ref("whatsapp", "120363000000000000@newsletter")[2] is True

    def test_whatsapp_e164_still_explicit_alongside_jids(self):
        """The pre-existing '+'-prefixed E.164 path must keep working."""
        chat_id, _, is_explicit = _parse_target_ref("whatsapp", "+15551234567")
        assert chat_id == "+15551234567"
        assert is_explicit is True

    def test_jid_suffix_only_matches_whatsapp(self):
        """WhatsApp JID suffixes must NOT be treated as explicit elsewhere."""
        assert _parse_target_ref("telegram", "120363408391911677@g.us")[2] is False
        assert _parse_target_ref("signal", "149606612619433@lid")[2] is False

    def test_non_jid_whatsapp_target_falls_through(self):
        """A bare friendly name is not a JID — it must fall through to
        directory resolution (returns not-explicit so the caller can resolve)."""
        assert _parse_target_ref("whatsapp", "general")[2] is False


class TestParseTargetRefSlack:
    """_parse_target_ref recognizes Slack channel/user IDs as explicit."""

    def test_thread_target_is_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref("slack", "C0B0QV5434G:171.000001")
        assert chat_id == "C0B0QV5434G"
        assert thread_id == "171.000001"
        assert is_explicit is True

    def test_public_channel_id_is_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref("slack", "C0B0QV5434G")
        assert chat_id == "C0B0QV5434G"
        assert thread_id is None
        assert is_explicit is True

    def test_private_channel_id_is_explicit(self):
        assert _parse_target_ref("slack", "G123ABCDEF")[2] is True

    def test_dm_id_is_explicit(self):
        assert _parse_target_ref("slack", "D123ABCDEF")[2] is True

    def test_user_id_is_not_explicit(self):
        """Slack user IDs (U...) and workspace IDs (W...) are NOT explicit send
        targets. chat.postMessage rejects them — a DM must be opened first via
        conversations.open to obtain a D... conversation ID.
        """
        assert _parse_target_ref("slack", "U123ABCDEF")[2] is False
        assert _parse_target_ref("slack", "W123ABCDEF")[2] is False

    def test_whitespace_is_stripped(self):
        chat_id, _, is_explicit = _parse_target_ref("slack", "  C0B0QV5434G  ")
        assert chat_id == "C0B0QV5434G"
        assert is_explicit is True

    def test_lowercase_or_short_id_is_not_explicit(self):
        assert _parse_target_ref("slack", "c0b0qv5434g")[2] is False
        assert _parse_target_ref("slack", "C123")[2] is False
        assert _parse_target_ref("slack", "X0B0QV5434G")[2] is False

    def test_slack_id_not_explicit_for_other_platforms(self):
        assert _parse_target_ref("discord", "C0B0QV5434G")[2] is False
        assert _parse_target_ref("telegram", "C0B0QV5434G")[2] is False


class TestParseTargetRefEmail:
    """_parse_target_ref recognizes email addresses as explicit for the email platform."""

    def test_standard_email_is_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref("email", "user@example.com")
        assert chat_id == "user@example.com"
        assert thread_id is None
        assert is_explicit is True

    def test_email_with_dots_in_local_part(self):
        chat_id, _, is_explicit = _parse_target_ref("email", "first.last@example.co.uk")
        assert chat_id == "first.last@example.co.uk"
        assert is_explicit is True

    def test_email_with_plus_tag(self):
        chat_id, _, is_explicit = _parse_target_ref("email", "user+tag@gmail.com")
        assert chat_id == "user+tag@gmail.com"
        assert is_explicit is True

    def test_email_strips_whitespace(self):
        chat_id, _, is_explicit = _parse_target_ref("email", "  user@example.com  ")
        assert chat_id == "user@example.com"
        assert is_explicit is True

    def test_invalid_email_not_explicit(self):
        assert _parse_target_ref("email", "not-an-email")[2] is False
        assert _parse_target_ref("email", "@example.com")[2] is False
        assert _parse_target_ref("email", "user@")[2] is False
        assert _parse_target_ref("email", "user@.com")[2] is False

    def test_email_not_explicit_for_other_platforms(self):
        assert _parse_target_ref("telegram", "user@example.com")[2] is False
        assert _parse_target_ref("discord", "user@example.com")[2] is False
        assert _parse_target_ref("slack", "user@example.com")[2] is False


class TestEmailHomeChannelErrorHint:
    """The no-home-channel error for email points at the real env var.

    Email reads its home channel from EMAIL_HOME_ADDRESS (gateway/config.py),
    not the generic EMAIL_HOME_CHANNEL. The error guidance must name the
    variable that is actually consulted so users who follow it succeed.
    """

    def test_email_error_names_email_home_address(self):
        email_cfg = SimpleNamespace(enabled=True, token="", extra={})
        config = SimpleNamespace(
            platforms={Platform.EMAIL: email_cfg},
            get_home_channel=lambda _platform: None,
        )
        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "email",
                        "message": "hi",
                    }
                )
            )
        assert "EMAIL_HOME_ADDRESS" in result["error"]
        assert "EMAIL_HOME_CHANNEL" not in result["error"]

    def test_non_email_platform_keeps_generic_home_channel_hint(self):
        telegram_cfg = SimpleNamespace(enabled=True, token="***", extra={})
        config = SimpleNamespace(
            platforms={Platform.TELEGRAM: telegram_cfg},
            get_home_channel=lambda _platform: None,
        )
        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram",
                        "message": "hi",
                    }
                )
            )
        assert "TELEGRAM_HOME_CHANNEL" in result["error"]


# ---------------------------------------------------------------------------
# Discord media attachment support
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for _derive_forum_thread_name
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for _send_discord with forum channel support
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for _send_discord forum + media multipart upload
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for the process-local forum-probe cache
# ---------------------------------------------------------------------------


        # Only one session opened (thread creation) — no probe session this time
        # (verified by not raising from our side_effect exhaustion)


# ---------------------------------------------------------------------------
# _send_signal — chunking + 429 retry (mirrors gateway adapter behavior)
# ---------------------------------------------------------------------------


# ── _send_via_adapter standalone fallback ────────────────────────────────


class _FakePlatform:
    """Stand-in for the gateway.config.Platform enum.  Holds the .value
    attribute consulted by ``_send_via_adapter`` for registry lookups."""

    def __init__(self, value):
        self.value = value


class TestSendViaAdapterStandaloneFallback:
    """Coverage for the out-of-process plugin-platform send path.

    When the gateway runner is not in this process (e.g. ``alvarez cron``
    runs separately from ``alvarez gateway``), ``_send_via_adapter`` should
    fall through to the plugin's ``standalone_sender_fn`` registered on
    its ``PlatformEntry``.  Without the hook, the existing error string
    is returned (with a more helpful tail).
    """

    @staticmethod
    def _make_entry(send_fn):
        from gateway.platform_registry import PlatformEntry

        return PlatformEntry(
            name="fakeplatform",
            label="Fake",
            adapter_factory=lambda cfg: None,
            check_fn=lambda: True,
            standalone_sender_fn=send_fn,
        )


    @pytest.mark.asyncio
    async def test_standalone_sender_fn_called_when_no_adapter(self, monkeypatch):
        """Registry has hook, runner ref returns None: the hook is awaited."""
        from tools.send_message_tool import _send_via_adapter
        from gateway.platform_registry import platform_registry

        recorded = {}

        async def fake_send(pconfig, chat_id, message, **kwargs):
            recorded["pconfig"] = pconfig
            recorded["chat_id"] = chat_id
            recorded["message"] = message
            recorded["kwargs"] = kwargs
            return {"success": True, "message_id": "msg-42"}

        platform_registry.register(self._make_entry(fake_send))
        try:
            monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)

            pconfig = SimpleNamespace(extra={})
            result = await _send_via_adapter(
                _FakePlatform("fakeplatform"),
                pconfig,
                "room/123",
                "hello cron",
            )
        finally:
            platform_registry.unregister("fakeplatform")

        assert result == {"success": True, "message_id": "msg-42"}
        assert recorded["chat_id"] == "room/123"
        assert recorded["message"] == "hello cron"
        assert recorded["pconfig"] is pconfig

    @pytest.mark.asyncio
    async def test_standalone_sender_fn_kwargs_forwarded(self, monkeypatch):
        """thread_id, media_files, and force_document all reach the hook."""
        from tools.send_message_tool import _send_via_adapter
        from gateway.platform_registry import platform_registry

        recorded = {}

        async def fake_send(pconfig, chat_id, message, *, thread_id=None,
                            media_files=None, force_document=False):
            recorded["thread_id"] = thread_id
            recorded["media_files"] = media_files
            recorded["force_document"] = force_document
            return {"success": True, "message_id": "x"}

        platform_registry.register(self._make_entry(fake_send))
        try:
            monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)

            await _send_via_adapter(
                _FakePlatform("fakeplatform"),
                SimpleNamespace(extra={}),
                "chat-1",
                "hi",
                thread_id="thread-7",
                media_files=["/tmp/a.png"],
                force_document=True,
            )
        finally:
            platform_registry.unregister("fakeplatform")

        assert recorded["thread_id"] == "thread-7"
        assert recorded["media_files"] == ["/tmp/a.png"]
        assert recorded["force_document"] is True

    @pytest.mark.asyncio
    async def test_standalone_sender_fn_absent_returns_helpful_error(self, monkeypatch):
        """Registry entry has no hook: the fall-through error explains both
        options (gateway-running and standalone hook)."""
        from tools.send_message_tool import _send_via_adapter
        from gateway.platform_registry import platform_registry

        platform_registry.register(self._make_entry(None))
        try:
            monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)

            result = await _send_via_adapter(
                _FakePlatform("fakeplatform"),
                SimpleNamespace(extra={}),
                "chat-1",
                "hi",
            )
        finally:
            platform_registry.unregister("fakeplatform")

        assert "error" in result
        assert "fakeplatform" in result["error"]
        assert "standalone_sender_fn" in result["error"]

    @pytest.mark.asyncio
    async def test_standalone_sender_fn_raises_is_caught_and_formatted(self, monkeypatch):
        """Hook raises: error dict has 'Plugin standalone send failed: ...'"""
        from tools.send_message_tool import _send_via_adapter
        from gateway.platform_registry import platform_registry

        async def boom(pconfig, chat_id, message, **kwargs):
            raise ValueError("boom!")

        platform_registry.register(self._make_entry(boom))
        try:
            monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)

            result = await _send_via_adapter(
                _FakePlatform("fakeplatform"),
                SimpleNamespace(extra={}),
                "chat-1",
                "hi",
            )
        finally:
            platform_registry.unregister("fakeplatform")

        assert result == {"error": "Plugin standalone send failed: boom!"}

    @pytest.mark.asyncio
    async def test_standalone_sender_fn_return_shape_passed_through(self, monkeypatch):
        """Hook returns success dict: passed through unchanged."""
        from tools.send_message_tool import _send_via_adapter
        from gateway.platform_registry import platform_registry

        async def fake_send(pconfig, chat_id, message, **kwargs):
            return {"success": True, "message_id": "abc-123", "extra_field": "preserved"}

        platform_registry.register(self._make_entry(fake_send))
        try:
            monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)

            result = await _send_via_adapter(
                _FakePlatform("fakeplatform"),
                SimpleNamespace(extra={}),
                "chat-1",
                "hi",
            )
        finally:
            platform_registry.unregister("fakeplatform")

        assert result["success"] is True
        assert result["message_id"] == "abc-123"
        assert result["extra_field"] == "preserved"


# ---------------------------------------------------------------------------
# _check_send_message — availability gating
# ---------------------------------------------------------------------------

class TestCheckSendMessage:
    """The tool's check_fn governs whether the model sees ``send_message`` as
    callable for a given session. The four passing conditions are:

    1. ``ALVAREZ_KANBAN_TASK`` is set (worker spawned by the kanban dispatcher
       — parent gateway is by definition running, but the worker's
       ``ALVAREZ_HOME`` may be a profile dir without a ``gateway.pid``).
    2. ``ALVAREZ_SESSION_PLATFORM`` resolves to a non-empty, non-``local`` value
       (the session is wired to a messaging platform like Telegram).
    3. ``is_gateway_running()`` returns True (CLI / orchestrator profile with
       a live gateway colocated under the same ``ALVAREZ_HOME``).
    4. None of the above → False, tool is hidden.
    """

    def test_kanban_task_env_grants_access(self, monkeypatch):
        """Workers spawned by the dispatcher (ALVAREZ_KANBAN_TASK set) must be
        allowed regardless of session_platform / gateway-pid state."""
        from tools.send_message_tool import _check_send_message

        monkeypatch.setenv("ALVAREZ_KANBAN_TASK", "t_abc12345")
        monkeypatch.delenv("ALVAREZ_SESSION_PLATFORM", raising=False)

        with patch("gateway.session_context.get_session_env", return_value=""), \
             patch("gateway.status.is_gateway_running", return_value=False):
            assert _check_send_message() is True

    def test_kanban_task_env_short_circuits_before_gateway_check(self, monkeypatch):
        """Honoring ALVAREZ_KANBAN_TASK must not depend on importing or calling
        gateway.status — the worker may run with a ALVAREZ_HOME that has no
        gateway.pid, and we don't want that import path to be load-bearing."""
        from tools.send_message_tool import _check_send_message

        monkeypatch.setenv("ALVAREZ_KANBAN_TASK", "t_abc12345")

        with patch("gateway.session_context.get_session_env",
                   side_effect=AssertionError("session_context not consulted "
                                              "when ALVAREZ_KANBAN_TASK is set")), \
             patch("gateway.status.is_gateway_running",
                   side_effect=AssertionError("gateway.status not consulted "
                                              "when ALVAREZ_KANBAN_TASK is set")):
            assert _check_send_message() is True

    def test_messaging_platform_session_grants_access(self, monkeypatch):
        """Telegram/Discord/etc. sessions pass via the platform branch even
        without ALVAREZ_KANBAN_TASK."""
        from tools.send_message_tool import _check_send_message

        monkeypatch.delenv("ALVAREZ_KANBAN_TASK", raising=False)

        with patch("gateway.session_context.get_session_env", return_value="telegram"), \
             patch("gateway.status.is_gateway_running", return_value=False):
            assert _check_send_message() is True

    def test_local_platform_falls_through_to_gateway_check(self, monkeypatch):
        """``ALVAREZ_SESSION_PLATFORM=local`` means CLI-style — must defer to
        is_gateway_running() rather than auto-grant."""
        from tools.send_message_tool import _check_send_message

        monkeypatch.delenv("ALVAREZ_KANBAN_TASK", raising=False)

        with patch("gateway.session_context.get_session_env", return_value="local"), \
             patch("gateway.status.is_gateway_running", return_value=True) as gw_mock:
            assert _check_send_message() is True
            gw_mock.assert_called_once()

    def test_running_gateway_grants_access(self, monkeypatch):
        """Plain CLI session (no kanban task, empty platform) with a live
        gateway: tool is callable."""
        from tools.send_message_tool import _check_send_message

        monkeypatch.delenv("ALVAREZ_KANBAN_TASK", raising=False)

        with patch("gateway.session_context.get_session_env", return_value=""), \
             patch("gateway.status.is_gateway_running", return_value=True):
            assert _check_send_message() is True

    def test_no_signals_means_unavailable(self, monkeypatch):
        """No kanban task, no platform, no gateway: tool is hidden."""
        from tools.send_message_tool import _check_send_message

        monkeypatch.delenv("ALVAREZ_KANBAN_TASK", raising=False)

        with patch("gateway.session_context.get_session_env", return_value=""), \
             patch("gateway.status.is_gateway_running", return_value=False):
            assert _check_send_message() is False

    def test_gateway_status_import_error_is_swallowed(self, monkeypatch):
        """If gateway.status can't be imported (unusual deployment / partial
        install), the check returns False rather than raising."""
        from tools.send_message_tool import _check_send_message

        monkeypatch.delenv("ALVAREZ_KANBAN_TASK", raising=False)

        with patch("gateway.session_context.get_session_env", return_value=""), \
             patch("gateway.status.is_gateway_running",
                   side_effect=ImportError("simulated")):
            assert _check_send_message() is False


class TestSendTelegramThreadNotFoundRetry:
    """Tests for thread-not-found retry behaviour in _send_telegram (#27012)."""

    def test_is_thread_not_found_matches_expected_errors(self):
        """_is_telegram_thread_not_found should detect thread-not-found errors."""
        class FakeError(Exception):
            pass

        assert _is_telegram_thread_not_found(FakeError("message thread not found")) is True
        assert _is_telegram_thread_not_found(FakeError("THREAD NOT FOUND")) is True
        assert _is_telegram_thread_not_found(FakeError("Bad Request: thread not found")) is True
        assert _is_telegram_thread_not_found(FakeError("chat not found")) is False
        assert _is_telegram_thread_not_found(FakeError("parse error")) is False
        assert _is_telegram_thread_not_found(FakeError("")) is False

    def test_text_send_retries_without_thread_id_on_thread_not_found(self):
        """When thread is not found, the text send should retry without
        message_thread_id."""
        call_args = []

        async def fake_retry(bot, *, chat_id, text, parse_mode, **kwargs):
            call_args.append(dict(kwargs, chat_id=chat_id, text=text))
            if len(call_args) == 1:
                raise Exception("Bad Request: message thread not found")
            return SimpleNamespace(message_id=42)

        async def run_test():
            with patch(
                "tools.send_message_tool._send_telegram_message_with_retry",
                fake_retry,
            ):
                # _send_telegram imports Bot locally; we only need to mock
                # the send path, not Bot itself (Bot import falls through
                # normally since python-telegram-bot is installed).
                return await _send_telegram(
                    "fake-token", "-100123", "hello from topic 17585",
                    thread_id="17585",
                )

        result = asyncio.run(run_test())
        assert result["success"] is True
        assert result["message_id"] == "42"
        assert len(call_args) == 2, f"expected 2 calls, got {len(call_args)}"
        # First call should have message_thread_id
        assert call_args[0].get("message_thread_id") is not None
        # Second call (retry) should NOT have message_thread_id
        assert "message_thread_id" not in call_args[1], \
            "retry should drop message_thread_id after thread-not-found"

    def test_disable_web_page_preview_not_leaked_to_media_sends(self):
        """disable_web_page_preview should only appear in text send, not media sends."""
        text_kwargs_seen = []
        media_kwargs_seen = []

        class FakeBot:
            async def send_message(self, **kwargs):
                text_kwargs_seen.append(kwargs)
                return SimpleNamespace(message_id=1)

            async def send_document(self, **kwargs):
                media_kwargs_seen.append(kwargs)
                return SimpleNamespace(message_id=2)

        import tempfile
        media_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                tf.write(b"%PDF-1.4 test content")
                media_path = tf.name

            async def run_test():
                with patch("telegram.Bot", return_value=FakeBot()):
                    return await _send_telegram(
                        "fake-token", "-100123", "check preview",
                        media_files=[(media_path, False)],
                        disable_link_previews=True,
                    )

            result = asyncio.run(run_test())
            assert result["success"] is True
            # Text send should have disable_web_page_preview
            assert text_kwargs_seen[0].get("disable_web_page_preview") is True
            # Media send should NOT have disable_web_page_preview
            assert "disable_web_page_preview" not in media_kwargs_seen[0], \
                "disable_web_page_preview leaked into send_document kwargs"
        finally:
            if media_path and os.path.exists(media_path):
                os.unlink(media_path)
