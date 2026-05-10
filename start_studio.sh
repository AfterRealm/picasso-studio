#!/usr/bin/env bash
# Picasso Studio launcher for macOS / Linux.
#
# Mirrors the Windows start_studio.bat. Resolves the script's own directory
# so it works whether you double-click it or invoke from anywhere on PATH.
# Set PICASSO_PORT / PICASSO_HOST in your shell to override the bind.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${HERE}/scripts/start_studio.py" "$@"
