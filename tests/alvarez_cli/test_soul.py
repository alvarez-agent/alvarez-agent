"""Tests for the ``alvarez soul`` personality-swap command."""

from argparse import Namespace

import pytest

from alvarez_cli import soul


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ALVAREZ_HOME", str(tmp_path))
    return tmp_path


def test_save_and_use_round_trip(home, capsys):
    (home / "SOUL.md").write_text("You are grumpy.\n")
    assert soul._cmd_save(Namespace(name="grumpy", force=False)) == 0

    (home / "SOUL.md").write_text("You are cheerful.\n")
    assert soul._cmd_save(Namespace(name="cheerful", force=False)) == 0

    assert soul._cmd_use(Namespace(name="grumpy")) == 0
    assert (home / "SOUL.md").read_text().strip() == "You are grumpy."


def test_use_stashes_unsaved_personality(home):
    (home / "souls").mkdir()
    (home / "souls" / "work.md").write_text("You are all business.\n")
    (home / "SOUL.md").write_text("Handcrafted, never saved.\n")

    assert soul._cmd_use(Namespace(name="work")) == 0
    assert (home / "SOUL.md").read_text().strip() == "You are all business."
    assert (home / "souls" / "_previous.md").read_text().strip() == "Handcrafted, never saved."


def test_use_unknown_name_fails(home, capsys):
    assert soul._cmd_use(Namespace(name="nope")) == 1


def test_save_refuses_silent_overwrite(home):
    (home / "SOUL.md").write_text("v2\n")
    (home / "souls").mkdir()
    (home / "souls" / "mine.md").write_text("v1\n")
    assert soul._cmd_save(Namespace(name="mine", force=False)) == 1
    assert soul._cmd_save(Namespace(name="mine", force=True)) == 0
    assert (home / "souls" / "mine.md").read_text().strip() == "v2"


def test_list_marks_active(home, capsys):
    (home / "SOUL.md").write_text("A\n")
    (home / "souls").mkdir()
    (home / "souls" / "a.md").write_text("A\n")
    (home / "souls" / "b.md").write_text("B\n")
    assert soul._cmd_list(Namespace()) == 0
    out = capsys.readouterr().out
    assert "* a" in out
    assert "* b" not in out
