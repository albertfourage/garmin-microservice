#!/usr/bin/env bash
set -euo pipefail

# Expect this env var to be set in Railway
: "${Garmintokens_Path:?Garmintokens_Path env var is missing}"

# Write tokens from env into the file your app expects
if [[ -n "${GARMINTOKENS_JSON:-}" ]]; then
  mkdir -p "$(dirname "$Garmintokens_Path")"
  printf "%s" "$GARMINTOKENS_JSON" > "$Garmintokens_Path"
elif [[ -n "${GARMINTOKENS_B64:-}" ]]; then
  mkdir -p "$(dirname "$Garmintokens_Path")"
  echo "$GARMINTOKENS_B64" | base64 -d > "$Garmintokens_Path"
else
  echo "No tokens provided (set GARMINTOKENS_JSON or GARMINTOKENS_B64 in Railway)." >&2
  exit 1
fi

# Install and start your app (adjust the last line to your entrypoint)
python -m pip install --no-cache-dir -r requirements.txt
python main.py
