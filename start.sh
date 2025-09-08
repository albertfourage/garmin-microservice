#!/usr/bin/env bash
set -Eeuo pipefail

# Defaults and env
export TZ="${TZ:-Europe/Bratislava}"
PORT="${PORT:-8080}"

# Token path: prefer GARMINTOKENS_PATH, support legacy Garmintokens_Path, default to /data/garmintokens.json
TOKENS_PATH="${GARMINTOKENS_PATH:-${Garmintokens_Path:-/data/garmintokens.json}}"

echo "[start] pwd=$(pwd)"
echo "[start] python=$(python -V 2>&1)"
echo "[start] port=$PORT  tz=$TZ  tokens_path=$TOKENS_PATH"

# Ensure token directory exists
mkdir -p "$(dirname "$TOKENS_PATH")"

# Write tokens from env into file (raw JSON or base64)
if [[ -n "${GARMINTOKENS_JSON:-}" ]]; then
  printf "%s" "$GARMINTOKENS_JSON" >"$TOKENS_PATH"
elif [[ -n "${GARMINTOKENS_B64:-}" ]]; then
  echo "$GARMINTOKENS_B64" | base64 -d >"$TOKENS_PATH"
else
  echo "[start] ERROR: No tokens provided. Set GARMINTOKENS_JSON or GARMINTOKENS_B64." >&2
  exit 1
fi

chmod 600 "$TOKENS_PATH" || true
export GARMINTOKENS_PATH="$TOKENS_PATH"

# Validate JSON
python - <<'PY'
import json, os, sys
p=os.environ["GARMINTOKENS_PATH"]
try:
    with open(p,"rb") as f: json.load(f)
except Exception as e:
    sys.stderr.write(f"[start] ERROR: Invalid JSON in {p}: {e}\n"); sys.exit(1)
else:
    sys.stderr.write(f"[start] OK: Valid JSON at {p}\n")
PY

# Determine ASGI target
if [[ -n "${ASGI_APP:-}" ]]; then
  TARGET="$ASGI_APP"
else
  TARGET="$(python - <<'PY'
import importlib
cands=["app.main:app","app.api:app","app.main:api","main:app","app:app"]
for c in cands:
    try:
        m,v=c.split(":"); getattr(importlib.import_module(m), v)
    except Exception: pass
    else:
        print(c); break
PY
  )"
fi

if [[ -z "${TARGET:-}" ]]; then
  echo "[start] ERROR: Could not auto-detect FastAPI app. Set ASGI_APP env var (e.g., app.main:app)." >&2
  exit 1
fi
echo "[start] Using ASGI target: ${TARGET}"

# Launch Uvicorn
exec uvicorn "${TARGET}" --host 0.0.0.0 --port "${PORT}" --proxy-headers
