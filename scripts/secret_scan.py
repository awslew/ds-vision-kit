#!/usr/bin/env python3
"""Thorough secret scan for a git repository — run before any public push.

Scans every tracked file AND every git blob across all history for high-signal
secret patterns: API keys in all common formats (any length), cookies, private
keys, tokens, high-entropy strings. Path-like and code-identifier false
positives are filtered out. Prints matches with file + line so each can be
judged. Exit code 0 = clean, 1 = hits found.

Usage:
    python scripts/secret_scan.py [REPO_PATH]   # default: this repository
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# --- regexes: name -> pattern ------------------------------------------------
PATTERNS: dict[str, re.Pattern] = {
    # any sk- key, any length (OpenAI-style) — catches short keys too.
    # The negative lookahead stops the scanner from flagging its own "sk-ant-"
    # pattern definition; real Anthropic keys are caught by the sk-ant pattern.
    "sk-any": re.compile(r"sk-(?!ant-)[A-Za-z0-9_-]{4,}"),
    # Anthropic
    "sk-ant": re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    # Google
    "google": re.compile(r"AIza[0-9A-Za-z_-]{10,}"),
    # GitHub (all token shapes)
    "github-tok": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}"),
    # Stripe
    "stripe": re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{10,}"),
    # AWS
    "aws": re.compile(r"AKIA[0-9A-Z]{16}"),
    # JWT
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # Bearer token
    "bearer": re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{10,}"),
    # private keys
    "privkey": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # cookie names carrying a value
    "cookie": re.compile(r"(?i)(sessionid|connect\.sid|PHPSESSID|JSESSIONID|csrftoken|csrf[_-]?token|cf_clearance|__cf[a-z0-9_]*|_ga=)\s*[:=]\s*\S+"),
    # secret-key assignment with a non-empty value (>= 8 chars)
    "assign": re.compile(
        r"""(?i)\b(api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret|secret[_-]?key|password|passwd|auth[_-]?token|session[_-]?token)\b\s*[:=]\s*["']?[A-Za-z0-9._~+/=-]{8,}"""),
    # long base64 (>= 40 chars), no path slashes
    "b64": re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
    # long hex (>= 32 chars)
    "hex": re.compile(r"\b[0-9a-fA-F]{32,}\b"),
}

# strings that are legitimately long and must not be reported
LEGIT_SUBSTRINGS = (
    "sk-...", "your-key", "YOUR_API_KEY", "no-key-needed", "example.com",
    "your-provider", "my-vision-model", "dev@ds-vision-kit.local",
    "Mozilla", "AppleWebKit", "Chrome", "Safari", "Windows", "Python311",
    "Microsoft", "msedge", "dejavu", "DejaVu", "truetype",
)


def is_legit(name: str, value: str) -> bool:
    if name == "b64" and "/" in value:
        return True  # path-like, not a key
    if name == "assign":
        # code identifiers / function calls are not secrets
        if re.match(r"\w+\([^)]*\)", value) or " " in value:
            return True
    return any(p in value for p in LEGIT_SUBSTRINGS)


def scan_text(text: str, label: str) -> list[str]:
    hits: list[str] = []
    for name, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            value = m.group(0)
            if is_legit(name, value):
                continue
            hits.append(f"[{label}] {name}: {value[:80]!r}")
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=str(REPO),
                        help="path to a git repo to scan (default: this repo)")
    args = parser.parse_args()
    repo = Path(args.target).resolve()
    if not (repo / ".git").exists() and not repo.is_dir():
        parser.error(f"not a git repo: {repo}")
    print(f"scanning {repo} ...")

    all_hits: list[str] = []

    # 1. tracked files in the working tree
    tracked = subprocess.run(["git", "ls-files"], cwd=repo,
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.splitlines()
    for rel in tracked:
        p = repo / rel
        if not p.is_file():
            continue
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            continue  # binary fixtures
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        all_hits.extend(scan_text(text, rel))

    # 2. every textual blob in git history (all commits)
    blobs = subprocess.run(["git", "rev-list", "--all", "--objects"], cwd=repo,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout.splitlines()
    seen_blobs: set[str] = set()
    for line in blobs:
        parts = line.split()
        if len(parts) < 2:
            continue
        blob = parts[0]
        if blob in seen_blobs:
            continue
        seen_blobs.add(blob)
        data = subprocess.run(["git", "cat-file", "blob", blob], cwd=repo,
                              capture_output=True).stdout
        if len(data) > 200_000:
            continue
        if any(b in data[:100] for b in (b"\x00", b"\xff\xd8", b"\x89PNG", b"GIF8")):
            continue  # binary
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            continue
        all_hits.extend(scan_text(text, f"git:{' '.join(parts[1:]) or blob[:8]}"))

    if all_hits:
        print(f"=== {len(set(all_hits))} unique HITS in {repo.name} (review each) ===")
        for h in sorted(set(all_hits)):
            print(h)
        return 1
    print(f"CLEAN: no keys / cookies / private keys / tokens in {repo.name} "
          "(tracked files or git history).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
