#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3.10 or newer is required. Install Python from python.org, then reopen Compass.'
  read -r -p 'Press Return to close. ' unused_reply
  exit 1
fi
exec python3 -m compass gui
