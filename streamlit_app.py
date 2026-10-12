import os
import sys
import uuid
import html
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import streamlit as st

try:
    from dotenv import find_dotenv, load_dotenv
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path, override=True)
    else:
        load_dotenv()
except Exception:
    pass

# Constants
SHEETAL_VOICE_ID = "b219f9f8d8e6455e85e470949d680229"
VOICE_NAME = "Sheetal"

# Streamlit Page Configuration
st.set_page_config(
    page_title="Text To Speech (Sheetal's Voice)",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom Styling (Dark Theme, Glassmorphism, Gradient Badges)
st.markdown("""
<style>
    /* Main container and font */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .stApp {
        background: radial-gradient(circle at 10% 10%, rgba(124, 58, 237, 0.12) 0%, transparent 40%),
                    radial-gradient(circle at 90% 80%, rgba(6, 182, 212, 0.10) 0%, transparent 40%),
                    #090c15;
        color: #f8fafc;
    }

    /* Voice Card */
    .voice-profile-card {
        background: rgba(18, 24, 38, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 16px;
        padding: 18px 22px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 16px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }
    .avatar-circle {
        width: 52px;
        height: 52px;
        border-radius: 50%;
        background: linear-gradient(135deg, #8b5cf6, #3b82f6);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1.2rem;
        color: white;
        box-shadow: 0 0 16px rgba(139, 92, 246, 0.4);
    }
    .voice-badge-tag {
        background: rgba(139, 92, 246, 0.18);
        border: 1px solid rgba(139, 92, 246, 0.35);
        color: #c4b5fd;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .voice-badge-engine {
        background: rgba(6, 182, 212, 0.14);
        border: 1px solid rgba(6, 182, 212, 0.35);
        color: #67e8f9;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .voice-id-code {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        background: rgba(0, 0, 0, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: #e2e8f0;
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 46px;
        transition: all 0.2s ease;
    }
    .stDownloadButton>button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 46px;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: white !important;
        border: none !important;
    }

    /* Mobile Responsive Optimizations */
    @media (max-width: 640px) {
        .block-container {
            padding: 1.5rem 0.8rem 3rem !important;
        }
        .voice-profile-card {
            flex-direction: column;
            align-items: flex-start !important;
            padding: 14px 16px !important;
            gap: 12px !important;
        }
        .voice-id-code {
            word-break: break-all;
            font-size: 0.72rem !important;
        }
        .stTextArea textarea {
            font-size: 16px !important; /* Prevents iOS auto-zoom */
        }
        .stButton>button, .stDownloadButton>button {
            width: 100% !important;
            min-height: 48px !important; /* Mobile touch target */
            font-size: 0.92rem !important;
            white-space: normal !important;
            height: auto !important;
            line-height: 1.3 !important;
            padding: 10px 14px !important;
        }
        [data-testid="column"] {
            min-width: 100% !important;
            margin-bottom: 8px !important;
        }
    }
</style>
""", unsafe_allow_html=True)


def get_api_key():
    """Retrieve HeyGen API key from Streamlit secrets, environment variables, or session state."""
    # 1. Streamlit secrets (for Streamlit Community Cloud deployment)
    if hasattr(st, "secrets") and "HEYGEN_API_KEY" in st.secrets:
        return st.secrets["HEYGEN_API_KEY"]
    # 2. Environment variables / .env
    key = os.getenv("HEYGEN_API_KEY")
    if key and key.strip():
        return key.strip()
    # 3. User entered in sidebar
    return st.session_state.get("user_heygen_api_key", "").strip()


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


def synthesize_speech(text: str, voice_id: str, api_key: str, force_new: bool = False, locale: str = None):
    """Call HeyGen API with Sheetal's voice, applying SSML pause logic when force_new is requested."""
    request_text = text
    input_type = "text"

    if force_new:
        nonce = uuid.uuid4().hex
        # Use an effective micro-pause (200-350ms) so HeyGen's Starfish model produces fresh audio
        pause_ms = 200 + (int(nonce[:2], 16) % 150)
        pause_seconds = pause_ms / 1000.0
        escaped_text = html.escape(text, quote=False)
        request_text = (
            f'<speak>{escaped_text}<break time="{pause_seconds:.3f}s"/>'
            f'<!-- cache-bust:{nonce} --></speak>'
        )
        input_type = "ssml"

    payload = {
        "text": request_text,
        "voice_id": voice_id,
        "input_type": input_type,
        "language": "en",
        "speed": 1.0,
    }
    if locale:
        payload["locale"] = locale

    session = get_requests_session()
    response = session.post(
        "https://api.heygen.com/v3/voices/speech",
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=(15, 180),
    )

    status_code = response.status_code
    try:
        resp_json = response.json()
    except Exception:
        resp_json = {}

    error_msg = ""
    if isinstance(resp_json, dict):
        error_msg = resp_json.get("message") or resp_json.get("error") or ""
        if not error_msg and "data" in resp_json and isinstance(resp_json["data"], dict):
            error_msg = resp_json["data"].get("message") or resp_json["data"].get("error") or ""

    # Credit exhaustion check
    is_credit_exhausted = (
        status_code == 402 or
        "credit" in error_msg.lower() or
        "quota" in error_msg.lower() or
        "insufficient" in error_msg.lower() or
        "balance" in error_msg.lower() or
        "limit reached" in error_msg.lower()
    )
    if is_credit_exhausted:
        return {
            "success": False,
            "error_type": "CREDITS_EXHAUSTED",
            "error": "HeyGen credits are exhausted. Please recharge your HeyGen account credits or upgrade your plan to generate more speech audio."
        }

    if not response.ok:
        if status_code in (401, 403):
            return {
                "success": False,
                "error_type": "AUTH_ERROR",
                "error": f"HeyGen authorization failed ({status_code}). Please verify your HEYGEN_API_KEY."
            }
        if status_code == 429:
            return {
                "success": False,
                "error_type": "RATE_LIMIT",
                "error": "HeyGen API rate limit reached. Please wait a few seconds and try again."
            }
        return {
            "success": False,
            "error_type": "API_ERROR",
            "error": f"HeyGen API Error ({status_code}): {error_msg or response.text}"
        }

    # Fetch audio content
    data_payload = resp_json.get("data", {})
    audio_url = data_payload.get("audio_url")
    duration = data_payload.get("duration", 0)

    if not audio_url:
        return {
            "success": False,
            "error_type": "NO_AUDIO_URL",
            "error": "HeyGen did not return a valid audio download URL."
        }

    audio_res = session.get(audio_url, timeout=(15, 180))
    audio_res.raise_for_status()

    return {
        "success": True,
        "audio_bytes": audio_res.content,
        "duration": duration,
        "audio_url": audio_url,
        "force_new": force_new
    }


# Header
st.title("Text To Speech (Sheetal's Voice)")
st.markdown("Convert your text into realistic, expressive speech using Sheetal's custom voice model.")

# Sheetal Voice Card
st.markdown(f"""
<div class="voice-profile-card">
    <div class="avatar-circle">SV</div>
    <div style="flex: 1;">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
            <strong style="font-size: 1.15rem; color: #ffffff;">{VOICE_NAME}</strong>
            <span class="voice-badge-tag">HDFC Female Voice</span>
            <span class="voice-badge-engine">Starfish Model</span>
        </div>
        <div style="font-size: 0.8rem; color: #94a3b8; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <span>🌐 English (Indian Accent)</span>
            <span class="voice-id-code">ID: {SHEETAL_VOICE_ID}</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar API Key Configuration (for public deployments where users can enter their own key if none is set in secrets)
api_key = get_api_key()
with st.sidebar:
    st.header("⚙️ Configuration")
    if api_key:
        st.success("✅ HeyGen API Key is configured.")
    else:
        st.warning("⚠️ No API Key found.")
        user_key = st.text_input("Enter HeyGen API Key", type="password", help="Add HEYGEN_API_KEY in Streamlit Secrets or enter it here.")
        if user_key:
            st.session_state["user_heygen_api_key"] = user_key
            st.rerun()
    st.caption("Target Voice ID: " + SHEETAL_VOICE_ID)

# Session state initialization
if "generated_audio" not in st.session_state:
    st.session_state.generated_audio = None
if "generated_duration" not in st.session_state:
    st.session_state.generated_duration = None
if "last_mode" not in st.session_state:
    st.session_state.last_mode = None
if "sample_text_val" not in st.session_state:
    st.session_state.sample_text_val = "Branch to collect ‘Form G’ with Income Tax Assessing Officer Stamp. Account cannot be closed solely on customer’s request."

# Quick Sample Pills
st.write("##### Quick Samples:")
col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    if st.button("📋 Form G Notice", use_container_width=True):
        st.session_state.sample_text_val = "Branch to collect ‘Form G’ with Income Tax Assessing Officer Stamp. Account cannot be closed solely on customer’s request."
        st.rerun()
with col_s2:
    if st.button("💬 Branch Inquiry", use_container_width=True):
        st.session_state.sample_text_val = "Well, this was very helpful. Please guide me on the transactions process at the branch."
        st.rerun()
with col_s3:
    if st.button("✨ Welcome Greeting", use_container_width=True):
        st.session_state.sample_text_val = "Welcome to our banking branch! How may I assist you with your savings account today?"
        st.rerun()

# Text Input Field
input_text = st.text_area(
    "Input Text",
    value=st.session_state.sample_text_val,
    height=130,
    max_chars=3000,
    placeholder="Type or paste the text you want Sheetal to speak...",
    help="Enter up to 3000 characters."
)

# Live Counter
char_len = len(input_text)
word_len = len(input_text.strip().split()) if input_text.strip() else 0
st.caption(f"{char_len} / 3000 characters • {word_len} words")

# Action Buttons
col_btn1, col_btn2 = st.columns([1, 1])

with col_btn1:
    btn_generate = st.button("🎙️ Generate Speech", type="primary", use_container_width=True)

with col_btn2:
    btn_regenerate = st.button("🔄 Regenerate Voice (--force-new)", use_container_width=True, help="Bypasses HeyGen cache with unique SSML pause to generate fresh audio.")

# Processing Logic
trigger_generate = btn_generate or btn_regenerate
is_force_new = bool(btn_regenerate)

if trigger_generate:
    # 1. Validation
    if not api_key:
        st.error("❌ HeyGen API Key is missing. Please set 'HEYGEN_API_KEY' in Streamlit Secrets, `.env`, or via the sidebar.")
    elif not input_text or not input_text.strip():
        st.error("⚠️ Text input is required. Please enter valid text before generating speech.")
    elif len(input_text.strip()) > 3000:
        st.error(f"⚠️ Text length ({len(input_text.strip())} chars) exceeds the 3000 character limit.")
    else:
        spinner_msg = "Regenerating Sheetal's voice (--force-new cache bypass)..." if is_force_new else "Synthesizing Sheetal's voice..."
        with st.spinner(spinner_msg):
            result = synthesize_speech(
                text=input_text.strip(),
                voice_id=SHEETAL_VOICE_ID,
                api_key=api_key,
                force_new=is_force_new
            )

            if not result.get("success"):
                if result.get("error_type") == "CREDITS_EXHAUSTED":
                    st.error("🚨 **HeyGen Credits Exhausted**\n\n" + result["error"])
                elif result.get("error_type") == "AUTH_ERROR":
                    st.error("🔒 **Authentication Error**\n\n" + result["error"])
                else:
                    st.error("❌ **Generation Failed**\n\n" + result.get("error", "An unexpected error occurred."))
            else:
                st.session_state.generated_audio = result["audio_bytes"]
                st.session_state.generated_duration = result.get("duration", 0)
                st.session_state.last_mode = "Regenerated fresh (--force-new)" if is_force_new else "Standard"
                st.success(f"✅ Speech {'regenerated fresh (--force-new)' if is_force_new else 'generated successfully'}! (Duration: {result.get('duration', 0):.2f}s)")

# Audio Preview and Download Section
st.divider()
st.subheader("🎧 Audio Preview")

if st.session_state.generated_audio:
    st.caption(f"Temporary in-browser preview • Duration: {st.session_state.generated_duration:.2f}s • Mode: {st.session_state.last_mode}")
    # In-browser preview without forced disk download
    st.audio(st.session_state.generated_audio, format="audio/wav")

    # Explicit Download Button
    st.download_button(
        label="⬇️ Download Audio (.wav)",
        data=st.session_state.generated_audio,
        file_name=f"sheetal_speech_{uuid.uuid4().hex[:8]}.wav",
        mime="audio/wav",
        use_container_width=True
    )
else:
    st.info("No audio generated yet. Enter text above and click **Generate Speech** to listen to Sheetal's preview.")

st.caption("Powered by HeyGen AI Starfish Engine • Sheetal Voice Model (Private)")
