#!/usr/bin/env bash
echo "============================================"
echo "         Python Chess Game Launcher"
echo "============================================"
echo
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed or not in PATH."
  echo "Please install Python 3.7 or newer."
  exit 1
fi
python3 - << 'PY'
import sys
if sys.version_info < (3, 7):
    print("Python 3.7 or newer is required.")
    sys.exit(1)
PY
if [ $? -ne 0 ]; then
  exit 1
fi
if [ -f "requirements.txt" ]; then
  echo
  echo "Installing Python dependencies from requirements.txt..."
  python3 -m pip install --upgrade pip >/dev/null 2>&1
  python3 -m pip install -r requirements.txt
fi
echo
echo "Launching chess game..."
echo
python3 -m chess_game.main "$@"

