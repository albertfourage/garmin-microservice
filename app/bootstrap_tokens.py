import os, pathlib

def main():
    token_dir = os.getenv("GARMINTOKENS", "/data/garmin_tokens")
    p = pathlib.Path(token_dir)
    p.mkdir(parents=True, exist_ok=True)

    o1 = os.getenv("OAUTH1_TOKEN_JSON")
    o2 = os.getenv("OAUTH2_TOKEN_JSON")

    if not (o1 and o2):
        print("bootstrap_tokens: missing OAUTH1_TOKEN_JSON or OAUTH2_TOKEN_JSON; continuing without writing tokens")
        return

    (p / "oauth1_token.json").write_text(o1, encoding="utf-8")
    (p / "oauth2_token.json").write_text(o2, encoding="utf-8")

    print(f"bootstrap_tokens: wrote tokens to {p}")

if __name__ == "__main__":
    main()
