# app/bootstrap_tokens.py
import json
import os
import pathlib
import sys
from garminconnect import Garmin

TOKENS_DIR = pathlib.Path(os.getenv("GARMINTOKENS", "/data/garmin_tokens"))

def _write_json(p: pathlib.Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")

def main():
    # If tokens already exist, do nothing (idempotent)
    o1 = TOKENS_DIR / "oauth1_token.json"
    o2 = TOKENS_DIR / "oauth2_token.json"
    if o1.exists() and o2.exists():
        print(f"[bootstrap_tokens] Found existing tokens in {TOKENS_DIR}", flush=True)
        return

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not (email and password):
        print("[bootstrap_tokens] No tokens found and no GARMIN_EMAIL/PASSWORD set; skipping bootstrap.", flush=True)
        return

    TOKENS_DIR.mkdir(parents=True, exist_ok=True)

    # Login to create/refresh tokens (garth will dump to TOKENS_DIR)
    os.environ["GARMINTOKENS"] = str(TOKENS_DIR)
    g = Garmin(email, password)
    g.login()
    # g.garth.dump(TOKENS_DIR)  # garminconnect handles dump on login; keep explicit if needed
    print(f"[bootstrap_tokens] Wrote tokens to {TOKENS_DIR}", flush=True)

if __name__ == "__main__":
    main()
