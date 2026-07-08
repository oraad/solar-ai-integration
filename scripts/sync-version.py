#!/usr/bin/env python3
"""Sync or verify manifest.json version from VERSION."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def paths_for_root(root: Path) -> dict[str, Path]:
    return {
        "version": root / "VERSION",
        "manifest": root / "custom_components" / "solar_ai_optimizer" / "manifest.json",
    }


def parse_version_text(raw: str) -> str:
    return raw.replace("\r", "").strip()


def read_version_bytes(version_file: Path) -> bytes:
    if not version_file.is_file():
        raise SystemExit(f"Missing {version_file}")
    return version_file.read_bytes()


def canonical_version_bytes(version: str) -> bytes:
    return f"{version}\n".encode("utf-8")


def read_canonical_version(version_file: Path) -> str:
    version = parse_version_text(read_version_bytes(version_file).decode("utf-8"))
    if not version:
        raise SystemExit(f"{version_file} is empty")
    return version


def verify_version_lf(version_file: Path) -> bool:
    raw = read_version_bytes(version_file)
    if b"\r" in raw:
        print(f"{version_file} contains CR bytes; run sync-version.py to normalize", file=sys.stderr)
        return False
    expected = canonical_version_bytes(read_canonical_version(version_file))
    if raw != expected:
        print(
            f"{version_file} must be exactly '<version>\\n' (LF only); run sync-version.py to normalize",
            file=sys.stderr,
        )
        return False
    return True


def write_version_file(version_file: Path, version: str) -> None:
    version_file.write_bytes(canonical_version_bytes(version))


def read_manifest_version(manifest_json: Path) -> str:
    data = json.loads(manifest_json.read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit(f'Missing "version" in {manifest_json}')
    return version


def write_manifest_version(manifest_json: Path, version: str) -> None:
    data = json.loads(manifest_json.read_text(encoding="utf-8"))
    data["version"] = version
    manifest_json.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify VERSION (LF-only) and manifest.json; do not write",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_DEFAULT_ROOT,
        help="Repository root (default: parent of scripts/)",
    )
    args = parser.parse_args()

    paths = paths_for_root(args.root.resolve())
    version_file = paths["version"]
    manifest_json = paths["manifest"]

    if args.check:
        ok = verify_version_lf(version_file)
        expected = read_canonical_version(version_file)
        if not manifest_json.is_file():
            print(f"Missing manifest: {manifest_json}", file=sys.stderr)
            return 1
        actual = read_manifest_version(manifest_json)
        if actual != expected:
            print(
                f"manifest drift: {manifest_json} has {actual!r}, expected {expected!r}",
                file=sys.stderr,
            )
            ok = False
        if not ok:
            return 1
        print(f"Version files match {expected}")
        return 0

    expected = read_canonical_version(version_file)
    changed = False
    raw_before = read_version_bytes(version_file)
    write_version_file(version_file, expected)
    if raw_before != canonical_version_bytes(expected):
        print(f"Normalized {version_file} to LF")
        changed = True

    if not manifest_json.is_file():
        print(f"Missing manifest: {manifest_json}", file=sys.stderr)
        return 1

    if read_manifest_version(manifest_json) != expected:
        write_manifest_version(manifest_json, expected)
        print(f"Updated {manifest_json} -> {expected}")
        changed = True

    if not changed:
        print(f"Already in sync at {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
