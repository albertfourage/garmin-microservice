#!/usr/bin/env bash
set -euo pipefail

# Optional: set timezone for logs
export TZ="${TZ:-Europe/Bratislava}"

# Create tokens file from env if provided
TOKENS_PATH="${Garmintokens_Path:-/data/garmintokens.json}"
mkdir -p "$(dirname "$TOKENS_PATH")"
if [[ -n "${GARMINTOKENS_JSON:-}" ]]; then
  echo "$GARMINTOKENS_JSON" > "$TOKENS_PATH"
elif [[ -n "${GARMINTOKENS_B64:-}" ]]; then
  python - <<'PY'
import os, base64, json, sys, pathlib
p = os.environ.get("Garmintokens_Path","/data/garmintokens.json")
raw = base64.b64decode(os.environ["GARMINTOKENS_B64"]).decode()
# sanity check
json.loads(raw)
pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
open(p,"w",encoding="utf-8").write(raw)
print(f"Wrote tokens to {p}", file=sys.stderr)
PY
else
  echo "No tokens env provided; continuing (app may login headlessly)" >&2
fi

# Start your web app; ensure host 0.0.0.0 and port $PORT
echo "Binding to 0.0.0.0:${PORT:-8000}" >&2
uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
