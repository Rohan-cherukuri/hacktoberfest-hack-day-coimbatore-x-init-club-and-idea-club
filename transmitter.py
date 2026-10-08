import os
import shutil
import requests
import datetime
from datetime import datetime, timezone, timedelta
import streamlit as st
import whisper
import imageio_ffmpeg
from audio_recorder_streamlit import audio_recorder

# --- 1. AUTOMATIC FFMPEG SETUP ---
try:
    ffmpeg_source = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_target = os.path.join(os.getcwd(), "ffmpeg.exe")
    if not os.path.exists(ffmpeg_target):
        shutil.copy(ffmpeg_source, ffmpeg_target)
    if os.getcwd() not in os.environ["PATH"]:
        os.environ["PATH"] = os.getcwd() + os.pathsep + os.environ["PATH"]
except Exception:
    pass

# --- 2. CONFIGURATION & URLS ---
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_GEMMA_MODEL = "gemma4:e2b"
DEFAULT_LAPTOP_B_IP = "172.19.207.134"
DEFAULT_BASE_PORT = "5000"

# --- 3. STREAMLIT PAGE CONFIGURATION ---
st.set_page_config(
    page_title="RelayZero — Tactical Field Unit",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Session States
if "report_text" not in st.session_state:
    st.session_state["report_text"] = ""
if "last_tx_result" not in st.session_state:
    st.session_state["last_tx_result"] = None
if "laptop_b_ip" not in st.session_state:
    st.session_state["laptop_b_ip"] = DEFAULT_LAPTOP_B_IP
if "gemma_model" not in st.session_state:
    st.session_state["gemma_model"] = DEFAULT_GEMMA_MODEL

# --- 4. TACTICAL CSS STYLING (MATCHING LAPTOP B COMMAND CENTER) ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Share+Tech+Mono&family=JetBrains+Mono:wght@400;600&display=swap');

/* Main Canvas Background & Base Typography */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d1117 !important;
    background-image: radial-gradient(circle at 50% -10%, rgba(0, 90, 180, 0.15), rgba(13, 17, 23, 1) 75%) !important;
    color: #c9d1d9 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Hide default Streamlit headers, footers & chrome for native look */
header[data-testid="stHeader"], footer, #MainMenu, div[data-testid="stDecoration"], .viewerBadge_container__1QSob {
    display: none !important;
}

.main .block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px !important;
}

/* Top Tactical Banner */
.tactical-banner {
    background: rgba(22, 27, 34, 0.95);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid #30363d;
    border-top: 3px solid #388bfd;
    border-radius: 12px;
    padding: 1.2rem 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
}

.banner-title-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.banner-title {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.65rem;
    font-weight: 700;
    color: #f0f6fc;
    letter-spacing: 2px;
    text-shadow: 0 0 14px rgba(56, 139, 253, 0.4);
    display: flex;
    align-items: center;
    gap: 12px;
}

.banner-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    color: #8b949e;
    font-weight: 400;
    letter-spacing: 0.5px;
}

.banner-status-group {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
}

.glass-pill {
    background: rgba(13, 17, 23, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(48, 54, 61, 0.9);
    border-radius: 20px;
    padding: 6px 16px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.82rem;
    color: #8b949e;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.pulse-dot {
    width: 9px;
    height: 9px;
    background-color: #3fb950;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 8px #3fb950;
    animation: pulse-green-glow 1.8s infinite;
}

@keyframes pulse-green-glow {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(63, 185, 80, 0.7); }
    70% { transform: scale(1.05); box-shadow: 0 0 0 8px rgba(63, 185, 80, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(63, 185, 80, 0); }
}

.timestamp-badge {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.85rem;
    color: #58a6ff;
    letter-spacing: 1px;
}

/* Tactical Cards */
.tactical-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 1.5rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.tactical-header {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.15rem;
    font-weight: 700;
    color: #58a6ff;
    letter-spacing: 1.5px;
    border-bottom: 1px solid #21262d;
    padding-bottom: 0.75rem;
    margin-bottom: 1.25rem;
    display: flex;
    align-items: center;
    gap: 10px;
}

.header-accent-line {
    width: 4px;
    height: 18px;
    background: #388bfd;
    border-radius: 2px;
    display: inline-block;
}

/* Voice Input Container */
.voice-wrapper {
    background: #0b0f19;
    border: 1px dashed #30363d;
    border-radius: 8px;
    padding: 1.25rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 160px;
}

.voice-title {
    font-family: 'Share Tech Mono', monospace;
    color: #f0f6fc;
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 0.4rem;
}

.voice-sub {
    font-size: 0.8rem;
    color: #8b949e;
    margin-bottom: 0.8rem;
}

/* Text Area Overrides */
.stTextArea textarea {
    background-color: #0b0f19 !important;
    color: #58a6ff !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 1rem !important;
    line-height: 1.5 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    padding: 0.85rem !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5) !important;
}

.stTextArea textarea:focus {
    border-color: #388bfd !important;
    box-shadow: 0 0 12px rgba(56, 139, 253, 0.3) !important;
    outline: none !important;
}

.stTextArea textarea::placeholder {
    color: #484f58 !important;
}

/* Action Button Styling */
div.stButton > button {
    width: 100% !important;
    background: linear-gradient(135deg, #1f6beb 0%, #238636 100%) !important;
    color: #ffffff !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 1.2rem !important;
    font-weight: 700 !important;
    letter-spacing: 1.5px !important;
    border: 1px solid #388bfd !important;
    border-radius: 8px !important;
    padding: 0.9rem 1.5rem !important;
    text-transform: uppercase !important;
    box-shadow: 0 4px 20px rgba(31, 107, 235, 0.4) !important;
    transition: all 0.2s ease-in-out !important;
    cursor: pointer !important;
}

div.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 25px rgba(63, 185, 80, 0.5) !important;
    border-color: #3fb950 !important;
}

div.stButton > button:active {
    transform: translateY(1px) !important;
}

/* Terminal Monospace Box for Raw Telemetry */
.terminal-card {
    background-color: #010409;
    border: 1px solid #21262d;
    border-left: 4px solid #3fb950;
    border-radius: 6px;
    padding: 1.1rem 1.25rem;
    font-family: 'Share Tech Mono', 'JetBrains Mono', monospace;
    font-size: 1.05rem;
    color: #2ea043;
    line-height: 1.6;
    letter-spacing: 0.5px;
    box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.8);
    word-break: break-all;
    margin-bottom: 1.25rem;
}

/* Triage Summary Badges Grid */
.triage-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
    margin-top: 0.8rem;
}

.triage-badge {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.triage-label {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.75rem;
    color: #8b949e;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.triage-value {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.1rem;
    font-weight: 700;
    color: #f0f6fc;
}

.prio-critical { color: #f85149 !important; text-shadow: 0 0 8px rgba(248, 81, 73, 0.4); }
.prio-high { color: #d29922 !important; text-shadow: 0 0 8px rgba(210, 153, 34, 0.4); }
.prio-medium, .prio-low, .prio-normal { color: #3fb950 !important; text-shadow: 0 0 8px rgba(63, 185, 80, 0.4); }

/* Dispatch Receipt Status Pills */
.receipt-pill-success {
    background: rgba(46, 160, 67, 0.15);
    border: 1px solid #2ea043;
    color: #3fb950;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1.25rem;
}

.receipt-pill-warning {
    background: rgba(210, 153, 34, 0.15);
    border: 1px solid #d29922;
    color: #d29922;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1.25rem;
}

.receipt-pill-error {
    background: rgba(248, 81, 73, 0.15);
    border: 1px solid #f85149;
    color: #f85149;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1.25rem;
}
</style>
""", unsafe_allow_html=True)

# --- 5. LOAD OFFLINE WHISPER MODEL ---
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("tiny")

whisper_model = load_whisper_model()

# Helper function to parse raw telemetry format
def parse_telemetry(raw_str):
    fields = {
        "PRIO": "NORMAL",
        "LOC": "UNSPECIFIED",
        "HAZ": "INCIDENT",
        "CAS": "0",
        "REQ": "NONE"
    }
    clean_str = raw_str.replace("RAW TX:", "").strip()
    parts = clean_str.split("|")
    for part in parts:
        if ":" in part:
            k, v = part.split(":", 1)
            k = k.strip().upper()
            v = v.strip()
            if k in fields:
                fields[k] = v
    return fields

# Current UTC+5:30 IST timestamp
tz_ist = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(tz_ist).strftime("%Y-%m-%d %H:%M:%S IST [UTC+5:30]")

# --- 6. TOP TACTICAL BANNER ---
st.markdown(f"""
<div class="tactical-banner">
    <div class="banner-title-group">
        <div class="banner-title">📡 RELAYZERO — TACTICAL FIELD UNIT</div>
        <div class="banner-subtitle">Disaster Mesh Edge Node · Ettimadai Sector</div>
    </div>
    <div class="banner-status-group">
        <div class="glass-pill">
            <span class="pulse-dot"></span>
            <span>EDGE AI ACTIVE | MODEL: GEMMA 4 (OLLAMA) | BASE STATION: {st.session_state["laptop_b_ip"]}:{DEFAULT_BASE_PORT}</span>
        </div>
        <div class="timestamp-badge">⏱️ {now_ist}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 7. SECTION 1: INCIDENT ACQUISITION & TRANSCRIPTION ---
st.markdown('<div class="tactical-card">', unsafe_allow_html=True)
st.markdown("""
<div class="tactical-header">
    <span class="header-accent-line"></span>
    <span>[01] ACQUIRE INCIDENT REPORT</span>
</div>
""", unsafe_allow_html=True)

col_voice, col_text = st.columns([1, 2])

with col_voice:
    st.markdown('<div class="voice-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="voice-title">🎙️ VOICE INCIDENT CAPTURE</div>', unsafe_allow_html=True)
    st.markdown('<div class="voice-sub">Offline Whisper Speech-to-Text</div>', unsafe_allow_html=True)
    audio_bytes = audio_recorder(
        text="Click mic to Record/Stop",
        recording_color="#f85149",
        neutral_color="#388bfd",
        icon_name="microphone",
        icon_size="2x"
    )
    st.markdown('</div>', unsafe_allow_html=True)

if audio_bytes:
    with st.spinner("Transcribing voice note offline via Whisper..."):
        temp_audio = "temp_voice.wav"
        with open(temp_audio, "wb") as f:
            f.write(audio_bytes)
        try:
            stt_result = whisper_model.transcribe(temp_audio)
            transcribed_text = stt_result.get("text", "").strip()
            if transcribed_text:
                st.session_state["report_text"] = transcribed_text
                st.success("Voice transcribed successfully!")
        except Exception as e:
            st.error(f"Voice transcription error: {e}")
        finally:
            if os.path.exists(temp_audio):
                os.remove(temp_audio)

with col_text:
    user_input = st.text_area(
        "Incident Details:",
        value=st.session_state["report_text"],
        height=160,
        placeholder="Type disaster report or record voice note (e.g., 'Fire in the central library, 2 people injured, need medical team immediately')..."
    )
    st.session_state["report_text"] = user_input

# Quick Preset Emergency Incident Chips
st.markdown('<div style="margin-top: 10px; font-family: \'Share Tech Mono\', monospace; font-size: 0.8rem; color: #8b949e;">QUICK PRESET INCIDENTS:</div>', unsafe_allow_html=True)
p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns([1, 1, 1, 1, 0.8])
with p_col1:
    if st.button("🔥 Central Library Fire", key="preset1"):
        st.session_state["report_text"] = "Fire in the central library, 2 people injured, need medical team immediately"
        st.rerun()
with p_col2:
    if st.button("🌊 Sector 4 Flash Flood", key="preset2"):
        st.session_state["report_text"] = "Flash flood rising rapidly in Sector 4 residential zone, 5 families trapped on roofs"
        st.rerun()
with p_col3:
    if st.button("🩹 Junction Collapse", key="preset3"):
        st.session_state["report_text"] = "Structural collapse at Ettimadai junction, 3 severe casualties needing immediate triage and ambulance"
        st.rerun()
with p_col4:
    if st.button("⚡ Substation Fire", key="preset4"):
        st.session_state["report_text"] = "Main power substation transformer fire near North Gate, high voltage hazard present"
        st.rerun()
with p_col5:
    if st.button("🗑️ Clear", key="preset_clear"):
        st.session_state["report_text"] = ""
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- 8. SECTION 2: EXECUTION TRIGGER ---
st.markdown('<div class="tactical-card">', unsafe_allow_html=True)
st.markdown("""
<div class="tactical-header">
    <span class="header-accent-line"></span>
    <span>[02] SEMANTIC COMPRESSION & MESH TRANSMISSION</span>
</div>
""", unsafe_allow_html=True)

if st.button("⚡ COMPRESS WITH GEMMA 4 & BROADCAST OVER MESH"):
    if user_input.strip():
        with st.spinner("Processing Semantic Compression via Local Ollama..."):
            prompt = f"""You are an edge telemetry compressor for disaster mesh networks.
If the message is an emergency, extract facts into this exact format:
PRIO:<CRITICAL/HIGH>|LOC:<Location>|HAZ:<Hazard>|CAS:<Count>|REQ:<NeededResources>
Output ONLY the formatted string without extra text.

Input: {user_input}
Output:"""

            payload = {
                "model": st.session_state["gemma_model"],
                "prompt": prompt,
                "stream": False
            }

            try:
                # Call local Ollama AI Engine
                ollama_res = requests.post(OLLAMA_URL, json=payload, timeout=180)
                
                if ollama_res.status_code == 200:
                    telemetry = ollama_res.json().get("response", "").strip()
                    raw_tx_formatted = f"RAW TX: {telemetry}"
                    
                    # Forward packet to Base Station Command Center over local mesh network
                    base_url = f"http://{st.session_state['laptop_b_ip']}:{DEFAULT_BASE_PORT}/receive"
                    tx_status = None
                    tx_success = False
                    
                    try:
                        req = requests.post(base_url, json={"packet": telemetry}, timeout=5)
                        tx_status = req.status_code
                        tx_success = (req.status_code == 200)
                    except Exception as net_err:
                        tx_status = f"Connection Failed ({net_err})"
                        tx_success = False
                    
                    # Save transmission dispatch log to session state for live display
                    st.session_state["last_tx_result"] = {
                        "raw_tx": raw_tx_formatted,
                        "telemetry": telemetry,
                        "tx_status": tx_status,
                        "tx_success": tx_success,
                        "parsed": parse_telemetry(telemetry),
                        "timestamp": datetime.now(tz_ist).strftime("%H:%M:%S IST")
                    }
                else:
                    st.error(f"Local Ollama returned error status: {ollama_res.status_code}")
            except requests.exceptions.Timeout:
                st.error("Ollama timed out loading Gemma 4 into memory. Warm up Ollama by running `ollama run gemma4:e2b` in terminal.")
            except Exception as e:
                st.error(f"Failed to communicate with local Ollama service at 127.0.0.1: {e}")
    else:
        st.warning("Please enter an incident report or record a voice note before transmitting.")

st.markdown('</div>', unsafe_allow_html=True)

# --- 9. SECTION 3: EDGE TELEMETRY INSPECTOR (LIVE OUTPUT FEED) ---
if st.session_state["last_tx_result"]:
    res = st.session_state["last_tx_result"]
    parsed = res["parsed"]
    prio = parsed.get("PRIO", "NORMAL").upper()
    
    # Priority color class mapping
    if prio == "CRITICAL":
        prio_class = "prio-critical"
    elif prio == "HIGH":
        prio_class = "prio-high"
    else:
        prio_class = "prio-medium"

    st.markdown('<div class="tactical-card">', unsafe_allow_html=True)
    st.markdown("""
    <div class="tactical-header">
        <span class="header-accent-line"></span>
        <span>[03] EDGE TELEMETRY INSPECTOR</span>
    </div>
    """, unsafe_allow_html=True)

    # Dispatch Receipt Pill
    if res["tx_success"]:
        st.markdown("""
        <div class="receipt-pill-success">
            <span>🟢 TRANSMISSION ACKNOWLEDGED BY BASE STATION (200 OK)</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="receipt-pill-warning">
            <span>⚠️ MESH BROADCAST ATTEMPTED: BASE STATION RESPONSE [{res['tx_status']}]</span>
        </div>
        """, unsafe_allow_html=True)

    # Raw Telemetry Card (Matching Laptop B Monospace Box)
    st.markdown(f"""
    <div class="terminal-card">
        {res['raw_tx']}
    </div>
    """, unsafe_allow_html=True)

    # Quick Triage Summary Grid (4 Micro-Badges)
    st.markdown(f"""
    <div class="triage-grid">
        <div class="triage-badge">
            <span class="triage-label">🚨 EXTRACTED PRIORITY</span>
            <span class="triage-value {prio_class}">{parsed.get('PRIO', 'N/A')}</span>
        </div>
        <div class="triage-badge">
            <span class="triage-label">📍 RESOLVED LOCATION</span>
            <span class="triage-value" style="color: #388bfd;">{parsed.get('LOC', 'N/A')}</span>
        </div>
        <div class="triage-badge">
            <span class="triage-label">⚠️ HAZARD TYPE</span>
            <span class="triage-value" style="color: #d29922;">{parsed.get('HAZ', 'N/A')}</span>
        </div>
        <div class="triage-badge">
            <span class="triage-label">🚑 CASUALTY COUNT</span>
            <span class="triage-value" style="color: #f85149;">{parsed.get('CAS', '0')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# Optional Collapsible Configuration Bar
with st.expander("⚙️ Field Node Network Configuration"):
    cfg_col1, cfg_col2 = st.columns(2)
    with cfg_col1:
        new_ip = st.text_input("Base Station IPv4 Address", value=st.session_state["laptop_b_ip"])
        if new_ip != st.session_state["laptop_b_ip"]:
            st.session_state["laptop_b_ip"] = new_ip
    with cfg_col2:
        new_model = st.text_input("Local Ollama Model Tag", value=st.session_state["gemma_model"])
        if new_model != st.session_state["gemma_model"]:
            st.session_state["gemma_model"] = new_model
