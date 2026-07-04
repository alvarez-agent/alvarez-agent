"""Config migration: agent.personalities → agent.moods (v34)."""

import yaml

from alvarez_cli.config import migrate_config


def test_v33_config_renames_personalities_to_moods(tmp_path, monkeypatch):
    monkeypatch.setenv("ALVAREZ_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "_config_version": 33,
                "agent": {"personalities": {"custom": "You are custom."}},
                "display": {"personality": "custom"},
            }
        ),
        encoding="utf-8",
    )

    migrate_config(interactive=False, quiet=True)

    migrated = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    agent = migrated.get("agent") or {}
    display = migrated.get("display") or {}
    assert "personalities" not in agent
    assert agent.get("moods") == {"custom": "You are custom."}
    assert "personality" not in display
    assert display.get("mood") == "custom"
