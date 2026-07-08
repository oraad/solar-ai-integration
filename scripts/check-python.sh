#!/usr/bin/env bash
set -euo pipefail
python -c 'import sys; assert sys.version_info >= (3, 14), f"Python 3.14+ required, got {sys.version}"'
echo "OK: $(python --version)"
