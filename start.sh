#!/usr/bin/env bash
set -Eeuo pipefail

# ------------------------------------------------------------
# start.sh — minimal, two-file tokens only
# Inputs (one of):
#   - Env vars: OAUTH1_TOKEN_JSON + OAUTH2_TOKEN_JSON
#   - Existing files in /data/garmin_tokens/{oauth1_token.json,oauth2_token.json}
#
# Exports:
#   - GARMINTOKENS=/data/garmin_tokens
# ------------------------------------------------------------

export TZ="${TZ:-Europe/Bratislava}"
PORT="${PORT:-8080}"
TOKENS_DIR="/data/garmin_tokens"
O1_PATH="$TOKENS_DIR/oauth1_token.json"
O2_PATH="$TOKENS_DIR/oauth2_token.json"

echo "[start] pwd=$(pwd)"
echo "[start] python=$(python -V 2>&1)"
echo "[start] port=$PORT  tz=$TZ"
echo "[start] tokens_dir=$TOKENS_DIR"

# Guard: if a leftover FILE exists where the directory should be, move it aside
if [[ -e "$TOKENS_DIR" && ! -d "$TOKENS_DIR" ]]; then
  echo "[start] Found legacy file at $TOKENS_DIR; moving to /data/garmintokens.json.legacy"
  mv -f "$TOKENS_DIR" /data/garmintokens.json.legacy
fi

# Ensure tokens directory exists
mkdir -p "$TOKENS_DIR"

# Source of truth for tokens
mode=""
if [[ -n "${OAUTH1_TOKEN_JSON:-}" && -n "${OAUTH2_TOKEN_JSON:-}" ]]; then
  printf "%s" "$OAUTH1_TOKEN_JSON" >"$O1_PATH"
  printf "%s" "$OAUTH2_TOKEN_JSON" >"$O2_PATH"
  chmod 600 "$O1_PATH" "$O2_PATH" || true
  mode="dir(env)"
  echo "[start] Wrote oauth1/2 tokens from env to $TOKENS_DIR"
elif [[ -f "$O1_PATH" && -f "$O2_PATH" ]]; then
  mode="dir(existing)"
  echo "[start] Using existing tokens in $TOKENS_DIR"
else
  echo "[start] ERROR: No tokens found. Set OAUTH1_TOKEN_JSON and OAUTH2_TOKEN_JSON, or attach a Volume with $O1_PATH and $O2_PATH." >&2
  exit 1
fi

# Validate JSON (best-effort, fail hard if invalid)
python - <<'PY'
import json, os, sys, pathlib
td = pathlib.Path("/data/garmin_tokens")
o1, o2 = td/"oauth1_token.json", td/"oauth2_token.json"
for f in (o1, o2):
    try:
        with open(f, "rb") as fh:
            json.load(fh)
        sys.stderr.write(f"[start] OK: Valid JSON at {f}\n")
    except Exception as e:
        sys.stderr.write(f"[start] ERROR: Invalid JSON in {f}: {e}\n")
        sys.exit(1)
PY

# Export for garth/garminconnect
export GARMINTOKENS="$TOKENS_DIR"

# Pick ASGI target (simple default; override with ASGI_APP if needed)
TARGET="${ASGI_APP:-app.main:app}"

echo "[start] Using ASGI target: $TARGET (tokens mode: $mode)"
exec uvicorn "$TARGET" --host 0.0.0.0 --port "${PORT}"
