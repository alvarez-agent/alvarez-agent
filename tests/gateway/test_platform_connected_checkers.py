"""
Verify that every gateway platform — built-in and plugin — has a connection
checker so ``GatewayConfig.get_connected_platforms()`` doesn't silently drop
platforms with bespoke auth requirements.
"""

from unittest.mock import MagicMock

import pytest

from gateway.config import Platform, _PLATFORM_CONNECTED_CHECKERS, _BUILTIN_PLATFORM_VALUES


@pytest.mark.parametrize("platform, checker", list(_PLATFORM_CONNECTED_CHECKERS.items()))
def test_checker_handles_minimal_config(platform, checker):
    """Each bespoke checker must not crash on a minimal PlatformConfig."""
    mock_config = MagicMock()
    mock_config.extra = {}
    mock_config.token = None
    mock_config.api_key = None
    mock_config.enabled = True

    # Should return a bool without raising
    result = checker(mock_config)
    assert isinstance(result, bool)


@pytest.mark.parametrize("platform, checker", list(_PLATFORM_CONNECTED_CHECKERS.items()))
def test_checker_returns_true_when_configured(platform, checker, monkeypatch):
    """Each bespoke checker must return True when the config looks valid."""
    mock_config = MagicMock()
    mock_config.token = None
    mock_config.api_key = None
    mock_config.enabled = True

    # Set up platform-specific mock extra fields so the checker succeeds
    if platform == Platform.WEIXIN:
        mock_config.extra = {"account_id": "123", "token": "***"}
    elif platform == Platform.SIGNAL:
        mock_config.extra = {"http_url": "http://signal:8080"}
    elif platform == Platform.EMAIL:
        mock_config.extra = {"address": "alvarez@example.com"}
    elif platform == Platform.SMS:
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
        mock_config.extra = {}
    elif platform in {
        Platform.API_SERVER,
        Platform.WEBHOOK,
        Platform.WHATSAPP,
    }:
        mock_config.extra = {}
    elif platform == Platform.MSGRAPH_WEBHOOK:
        mock_config.extra = {"client_state": "expected-client-state"}
    elif platform == Platform.FEISHU:
        mock_config.extra = {"app_id": "app"}
    elif platform == Platform.WECOM:
        mock_config.extra = {"bot_id": "bot"}
    elif platform == Platform.WECOM_CALLBACK:
        mock_config.extra = {"corp_id": "corp"}
    elif platform == Platform.BLUEBUBBLES:
        mock_config.extra = {"server_url": "http://bb:1234", "password": "pw"}
    elif platform == Platform.QQBOT:
        mock_config.extra = {"app_id": "app", "client_secret": "sec"}
    elif platform == Platform.YUANBAO:
        mock_config.extra = {"app_id": "app", "app_secret": "sec"}
    elif platform == Platform.DINGTALK:
        mock_config.extra = {"client_id": "id", "client_secret": "sec"}
    elif platform == Platform.RELAY:
        mock_config.extra = {"relay_url": "wss://connector.example/relay"}
    else:
        pytest.skip(f"No synthetic config defined for {platform.value}")

    result = checker(mock_config)
    assert result is True, f"{platform.value} checker should return True with valid-looking config"
