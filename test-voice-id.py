import os
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


def load_env_file():
    if load_dotenv:
        load_dotenv(override=True)
        return

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def list_voices(voice_type):
    token = None
    while True:
        params = {"engine": "starfish", "type": voice_type, "limit": 100}
        if token:
            params["token"] = token

        response = requests.get(
            "https://api.heygen.com/v3/voices",
            headers={"X-Api-Key": os.environ["HEYGEN_API_KEY"]},
            params=params,
            timeout=(15, 60),
        )
        print(f"Status ({voice_type}):", response.status_code)
        response.raise_for_status()

        payload = response.json()
        for voice in payload.get("data", []):
            print(
                voice.get("voice_id"),
                "|",
                voice.get("name", "(unnamed)"),
                "|",
                voice.get("language", "unknown language"),
                "|",
                voice.get("gender", "unknown gender"),
                "|",
                f"support_locale={voice.get('support_locale')}",
            )

        if not payload.get("has_more"):
            break

        token = payload.get("next_token")
        if not token:
            break


load_env_file()

if "HEYGEN_API_KEY" not in os.environ:
    raise ValueError("Missing HEYGEN_API_KEY in .env")

list_voices("public")
list_voices("private")
