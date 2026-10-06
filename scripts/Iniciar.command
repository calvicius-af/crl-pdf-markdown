#!/bin/bash
set -e
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python scripts/launch_gui.py
fi
exec python3 scripts/launch_gui.py
