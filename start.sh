#!/usr/bin/env bash
set -euo pipefail

# Expect this env var to be set in Railway
: "${GARMINTOKENS_PATH_Path:?GARMINTOKENS_PATH_Path env var is missing}"

# Write tokens from env into the file your app expects
if [[ -n "${GARMINTOKENS_PATH_JSON:-}" ]]; then
  mkdir -p "$(dirname "$GARMINTOKENS_PATH_Path")"
  printf "%s" "$GARMINTOKENS_PATH_JSON" > "$GARMINTOKENS_PATH_Path"
elif [[ -n "${GARMINTOKENS_PATH_B64:-}" ]]; then
  mkdir -p "$(dirname "$GARMINTOKENS_PATH_Path")"
  echo "$GARMINTOKENS_PATH_B64" | base64 -d > "$GARMINTOKENS_PATH_Path"
else
  echo "No tokens provided (set GARMINTOKENS_PATH_JSON or GARMINTOKENS_PATH_B64 in Railway)." >&2
  exit 1
fi

# Install and start your app (adjust the last line to your entrypoint)
python -m pip install --no-cache-dir -r requirements.txt
python main.py
