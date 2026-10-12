import argparse
import hashlib
import html
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from dotenv import find_dotenv, load_dotenv
except ModuleNotFoundError:
    find_dotenv = None
    load_dotenv = None


def load_env_file():
    if find_dotenv and load_dotenv:
        env_path = find_dotenv(usecwd=True)
        load_dotenv(env_path, override=True)
        return env_path

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return ""

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

    return str(env_path)


ENV_PATH = load_env_file()

API_KEY = os.getenv("HEYGEN_API_KEY")
DEFAULT_VOICE_ID = os.getenv("HEYGEN_VOICE_ID")

if not API_KEY or not DEFAULT_VOICE_ID:
    raise ValueError(
        "Missing HEYGEN_API_KEY or HEYGEN_VOICE_ID. "
        "Add both values to your .env file."
    )

DEFAULT_TEXT = (
    "Branch to collect ‘Form G’ with Income Tax Assessing Officer Stamp. Account cannot be closed solely on customer’s request."
)

parser = argparse.ArgumentParser(description="Generate speech using HeyGen TTS.")
parser.add_argument(
    "--voice-id",
    default=DEFAULT_VOICE_ID,
    help="HeyGen Starfish voice ID. Defaults to HEYGEN_VOICE_ID from .env.",
)
parser.add_argument(
    "--text",
    default=os.getenv("HEYGEN_TEXT", DEFAULT_TEXT),
    help="Text to synthesize. Defaults to HEYGEN_TEXT or the sample line.",
)
parser.add_argument(
    "--locale",
    default=os.getenv("HEYGEN_LOCALE"),
    help="Optional BCP-47 accent/locale hint, for example en-IN for Indian English.",
)
parser.add_argument(
    "--output",
    help="Output audio path. Defaults to a voice/text-specific filename.",
)
parser.add_argument(
    "--no-validate-voice",
    action="store_true",
    help="Skip checking that the voice exists in the Starfish-compatible voice list.",
)
parser.add_argument(
    "--validate-only",
    action="store_true",
    help="Validate the selected voice ID without generating audio.",
)
parser.add_argument(
    "--force-new",
    action="store_true",
    help="Use SSML with a tiny unique trailing pause to avoid HeyGen returning cached audio.",
)
args = parser.parse_args()

VOICE_ID = args.voice_id.strip()
TEXT = args.text.strip()
LOCALE = args.locale.strip() if args.locale else None

if not VOICE_ID:
    raise ValueError("HEYGEN_VOICE_ID is blank.")

if not TEXT:
    raise ValueError("Text is blank.")

session = requests.Session()

retries = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["POST", "GET"]),
)

session.mount("https://", HTTPAdapter(max_retries=retries))


def get_starfish_voice(voice_id):
    for voice_type in ("public", "private"):
        token = None
        while True:
            params = {"engine": "starfish", "type": voice_type, "limit": 100}
            if token:
                params["token"] = token

            response = session.get(
                "https://api.heygen.com/v3/voices",
                headers={"X-Api-Key": API_KEY},
                params=params,
                timeout=(15, 60),
            )
            response.raise_for_status()

            payload = response.json()
            for voice in payload.get("data", []):
                if voice.get("voice_id") == voice_id:
                    return {**voice, "type": voice_type}

            if not payload.get("has_more"):
                break

            token = payload.get("next_token")
            if not token:
                break

    return None


def default_output_path(audio_url, voice_id, text):
    suffix = Path(urlparse(audio_url).path).suffix or ".wav"
    text_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return Path(f"output_{voice_id[:8]}_{text_hash}{suffix}")


def build_request_body():
    request_text = TEXT
    input_type = "text"

    if args.force_new:
        nonce = uuid.uuid4().hex
        # HeyGen Starfish ignores pauses under ~100ms. A 200-350ms micro-pause forces fresh generation.
        pause_ms = 200 + (int(nonce[:2], 16) % 150)
        pause_seconds = pause_ms / 1000
        escaped_text = html.escape(TEXT, quote=False)
        request_text = (
            f"<speak>{escaped_text}<break time=\"{pause_seconds:.3f}s\"/>"
            f"<!-- cache-bust:{nonce} --></speak>"
        )
        input_type = "ssml"

    body = {
        "text": request_text,
        "voice_id": VOICE_ID,
        "input_type": input_type,
        "language": "en",
        "speed": 1.0,
    }
    if LOCALE:
        body["locale"] = LOCALE

    return body


try:
    print("Loaded .env:", ENV_PATH or "not found")
    print("Using voice ID:", VOICE_ID)
    print("Using locale:", LOCALE or "(auto)")
    print("Text SHA1:", hashlib.sha1(TEXT.encode("utf-8")).hexdigest())
    print("Force new:", args.force_new)

    if not args.no_validate_voice:
        voice = get_starfish_voice(VOICE_ID)
        if not voice:
            sys.exit(
                "Voice ID was not found in GET /v3/voices?engine=starfish. "
                "Pick a Starfish-compatible voice ID, or run with "
                "--no-validate-voice if you are sure it is valid."
            )

        print(
            "Voice match:",
            voice.get("name", "(unnamed)"),
            (
                f"[{voice.get('type')}, "
                f"{voice.get('language', 'unknown language')}, "
                f"support_locale={voice.get('support_locale')}]"
            ),
        )

    if args.validate_only:
        print("Validation passed. No audio was generated.")
        sys.exit(0)

    request_body = build_request_body()
    print(
        "Request text SHA1:",
        hashlib.sha1(request_body["text"].encode("utf-8")).hexdigest(),
    )

    response = session.post(
        "https://api.heygen.com/v3/voices/speech",
        headers={
            "X-Api-Key": API_KEY,
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=(15, 180),  # (connection timeout, server-response timeout)
    )

    print("HTTP status:", response.status_code)

    if not response.ok:
        print("HeyGen response:", response.text)
        response.raise_for_status()

    payload = response.json()
    data = payload["data"]

    audio_url = data["audio_url"]
    print("Audio URL:", audio_url)
    print("Duration:", data.get("duration"), "seconds")

    audio_response = session.get(audio_url, timeout=(15, 180))
    audio_response.raise_for_status()

    output_path = (
        Path(args.output)
        if args.output
        else default_output_path(audio_url, VOICE_ID, request_body["text"])
    )
    with open(output_path, "wb") as f:
        f.write(audio_response.content)

    print("Success: saved", output_path)

except requests.exceptions.ConnectTimeout:
    sys.exit("Connection timeout: check internet, VPN, firewall, or proxy settings.")

except requests.exceptions.ReadTimeout:
    sys.exit(
        "HeyGen did not respond within 180 seconds. "
        "Retry later; also test with a very short sentence and verify your network."
    )

except requests.exceptions.HTTPError as e:
    sys.exit(f"HTTP error: {e}")

except requests.exceptions.RequestException as e:
    sys.exit(f"Network/API request failed: {e}")
