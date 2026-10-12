import os
import sys
import uuid
import html
import time
import re
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_file
import io
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
        if env_path:
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


# Load environment variables
load_env_file()

SHEETAL_VOICE_ID = "b219f9f8d8e6455e85e470949d680229"
VOICE_NAME = "Sheetal"

app = Flask(__name__)

# Temporary in-memory audio storage
# audio_id -> {"data": bytes, "created_at": float, "duration": float, "force_new": bool, "text": str}
AUDIO_CACHE = {}


def cleanup_audio_cache():
    """Remove audio records older than 1 hour to prevent memory bloat."""
    now = time.time()
    expired = [aid for aid, item in AUDIO_CACHE.items() if now - item["created_at"] > 3600]
    for aid in expired:
        AUDIO_CACHE.pop(aid, None)


def get_requests_session():
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
    return session


def build_heygen_request_body(text: str, voice_id: str, force_new: bool = False, locale: str = None):
    request_text = text
    input_type = "text"

    if force_new:
        nonce = uuid.uuid4().hex
        # HeyGen Starfish ignores pauses under ~100ms. A 200-350ms micro-pause forces fresh generation.
        pause_ms = 200 + (int(nonce[:2], 16) % 150)
        pause_seconds = pause_ms / 1000.0
        escaped_text = html.escape(text, quote=False)
        request_text = (
            f'<speak>{escaped_text}<break time="{pause_seconds:.3f}s"/>'
            f'<!-- cache-bust:{nonce} --></speak>'
        )
        input_type = "ssml"

    body = {
        "text": request_text,
        "voice_id": voice_id,
        "input_type": input_type,
        "language": "en",
        "speed": 1.0,
    }
    if locale:
        body["locale"] = locale

    return body


@app.route("/")
def index():
    return render_template("index.html", voice_name=VOICE_NAME, voice_id=SHEETAL_VOICE_ID)


@app.route("/api/voice-info", methods=["GET"])
def voice_info():
    api_key = os.getenv("HEYGEN_API_KEY", "")
    return jsonify({
        "voice_name": VOICE_NAME,
        "voice_id": SHEETAL_VOICE_ID,
        "has_api_key": bool(api_key.strip()),
        "status": "ready"
    })


@app.route("/api/generate", methods=["POST"])
def generate_speech():
    cleanup_audio_cache()

    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key or not api_key.strip():
        return jsonify({
            "success": False,
            "error_type": "CONFIG_ERROR",
            "error": "HeyGen API Key is missing. Please set 'HEYGEN_API_KEY' in your .env configuration file."
        }), 400

    data = request.get_json(silent=True) or {}
    raw_text = data.get("text", "")
    force_new = bool(data.get("force_new", False))
    locale = data.get("locale") or os.getenv("HEYGEN_LOCALE") or None

    # Input validations
    if not raw_text or not isinstance(raw_text, str):
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_EMPTY",
            "error": "Text input is required. Please type or paste some text to synthesize."
        }), 400

    cleaned_text = raw_text.strip()
    if not cleaned_text:
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_WHITESPACE",
            "error": "Text cannot consist only of spaces or whitespace. Please enter valid speech content."
        }), 400

    if len(cleaned_text) > 3000:
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_LENGTH",
            "error": f"Text length ({len(cleaned_text)} characters) exceeds the 3000 character limit for a single synthesis request."
        }), 400

    script_path = Path(__file__).parent / "tts_heygen.py"

    # Execute tts_heygen.py CLI script with --force-new when requested
    if script_path.exists():
        temp_id = uuid.uuid4().hex
        temp_audio_file = Path(tempfile.gettempdir()) / f"sheetal_tts_{temp_id}.wav"

        cmd = [
            sys.executable,
            str(script_path),
            "--voice-id", SHEETAL_VOICE_ID,
            "--text", cleaned_text,
            "--output", str(temp_audio_file),
            "--no-validate-voice"
        ]
        if force_new:
            cmd.append("--force-new")

        print(f"[TTS Server] Invoking command: {' '.join(cmd)}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=190)
            combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            print(f"[TTS Server Output]\n{combined_output.strip()}")

            # Check for credit exhaustion specifically
            lower_out = combined_output.lower()
            if (
                "402" in lower_out or
                "credit" in lower_out or
                "quota" in lower_out or
                "insufficient" in lower_out or
                "balance" in lower_out or
                "limit reached" in lower_out
            ):
                return jsonify({
                    "success": False,
                    "error_type": "CREDITS_EXHAUSTED",
                    "error": "HeyGen credits are exhausted. Please recharge your HeyGen credits or upgrade your plan to generate more speech audio."
                }), 402

            if proc.returncode == 0 and temp_audio_file.exists():
                audio_bytes = temp_audio_file.read_bytes()
                try:
                    temp_audio_file.unlink()
                except Exception:
                    pass

                # Parse duration from CLI output
                duration = 0.0
                dur_match = re.search(r"Duration:\s*([\d\.]+)", proc.stdout)
                if dur_match:
                    try:
                        duration = float(dur_match.group(1))
                    except ValueError:
                        pass

                audio_id = uuid.uuid4().hex
                AUDIO_CACHE[audio_id] = {
                    "data": audio_bytes,
                    "created_at": time.time(),
                    "duration": duration,
                    "force_new": force_new,
                    "text": cleaned_text,
                    "filename": f"sheetal_tts_{audio_id[:8]}.wav"
                }

                return jsonify({
                    "success": True,
                    "audio_id": audio_id,
                    "duration": round(duration, 2) if duration else 0,
                    "force_new": force_new,
                    "preview_url": f"/api/audio/{audio_id}",
                    "download_url": f"/api/download/{audio_id}",
                    "message": "Speech generated successfully!" if not force_new else "Speech regenerated fresh (cache bypassed with --force-new)!"
                })
            else:
                # Subprocess exited with error
                if "timeout" in lower_out:
                    return jsonify({
                        "success": False,
                        "error_type": "TIMEOUT",
                        "error": "HeyGen request timed out. Please check your network connection and try again."
                    }), 504

                return jsonify({
                    "success": False,
                    "error_type": "HEYGEN_CLI_ERROR",
                    "error": proc.stderr.strip() or proc.stdout.strip() or f"Command failed with exit code {proc.returncode}."
                }), 500

        except subprocess.TimeoutExpired:
            return jsonify({
                "success": False,
                "error_type": "TIMEOUT",
                "error": "HeyGen synthesis command timed out after 190 seconds."
            }), 504
        except Exception as e:
            print(f"[TTS Server Error] Subprocess execution error: {e}")
            # Fall through to direct API execution if subprocess invocation fails

    # Direct API execution fallback
    voice_id = SHEETAL_VOICE_ID
    request_body = build_heygen_request_body(cleaned_text, voice_id, force_new=force_new, locale=locale)
    session = get_requests_session()

    try:
        api_response = session.post(
            "https://api.heygen.com/v3/voices/speech",
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=(15, 180)
        )

        status_code = api_response.status_code
        try:
            resp_json = api_response.json()
        except Exception:
            resp_json = {}

        error_msg = ""
        if isinstance(resp_json, dict):
            error_msg = resp_json.get("message") or resp_json.get("error") or ""
            if not error_msg and "data" in resp_json and isinstance(resp_json["data"], dict):
                error_msg = resp_json["data"].get("message") or resp_json["data"].get("error") or ""

        # Check for credit exhaustion specifically
        is_credit_exhausted = (
            status_code == 402 or
            "credit" in error_msg.lower() or
            "quota" in error_msg.lower() or
            "insufficient" in error_msg.lower() or
            "balance" in error_msg.lower() or
            "limit reached" in error_msg.lower()
        )

        if is_credit_exhausted:
            return jsonify({
                "success": False,
                "error_type": "CREDITS_EXHAUSTED",
                "error": "HeyGen credits are exhausted. Please recharge your HeyGen credits or upgrade your plan to generate more speech audio."
            }), 402

        if not api_response.ok:
            if status_code == 401 or status_code == 403:
                return jsonify({
                    "success": False,
                    "error_type": "AUTH_ERROR",
                    "error": f"HeyGen authorization failed (HTTP {status_code}). Please verify your HEYGEN_API_KEY in .env."
                }), 401

            if status_code == 429:
                return jsonify({
                    "success": False,
                    "error_type": "RATE_LIMIT",
                    "error": "HeyGen API rate limit reached. Please wait a moment and try again."
                }), 429

            return jsonify({
                "success": False,
                "error_type": "HEYGEN_API_ERROR",
                "error": f"HeyGen API Error ({status_code}): {error_msg or api_response.text}"
            }), status_code

        data_payload = resp_json.get("data", {})
        audio_url = data_payload.get("audio_url")
        duration = data_payload.get("duration", 0)

        if not audio_url:
            return jsonify({
                "success": False,
                "error_type": "NO_AUDIO_URL",
                "error": "HeyGen processed the request but did not return a valid audio download URL."
            }), 502

        audio_fetch = session.get(audio_url, timeout=(15, 180))
        audio_fetch.raise_for_status()

        audio_id = uuid.uuid4().hex
        AUDIO_CACHE[audio_id] = {
            "data": audio_fetch.content,
            "created_at": time.time(),
            "duration": duration,
            "force_new": force_new,
            "text": cleaned_text,
            "filename": f"sheetal_tts_{audio_id[:8]}.wav"
        }

        return jsonify({
            "success": True,
            "audio_id": audio_id,
            "duration": round(duration, 2) if duration else 0,
            "force_new": force_new,
            "preview_url": f"/api/audio/{audio_id}",
            "download_url": f"/api/download/{audio_id}",
            "message": "Speech generated successfully!" if not force_new else "Speech regenerated fresh (cache bypassed with --force-new)!"
        })

    except requests.exceptions.ConnectTimeout:
        return jsonify({
            "success": False,
            "error_type": "TIMEOUT_CONNECT",
            "error": "Connection timed out while connecting to HeyGen API. Please check your internet connection or firewall/proxy."
        }), 504

    except requests.exceptions.ReadTimeout:
        return jsonify({
            "success": False,
            "error_type": "TIMEOUT_READ",
            "error": "HeyGen took longer than 180 seconds to synthesize the audio. Try with shorter text or retry shortly."
        }), 504

    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error_type": "NETWORK_ERROR",
            "error": f"Network error communicating with HeyGen: {str(e)}"
        }), 502

    except Exception as e:
        return jsonify({
            "success": False,
            "error_type": "SERVER_ERROR",
            "error": f"An unexpected server error occurred: {str(e)}"
        }), 500


@app.route("/api/audio/<audio_id>", methods=["GET"])
def stream_audio(audio_id):
    """Serve the audio for in-browser audio preview without initiating a file download."""
    item = AUDIO_CACHE.get(audio_id)
    if not item:
        return jsonify({"error": "Audio file not found or expired from temporary preview cache."}), 404

    return Response(
        item["data"],
        mimetype="audio/wav",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Content-Length": str(len(item["data"]))
        }
    )


@app.route("/api/download/<audio_id>", methods=["GET"])
def download_audio(audio_id):
    """Explicitly trigger file download with Content-Disposition attachment."""
    item = AUDIO_CACHE.get(audio_id)
    if not item:
        return jsonify({"error": "Audio file not found or expired from temporary cache."}), 404

    return send_file(
        io.BytesIO(item["data"]),
        mimetype="audio/wav",
        as_attachment=True,
        download_name=item.get("filename", f"sheetal_tts_{audio_id[:8]}.wav")
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Text-to-Speech (Sheetal's Voice) server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
