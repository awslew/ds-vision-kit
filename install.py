#!/usr/bin/env python3
"""Install ds-vision-kit: put the CLI commands on PATH and optionally install
the skills into ~/.claude/skills.

Creates one launcher per command in a bin directory that is on your PATH
(default: ~/bin on Windows/Git-Bash, ~/.local/bin elsewhere). On Windows both a
POSIX shim (for Git Bash) and a .cmd launcher (for cmd.exe / PowerShell) are
written, so the commands work everywhere.

Usage:
    python install.py                # shims + skills
    python install.py --no-skills    # only shims (commands on PATH)
    python install.py --bin DIR      # install shims into DIR instead of the default
    python install.py --dry-run      # print what would be created, change nothing

Commands installed:
    glance  ground  detect  trace  crop      (from bin/)
    palette pixel-diff  extract-fg  html-shot  long-ocr   (from scripts/)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent

COMMANDS = [
    ("glance", "bin/glance"),
    ("ground", "bin/ground"),
    ("detect", "bin/detect"),
    ("trace", "bin/trace"),
    ("crop", "bin/crop"),
    ("palette", "scripts/dominant_colors.py"),
    ("pixel-diff", "scripts/pixel_diff.py"),
    ("extract-fg", "scripts/extract_fg.py"),
    ("html-shot", "scripts/html_shot.py"),
    ("long-ocr", "scripts/long_screenshot_ocr.py"),
]


def default_bin_dir() -> Path:
    if os.name == "nt":
        return Path.home() / "bin"
    if os.environ.get("XDG_BIN_HOME"):
        return Path(os.environ["XDG_BIN_HOME"])
    return Path.home() / ".local" / "bin"


def write_shim(bin_dir: Path, name: str, script: Path, python: str, dry_run: bool) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / name
    # POSIX shim (works in Git Bash on Windows, and everywhere on macOS/Linux).
    # Use forward-slash paths and quote everything: backslashes are eaten by the
    # shell ("C:\Users" -> "C:Users") and an unquoted Windows path breaks exec.
    python_fs = str(Path(python).as_posix())
    script_fs = str(script.as_posix())
    shim.write_text(
        f'#!/bin/sh\nexec "{python_fs}" "{script_fs}" "$@"\n', encoding="utf-8")
    try:
        shim.chmod(0o755)
    except OSError:
        pass
    if os.name == "nt":
        # .cmd launcher for native cmd.exe / PowerShell. Backslashes are correct here.
        (bin_dir / (name + ".cmd")).write_text(
            f'@echo off\r\n"{python}" "{script}" %*\r\n', encoding="utf-8")
    action = "would write" if dry_run else "wrote"
    print(f"[install] {action} {shim}")

    if dry_run and os.name == "nt":
        print(f"[install] would write {bin_dir / (name + '.cmd')}")


def install_skills(dry_run: bool) -> None:
    skills_src = REPO / "skills"
    skills_dst = Path.home() / ".claude" / "skills"
    for name in ("vision-core", "_template", "ui-feedback", "ocr-extract",
                 "chart-reading", "image-qa"):
        src = skills_src / name
        if not src.is_dir():
            continue
        dst = skills_dst / name
        action = "would copy" if dry_run else "copied"
        if dst.exists():
            print(f"[install] SKIP {name}: already exists at {dst} (remove it first to reinstall)")
            continue
        if dry_run:
            print(f"[install] {action} {src} -> {dst}")
            continue
        shutil.copytree(src, dst)
        print(f"[install] {action} {src} -> {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-skills", action="store_true",
                        help="only install CLI shims, do not touch ~/.claude/skills")
    parser.add_argument("--bin", default=str(default_bin_dir()),
                        help="directory to install command shims into (default: ~/bin on Windows, ~/.local/bin otherwise)")
    parser.add_argument("--dry-run", action="store_true", help="print actions without running them")
    args = parser.parse_args()

    python = sys.executable
    print(f"[install] using python: {python}")
    print(f"[install] repo root: {REPO}")

    bin_dir = Path(args.bin).expanduser()
    for name, rel in COMMANDS:
        script = (REPO / rel).resolve()
        if not script.is_file():
            print(f"[install] WARNING script not found, skipping {name}: {script}", file=sys.stderr)
            continue
        write_shim(bin_dir, name, script, python, args.dry_run)

    if not args.dry_run:
        print(f"\n[install] add {bin_dir} to your PATH if it is not already there.")
        print("[install] then verify: glance --help")

    if not args.no_skills:
        install_skills(args.dry_run)
        if not args.dry_run:
            print("\n[install] skills copied to ~/.claude/skills. Restart Claude Code to pick them up.")

    if not args.dry_run and not (REPO / ".env").exists():
        print("\n[install] next step: copy .env.example to .env and fill in your provider keys.")
        print("[install]   copy .env.example .env   (or set VISION_ENV_FILE)")


if __name__ == "__main__":
    main()
