# Text To Speech Studio (Sheetal's Voice)

A modern, high-fidelity Text-to-Speech (TTS) studio and multi-provider toolkit built with Python, Flask, and Vanilla CSS/JS. The application features a dedicated web interface for **Sheetal's Voice** using HeyGen's Starfish neural TTS engine, alongside CLI tools for HeyGen voice exploration and ElevenLabs multilingual streaming.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Project Architecture](#project-architecture)
- [Prerequisites & Installation](#prerequisites--installation)
- [Configuration (.env)](#configuration-env)
- [Running the Web Studio](#running-the-web-studio)
- [CLI Tools & Scripts](#cli-tools--scripts)
  - [HeyGen TTS CLI (`tts_heygen.py`)](#heygen-tts-cli-tts_heygenpy)
  - [Voice Discovery (`test-voice-id.py`)](#voice-discovery-test-voice-idpy)
  - [ElevenLabs Streaming (`tts_elevenlabs.py`)](#elevenlabs-streaming-tts_elevenlabspy)
- [REST API Endpoints](#rest-api-endpoints)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Technical Highlights](#technical-highlights)
  - [Cache-Busting Regeneration (`--force-new`)](#cache-busting-regeneration---force-new)
  - [Credit Exhaustion Handling](#credit-exhaustion-handling)
  - [Temporary In-Memory Preview](#temporary-in-memory-preview)

---

## Overview

The primary focus of this project is **Sheetal's Voice** (`b219f9f8d8e6455e85e470949d680229`), a private HeyGen Starfish model tuned for English with an authentic Indian accent. The web application allows users to enter text, preview synthesized speech directly in their browser without downloading, trigger fresh generations with cache-busting, and download `.wav` audio files when desired.

---

## Key Features

- **Sheetal Voice Studio**: Sleek, glassmorphic dark-mode web interface with ambient glows and responsive controls.
- **In-Browser Audio Preview**: Synthesized audio is held temporarily in server memory and streamed into an interactive HTML5 audio player (play/pause, scrubbing timeline, volume, duration) without saving directly to the user's filesystem.
- **Explicit Audio Download**: Dedicated download button serves audio with `Content-Disposition: attachment; filename="sheetal_tts_<id>.wav"`.
- **Force-New Regeneration**: One-click **Regenerate Voice** button invokes the `--force-new` SSML cache-busting logic, guaranteeing a fresh audio variation from HeyGen's neural engine.
- **Comprehensive Input Validation**:
  - Rejects empty input and pure whitespace with actionable user alerts.
  - Warns when text exceeds the 3000 character limit.
  - Live character and word counters.
- **Credit Exhaustion Detection**: Specifically identifies HTTP 402 or credit/quota depletion responses from HeyGen and presents a prominent warning banner informing the user that credits need to be recharged.
- **Quick Sample Prompts**: One-click chips for testing banking notices (Form G notice, customer inquiry, branch welcome).
- **Multi-Provider Support**: Includes standalone scripts for HeyGen voice catalog discovery and ElevenLabs Multilingual v2 audio generation.

---

## Project Architecture

```
Text-to-speech/
├── app.py                  # Flask web backend & API controller
├── tts_heygen.py           # Production CLI tool for HeyGen TTS with --force-new logic
├── tts_elevenlabs.py       # ElevenLabs Multilingual v2 streaming TTS script
├── test-voice-id.py        # HeyGen Starfish voice discovery & pagination tool
├── test_app.py             # Automated unit & integration test suite (8 tests)
├── requirements.txt        # Pinned Python package dependencies
├── .env                    # Environment credentials & voice IDs (git-ignored)
├── README.md               # Complete project documentation
├── templates/
│   └── index.html          # Semantic HTML5 UI with glassmorphic styling
└── static/
    ├── css/
    │   └── style.css       # Custom design system, dark mode, animations
    └── js/
        └── app.js          # Client-side audio player, validation, and API fetch
```

---

## Prerequisites & Installation

### Requirements
- **Python 3.10+** (tested on Python 3.13 and 3.15)
- **uv** (recommended) or standard **pip**

### 1. Clone or Open Workspace
```bash
cd d:\Internship\Text-to-speech
```

### 2. Create and Activate Virtual Environment

Using `uv` (fast):
```powershell
uv venv .venv
.venv\Scripts\activate
```

Or using standard Python `venv`:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

---

## Configuration (.env)

Create or update the `.env` file in the root directory:

```env
# HeyGen Configuration
HEYGEN_API_KEY=sk_V2_hgu_...
HEYGEN_VOICE_ID=b219f9f8d8e6455e85e470949d680229

# ElevenLabs Configuration (Optional for ElevenLabs script)
ELEVENLABS_API_KEY=sk_f035...
ELEVENLABS_VOICE_ID=bc2f4d8...

# Optional Locale Hint
HEYGEN_LOCALE=en-IN
```

| Variable | Description |
| :--- | :--- |
| `HEYGEN_API_KEY` | Your HeyGen v2/v3 API key. |
| `HEYGEN_VOICE_ID` | Target voice model ID (defaults to Sheetal: `b219f9f8d8e6455e85e470949d680229`). |
| `ELEVENLABS_API_KEY` | API key for ElevenLabs synthesis. |
| `ELEVENLABS_VOICE_ID` | Default voice ID for ElevenLabs script. |
| `HEYGEN_LOCALE` | Optional BCP-47 locale hint (e.g., `en-IN` for Indian English). |

---

## Running the Web Studio

Start the Flask application:

```powershell
python app.py
```

The server starts on `http://localhost:5000`. Open your browser and navigate to:
```
http://localhost:5000
```

### Web Interface Controls

1. **Input Textarea**: Enter speech text or click any of the **Try quick samples** chips.
2. **Generate Speech**: Generates audio using Sheetal's voice and loads the player for instant preview.
3. **Regenerate Voice (`--force-new`)**: Bypasses server caching to produce a freshly synthesized speech clip.
4. **Download Audio**: Downloads the generated `.wav` audio file with descriptive filename (`sheetal_tts_<id>.wav`).
5. **Interactive Player**: Scrub through the audio waveform, toggle play/pause, adjust volume, or mute.

---

## CLI Tools & Scripts

### HeyGen TTS CLI (`tts_heygen.py`)

A standalone CLI tool supporting all HeyGen Starfish synthesis parameters:

```powershell
# Basic speech synthesis
python tts_heygen.py --text "Welcome to our branch." --output output.wav

# Force fresh generation bypassing HeyGen's audio cache
python tts_heygen.py --text "Welcome to our branch." --output output_fresh.wav --force-new

# Validate voice ID without consuming API credits
python tts_heygen.py --validate-only

# Specify custom voice ID and locale hint
python tts_heygen.py --voice-id b219f9f8d8e6455e85e470949d680229 --locale en-IN --text "Hello world"
```

#### CLI Arguments:
- `--text`: Text to synthesize (defaults to prompt in `.env` or sample banking line).
- `--voice-id`: Voice ID (defaults to `HEYGEN_VOICE_ID`).
- `--output`: Output `.wav` file path (defaults to `output_<voice_id>_<hash>.wav`).
- `--force-new`: Injects an effective micro-pause and unique SSML nonce to bypass HeyGen's server cache.
- `--validate-only`: Checks if the voice ID exists without synthesizing audio or using credits.
- `--no-validate-voice`: Skips pre-flight voice query to speed up execution.
- `--locale`: BCP-47 locale hint (e.g. `en-IN`).

---

### Voice Discovery (`test-voice-id.py`)

Lists all Starfish-compatible public and private voices associated with your HeyGen account, with automatic pagination:

```powershell
python test-voice-id.py
```

Output includes `voice_id`, `name`, `language`, `gender`, and `support_locale`.

---

### ElevenLabs Streaming (`tts_elevenlabs.py`)

Generates streaming audio via ElevenLabs SDK using the `eleven_multilingual_v2` model:

```powershell
python tts_elevenlabs.py
```

Saves the resulting audio to `output.mp3`.

---

## REST API Endpoints

The Flask backend exposes the following RESTful endpoints:

### 1. `GET /api/voice-info`
Returns current voice model metadata and API key availability.
- **Response `(200 OK)`**:
  ```json
  {
    "voice_name": "Sheetal",
    "voice_id": "b219f9f8d8e6455e85e470949d680229",
    "has_api_key": true,
    "status": "ready"
  }
  ```

### 2. `POST /api/generate`
Synthesizes speech using Sheetal's voice ID.
- **Request Body**:
  ```json
  {
    "text": "Please collect Form G at the branch.",
    "force_new": false
  }
  ```
- **Response `(200 OK)`**:
  ```json
  {
    "success": true,
    "audio_id": "830329934ce24a949792c993a3ae18c6",
    "duration": 2.12,
    "force_new": false,
    "preview_url": "/api/audio/830329934ce24a949792c993a3ae18c6",
    "download_url": "/api/download/830329934ce24a949792c993a3ae18c6",
    "message": "Speech generated successfully!"
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Input validation failure (`VALIDATION_EMPTY`, `VALIDATION_WHITESPACE`, `VALIDATION_LENGTH`).
  - `402 Payment Required`: `CREDITS_EXHAUSTED` with user guidance.
  - `429 Too Many Requests`: Rate limit reached.
  - `504 Gateway Timeout`: HeyGen connection or read timeout.

### 3. `GET /api/audio/<audio_id>`
Streams raw `audio/wav` bytes for browser preview with anti-caching headers (`Cache-Control: no-cache, no-store, must-revalidate`).

### 4. `GET /api/download/<audio_id>`
Serves the audio file with `Content-Disposition: attachment; filename="sheetal_tts_<id>.wav"`.

---

## Testing & Quality Assurance

The project includes an end-to-end integration and unit test suite in [`test_app.py`](test_app.py).

Run the tests:
```powershell
python -m unittest test_app.py -v
```

### Test Suite Coverage:
1. `test_01_index_page_title_and_elements`: Verifies page title `"Text To Speech (Sheetal's Voice)"` and unique element IDs.
2. `test_02_voice_info_endpoint`: Validates `/api/voice-info` metadata.
3. `test_03_empty_text_validation`: Ensures empty text returns HTTP 400 with specific error messages.
4. `test_04_whitespace_only_validation`: Ensures whitespace-only text is rejected.
5. `test_05_character_limit_validation`: Confirms texts over 3000 chars are rejected.
6. `test_06_credit_exhaustion_error_notification`: Simulates HTTP 402 and credit depletion to verify credit exhaustion alerts.
7. `test_07_audio_preview_and_download_flow`: Tests audio streaming preview vs separate attachment download headers.
8. `test_08_regenerate_force_new_argument`: Verifies that `--force-new` is passed to the CLI command execution.

---

## Technical Highlights

### Cache-Busting Regeneration (`--force-new`)
HeyGen's Starfish TTS model caches identical requests server-side. Furthermore, pauses below ~100ms are quantized to 0 by HeyGen's audio renderer, producing identical audio hashes. 

To overcome this, `--force-new` constructs an SSML wrapper with an effective, natural micro-pause:
```python
pause_ms = 200 + (int(nonce[:2], 16) % 150)  # 200ms to 350ms
request_text = (
    f'<speak>{escaped_text}<break time="{pause_seconds:.3f}s"/>'
    f'<!-- cache-bust:{nonce} --></speak>'
)
```
This imperceptible pause at the end of the sentence forces HeyGen's neural engine to generate a brand new, unique audio waveform every single time.

### Credit Exhaustion Handling
When HeyGen credits are depleted, the API returns HTTP 402 or an error payload mentioning `"credit"`, `"quota"`, or `"insufficient"`. The application catches these states and displays a high-visibility warning banner advising the user to recharge or upgrade their plan.

### Temporary In-Memory Preview
Generated audio is buffered in server-side memory (`AUDIO_CACHE`) keyed by unique UUIDs. Expired entries older than 1 hour are automatically purged by `cleanup_audio_cache()`. This ensures the audio is immediately playable in the browser without cluttering the user's hard drive until they explicitly click **Download Audio**.

---

## License

This project is licensed under the Apache 2.0 License.
