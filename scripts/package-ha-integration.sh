#!/usr/bin/env bash
# Package the HACS custom integration as a flat domain zip for GitHub Releases.
# Zip root = contents of custom_components/solar_ai_optimizer/ so HACS extracts
# into config/custom_components/solar_ai_optimizer/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN_DIR="$ROOT/custom_components/solar_ai_optimizer"
OUT_DIR="$ROOT/dist"
ZIP_NAME="solar_ai_optimizer.zip"

if [[ ! -f "$DOMAIN_DIR/manifest.json" ]]; then
  echo "error: missing $DOMAIN_DIR/manifest.json" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR/$ZIP_NAME"

# Prefer Info-ZIP; fall back to Python zipfile on hosts without zip(1).
if command -v zip >/dev/null 2>&1; then
  (
    cd "$DOMAIN_DIR"
    zip -qr "$OUT_DIR/$ZIP_NAME" . \
      -x 'tests/*' 'tests/**' \
         'brand/_candidates/*' 'brand/_candidates/**' \
         'mypy.ini' \
         '*.pyc' '__pycache__/*' '*/__pycache__/*' \
         '.mypy_cache/*' '*/.mypy_cache/*' \
         '.pytest_cache/*' '*/.pytest_cache/*' \
         '.*' '*/.*'
  )
else
  python - "$DOMAIN_DIR" "$OUT_DIR/$ZIP_NAME" <<'PY'
import sys
import zipfile
from pathlib import Path

domain = Path(sys.argv[1])
out = Path(sys.argv[2])
skip_parts = {"tests", "__pycache__", ".mypy_cache", ".pytest_cache", "_candidates"}
skip_names = {"mypy.ini"}
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(domain.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(domain)
        if any(part in skip_parts or part.startswith(".") for part in rel.parts):
            continue
        if path.name in skip_names or path.suffix == ".pyc":
            continue
        zf.write(path, rel.as_posix())
print(f"wrote {out}")
PY
fi

python - "$OUT_DIR/$ZIP_NAME" <<'PY'
import sys
import zipfile
from pathlib import Path

zpath = Path(sys.argv[1])
with zipfile.ZipFile(zpath) as zf:
    names = zf.namelist()

assert "manifest.json" in names, names[:40]
assert "__init__.py" in names, names[:40]
assert "py.typed" in names, names
assert "icons.json" in names, names
assert "quality_scale.yaml" in names, names
assert "mypy.ini" not in names, names
assert not any(n == "tests" or n.startswith("tests/") for n in names), names
assert any(n.startswith("brand/") for n in names), names
assert "VERSION" not in names and "CHANGELOG.md" not in names, names
assert not any(n.startswith("custom_components/") for n in names), names
print(f"zip OK: {zpath} ({len(names)} entries)")
PY
