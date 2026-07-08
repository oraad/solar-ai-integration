#!/usr/bin/env python3
"""Extract a version section from CHANGELOG.md for GitHub release notes."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def excerpt(changelog: str, version: str) -> str | None:
    """Return the body under ## [version] or None if not found."""
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog)
    if not match:
        return None
    body = match.group(1).strip()
    integration_only = re.search(
        r"^### Integration\s*\n(.*?)(?=^### |\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if integration_only:
        body = integration_only.group(1).strip()
    return body or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to CHANGELOG.md",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Release version without leading v (e.g. 0.1.0)",
    )
    args = parser.parse_args()

    text = args.changelog.read_text(encoding="utf-8")
    section = excerpt(text, args.version)
    if section is None:
        return 1
    sys.stdout.write(section)
    if not section.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
