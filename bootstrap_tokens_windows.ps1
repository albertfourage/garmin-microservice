# Usage:
#   powershell -ExecutionPolicy Bypass -File .\bootstrap_tokens_windows.ps1 -Email you@example.com
param([Parameter(Mandatory=$true)][string]$Email)

python - << 'PY'
from garminconnect import Garmin
import os, json, getpass, pathlib
email = "'$Email'"
pwd = getpass.getpass(f"Garmin password for {email}: ")
tokens_path = str(pathlib.Path.cwd() / "tokens.json")
os.environ["GARMINTOKENS"] = tokens_path
g = Garmin(email, pwd); g.login()
print("Tokens saved to:", tokens_path)
PY
