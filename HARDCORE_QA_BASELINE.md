# SG CUBE — HARDCORE QA & SYSTEM RECONNAISSANCE BASELINE

**Generated At:** 2026-09-28 | **Mission:** Phase 0 Full System Reconnaissance

---

## 1. Environment & Runtimes
- **Operating System:** Windows NT (nt) - Windows 11
- **Official Installed Python:** `C:\Users\Shara\AppData\Local\Programs\SG-CUBE\runtime\Scripts\python.exe`
- **Python Version:** `3.13.9`
- **Source Repository:** `D:\VisionClaw-main`
- **Installed Application Root:** `C:\Users\Shara\AppData\Local\Programs\SG-CUBE`
- **Launch Scripts:** `D:\VisionClaw-main\run.bat`, `C:\Users\Shara\AppData\Local\Programs\SG-CUBE\run.bat`

### Key Dependencies & Versions
- **torch:** `2.13.0+cu126`
- **torchvision:** `0.28.0+cu126`
- **torchaudio:** `2.11.0+cpu`
- **pyside6:** `NOT LOADED (No module named 'pyside6')`
- **pycaw:** `Available`
- **comtypes:** `1.4.17`
- **sounddevice:** `0.5.6`
- **speech_recognition:** `3.17.0`
- **numpy:** `2.5.2`
- **PIL:** `12.3.0`
- **psutil:** `7.2.2`
- **mss:** `10.2.0`
- **starlette:** `1.3.1`
- **uvicorn:** `0.52.1`
- **websockets:** `16.1.1`
- **pyperclip:** `1.11.0`
- **cv2 (OpenCV):** `5.0.0`

---

## 2. Physical Hardware Endpoints & Native Probing

### Audio Input / Output Devices (sounddevice)
- **Device 0:** Microsoft Sound Mapper - Input (In: 2, Out: 0, Default SR: 44100.0Hz)
- **Device 1:** Microphone Array (Intel® Smart  (In: 4, Out: 0, Default SR: 44100.0Hz)
- **Device 2:** Microsoft Sound Mapper - Output (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 3:** Speaker (Realtek(R) Audio) (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 4:** Primary Sound Capture Driver (In: 2, Out: 0, Default SR: 44100.0Hz)
- **Device 5:** Microphone Array (Intel® Smart Sound Technology for Digital Microphones) (In: 4, Out: 0, Default SR: 44100.0Hz)
- **Device 6:** Primary Sound Driver (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 7:** Speaker (Realtek(R) Audio) (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 8:** Speaker (Realtek(R) Audio) (In: 0, Out: 2, Default SR: 48000.0Hz)
- **Device 9:** Microphone Array (Intel® Smart Sound Technology for Digital Microphones) (In: 2, Out: 0, Default SR: 48000.0Hz)
- **Device 10:** Microphone Array 1 () (In: 2, Out: 0, Default SR: 48000.0Hz)
- **Device 11:** Microphone Array 2 () (In: 2, Out: 0, Default SR: 48000.0Hz)
- **Device 12:** Microphone Array 3 () (In: 4, Out: 0, Default SR: 16000.0Hz)
- **Device 13:** Speakers 1 (Realtek HD Audio output with SST) (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 14:** Speakers 2 (Realtek HD Audio output with SST) (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 15:** PC Speaker (Realtek HD Audio output with SST) (In: 2, Out: 0, Default SR: 48000.0Hz)
- **Device 16:** Headphones 1 (Realtek HD Audio 2nd output with SST) (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 17:** Headphones 2 (Realtek HD Audio 2nd output with SST) (In: 0, Out: 2, Default SR: 44100.0Hz)
- **Device 18:** PC Speaker (Realtek HD Audio 2nd output with SST) (In: 2, Out: 0, Default SR: 48000.0Hz)
- **Device 19:** Stereo Mix (Realtek HD Audio Stereo input) (In: 2, Out: 0, Default SR: 48000.0Hz)
- **Device 20:** Microphone (Realtek HD Audio Mic input) (In: 2, Out: 0, Default SR: 44100.0Hz)
- **Device 21:** Headset (@System32\drivers\bthhfenum.sys,#2;%1 Hands-Free%0
;(Nirvana Ion)) (In: 0, Out: 1, Default SR: 16000.0Hz)
- **Device 22:** Headset (@System32\drivers\bthhfenum.sys,#2;%1 Hands-Free%0
;(Nirvana Ion)) (In: 1, Out: 0, Default SR: 16000.0Hz)
- **Device 23:** Input () (In: 2, Out: 0, Default SR: 44100.0Hz)
- **Device 24:** Headphones () (In: 0, Out: 2, Default SR: 48000.0Hz)
- **Device 25:** Output (@System32\drivers\bthhfenum.sys,#4;%1 Hands-Free HF Audio%0
;(Sharath's A35)) (In: 0, Out: 1, Default SR: 8000.0Hz)
- **Device 26:** Input (@System32\drivers\bthhfenum.sys,#4;%1 Hands-Free HF Audio%0
;(Sharath's A35)) (In: 1, Out: 0, Default SR: 8000.0Hz)

### Video Capture Device (DirectShow)
- **Camera 0:** DirectShow Operational (Resolution: 640x480, Frame Grab: Success)

---

## 3. Network Interfaces, Ports & Mutexes
- **Port 49152 (TCP):** GUI IPC Port & Single-Instance Mutex (held by primary SGCubeApp process).
- **Port 49153 (TCP):** Background Wake Listener IPC Handoff Port (held by wake_listener.py).
- **Port 8000 (TCP/HTTP/WS):** Starlette / Uvicorn Presentation Bridge Server (`/api/*`, `/ws`, static UI mount).

---

## 4. Authoritative Process & Thread Architecture

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


---

## 5. Protected User Data & Database Baselines

### Source Data (`D:\VisionClaw-main\data`)
- **`face_memory\hanumanth_6ed122\embedding.npy`** (640 bytes)
- **`face_memory\hanumanth_6ed122\gallery.npy`** (1664 bytes)
- **`face_memory\hanumanth_6ed122\metadata.json`** (210 bytes): JSON Keys: `['id', 'name', 'created_at', 'has_reference_image', 'version', 'dimension', 'gallery_size', 'extra']`
- **`face_memory\hanumanth_6ed122\reference.jpg`** (4534 bytes)
- **`history\conversations.db`** (552960 bytes): Tables: `{'sessions': 1901, 'messages': 926, 'messages_fts': 312, 'messages_fts_data': 23, 'messages_fts_idx': 21, 'messages_fts_content': 312, 'messages_fts_docsize': 312, 'messages_fts_config': 1}`
- **`logs\visionclaw.log`** (278080 bytes)
- **`memory\local_memory_v2.db`** (49152 bytes): Tables: `{'local_memories': 4, 'local_memories_fts': 4, 'local_memories_fts_data': 16, 'local_memories_fts_idx': 14, 'local_memories_fts_content': 4, 'local_memories_fts_docsize': 4, 'local_memories_fts_config': 1}`
- **`memory\lockout_state.json`** (113 bytes): JSON Keys: `['version', 'failed_attempts', 'locked_until', 'last_attempt_time']`
- **`memory\master_key.dpapi`** (334 bytes)
- **`memory\memories.db`** (61440 bytes): Tables: `{'memories': 3, 'conversation_summaries': 0, 'memories_fts': 2, 'memories_fts_data': 4, 'memories_fts_idx': 2, 'memories_fts_content': 2, 'memories_fts_docsize': 2, 'memories_fts_config': 1}`
- **`memory\migration_v2.json`** (280 bytes): JSON Keys: `['started_at', 'legacy_memories_found', 'normal_migrated', 'sensitive_migrated', 'vault_records_migrated', 'errors', 'verified', 'migrated', 'total_v2_records', 'completed_at']`
- **`memory\security_audit.log`** (5559 bytes)
- **`models\face_detection_yunet_2023mar.onnx`** (232589 bytes)
- **`models\face_recognition_sface_2021dec.onnx`** (38696353 bytes)
- **`secure_vault\vault.db`** (24576 bytes): Tables: `{'secure_records': 0}`
- **`tasks\tasks.db`** (24576 bytes): Tables: `{'tasks': 0}`
- **`user_preferences\multi_api_credentials.dat`** (1314 bytes)
- **`user_preferences\preferences.json`** (679 bytes): JSON Keys: `['voice_enabled', 'greeting_enabled', 'greeting_cooldown_seconds', 'recognition_threshold', 'environment_monitor_enabled', 'safety_alerts_enabled', 'announcement_cooldown_seconds', 'ocr_language', 'currency_mode', 'response_verbosity', 'assistant_voice', 'last_greeting_date', 'last_greeting_timestamp', 'first_run_completed', 'user_name', 'user_display_name', 'user_profile_photo_path', 'user_profile_notes', 'developer_mode']`

### Installed Data (`C:\Users\Shara\AppData\Local\Programs\SG-CUBE\data`)
- **`conversations.db`** (0 bytes): Tables: `{}`
- **`history\conversations.db`** (294912 bytes): Tables: `{'sessions': 210, 'messages': 569, 'messages_fts': 569, 'messages_fts_data': 26, 'messages_fts_idx': 24, 'messages_fts_content': 569, 'messages_fts_docsize': 569, 'messages_fts_config': 1}`
- **`logs\visionclaw.log`** (192773 bytes)
- **`memory\argon2_verifier.json`** (203 bytes): JSON Keys: `['version', 'algorithm', 'argon2_hash', 'created_at']`
- **`memory\local_memory_v2.db`** (49152 bytes): Tables: `{'local_memories': 6, 'local_memories_fts': 5, 'local_memories_fts_data': 12, 'local_memories_fts_idx': 10, 'local_memories_fts_content': 5, 'local_memories_fts_docsize': 5, 'local_memories_fts_config': 1}`
- **`memory\lockout_state.json`** (113 bytes): JSON Keys: `['version', 'failed_attempts', 'locked_until', 'last_attempt_time']`
- **`memory\master_key.dpapi`** (334 bytes)
- **`memory\memories.db`** (61440 bytes): Tables: `{'memories': 5, 'conversation_summaries': 0, 'memories_fts': 5, 'memories_fts_data': 17, 'memories_fts_idx': 15, 'memories_fts_content': 5, 'memories_fts_docsize': 5, 'memories_fts_config': 1}`
- **`memory\migration_v2.json`** (278 bytes): JSON Keys: `['started_at', 'legacy_memories_found', 'normal_migrated', 'sensitive_migrated', 'vault_records_migrated', 'errors', 'verified', 'migrated', 'total_v2_records', 'completed_at']`
- **`memory\phonetic_verifier.dpapi`** (523 bytes)
- **`memory\security_audit.log`** (2359 bytes)
- **`models\.gitkeep`** (0 bytes)
- **`models\face_detection_yunet_2023mar.onnx`** (232589 bytes)
- **`models\face_recognition_sface_2021dec.onnx`** (38696353 bytes)
- **`secure_vault\speaker_profile.dat`** (4593 bytes)
- **`secure_vault\vault.db`** (24576 bytes): Tables: `{'secure_records': 1}`
- **`secure_vault\vault_master_key.dpapi`** (323 bytes)
- **`tasks\tasks.db`** (24576 bytes): Tables: `{'tasks': 2}`
- **`user_preferences\multi_api_credentials.dat`** (1314 bytes)
- **`user_preferences\preferences.json`** (820 bytes): JSON Keys: `['voice_enabled', 'greeting_enabled', 'greeting_cooldown_seconds', 'recognition_threshold', 'environment_monitor_enabled', 'safety_alerts_enabled', 'announcement_cooldown_seconds', 'ocr_language', 'currency_mode', 'response_verbosity', 'assistant_voice', 'last_greeting_date', 'last_greeting_timestamp', 'first_run_completed', 'user_name', 'user_display_name', 'user_profile_photo_path', 'user_profile_notes', 'camera_index', 'microphone_index', 'speaker_index', 'dark_mode', 'auto_start', 'user_role', 'developer_mode', 'security_onboarding_completed']`
- **`user_preferences\recovery_verifier.dat`** (654 bytes)
- **`user_preferences\security_verifier.dat`** (654 bytes)

---

## 6. Failure Boundaries & Known Limitations

1. **Windows Display Brightness:**
   - Supported natively on internal laptop panels via WMI `WmiMonitorBrightnessMethods`.
   - External desktop monitors without DDC/CI or over HDMI/DP lacking WMI brightness controls report `UNSUPPORTED` honestly (never faked).
2. **Audio Endpoint Exclusivity:**
   - Pycaw controls the primary active playback endpoint. If the user disconnects all audio playback devices, Pycaw gracefully reports endpoint unavailable.
3. **Camera Device Access:**
   - Standard USB webcams on Windows permit only one active DirectShow stream at a time. If an external application (e.g. Teams, Zoom) locks Camera 0, SG CUBE cleanly marks camera status as DEGRADED / UNAVAILABLE and keeps audio/perception running.
4. **Network & Cloud Services:**
   - Gemini Live requires internet connectivity. In offline or degraded mode, SG CUBE falls back 100% locally to Local Memory V2, Secure Vault, Windows SAPI, and native automation.
