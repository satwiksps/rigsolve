#!/usr/bin/env python3
"""Fail when a relative Markdown link points at a missing repository file."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
IGNORED_SCHEMES = {"http", "https", "mailto"}
IGNORED_PARTS = {"node_modules", ".next", ".vercel"}


def _target_path(document: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme in IGNORED_SCHEMES or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    return (ROOT / path.lstrip("/")) if path.startswith("/") else (document.parent / path)


def main() -> int:
    failures: list[str] = []
    documents = sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part.startswith(".") and part != ".github" for part in path.parts)
        and not any(part in IGNORED_PARTS for part in path.parts)
    )
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            target = _target_path(document, match.group("target"))
            if target is not None and not target.exists():
                source = document.relative_to(ROOT).as_posix()
                destination = match.group("target")
                failures.append(f"{source}: missing link target {destination!r}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Checked relative links in {len(documents)} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
