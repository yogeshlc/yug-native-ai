#!/bin/zsh
cd "${0:A:h}"
if ! command -v python3 >/dev/null; then
  echo "Install Python 3 from https://www.python.org/downloads/macos/ and try again."
  read
  exit 1
fi
open "http://127.0.0.1:${YUG_PORT:-8787}"
python3 server.py
