"""CLI subcommand: ``alvarez soul <subcommand>``.

Swap the agent personality by managing named SOUL.md variants in
``$ALVAREZ_HOME/souls/``.  SOUL.md is re-read every message, so ``use``
takes effect immediately — no restart needed.

No side effects at import time — ``main.py`` wires the argparse subparsers
on demand via :func:`register_cli`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _print(msg: str = "") -> None:
    print(msg)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _home() -> Path:
    from alvarez_constants import get_alvarez_home

    return get_alvarez_home()


def _soul_path() -> Path:
    return _home() / "SOUL.md"


def _souls_dir() -> Path:
    return _home() / "souls"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _saved_souls() -> list[Path]:
    d = _souls_dir()
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.md") if p.is_file())


def _active_name() -> str | None:
    """Name of the saved soul whose content matches the live SOUL.md, if any."""
    current = _read(_soul_path())
    if not current:
        return None
    for p in _saved_souls():
        if _read(p) == current:
            return p.stem
    return None


def _cmd_show(args) -> int:
    soul = _soul_path()
    current = _read(soul)
    if not current:
        _print(f"No personality set ({soul} is missing or empty).")
    else:
        active = _active_name()
        label = f" (saved as: {active})" if active else " (not saved — `alvarez soul save <name>` to keep it)"
        _print(f"Active personality — {soul}{label}\n")
        preview = current.splitlines()
        for line in preview[:12]:
            _print(f"  {line}")
        if len(preview) > 12:
            _print(f"  … ({len(preview) - 12} more lines)")
    saved = _saved_souls()
    if saved:
        _print(f"\nSaved souls ({len(saved)}) — switch with `alvarez soul use <name>`:")
        for p in saved:
            _print(f"  {p.stem}")
    return 0


def _cmd_list(args) -> int:
    saved = _saved_souls()
    if not saved:
        _print(f"No saved souls in {_souls_dir()}.")
        _print("Save the current one with: alvarez soul save <name>")
        return 0
    active = _active_name()
    for p in saved:
        marker = "* " if p.stem == active else "  "
        first_line = _read(p).splitlines()[0][:70] if _read(p) else "(empty)"
        _print(f"{marker}{p.stem:<24} {first_line}")
    return 0


def _cmd_save(args) -> int:
    current = _read(_soul_path())
    if not current:
        _err(f"✗ nothing to save — {_soul_path()} is missing or empty")
        return 1
    dest = _souls_dir() / f"{args.name}.md"
    if dest.exists() and _read(dest) != current and not args.force:
        _err(f"✗ {dest} already exists with different content (use --force to overwrite)")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(current + "\n", encoding="utf-8")
    _print(f"✓ saved current personality as '{args.name}' ({dest})")
    return 0


def _cmd_use(args) -> int:
    src = _souls_dir() / f"{args.name}.md"
    if not src.is_file():
        _err(f"✗ no saved soul named '{args.name}' in {_souls_dir()}")
        names = [p.stem for p in _saved_souls()]
        if names:
            _err("  available: " + ", ".join(names))
        return 1
    content = _read(src)
    if not content:
        _err(f"✗ {src} is empty")
        return 1
    soul = _soul_path()
    current = _read(soul)
    if current == content:
        _print(f"'{args.name}' is already the active personality.")
        return 0
    # Never lose an unsaved personality: stash it before overwriting.
    if current and _active_name() is None:
        backup = _souls_dir() / "_previous.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(current + "\n", encoding="utf-8")
        _print(f"(unsaved personality stashed as '_previous' — {backup})")
    soul.parent.mkdir(parents=True, exist_ok=True)
    soul.write_text(content + "\n", encoding="utf-8")
    _print(f"✓ personality switched to '{args.name}' — takes effect on the next message")
    return 0


def _cmd_delete(args) -> int:
    src = _souls_dir() / f"{args.name}.md"
    if not src.is_file():
        _err(f"✗ no saved soul named '{args.name}'")
        return 1
    src.unlink()
    _print(f"✓ deleted saved soul '{args.name}' (active SOUL.md untouched)")
    return 0


# ─────────────────────────────────────────────────────────────────────────
# argparse wiring
# ─────────────────────────────────────────────────────────────────────────

def register_cli(parent: argparse.ArgumentParser) -> None:
    """Attach ``soul`` subcommands to *parent* (called by main.py)."""
    parent.set_defaults(func=_cmd_show)
    subs = parent.add_subparsers(dest="soul_command")

    subs.add_parser("show", help="Show the active personality and saved souls").set_defaults(
        func=_cmd_show
    )

    subs.add_parser("list", help="List saved souls (* marks the active one)").set_defaults(
        func=_cmd_list
    )

    p_save = subs.add_parser("save", help="Save the current SOUL.md as a named soul")
    p_save.add_argument("name", help="Name to save it under (souls/<name>.md)")
    p_save.add_argument("--force", action="store_true", help="Overwrite an existing saved soul")
    p_save.set_defaults(func=_cmd_save)

    p_use = subs.add_parser("use", help="Switch SOUL.md to a saved soul (immediate, no restart)")
    p_use.add_argument("name", help="Saved soul to activate")
    p_use.set_defaults(func=_cmd_use)

    p_del = subs.add_parser("delete", help="Delete a saved soul (never touches active SOUL.md)")
    p_del.add_argument("name", help="Saved soul to delete")
    p_del.set_defaults(func=_cmd_delete)
