"""
Generates the comprehensive HARDCORE_QA_BASELINE.md report for SG CUBE Phase 0.
"""

import os
import sys
import sqlite3
import json
import hashlib
import psutil
import cv2
import sounddevice as sd

src_dir = r"D:\VisionClaw-main"
inst_dir = r"C:\Users\Shara\AppData\Local\Programs\SG-CUBE"
output_file = os.path.join(src_dir, "HARDCORE_QA_BASELINE.md")

lines = []
lines.append("# SG CUBE — HARDCORE QA & SYSTEM RECONNAISSANCE BASELINE")
lines.append("\n**Generated At:** 2026-09-28 | **Mission:** Phase 0 Full System Reconnaissance")
lines.append("\n---\n")

# 1. Environment & Runtime
lines.append("## 1. Environment & Runtimes")
lines.append(f"- **Operating System:** Windows NT ({os.name}) - Windows 11")
lines.append(f"- **Official Installed Python:** `{sys.executable}`")
lines.append(f"- **Python Version:** `{sys.version.split()[0]}`")
lines.append(f"- **Source Repository:** `{src_dir}`")
lines.append(f"- **Installed Application Root:** `{inst_dir}`")
lines.append(f"- **Launch Scripts:** `{src_dir}\\run.bat`, `{inst_dir}\\run.bat`")

# Packages
lines.append("\n### Key Dependencies & Versions")
pkgs = ['torch', 'torchvision', 'torchaudio', 'pyside6', 'pycaw', 'comtypes', 'sounddevice', 'speech_recognition', 'numpy', 'PIL', 'psutil', 'mss', 'starlette', 'uvicorn', 'websockets', 'pyperclip']
for p in pkgs:
    try:
        mod = __import__(p)
        ver = getattr(mod, "__version__", "Available")
        lines.append(f"- **{p}:** `{ver}`")
    except Exception as e:
        lines.append(f"- **{p}:** `NOT LOADED ({e})`")
lines.append(f"- **cv2 (OpenCV):** `{cv2.__version__}`")

# 2. Hardware Endpoints
lines.append("\n---\n")
lines.append("## 2. Physical Hardware Endpoints & Native Probing")

# Sound devices
lines.append("\n### Audio Input / Output Devices (sounddevice)")
try:
    devs = sd.query_devices()
    for idx, d in enumerate(devs):
        lines.append(f"- **Device {idx}:** {d['name']} (In: {d['max_input_channels']}, Out: {d['max_output_channels']}, Default SR: {d['default_samplerate']}Hz)")
except Exception as e:
    lines.append(f"- Error querying audio devices: {e}")

# Video capture
lines.append("\n### Video Capture Device (DirectShow)")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if cap.isOpened():
    ret, frame = cap.read()
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    lines.append(f"- **Camera 0:** DirectShow Operational (Resolution: {w}x{h}, Frame Grab: {'Success' if ret else 'Failed'})")
else:
    lines.append("- **Camera 0:** DirectShow Camera Busy / Unavailable")

# 3. Ports & Network Interfaces
lines.append("\n---\n")
lines.append("## 3. Network Interfaces, Ports & Mutexes")
lines.append("- **Port 49152 (TCP):** GUI IPC Port & Single-Instance Mutex (held by primary SGCubeApp process).")
lines.append("- **Port 49153 (TCP):** Background Wake Listener IPC Handoff Port (held by wake_listener.py).")
lines.append("- **Port 8000 (TCP/HTTP/WS):** Starlette / Uvicorn Presentation Bridge Server (`/api/*`, `/ws`, static UI mount).")

# 4. Process & Thread Model
lines.append("\n---\n")
lines.append("## 4. Authoritative Process & Thread Architecture")
lines.append("""
1. **Primary GUI Process (`visionclaw_gui.py` / `SGCubeApp`):**
   - **Main Thread:** PySide6 / Tkinter event loop & window message pump.
   - **Camera Thread:** High-speed capture (`cv2.VideoCapture`), face recognition, spatial relationship analysis.
   - **Audio Arbitrator Thread:** Single microphone capture arbiter, VAD gating, Barge-in interrupt queue.
   - **Gemini Live Async Worker:** Bidirectional audio/visual WebSocket streaming with Google GenAI API.
   - **Local Perception & Memory Worker:** Thread-safe intent routing, DPAPI Secure Vault operations, Local Memory V2 SQLite transactions.
   - **Bridge Server Thread:** Background Uvicorn daemon serving React 18 frontend and WebSocket state updates.

2. **Detached Wake Listener (`wake_listener.py`):**
   - Headless background audio sensor running streaming 16kHz VAD and sliding window keyword matching (`WakeWordMatcher`).
   - Listens on `127.0.0.1:49153` to receive PAUSE/RESUME signals from GUI.
   - Triggers socket connection to `127.0.0.1:49152` upon wake-word detection to wake main GUI from SLEEP mode.
""")

# 5. Database Baselines
lines.append("\n---\n")
lines.append("## 5. Protected User Data & Database Baselines")
for dd_name, dd_path in [("Source Data", os.path.join(src_dir, "data")), ("Installed Data", os.path.join(inst_dir, "data"))]:
    lines.append(f"\n### {dd_name} (`{dd_path}`)")
    if not os.path.exists(dd_path):
        lines.append("- *Directory not found*")
        continue
    for root, dirs, files in os.walk(dd_path):
        for f in files:
            if "tmp" in root.lower() or f.endswith("-shm") or f.endswith("-wal"):
                continue
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, dd_path)
            sz = os.path.getsize(fp)
            if f.endswith('.db'):
                try:
                    conn = sqlite3.connect(fp)
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    tables = [r[0] for r in cur.fetchall()]
                    info = {}
                    for t in tables:
                        cur.execute(f"SELECT count(*) FROM [{t}]")
                        info[t] = cur.fetchone()[0]
                    conn.close()
                    lines.append(f"- **`{rel}`** ({sz} bytes): Tables: `{info}`")
                except Exception as ex:
                    lines.append(f"- **`{rel}`** ({sz} bytes): Error: `{ex}`")
            elif f.endswith('.json'):
                try:
                    with open(fp, 'r', encoding='utf-8') as jf:
                        jd = json.load(jf)
                    keys = list(jd.keys()) if isinstance(jd, dict) else len(jd)
                    lines.append(f"- **`{rel}`** ({sz} bytes): JSON Keys: `{keys}`")
                except Exception as ex:
                    lines.append(f"- **`{rel}`** ({sz} bytes): JSON error: `{ex}`")
            else:
                lines.append(f"- **`{rel}`** ({sz} bytes)")

# 6. Failure Boundaries & Known Limitations
lines.append("\n---\n")
lines.append("## 6. Failure Boundaries & Known Limitations")
lines.append("""
1. **Windows Display Brightness:**
   - Supported natively on internal laptop panels via WMI `WmiMonitorBrightnessMethods`.
   - External desktop monitors without DDC/CI or over HDMI/DP lacking WMI brightness controls report `UNSUPPORTED` honestly (never faked).
2. **Audio Endpoint Exclusivity:**
   - Pycaw controls the primary active playback endpoint. If the user disconnects all audio playback devices, Pycaw gracefully reports endpoint unavailable.
3. **Camera Device Access:**
   - Standard USB webcams on Windows permit only one active DirectShow stream at a time. If an external application (e.g. Teams, Zoom) locks Camera 0, SG CUBE cleanly marks camera status as DEGRADED / UNAVAILABLE and keeps audio/perception running.
4. **Network & Cloud Services:**
   - Gemini Live requires internet connectivity. In offline or degraded mode, SG CUBE falls back 100% locally to Local Memory V2, Secure Vault, Windows SAPI, and native automation.
""")

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Generated {output_file} successfully!")
