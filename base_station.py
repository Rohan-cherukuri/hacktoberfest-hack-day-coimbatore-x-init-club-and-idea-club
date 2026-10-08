import os
import json
import csv
import io
import threading
import requests as _requests
from datetime import datetime
from flask import Flask, request
import streamlit as st
import streamlit.components.v1 as components
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh

# ─────────────────────────────────────────────────────────────────
#  FLASK RECEIVER ENGINE  (background thread — port 5000)
# ─────────────────────────────────────────────────────────────────
flask_app = Flask(__name__)
DATA_FILE  = "incidents.json"
LOCAL_IP   = "172.20.10.2"
PORT       = 5000

CAMPUS_ZONES = {
    "LIBRARY":  {"coords": [10.9038, 76.8998], "label": "Central Library"},
    "ACADEMIC": {"coords": [10.9025, 76.9015], "label": "Academic Block AB1"},
    "HOSTEL":   {"coords": [10.9055, 76.8982], "label": "Student Hostels Complex"},
    "CANTEEN":  {"coords": [10.9030, 76.9008], "label": "Main Food Court"},
    "GATE":     {"coords": [10.9005, 76.8970], "label": "Main Entrance Gate"},
    "SPORTS":   {"coords": [10.9012, 76.9032], "label": "Sports Complex"},
    "LAB":      {"coords": [10.9021, 76.9020], "label": "Research Labs Block"},
    "ADMIN":    {"coords": [10.9018, 76.9000], "label": "Administration Block"},
    "MEDICAL":  {"coords": [10.9045, 76.9005], "label": "Medical / Health Centre"},
    "PARKING":  {"coords": [10.9008, 76.8975], "label": "Parking & Vehicle Bay"},
}

# Geocode cache — avoids hammering Nominatim on every packet re-parse
_geo_cache: dict = {}

def _nominatim_geocode(query: str):
    """Try Nominatim (OSM). Returns (lat, lon) or None on failure."""
    if query in _geo_cache:
        return _geo_cache[query]
    try:
        resp = _requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "RelayZero-DisasterMesh/1.0"},
            timeout=4,
        )
        data = resp.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            _geo_cache[query] = (lat, lon)
            return lat, lon
    except Exception:
        pass
    return None

def resolve_location(loc_text: str):
    """Match known campus zones first; fall back to Nominatim; then campus centre."""
    loc_upper = loc_text.upper()
    for key, data in CAMPUS_ZONES.items():
        if key in loc_upper:
            return data["coords"], data["label"]
    # Try live geocoding for free-text locations (e.g. "Nike outlet mall, Vishaker Patnam")
    geo = _nominatim_geocode(loc_text)
    if geo:
        return list(geo), loc_text
    # Offline hard-fallback
    return [10.9027, 76.9006], f"Reported: {loc_text}"

def log_packet(raw_packet: str):
    incidents = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                incidents = json.load(f)
        except Exception:
            pass

    parsed = {
        "timestamp":  datetime.now().strftime("%H:%M:%S"),
        "raw_packet": raw_packet,
        "bytes":      len(raw_packet.encode("utf-8")),
        "PRIO": "UNKNOWN",
        "LOC":  "UNKNOWN",
        "HAZ":  "UNKNOWN",
        "CAS":  "0",
        "REQ":  "NONE",
    }

    for item in raw_packet.split("|"):
        if ":" in item:
            k, v = item.split(":", 1)
            parsed[k.strip().upper()] = v.strip()

    coords, zone_name = resolve_location(parsed["LOC"])
    parsed["coords"]    = coords
    parsed["zone_name"] = zone_name

    incidents.insert(0, parsed)
    with open(DATA_FILE, "w") as f:
        json.dump(incidents, f, indent=2)

@flask_app.route("/receive", methods=["POST"])
def receive_packet():
    payload = request.json or {}
    packet  = payload.get("packet", "")
    if packet:
        log_packet(packet)
    return {"status": "ACK"}, 200

@st.cache_resource
def start_listener():
    t = threading.Thread(
        target=lambda: flask_app.run(
            host="0.0.0.0", port=PORT, debug=False, use_reloader=False
        ),
        daemon=True,
    )
    t.start()
    return True

start_listener()

# ─────────────────────────────────────────────────────────────────
#  STREAMLIT PAGE CONFIG
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RelayZero | Tactical Command",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st_autorefresh(interval=3000, key="data_refresh")

# ─────────────────────────────────────────────────────────────────
#  GLOBAL CSS
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background-color: #0d1117;
    background-image:
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,90,180,0.15), transparent),
        linear-gradient(180deg, #0d1117 0%, #0a0e17 100%);
    color: #e6edf3;
}

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem !important; padding-bottom: 0.5rem !important; }

/* ── Top Banner ─────────────────────────────────────────────── */
.rz-banner {
    background: linear-gradient(135deg, rgba(13,17,23,0.92) 0%, rgba(17,26,45,0.92) 100%);
    border: 1px solid rgba(48,54,61,0.8);
    border-bottom: 1px solid rgba(31,111,235,0.35);
    border-radius: 12px;
    padding: 16px 24px;
    margin-bottom: 18px;
    backdrop-filter: blur(12px);
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
}
.rz-title {
    font-size: 3.2rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    color: #e6edf3;
    text-transform: uppercase;
    line-height: 1;
}
.rz-title span { color: #388bfd; }
.rz-status-group { display: flex; align-items: center; gap: 24px; }

/* ── Datetime display (replaces green pill) ────────────────────── */
.rz-datetime { text-align: right; }
.rz-date {
    font-family: 'Inter', sans-serif;
    font-size: 1.0rem;
    font-weight: 600;
    color: #79c0ff;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.rz-time {
    font-family: 'Share Tech Mono', monospace;
    font-size: 2.4rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.08em;
    line-height: 1.1;
}
.rz-tz {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.72rem;
    color: #484f58;
    letter-spacing: 0.10em;
    margin-top: 2px;
}

/* ── KPI Cards ───────────────────────────────────────────────── */
.kpi-row { display: flex; gap: 12px; margin-bottom: 20px; }
.kpi-card {
    flex: 1;
    background: linear-gradient(145deg, rgba(22,27,34,0.95), rgba(13,17,23,0.95));
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 4px; border-radius: 12px 12px 0 0;
}
.kpi-card.blue::before  { background: linear-gradient(90deg, #1f6feb, #388bfd); }
.kpi-card.red::before   { background: linear-gradient(90deg, #da3633, #f85149); }
.kpi-card.amber::before { background: linear-gradient(90deg, #9e6a03, #d29922); }
/* Dynamic danger-level top ribbons */
.kpi-card.danger-red::before    { background: linear-gradient(90deg, #da3633, #f85149); }
.kpi-card.danger-orange::before { background: linear-gradient(90deg, #9e6a03, #d29922); }
.kpi-card.danger-gray::before   { background: linear-gradient(90deg, #30363d, #484f58); }

.kpi-label { font-size: 1.0rem; color: #8b949e; text-transform: uppercase; font-family: 'Share Tech Mono', monospace; margin-bottom: 8px; font-weight: bold; }
.kpi-value { font-size: 3.0rem; font-weight: 700; font-family: 'Share Tech Mono', monospace; line-height: 1; margin-bottom: 8px; }
.kpi-card.blue  .kpi-value { color: #388bfd; }
.kpi-card.red   .kpi-value { color: #f85149; }
.kpi-card.amber .kpi-value { color: #d29922; }
/* Dynamic danger-level value colours */
.kpi-card.danger-red    .kpi-value { color: #f85149; }
.kpi-card.danger-orange .kpi-value { color: #d29922; }
.kpi-card.danger-gray   .kpi-value { color: #8b949e; }
.kpi-delta { font-size: 0.85rem; color: #6e7681; font-family: 'Share Tech Mono', monospace; }

/* ── Section Headers ─────────────────────────────────────────── */
.section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }
.section-title { font-size: 1.1rem; font-weight: 600; text-transform: uppercase; color: #8b949e; font-family: 'Share Tech Mono', monospace; }
.section-icon { font-size: 1.3rem; }
.section-badge { margin-left: auto; background: rgba(56,139,253,0.15); border: 1px solid rgba(56,139,253,0.35); border-radius: 10px; padding: 4px 12px; font-size: 0.85rem; color: #388bfd; font-family: 'Share Tech Mono', monospace; }

/* ── Incident Cards ──────────────────────────────────────────── */
.feed-scroll { max-height: 540px; overflow-y: auto; padding-right: 4px; }
.feed-scroll::-webkit-scrollbar { width: 4px; }
.feed-scroll::-webkit-scrollbar-track { background: transparent; }
.feed-scroll::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }

.ic-card {
    background: linear-gradient(145deg, rgba(22,27,34,0.96), rgba(13,17,23,0.96));
    border-radius: 10px; padding: 18px 20px; margin-bottom: 12px;
    position: relative; overflow: hidden;
    transition: transform 0.15s;
}
.ic-card:hover { transform: translateX(2px); }
.ic-card.crit { border: 1px solid rgba(248,81,73,0.50); border-left: 5px solid #f85149; }
.ic-card.high { border: 1px solid rgba(210,153,34,0.45); border-left: 5px solid #d29922; }
.ic-card.unk  { border: 1px solid rgba(48,54,61,0.70);   border-left: 5px solid #484f58; }

.ic-top-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.ic-prio-badge { font-family: 'Share Tech Mono', monospace; font-size: 0.9rem; font-weight: 700; padding: 4px 12px; border-radius: 4px; }
.ic-prio-badge.crit { background: rgba(248,81,73,0.18); color: #f85149; border: 1px solid rgba(248,81,73,0.40); }
.ic-prio-badge.high { background: rgba(210,153,34,0.15); color: #d29922; border: 1px solid rgba(210,153,34,0.40); }
.ic-prio-badge.unk  { background: rgba(72,79,88,0.20);   color: #8b949e; border: 1px solid rgba(72,79,88,0.40); }
.ic-ts { font-size: 0.85rem; color: #8b949e; font-family: 'Share Tech Mono', monospace; }
.ic-location { font-size: 1.35rem; font-weight: 700; color: #e6edf3; margin-bottom: 12px; }
.ic-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
.ic-field { background: rgba(13,17,23,0.60); border: 1px solid #21262d; border-radius: 6px; padding: 10px 14px; }
.ic-field-label { font-size: 0.8rem; color: #8b949e; text-transform: uppercase; font-family: 'Share Tech Mono', monospace; margin-bottom: 4px; }
.ic-field-value { font-size: 1.1rem; font-weight: 600; color: #c9d1d9; font-family: 'Share Tech Mono', monospace; }
.ic-field-value.cas { color: #ff7b72; font-size: 1.3rem; }
.ic-field-value.haz { color: #ffa657; }
.ic-field-value.req { color: #79c0ff; }

/* Raw telemetry */
.rz-raw { background: #010409; border: 1px solid #1c2128; border-radius: 6px; padding: 10px 14px; font-family: 'Share Tech Mono', monospace; font-size: 0.9rem; color: #2ea043; display: flex; align-items: center; gap: 12px; overflow-x: auto; white-space: nowrap; }
.rz-raw-label { color: #3fb950; font-weight: 700; font-size: 0.8rem; background: rgba(46,160,67,0.12); border: 1px solid rgba(46,160,67,0.25); border-radius: 3px; padding: 2px 8px; flex-shrink: 0; }
.rz-raw-bytes { margin-left: auto; color: #8b949e; font-size: 0.85rem; flex-shrink: 0; }

/* Empty state */
.rz-empty { border: 2px dashed #21262d; border-radius: 10px; padding: 50px 20px; text-align: center; color: #8b949e; font-family: 'Share Tech Mono', monospace; font-size: 1.2rem; line-height: 2; }

/* Map wrapper */
.map-wrapper { border: 1px solid #21262d; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }

/* ── Top-right button column ─────────────────────────────────── */

/* Base shared style for ALL action buttons */
div[data-testid="stButton"] button {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.95rem !important;
    font-weight: bold !important;
    letter-spacing: 0.08em !important;
    border-radius: 8px !important;
    padding: 18px !important;
    width: 100% !important;
    text-align: center !important;
    transition: background 0.2s, box-shadow 0.2s !important;
}

/* REFRESH button — first stButton in col_btn → blue */
div[data-testid="stButton"]:first-of-type button {
    background: linear-gradient(145deg, rgba(31,111,235,0.18), rgba(13,17,23,0.95)) !important;
    border: 1px solid rgba(56,139,253,0.60) !important;
    color: #388bfd !important;
    box-shadow: 0 0 12px rgba(56,139,253,0.15) !important;
}
div[data-testid="stButton"]:first-of-type button:hover {
    background: linear-gradient(145deg, rgba(56,139,253,0.25), rgba(22,27,34,0.98)) !important;
    box-shadow: 0 0 22px rgba(56,139,253,0.30) !important;
}

/* PURGE LOGS button — second stButton in col_btn → red */
div[data-testid="stButton"] + div[data-testid="stButton"] button {
    background: linear-gradient(145deg, rgba(218,54,51,0.18), rgba(13,17,23,0.95)) !important;
    border: 1px solid rgba(248,81,73,0.60) !important;
    color: #f85149 !important;
    box-shadow: 0 0 12px rgba(248,81,73,0.15) !important;
}
div[data-testid="stButton"] + div[data-testid="stButton"] button:hover {
    background: linear-gradient(145deg, rgba(248,81,73,0.30), rgba(22,27,34,0.98)) !important;
    box-shadow: 0 0 22px rgba(248,81,73,0.30) !important;
}

/* ── Export CSV download button — green tactical card style ─── */
div[data-testid="stDownloadButton"] {
    height: 100%;
}
div[data-testid="stDownloadButton"] button {
    background: linear-gradient(145deg, rgba(22,27,34,0.98), rgba(13,17,23,0.98)) !important;
    border: 1px solid rgba(46,160,67,0.55) !important;
    border-top: 4px solid #2ea043 !important;
    color: #3fb950 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    border-radius: 12px !important;
    padding: 20px 24px !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 120px !important;
    text-align: left !important;
    line-height: 1.5 !important;
    box-shadow: 0 0 16px rgba(46,160,67,0.10) !important;
    transition: background 0.2s, box-shadow 0.2s !important;
    white-space: pre-line !important;
}
div[data-testid="stDownloadButton"] button:hover {
    background: linear-gradient(145deg, rgba(46,160,67,0.12), rgba(13,17,23,0.98)) !important;
    box-shadow: 0 0 24px rgba(46,160,67,0.22) !important;
}

/* ── Map legend ──────────────────────────────────────────────── */
.map-legend {
    background: linear-gradient(145deg, rgba(22,27,34,0.97), rgba(13,17,23,0.97));
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 8px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.78rem;
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    align-items: center;
}
.legend-item { display: flex; align-items: center; gap: 8px; color: #8b949e; }
.legend-dot  { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.legend-circle-crit { width: 16px; height: 16px; border-radius: 50%; background: rgba(248,81,73,0.40); border: 2px solid #f85149; flex-shrink: 0; }
.legend-circle-high { width: 16px; height: 16px; border-radius: 50%; background: rgba(210,153,34,0.35); border: 2px solid #d29922; flex-shrink: 0; }
.legend-ring  { width: 18px; height: 18px; border-radius: 50%; border: 2px dashed #6e7681; flex-shrink: 0; }
.legend-base  { width: 14px; height: 14px; border-radius: 50%; background: rgba(56,139,253,0.25); border: 2px solid #388bfd; flex-shrink: 0; }
.legend-sep   { color: #30363d; }

iframe { border: none !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  LOAD INCIDENT DATA
# ─────────────────────────────────────────────────────────────────
incidents = []
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            incidents = json.load(f)
    except Exception:
        pass

crit_count       = sum(1 for i in incidents if i.get("PRIO", "").upper() == "CRITICAL")
high_count       = sum(1 for i in incidents if i.get("PRIO", "").upper() in ("HIGH", "MEDIUM"))
total_casualties = sum(
    int(i.get("CAS", 0)) if str(i.get("CAS", "0")).isdigit() else 0
    for i in incidents
)
now_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S  UTC+5:30")

# ── Compute overall danger level ─────────────────────────────────
if crit_count > 0:
    danger_class  = "danger-red"
    danger_label  = "🔴 Current Danger Level"
    danger_number = crit_count
    danger_delta  = "PRIORITY: CRITICAL"
elif high_count > 0:
    danger_class  = "danger-orange"
    danger_label  = "🟠 Current Danger Level"
    danger_number = high_count
    danger_delta  = "PRIORITY: HIGH / MEDIUM"
else:
    danger_class  = "danger-gray"
    danger_label  = "⚪ Current Danger Level"
    danger_number = 0
    danger_delta  = "STATUS: NORMAL / UNKNOWN"


# ─────────────────────────────────────────────────────────────────
#  AUDIO SIREN (Zero-internet JS synthesizer)
# ─────────────────────────────────────────────────────────────────
if incidents and incidents[0].get("PRIO", "").upper() == "CRITICAL":
    latest_crit = incidents[0].get("timestamp")
    if st.session_state.get("last_siren") != latest_crit:
        st.session_state["last_siren"] = latest_crit
        siren_html = """
        <script>
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        if (ctx.state === 'suspended') { ctx.resume(); }
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = 'square';
        osc.frequency.setValueAtTime(600, ctx.currentTime);
        osc.frequency.linearRampToValueAtTime(1200, ctx.currentTime + 0.4);
        osc.frequency.linearRampToValueAtTime(600,  ctx.currentTime + 0.8);
        osc.frequency.linearRampToValueAtTime(1200, ctx.currentTime + 1.2);
        osc.frequency.linearRampToValueAtTime(600,  ctx.currentTime + 1.6);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 2.0);
        </script>"""
        components.html(siren_html, height=0, width=0)


# ─────────────────────────────────────────────────────────────────
#  TOP BANNER  +  ACTION BUTTONS
# ─────────────────────────────────────────────────────────────────
col_banner, col_btn = st.columns([4, 1.5])

with col_banner:
    st.markdown(f"""
    <div class="rz-banner">
        <div>
            <div class="rz-title">📡 Relay<span>Zero</span></div>
        </div>
        <div class="rz-status-group">
            <div class="rz-datetime">
                <div class="rz-date">{datetime.now().strftime("%d %b %Y")}</div>
                <div class="rz-time">{datetime.now().strftime("%H:%M:%S")}</div>
                <div class="rz-tz">UTC +5:30 · PORT {PORT} · {LOCAL_IP}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_btn:
    # Refresh button — clears cached data and reruns the full script
    if st.button("🔄 REFRESH", use_container_width=True, key="btn_refresh"):
        st.cache_data.clear()
        st.rerun()
    # Purge button — deletes all incident data then reruns
    if st.button("🗑️ PURGE LOGS", use_container_width=True, key="btn_purge"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.cache_data.clear()
        st.rerun()


# ─────────────────────────────────────────────────────────────────
#  KPI METRIC ROW
#  Card 1: Active Distress Alerts   (blue)
#  Card 2: Current Danger Level     (dynamic: red / orange / gray)
#  Card 3: Casualties Reported      (amber)
#  Card 4: Export CSV               (green — st.download_button styled)
# ─────────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div class="kpi-card blue">
        <div class="kpi-label">🔔 Active Distress Alerts</div>
        <div class="kpi-value">{len(incidents):02d}</div>
        <div class="kpi-delta">PACKETS RECEIVED</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="kpi-card {danger_class}">
        <div class="kpi-label">{danger_label}</div>
        <div class="kpi-value">{danger_number:02d}</div>
        <div class="kpi-delta">{danger_delta}</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="kpi-card amber">
        <div class="kpi-label">🩸 Casualties Reported</div>
        <div class="kpi-value">{total_casualties:02d}</div>
        <div class="kpi-delta">SUM ACROSS ALL ZONES</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    # Build CSV fresh for this download button
    csv_buf2 = io.StringIO()
    w2 = csv.DictWriter(
        csv_buf2,
        fieldnames=["timestamp", "PRIO", "zone_name", "HAZ", "CAS", "REQ", "raw_packet"],
    )
    w2.writeheader()
    for inc in incidents:
        w2.writerow({k: inc.get(k, "") for k in w2.fieldnames})

    st.download_button(
        label=f"📥 EXPORT LOGS\n\n{len(incidents)} records → CSV",
        data=csv_buf2.getvalue(),
        file_name="relayzero_dispatch_log.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ─────────────────────────────────────────────────────────────────
#  MAIN GRID  — Map (60%) | Dispatch Queue (40%)
# ─────────────────────────────────────────────────────────────────
col_map, col_feed = st.columns([3, 2], gap="medium")

# ── LEFT: Live Location Map ──────────────────────────────────────
with col_map:
    st.markdown("""
    <div class="section-header">
        <span class="section-icon">🗺️</span>
        <span class="section-title">Live Location Map</span>
    </div>
    """, unsafe_allow_html=True)

    center = incidents[0]["coords"] if incidents else [10.9027, 76.9006]
    zoom   = 17 if incidents else 16

    live_map = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        prefer_canvas=True,
    )

    # Dark tile filter
    live_map.get_root().html.add_child(folium.Element("""
    <style>
        .leaflet-tile { filter: brightness(0.70) saturate(0.6) hue-rotate(195deg); }
        .leaflet-container { background: #0d1117 !important; }
    </style>
    """))

    # ── Custom "Fly to Incident" button — pans to latest emergency ──
    if incidents:
        target_lat, target_lon = incidents[0]["coords"]
        fly_js = f"""
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Wait for Leaflet map to initialise
            var tryFlyBtn = setInterval(function() {{
                var maps = document.querySelectorAll('.leaflet-container');
                if (maps.length > 0) {{
                    clearInterval(tryFlyBtn);
                    // Create button
                    var btn = document.createElement('div');
                    btn.style.cssText = `
                        position:absolute; top:10px; right:10px; z-index:1000;
                        background:#0d1117; border:2px solid #f85149;
                        border-radius:8px; padding:8px 12px;
                        font-family:'Share Tech Mono',monospace; font-size:12px;
                        color:#f85149; cursor:pointer; letter-spacing:0.08em;
                        box-shadow:0 0 12px rgba(248,81,73,0.30);
                        user-select:none;
                    `;
                    btn.innerHTML = '🎯 FLY TO INCIDENT';
                    btn.onmouseover = function() {{ btn.style.background='rgba(248,81,73,0.15)'; }};
                    btn.onmouseout  = function() {{ btn.style.background='#0d1117'; }};
                    btn.onclick = function() {{
                        // Find the Leaflet map instance
                        for (var id in window) {{
                            if (window[id] && window[id]._leaflet_id) {{
                                try {{
                                    window[id].flyTo([{target_lat}, {target_lon}], 17, {{duration: 1.5}});
                                }} catch(e) {{}}
                            }}
                        }}
                        // Also try L.map instances stored on containers
                        maps.forEach(function(el) {{
                            if (el._leaflet_id && L.map && window['leaflet_map_' + el._leaflet_id]) {{
                                window['leaflet_map_' + el._leaflet_id].flyTo([{target_lat}, {target_lon}], 17);
                            }}
                        }});
                    }};
                    maps[0].style.position = 'relative';
                    maps[0].appendChild(btn);
                }}
            }}, 300);
        }});
        </script>"""
        live_map.get_root().html.add_child(folium.Element(fly_js))

    # Plot incidents
    for item in incidents:
        coords       = item.get("coords", [10.9027, 76.9006])
        prio_upper   = item.get("PRIO", "").upper()
        is_crit      = prio_upper == "CRITICAL"
        is_high      = prio_upper in ("HIGH", "MEDIUM")
        # Red for critical, true orange for high/medium, amber for unknown
        if is_crit:
            circle_color = "#ff2d2d"
            icon_color   = "red"
        elif is_high:
            circle_color = "#ff8c00"
            icon_color   = "orange"
        else:
            circle_color = "#d29922"
            icon_color   = "orange"

        # Filled danger zone
        folium.Circle(
            location=coords, radius=150,
            color=circle_color, weight=3,
            fill=True, fill_color=circle_color, fill_opacity=0.40,
            tooltip=f"⚠ DANGER ZONE · {item.get('zone_name', '')}",
        ).add_to(live_map)

        # Outer pulse dashed ring
        folium.Circle(
            location=coords, radius=250,
            color=circle_color, weight=2,
            fill=False, opacity=0.35, dash_array="6 4",
        ).add_to(live_map)

        popup_html = f"""
        <div style="font-family:monospace;font-size:13px;color:#c9d1d9;
                    background:#161b22;padding:12px 14px;border-radius:6px;
                    border:1px solid {circle_color};min-width:160px;">
            <b style="color:{circle_color};">
                {'⛔ CRITICAL' if is_crit else ('⚠ HIGH PRIORITY' if is_high else '◈ ALERT')}
            </b><hr style="border-color:#21262d;margin:6px 0;">
            <b>📍 Zone:</b> {item.get('zone_name', item.get('LOC', '?'))}<br>
            <b>🔥 Hazard:</b> {item.get('HAZ', '?')}<br>
            <b>🩸 CAS:</b> <span style="color:#ff7b72">{item.get('CAS', '0')}</span><br>
            <b>🚑 Needs:</b> {item.get('REQ', '?')}<br>
            <b>🕒 Time:</b> {item.get('timestamp', '?')}
        </div>"""

        folium.Marker(
            location=coords,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{'🔴' if is_crit else '🟠'} {item.get('zone_name', '')} — click for details",
            icon=folium.Icon(color=icon_color, icon="info-sign", prefix="glyphicon"),
        ).add_to(live_map)

    # Campus base-station dot
    folium.Marker(
        location=[10.9027, 76.9006],
        tooltip="📡 RelayZero Base Station — Amrita Campus HQ",
        icon=folium.DivIcon(
            html="""<div style="background:rgba(56,139,253,0.20);border:2px solid #388bfd;
                        border-radius:50%;width:14px;height:14px;
                        box-shadow:0 0 10px #388bfd;"></div>""",
            icon_size=(14, 14), icon_anchor=(7, 7),
        ),
    ).add_to(live_map)

    st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)
    st_folium(live_map, width=None, height=530, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Map Legend ────────────────────────────────────────────────
    st.markdown("""
    <div class="map-legend">
        <span style="color:#6e7681;font-size:0.72rem;letter-spacing:0.1em;text-transform:uppercase;font-weight:700;">MAP LEGEND</span>
        <span class="legend-sep">│</span>
        <span class="legend-item"><span class="legend-circle-crit"></span> Critical Zone (red)</span>
        <span class="legend-item"><span class="legend-circle-high"></span> High Priority Zone (orange)</span>
        <span class="legend-item"><span class="legend-ring"></span> Outer Threat Radius (250 m)</span>
        <span class="legend-item"><span class="legend-base"></span> Base Station HQ</span>
        <span class="legend-sep">│</span>
        <span class="legend-item">📍 Incident Marker — click for details</span>
        <span class="legend-item">🎯 Fly to Incident — top-right of map</span>
    </div>
    """, unsafe_allow_html=True)


# ── RIGHT: Emergency Dispatch Queue ─────────────────────────────
with col_feed:
    st.markdown(f"""
    <div class="section-header">
        <span class="section-icon">🚨</span>
        <span class="section-title">Emergency Dispatch Queue</span>
        <span class="section-badge">{len(incidents)} ACTIVE</span>
    </div>
    """, unsafe_allow_html=True)

    if not incidents:
        st.markdown("""
        <div class="rz-empty">
            ◈ NO ACTIVE EMERGENCY PACKETS<br>
            MONITORING OFFLINE MESH FREQUENCY<br>
            <span style="font-size:0.9rem;color:#6e7681;">
                Awaiting transmission on 172.20.10.2:5000
            </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        cards_html = '<div class="feed-scroll">'

        for item in incidents:
            prio    = item.get("PRIO", "UNKNOWN").upper()
            is_crit = prio == "CRITICAL"
            is_high = prio in ("HIGH", "MEDIUM")

            if is_crit:
                card_cls, badge_cls, badge_txt = "crit", "crit", "⛔ CRITICAL RESCUE REQUIRED"
            elif is_high:
                card_cls, badge_cls, badge_txt = "high", "high", "⚠ HIGH PRIORITY ALERT"
            else:
                card_cls, badge_cls, badge_txt = "unk",  "unk",  f"◈ {prio}"

            haz = item.get("HAZ", "UNKNOWN")
            cas = item.get("CAS", "0")
            req = item.get("REQ", "NONE")
            loc = item.get("zone_name", item.get("LOC", "UNKNOWN"))
            ts  = item.get("timestamp", "--:--:--")
            raw = item.get("raw_packet", "")
            byt = item.get("bytes", len(raw.encode()))

            cards_html += f"""
            <div class="ic-card {card_cls}">
                <div class="ic-top-row">
                    <span class="ic-prio-badge {badge_cls}">{badge_txt}</span>
                    <span class="ic-ts">{ts}</span>
                </div>
                <div class="ic-location">📍 {loc}</div>
                <div class="ic-grid">
                    <div class="ic-field">
                        <div class="ic-field-label">🔥 Hazard Type</div>
                        <div class="ic-field-value haz">{haz}</div>
                    </div>
                    <div class="ic-field">
                        <div class="ic-field-label">🩸 Injuries / CAS</div>
                        <div class="ic-field-value cas">{cas} Reported</div>
                    </div>
                    <div class="ic-field" style="grid-column: span 2;">
                        <div class="ic-field-label">🚑 Resource Request</div>
                        <div class="ic-field-value req">{req}</div>
                    </div>
                </div>
                <div class="rz-raw">
                    <span class="rz-raw-label">RAW&nbsp;TX</span>
                    {raw}
                    <span class="rz-raw-bytes">{byt}&nbsp;B</span>
                </div>
            </div>"""

        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    margin-top: 28px;
    padding: 18px 0 10px 0;
    border-top: 1px solid #21262d;
    text-align: center;
">
    <span style="
        font-family: 'Inter', sans-serif;
        font-size: 1.05rem;
        font-weight: 700;
        color: #ff7b72;
        letter-spacing: 0.06em;
    ">🇮🇳 Made in India with Love &nbsp;·&nbsp; <span style="color:#79c0ff;">Team Astra</span></span>
</div>
""", unsafe_allow_html=True)