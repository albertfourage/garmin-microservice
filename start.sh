#!/usr/bin/env bash
set -Eeuo pipefail

# ------------------------------------------------------------
# start.sh — boot script for the Garmin microservice
# Accepts either:
#   A) Two-file token directory mode (preferred):
#        OAUTH1_TOKEN_JSON, OAUTH2_TOKEN_JSON  -> /data/garmin_tokens/{oauth1,oauth2}_token.json
#      or existing files at /data/garmin_tokens/* (when a Volume is attached)
#   B) Single-file JSON mode (legacy):
#        GARMINTOKENS_JSON or GARMINTOKENS_B64  -> /data/garmintokens.json
#
# Exports GARMINTOKENS to whichever artifact exists (dir or file).
# Validates JSON before starting the ASGI server.
# ------------------------------------------------------------

# Environment defaults
export TZ="${TZ:-Europe/Bratislava}"
PORT="${PORT:-8080}"

# Canonical locations inside the container
TOKENS_FILE="${GARMINTOKENS_PATH:-${Garmintokens_Path:-/data/garmintokens.json}}"

echo "[start] pwd=$(pwd)"
echo "[start] python=$(python -V 2>&1)"
echo "[start] port=$PORT  tz=$TZ"

# Ensure destinations exist

# Decide token source and write/use it
mode=""
if [[ -n "${OAUTH1_TOKEN_JSON:-}" && -n "${OAUTH2_TOKEN_JSON:-}" ]]; then
  # Preferred: two-file mode via env
  printf "%s" "$OAUTH1_TOKEN_JSON" >"$TOKENS_DIR/oauth1_token.json"
  printf "%s" "$OAUTH2_TOKEN_JSON" >"$TOKENS_DIR/oauth2_token.json"
  chmod 600 "$TOKENS_DIR"/oauth*.json || true
  export GARMINTOKENS="$TOKENS_DIR"
  mode="dir(env)"
  echo "[start] OK: wrote oauth1/2 to $TOKENS_DIR"
elif [[ -n "${GARMINTOKENS_JSON:-}" ]]; then
  # Legacy: one-file raw JSON via env
  printf "%s" "$GARMINTOKENS_JSON" >"$TOKENS_FILE"
  chmod 600 "$TOKENS_FILE" || true
  export GARMINTOKENS="$TOKENS_FILE"
  mode="file(env)"
  echo "[start] OK: wrote tokens JSON to $TOKENS_FILE"
elif [[ -n "${GARMINTOKENS_B64:-}" ]]; then
  # Legacy: one-file Base64 via env
  echo "$GARMINTOKENS_B64" | base64 -d >"$TOKENS_FILE"
  chmod 600 "$TOKENS_FILE" || true
  export GARMINTOKENS="$TOKENS_FILE"
  mode="file(env:b64)"
  echo "[start] OK: wrote tokens from B64 to $TOKENS_FILE"
elif [[ -f "$TOKENS_FILE" ]]; then
  # Reuse existing single-file token in the Volume
  export GARMINTOKENS="$TOKENS_FILE"
  mode="file(existing)"
  echo "[start] OK: using existing $TOKENS_FILE"
elif [[ -f "$TOKENS_DIR/oauth1_token.json" && -f "$TOKENS_DIR/oauth2_token.json" ]]; then
  # Reuse existing two-file tokens in the Volume
  export GARMINTOKENS="$TOKENS_DIR"
  mode="dir(existing)"
  echo "[start] OK: using existing $TOKENS_DIR"
else
  echo "[start] ERROR: No tokens found. Provide OAUTH1_TOKEN_JSON + OAUTH2_TOKEN_JSON (preferred) "
  echo "        or GARMINTOKENS_JSON/GARMINTOKENS_B64 (legacy), or attach a Volume with existing tokens." >&2
  exit 1
fi

# Validate tokens JSON (best-effort)
python - <<'PY'
import json, os, sys, pathlib
p = os.environ["GARMINTOKENS"]
pp = pathlib.Path(p)

def check_file(f):
    try:
        with open(f, "rb") as fh:
            json.load(fh)
        sys.stderr.write(f"[start] OK: Valid JSON at {f}\n")
    except Exception as e:
        sys.stderr.write(f"[start] ERROR: Invalid JSON in {f}: {e}\n")
        sys.exit(1)

if pp.is_dir():
    check_file(pp / "oauth1_token.json")
    check_file(pp / "oauth2_token.json")
else:
    check_file(pp)
PY

# Auto-detect ASGI app target unless ASGI_APP is set
if [[ -n "${ASGI_APP:-}" ]]; then
  TARGET="$ASGI_APP"
else
  TARGET="$(python - <<'PY'
import importlib
cands=["app.main:app","app.api:app","app.main:api","main:app","app:app"]
for c in cands:
    try:
        m,v=c.split(":"); getattr(importlib.import_module(m), v)
    except Exception:
        pass
    else:
        print(c); break
PY
  )"
fi

if [[ -z "${TARGET:-}" ]]; then
  echo "[start] ERROR: Could not auto-detect ASGI app target. Set ASGI_APP='module:var'." >&2
  exit 1
fi

echo "[start] Using ASGI target: $TARGET  (tokens mode: $mode)"
exec uvicorn "$TARGET" --host 0.0.0.0 --port "${PORT}"
