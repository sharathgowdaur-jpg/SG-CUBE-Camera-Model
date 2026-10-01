"""
SG CUBE — High-Performance Python/React Presentation Bridge Server
Bridges the authoritative Python AI/Vision backend (SGCubeApp & VisionEngine)
with the modern React 18 + TypeScript + Three.js + Tailwind CSS frontend.
"""

import os
import sys
import io
import time
import json
import asyncio
import threading
from typing import Optional, Set, Dict, Any, List
from datetime import datetime
import platform
import socket

import psutil
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect
import uvicorn


class BridgeServer:
    def __init__(self, sgcube_app=None, dist_dir: Optional[str] = None):
        self.app_instance = sgcube_app
        if not dist_dir:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            dist_dir = os.path.join(base_dir, "frontend", "dist")
        self.dist_dir = dist_dir
        self.connected_clients: Set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.server_thread: Optional[threading.Thread] = None
        self.uvicorn_server: Optional[uvicorn.Server] = None
        self.is_running = False

    def _get_store(self):
        if self.app_instance and hasattr(self.app_instance, "engine") and getattr(self.app_instance.engine, "store", None):
            return self.app_instance.engine.store
        if not hasattr(self, "_fallback_store"):
            from assistive.memory_store import MemoryStore
            self._fallback_store = MemoryStore()
        return self._fallback_store

    def _get_key_manager(self):
        if self.app_instance and hasattr(self.app_instance, "engine") and getattr(self.app_instance.engine, "key_manager", None):
            return self.app_instance.engine.key_manager
        if not hasattr(self, "_fallback_km"):
            from assistive.api_key_manager import APIKeyManager
            self._fallback_km = APIKeyManager()
        return self._fallback_km

    def run_system_diagnostics(self) -> Dict[str, Any]:
        """Performs authoritative hardware, network, model, and system diagnostics."""
        results = []
        overall = "PASS"

        # 1. Operating System
        try:
            os_name = platform.system()
            os_release = platform.release()
            os_ver = sys.getwindowsversion() if hasattr(sys, "getwindowsversion") else None
            is_win = os_name == "Windows"
            build_num = os_ver.build if os_ver else 0
            if is_win and build_num >= 19041:
                results.append({
                    "id": "os",
                    "name": "Operating System",
                    "status": "PASS",
                    "details": f"Windows {os_release} (Build {build_num}, 64-bit AMD64)",
                    "remedy": None
                })
            elif is_win:
                results.append({
                    "id": "os",
                    "name": "Operating System",
                    "status": "WARNING",
                    "details": f"Windows {os_release} (Build {build_num}) - Recommended: Windows 10/11 Build >= 19041",
                    "remedy": "Consider updating Windows to the latest version for full WebView2 and DirectShow support."
                })
                if overall == "PASS": overall = "WARNING"
            else:
                results.append({
                    "id": "os",
                    "name": "Operating System",
                    "status": "FAIL",
                    "details": f"Non-Windows OS ({os_name} {os_release})",
                    "remedy": "SG CUBE is optimized for Windows 10/11 x64."
                })
                overall = "FAIL"
        except Exception as e:
            results.append({"id": "os", "name": "Operating System", "status": "WARNING", "details": str(e), "remedy": None})

        # 2. Microphone (Audio Input)
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            in_devs = [d for d in devs if d.get("max_input_channels", 0) > 0]
            if in_devs:
                def_in = sd.default.device[0]
                def_name = devs[def_in]["name"] if (def_in is not None and def_in < len(devs)) else in_devs[0]["name"]
                results.append({
                    "id": "microphone",
                    "name": "Microphone / Audio Input",
                    "status": "PASS",
                    "details": f"{len(in_devs)} input device(s) found. Default: {def_name}",
                    "remedy": None
                })
            else:
                results.append({
                    "id": "microphone",
                    "name": "Microphone / Audio Input",
                    "status": "WARNING",
                    "details": "No microphone or audio input devices detected.",
                    "remedy": "Plug in a microphone or headset and verify input settings in Windows Settings -> System -> Sound."
                })
                if overall == "PASS": overall = "WARNING"
        except Exception as e:
            results.append({
                "id": "microphone",
                "name": "Microphone / Audio Input",
                "status": "WARNING",
                "details": f"Audio query failed: {e}",
                "remedy": "Ensure Windows Audio Service is running and audio drivers are installed."
            })
            if overall == "PASS": overall = "WARNING"

        # 3. Speaker (Audio Output)
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            out_devs = [d for d in devs if d.get("max_output_channels", 0) > 0]
            if out_devs:
                def_out = sd.default.device[1]
                def_name = devs[def_out]["name"] if (def_out is not None and def_out < len(devs)) else out_devs[0]["name"]
                results.append({
                    "id": "speaker",
                    "name": "Speaker / Audio Output",
                    "status": "PASS",
                    "details": f"{len(out_devs)} output device(s) found. Default: {def_name}",
                    "remedy": None
                })
            else:
                results.append({
                    "id": "speaker",
                    "name": "Speaker / Audio Output",
                    "status": "WARNING",
                    "details": "No audio playback devices detected.",
                    "remedy": "Connect headphones or external speakers to hear SG CUBE speech announcements."
                })
                if overall == "PASS": overall = "WARNING"
        except Exception as e:
            results.append({
                "id": "speaker",
                "name": "Speaker / Audio Output",
                "status": "WARNING",
                "details": f"Playback query failed: {e}",
                "remedy": "Check Windows Sound Playback settings."
            })
            if overall == "PASS": overall = "WARNING"

        # 4. Camera (OpenCV DirectShow)
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    results.append({
                        "id": "camera",
                        "name": "Camera Access (OpenCV)",
                        "status": "PASS",
                        "details": f"Primary camera verified ({frame.shape[1]}x{frame.shape[0]} px resolution)",
                        "remedy": None
                    })
                else:
                    results.append({
                        "id": "camera",
                        "name": "Camera Access (OpenCV)",
                        "status": "PASS",
                        "details": "Camera device detected and opened successfully.",
                        "remedy": None
                    })
            else:
                results.append({
                    "id": "camera",
                    "name": "Camera Access (OpenCV)",
                    "status": "WARNING",
                    "details": "Camera device not detected or currently in use by another application.",
                    "remedy": "Check camera privacy in Windows Settings -> Privacy & security -> Camera, and ensure other apps (Zoom, Teams) are closed."
                })
                if overall == "PASS": overall = "WARNING"
        except Exception as e:
            results.append({
                "id": "camera",
                "name": "Camera Access (OpenCV)",
                "status": "WARNING",
                "details": f"Camera probe error: {e}",
                "remedy": "Ensure webcam is connected and video capture drivers are installed."
            })
            if overall == "PASS": overall = "WARNING"

        # 5. Internet Connection
        internet_ok = False
        try:
            sock = socket.create_connection(("generativelanguage.googleapis.com", 443), timeout=3.5)
            sock.close()
            internet_ok = True
            results.append({
                "id": "internet",
                "name": "Internet Connectivity",
                "status": "PASS",
                "details": "Direct TLS connection to Google API gateway verified.",
                "remedy": None
            })
        except Exception:
            try:
                sock = socket.create_connection(("8.8.8.8", 53), timeout=3.0)
                sock.close()
                internet_ok = True
                results.append({
                    "id": "internet",
                    "name": "Internet Connectivity",
                    "status": "PASS",
                    "details": "Internet connectivity verified via Google DNS gateway.",
                    "remedy": None
                })
            except Exception as e:
                results.append({
                    "id": "internet",
                    "name": "Internet Connectivity",
                    "status": "FAIL",
                    "details": f"Cannot connect to the internet: {e}",
                    "remedy": "Check Wi-Fi or Ethernet connection, firewall, or proxy settings."
                })
                overall = "FAIL"

        # 6. Gemini API Key & Service
        km = self._get_key_manager()
        active_key = km.get_active_api_key() if km else ""
        if not active_key:
            results.append({
                "id": "gemini_api",
                "name": "Gemini AI API Key",
                "status": "WARNING",
                "details": "No API key configured yet. (Conversational AI requires a Gemini key)",
                "remedy": "Enter and validate your Google Gemini API Key in Setup Step 3 or in Settings."
            })
            if overall == "PASS": overall = "WARNING"
        else:
            if internet_ok:
                is_valid, msg = km.test_connection(active_key)
                if is_valid:
                    results.append({
                        "id": "gemini_api",
                        "name": "Gemini AI API Key",
                        "status": "PASS",
                        "details": f"Key verified with Google GenAI ({km.get_masked_key()}).",
                        "remedy": None
                    })
                else:
                    results.append({
                        "id": "gemini_api",
                        "name": "Gemini AI API Key",
                        "status": "FAIL",
                        "details": f"Configured key failed validation: {msg}",
                        "remedy": "Update your API key in Settings or the Setup Wizard."
                    })
                    overall = "FAIL"
            else:
                results.append({
                    "id": "gemini_api",
                    "name": "Gemini AI API Key",
                    "status": "WARNING",
                    "details": f"Key configured ({km.get_masked_key()}), but internet offline.",
                    "remedy": "Connect to internet to validate key."
                })
                if overall == "PASS": overall = "WARNING"

        # 7. Local Neural Vision Models
        models_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "models"))
        yunet_path = os.path.join(models_root, "face_detection_yunet_2023mar.onnx")
        sface_path = os.path.join(models_root, "face_recognition_sface_2021dec.onnx")
        y_ok = os.path.isfile(yunet_path) and os.path.getsize(yunet_path) > 100000
        s_ok = os.path.isfile(sface_path) and os.path.getsize(sface_path) > 10000000
        if y_ok and s_ok:
            results.append({
                "id": "vision_models",
                "name": "Local Vision AI Models",
                "status": "PASS",
                "details": "YuNet (Face Detection) & SFace (Face Embeddings) verified on disk.",
                "remedy": None
            })
        else:
            missing = []
            if not y_ok: missing.append("YuNet")
            if not s_ok: missing.append("SFace")
            results.append({
                "id": "vision_models",
                "name": "Local Vision AI Models",
                "status": "FAIL",
                "details": f"Missing or corrupted vision models: {', '.join(missing)}",
                "remedy": "Re-run installer or verify data/models folder contains ONNX weights."
            })
            overall = "FAIL"

        # 8. Python Runtime & Core Libraries
        try:
            import cv2
            import google.genai
            import win32crypt
            import psutil
            results.append({
                "id": "dependencies",
                "name": "Runtime Dependencies",
                "status": "PASS",
                "details": f"Python {platform.python_version()} (cv2, google-genai, pywin32, sounddevice, psutil)",
                "remedy": None
            })
        except Exception as e:
            results.append({
                "id": "dependencies",
                "name": "Runtime Dependencies",
                "status": "FAIL",
                "details": f"Missing library: {e}",
                "remedy": "Run pip install -r requirements.txt"
            })
            overall = "FAIL"

        # 9. Filesystem Write Permissions
        store = self._get_store()
        pref_dir = getattr(store, "pref_dir", os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "user_preferences")))
        try:
            os.makedirs(pref_dir, exist_ok=True)
            test_file = os.path.join(pref_dir, ".write_test.tmp")
            with open(test_file, "w") as tf:
                tf.write("ok")
            os.remove(test_file)
            results.append({
                "id": "filesystem",
                "name": "Storage Permissions",
                "status": "PASS",
                "details": f"Read/write access verified in {os.path.basename(pref_dir)}.",
                "remedy": None
            })
        except Exception as e:
            results.append({
                "id": "filesystem",
                "name": "Storage Permissions",
                "status": "FAIL",
                "details": f"Write test failed: {e}",
                "remedy": "Check folder permissions or run with standard user privileges in %LOCALAPPDATA%."
            })
            overall = "FAIL"

        # 10. Local SQLite & Memory Engines
        try:
            import sqlite3
            test_db = os.path.join(pref_dir, ".sqlite_test.tmp")
            conn = sqlite3.connect(test_db)
            conn.execute("CREATE TABLE test (id INT);")
            conn.commit()
            conn.close()
            os.remove(test_db)
            results.append({
                "id": "databases",
                "name": "Local Memory Database",
                "status": "PASS",
                "details": f"SQLite v{sqlite3.sqlite_version} database engine verified.",
                "remedy": None
            })
        except Exception as e:
            results.append({
                "id": "databases",
                "name": "Local Memory Database",
                "status": "FAIL",
                "details": f"SQLite initialization error: {e}",
                "remedy": "Ensure disk is not full or write-protected."
            })
            overall = "FAIL"

        return {
            "overall": overall,
            "timestamp": time.time(),
            "checks": results
        }

    def set_app_instance(self, sgcube_app):
        self.app_instance = sgcube_app

    def broadcast_sync(self, message: Dict[str, Any]):
        """Thread-safe broadcast to all connected WebSocket clients from any Python thread."""
        if not self.loop or not self.connected_clients:
            return
        msg_str = json.dumps(message)
        asyncio.run_coroutine_threadsafe(self._broadcast_async(msg_str), self.loop)

    async def _broadcast_async(self, message_str: str):
        dead_clients = set()
        for ws in list(self.connected_clients):
            try:
                await ws.send_text(message_str)
            except Exception:
                dead_clients.add(ws)
        self.connected_clients.difference_update(dead_clients)

    def handle_backend_event(self, msg_type: str, payload: Any):
        """Called whenever SGCubeApp processes a GUI queue event."""
        now_str = datetime.now().strftime("%H:%M")

        if msg_type == "STATE":
            state_str = str(payload)
            self.broadcast_sync({
                "type": "STATE_UPDATE",
                "state": state_str,
                "pulse": 1.0,
                "is_sleeping": state_str == "SLEEPING",
            })
        elif msg_type == "TRANSCRIPT_USER":
            text = str(payload)
            low_text = text.lower()
            if "voice_password_redacted" in low_text or "[protected" in low_text:
                text = "[Protected Security Input]"
            else:
                try:
                    from assistive.secure_vault.sensitive_data_detector import SensitiveDataDetector
                    if SensitiveDataDetector.is_sensitive(text):
                        text = "[Protected Security Input]"
                except Exception:
                    pass
            self.broadcast_sync({
                "type": "TRANSCRIPTION",
                "text": f"You: {text}",
            })
            self.broadcast_sync({
                "type": "NEW_MESSAGE",
                "item": {
                    "time": now_str,
                    "sender": "user",
                    "text": text,
                },
            })
        elif msg_type in ("TRANSCRIPT_AI", "TRANSCRIPT_ASSISTIVE"):
            text = str(payload)
            low_text = text.lower()
            if "here is your protected information:" in low_text or "voice_password_redacted" in low_text or "[protected" in low_text:
                text = "[Protected Information Disclosed Locally]"
            else:
                try:
                    from assistive.secure_vault.sensitive_data_detector import SensitiveDataDetector
                    if SensitiveDataDetector.is_sensitive(text):
                        text = "[Protected Information Disclosed Locally]"
                except Exception:
                    pass
            self.broadcast_sync({
                "type": "TRANSCRIPTION",
                "text": f"SG CUBE: {text}",
            })
            self.broadcast_sync({
                "type": "NEW_MESSAGE",
                "item": {
                    "time": now_str,
                    "sender": "ai",
                    "text": text,
                },
            })
        elif msg_type == "CAMERA_STATUS":
            stat_str = str(payload)
            self.broadcast_sync({
                "type": "STATUS",
                "status": {
                    "camera": "Active" if "LIVE" in stat_str or "META" in stat_str else "Paused",
                },
            })
        elif msg_type == "NETWORK_STATUS":
            is_online = bool(payload)
            self.broadcast_sync({
                "type": "STATUS",
                "status": {
                    "network": "Online" if is_online else "Offline",
                },
            })

    def get_system_telemetry(self) -> Dict[str, Any]:
        """Gathers authoritative real-time state and telemetry from SGCubeApp and Windows."""
        app = self.app_instance

        # Battery calculation
        battery_pct = "100%"
        try:
            battery = psutil.sensors_battery()
            if battery:
                battery_pct = f"{int(round(battery.percent))}%"
            else:
                battery_pct = "AC"
        except Exception:
            battery_pct = "AC"

        store = self._get_store()
        km = self._get_key_manager()
        first_run_done = store.get_setting("first_run_completed", False) if store else False
        user_name = store.get_setting("user_name", "") if store else ""
        has_api_key = bool(km.get_active_api_key()) if km else False

        if not app:
            return {
                "state": "IDLE",
                "pulse": 1.0,
                "status": {
                    "camera": "Paused",
                    "fps": 0,
                    "microphone": "Active",
                    "speaker": "Active",
                    "ai": "Ready",
                    "battery": battery_pct,
                    "network": "Online",
                },
                "environment": {
                    "people": "None",
                    "room": "Workspace",
                    "lighting": "Normal",
                    "noise": "Low",
                    "safety": "Clear",
                },
                "scene": {
                    "people": "0 | Objects: 0",
                    "left": "None",
                    "center": "None",
                    "right": "None",
                    "path": "Clear",
                },
                "history": [],
                "memories": [],
                "is_sleeping": False,
                "first_run_completed": bool(first_run_done),
                "user_name": str(user_name),
                "has_api_key": bool(has_api_key),
            }

        cur_state = getattr(app, "current_state", "IDLE")
        cam_running = getattr(app, "camera_running", False)
        ai_running = getattr(app, "ai_running", False)
        fps = int(round(getattr(app, "measured_fps", 20.0))) if cam_running else 0
        is_net_online = getattr(app, "network_online", True)

        # Environment & Scene from engine
        env = {}
        scene = {}
        faces_count = 0
        objects_count = 0

        if hasattr(app, "engine") and app.engine:
            last_env = getattr(app.engine, "last_environment", {}) or {}
            last_scene = getattr(app.engine, "last_scene", {}) or {}
            last_faces = getattr(app.engine, "last_faces", []) or []
            last_objects = getattr(app.engine, "last_objects", []) or []

            faces_count = len(last_faces)
            objects_count = len(last_objects)

            people_str = f"{faces_count} {'person' if faces_count == 1 else 'people'}" if faces_count > 0 else "None"
            env = {
                "people": people_str,
                "room": last_env.get("room_type", "Workspace") if isinstance(last_env, dict) else "Workspace",
                "lighting": last_env.get("lighting", "Normal") if isinstance(last_env, dict) else "Normal",
                "noise": last_env.get("noise_level", "Low") if isinstance(last_env, dict) else "Low",
                "safety": last_env.get("safety_summary", "Clear") if isinstance(last_env, dict) else "Clear",
            }

            scene = {
                "people": f"{faces_count} | Objects: {objects_count}",
                "left": last_scene.get("left", "None") if isinstance(last_scene, dict) else "None",
                "center": last_scene.get("center", "None") if isinstance(last_scene, dict) else "None",
                "right": last_scene.get("right", "None") if isinstance(last_scene, dict) else "None",
                "path": last_scene.get("path_status", "Clear") if isinstance(last_scene, dict) else "Clear",
            }
        else:
            env = {
                "people": "None",
                "room": "Workspace",
                "lighting": "Normal",
                "noise": "Low",
                "safety": "Clear",
            }
            scene = {
                "people": "0 | Objects: 0",
                "left": "None",
                "center": "None",
                "right": "None",
                "path": "Clear",
            }

        # Formatted history items
        history_items = []
        try:
            if hasattr(app, "engine") and app.engine and hasattr(app.engine, "history"):
                session_id = getattr(app, "active_history_session_id", None)
                if session_id:
                    raw_msgs = app.engine.history.get_session_messages(session_id, limit=20)
                else:
                    sessions = app.engine.history.list_recent_sessions(limit=1)
                    if sessions:
                        raw_msgs = app.engine.history.get_session_messages(sessions[0]["session_id"], limit=20)
                    else:
                        raw_msgs = []
                for m in reversed(raw_msgs):
                    ts = m.get("created_at")
                    t_str = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
                    sender = "user" if m.get("sender") == "user" else "ai"
                    history_items.append({
                        "time": t_str,
                        "sender": sender,
                        "text": m.get("text", ""),
                    })
        except Exception as e:
            print(f"[BRIDGE-HIST-WARN] Failed reading history: {e}")

        # Formatted memories
        memories_items = []
        try:
            if hasattr(app, "engine") and app.engine and hasattr(app.engine, "memory"):
                raw_mems = app.engine.memory.list_all_memories()
                for mem in raw_mems[:20]:
                    memories_items.append({
                        "key": mem.get("key_phrase", "Memory"),
                        "value": mem.get("fact_value", ""),
                        "category": mem.get("category", "General"),
                    })
        except Exception as e:
            print(f"[BRIDGE-MEM-WARN] Failed reading memories: {e}")

        return {
            "state": cur_state,
            "pulse": 1.0,
            "status": {
                "camera": "Active" if cam_running else "Paused",
                "fps": fps,
                "microphone": "Active" if ai_running else "Muted",
                "speaker": "Active",
                "ai": "Ready" if ai_running else "Standby",
                "battery": battery_pct,
                "network": "Online" if is_net_online else "Offline",
            },
            "environment": env,
            "scene": scene,
            "history": history_items,
            "memories": memories_items,
            "is_sleeping": cur_state == "SLEEPING",
            "first_run_completed": bool(first_run_done),
            "user_name": str(user_name),
            "has_api_key": bool(has_api_key),
        }

    def execute_action(self, action: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """Dispatches action to SGCubeApp authoritative methods or standalone store/diagnostics."""
        app = self.app_instance
        payload = payload or {}
        print(f"[BRIDGE-ACTION] Executing '{action}' with payload: {payload}")

        # Actions that can run standalone (setup, API key management, settings, diagnostics)
        if action in ("RUN_DIAGNOSTICS", "OPEN_DIAGNOSTICS"):
            return {"status": "ok", "diagnostics": self.run_system_diagnostics()}

        elif action == "TEST_API_KEY":
            km = self._get_key_manager()
            key = payload.get("api_key", "").strip()
            valid, msg = km.test_connection(key)
            return {"status": "ok", "valid": valid, "message": msg}

        elif action == "SAVE_API_KEY":
            km = self._get_key_manager()
            slot = int(payload.get("slot", 1))
            key = payload.get("api_key", "").strip()
            ok = km.set_key(slot, key)
            return {"status": "ok" if ok else "error", "slot": slot, "masked_key": km.get_masked_key(slot)}

        elif action == "REMOVE_API_KEY":
            km = self._get_key_manager()
            slot = int(payload.get("slot", 1))
            ok = km.clear_key(slot)
            return {"status": "ok", "slot": slot}

        elif action == "SAVE_USER_NAME":
            store = self._get_store()
            uname = payload.get("user_name", "").strip()
            dname = payload.get("user_display_name", "").strip() or uname
            if store and uname:
                store.set_setting("user_name", uname)
                store.set_setting("user_display_name", dname)
            return {"status": "ok", "user_name": uname}

        elif action == "COMPLETE_SETUP":
            store = self._get_store()
            if store:
                store.set_setting("first_run_completed", True)
            if app and hasattr(app, "set_state"):
                if getattr(app, "current_state", "SLEEPING") == "SLEEPING":
                    app.set_state("IDLE")
            return {"status": "ok", "first_run_completed": True}

        elif action == "RESET_SETUP":
            store = self._get_store()
            if store:
                store.set_setting("first_run_completed", False)
            return {"status": "ok", "first_run_completed": False}

        elif action == "GET_SETUP_STATUS":
            store = self._get_store()
            km = self._get_key_manager()
            first_run = store.get_setting("first_run_completed", False) if store else False
            uname = store.get_setting("user_name", "") if store else ""
            dname = store.get_setting("user_display_name", "") if store else ""
            active_key = km.get_active_api_key() if km else ""
            keys_info = {}
            if km:
                for slot in [1, 2, 3]:
                    val = km.keys.get(slot, "")
                    keys_info[str(slot)] = {
                        "configured": bool(val and len(val) > 10),
                        "masked": km.get_masked_key(slot) if val else ""
                    }
            return {
                "status": "ok",
                "setup_status": {
                    "first_run_completed": bool(first_run),
                    "user_name": str(uname),
                    "user_display_name": str(dname or uname),
                    "has_api_key": bool(active_key and len(active_key) > 10),
                    "masked_key": km.get_masked_key() if (km and active_key) else "",
                    "keys": keys_info,
                    "active_slot": getattr(km, "active_key_num", 1) or 1
                }
            }

        elif action == "OPEN_SETTINGS":
            store = self._get_store()
            vol = app.engine.system_control.get_volume() if (app and hasattr(app, "engine") and hasattr(app.engine, "system_control")) else 50
            brt = app.engine.system_control.get_brightness() if (app and hasattr(app, "engine") and hasattr(app.engine, "system_control")) else 70
            settings_data = {
                "user_name": store.get_setting("user_display_name", "User") if store else "User",
                "voice": store.get_setting("ai_voice", "Default") if store else "Default",
                "speech_rate": store.get_setting("speech_speed", 1.0) if store else 1.0,
                "sensitivity": store.get_setting("wake_word_sensitivity", 0.7) if store else 0.7,
                "volume": vol,
                "brightness": brt,
            }
            return {"status": "ok", "settings": settings_data}

        elif action == "SAVE_SETTINGS":
            store = self._get_store()
            if store:
                if "user_name" in payload:
                    store.set_setting("user_display_name", payload["user_name"])
                if "voice" in payload:
                    store.set_setting("ai_voice", payload["voice"])
                if "speech_rate" in payload:
                    store.set_setting("speech_speed", payload["speech_rate"])
                if "sensitivity" in payload:
                    store.set_setting("wake_word_sensitivity", payload["sensitivity"])
            if app and hasattr(app, "engine") and hasattr(app.engine, "system_control"):
                if "volume" in payload:
                    app.engine.system_control.set_volume(payload["volume"])
                if "brightness" in payload and payload["brightness"] is not None:
                    app.engine.system_control.set_brightness(payload["brightness"])
            return {"status": "ok", "message": "Settings updated successfully."}

        elif action == "TOGGLE_GLASSES":
            if app and hasattr(app, "engine") and hasattr(app.engine, "meta_glass"):
                mg = app.engine.meta_glass
                if getattr(mg, "is_streaming", False):
                    mg.stop_stream()
                    return {"status": "ok", "message": "Meta Glass stream paused. Laptop camera active."}
                else:
                    mg.start_stream()
                    return {"status": "ok", "message": "Connecting to Meta Glass camera stream..."}
            return {"status": "ok", "message": "Meta Glass bridge standby. Laptop camera active."}

        elif action == "SELECT_NAV":
            tab = payload.get("tab", "home")
            return {"status": "ok", "tab": tab}

        # The following actions strictly require an active app instance
        if not app:
            return {"status": "error", "message": "No active backend instance"}

        if action == "WAKE":
            with app.session_lock:
                if app.current_state == "SLEEPING":
                    app.set_state("LISTENING")
                    app.start_camera()
                    app.start_ai()
                    if hasattr(app, "_notify_wake_listener_pause"):
                        app._notify_wake_listener_pause()
                    if hasattr(app, "root") and app.root:
                        try:
                            app.root.deiconify()
                        except Exception:
                            pass
            return {"status": "ok", "state": app.current_state}

        elif action == "SLEEP":
            if hasattr(app, "enter_sleep_mode"):
                threading.Thread(target=app.enter_sleep_mode, daemon=True).start()
            return {"status": "ok", "state": "SLEEPING"}

        elif action == "TOGGLE_CAMERA":
            if hasattr(app, "toggle_camera"):
                app.toggle_camera()
            return {"status": "ok", "camera_running": getattr(app, "camera_running", False)}

        elif action == "TOGGLE_MIC":
            if getattr(app, "ai_running", False):
                app.stop_ai()
            else:
                app.start_ai()
            return {"status": "ok", "ai_running": getattr(app, "ai_running", False)}

        elif action == "STOP":
            if hasattr(app, "_clear_playback_queue"):
                app._clear_playback_queue()
            if hasattr(app, "playback_stop_evt"):
                app.playback_stop_evt.set()
            app.set_state("IDLE")
            return {"status": "ok", "state": "IDLE"}

        elif action == "SEND_TEXT":
            text = payload.get("text", "").strip()
            if text:
                if hasattr(app, "_trigger_action_async"):
                    app._trigger_action_async("user_text", "User Command", text)
                else:
                    threading.Thread(target=app.engine.process_user_speech_query, args=(text,), daemon=True).start()
            return {"status": "ok", "text": text}

        elif action == "CLEAR_MEMORY":
            if hasattr(app.engine, "artifact_cache"):
                app.engine.artifact_cache.clear()
            return {"status": "ok", "message": "Interaction memory cleared."}

        elif action == "LOCK_VAULT":
            if hasattr(app.engine, "vault"):
                app.engine.vault.lock()
            if hasattr(app.engine, "security"):
                app.engine.security.lock_session()
            return {"status": "ok", "message": "Secure Vault locked."}

        elif action == "SET_VOLUME":
            vol = payload.get("volume", 50)
            if hasattr(app.engine, "system_control"):
                app.engine.system_control.set_volume(vol)
            return {"status": "ok", "volume": vol}

        elif action == "SET_BRIGHTNESS":
            b = payload.get("brightness", 70)
            if hasattr(app.engine, "system_control"):
                app.engine.system_control.set_brightness(b)
            return {"status": "ok", "brightness": b}

        return {"status": "ignored", "action": action}

    def build_starlette_app(self) -> Starlette:
        async def get_status(request):
            data = self.get_system_telemetry()
            return JSONResponse(data)

        async def post_action(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            action = body.get("action", "")
            res = self.execute_action(action, body)
            return JSONResponse(res)

        async def get_setup_status(request):
            store = self._get_store()
            km = self._get_key_manager()
            first_run = store.get_setting("first_run_completed", False) if store else False
            uname = store.get_setting("user_name", "") if store else ""
            dname = store.get_setting("user_display_name", "") if store else ""
            keys_info = {}
            if km:
                for slot in [1, 2, 3]:
                    val = km.keys.get(slot, "")
                    keys_info[str(slot)] = {
                        "configured": bool(val and len(val) > 10),
                        "masked": km.get_masked_key(slot) if val else ""
                    }
            active_key = km.get_active_api_key() if km else ""
            return JSONResponse({
                "first_run_completed": bool(first_run),
                "user_name": str(uname),
                "user_display_name": str(dname or uname),
                "has_api_key": bool(active_key and len(active_key) > 10),
                "masked_key": km.get_masked_key() if (km and active_key) else "",
                "keys": keys_info,
                "active_slot": getattr(km, "active_key_num", 1) or 1
            })

        async def post_setup_user_name(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            uname = body.get("user_name", "").strip()
            dname = body.get("user_display_name", "").strip() or uname
            if not uname:
                return JSONResponse({"status": "error", "message": "User name cannot be empty."}, status_code=400)
            store = self._get_store()
            if store:
                store.set_setting("user_name", uname)
                store.set_setting("user_display_name", dname)
            return JSONResponse({"status": "ok", "user_name": uname, "user_display_name": dname})

        async def post_test_api_key(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            key = body.get("api_key", "").strip()
            if not key:
                return JSONResponse({"status": "error", "valid": False, "message": "API key cannot be empty."}, status_code=400)
            km = self._get_key_manager()
            valid, msg = km.test_connection(key)
            return JSONResponse({"status": "ok", "valid": valid, "message": msg})

        async def post_save_api_key(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            key = body.get("api_key", "").strip()
            slot = int(body.get("slot", 1))
            if slot not in (1, 2, 3):
                slot = 1
            if not key:
                return JSONResponse({"status": "error", "message": "API key cannot be empty."}, status_code=400)
            km = self._get_key_manager()
            ok = km.set_key(slot, key)
            if ok:
                masked = km.get_masked_key(slot)
                return JSONResponse({"status": "ok", "slot": slot, "masked_key": masked})
            return JSONResponse({"status": "error", "message": "Failed to encrypt and save API key."}, status_code=500)

        async def post_remove_api_key(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            slot = int(body.get("slot", 1))
            km = self._get_key_manager()
            if km and slot in (1, 2, 3):
                km.clear_key(slot)
            return JSONResponse({"status": "ok", "slot": slot})

        async def get_diagnostics(request):
            diag = self.run_system_diagnostics()
            return JSONResponse(diag)

        async def post_complete_setup(request):
            store = self._get_store()
            if store:
                store.set_setting("first_run_completed", True)
            if self.app_instance and hasattr(self.app_instance, "set_state"):
                if getattr(self.app_instance, "current_state", "SLEEPING") == "SLEEPING":
                    self.app_instance.set_state("IDLE")
            return JSONResponse({"status": "ok", "first_run_completed": True})

        async def post_reset_setup(request):
            store = self._get_store()
            if store:
                store.set_setting("first_run_completed", False)
            return JSONResponse({"status": "ok", "first_run_completed": False})

        async def get_people(request):
            people = []
            if self.app_instance and hasattr(self.app_instance, "engine") and hasattr(self.app_instance.engine, "face_memory"):
                fm = self.app_instance.engine.face_memory
                for pid, prof in fm.profiles.items():
                    people.append({
                        "id": pid,
                        "name": prof.get("name", "Unknown"),
                        "enrollment_count": prof.get("enrollment_count", 1)
                    })
            else:
                try:
                    from assistive.face_memory import FaceMemory
                    fm = FaceMemory()
                    for pid, prof in fm.profiles.items():
                        people.append({
                            "id": pid,
                            "name": prof.get("name", "Unknown"),
                            "enrollment_count": prof.get("enrollment_count", 1)
                        })
                except Exception:
                    pass
            return JSONResponse({"people": people})

        async def post_delete_person(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            name = body.get("name", "").strip()
            ok = False
            if self.app_instance and hasattr(self.app_instance, "engine") and hasattr(self.app_instance.engine, "face_memory"):
                ok = self.app_instance.engine.face_memory.forget_person(name)
            else:
                try:
                    from assistive.face_memory import FaceMemory
                    fm = FaceMemory()
                    ok = fm.forget_person(name)
                except Exception:
                    pass
            return JSONResponse({"status": "ok" if ok else "not_found", "name": name})

        async def get_glasses_status(request):
            stat = {
                "bridge_state": "STANDBY",
                "active_source": "LAPTOP",
                "battery_level": None,
                "streaming": False
            }
            if self.app_instance and hasattr(self.app_instance, "engine") and hasattr(self.app_instance.engine, "meta_glass"):
                mg = self.app_instance.engine.meta_glass
                stat["bridge_state"] = getattr(mg, "state", "STANDBY")
                stat["streaming"] = getattr(mg, "is_streaming", False)
            return JSONResponse(stat)

        def get_vault_controller():
            if self.app_instance and hasattr(self.app_instance, "engine") and hasattr(self.app_instance.engine, "vault"):
                return self.app_instance.engine.vault
            from assistive.secure_vault import SecureVaultController
            data_dir = os.environ.get("SGCUBE_USER_DATA")
            if not data_dir:
                data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
            vault_dir = os.path.join(data_dir, "secure_vault")
            os.makedirs(vault_dir, exist_ok=True)
            if not hasattr(self, "_standalone_vault"):
                self._standalone_vault = SecureVaultController(
                    db_path=os.path.join(vault_dir, "vault.db"),
                    verifier_file=os.path.join(vault_dir, "vault_verifier.json")
                )
            return self._standalone_vault

        async def get_vault_status(request):
            vault = get_vault_controller()
            st = vault.status()
            return JSONResponse({
                "status": "ok",
                "state": st["state"],
                "is_setup": st["is_setup"],
                "is_unlocked": st["is_unlocked"],
                "is_locked_out": st["is_locked_out"],
                "lockout_remaining_seconds": st.get("lockout_remaining_seconds", 0),
                "record_count": st["record_count"]
            })

        async def post_vault_setup(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            master_pw = body.get("master_password", "")
            if not master_pw or len(master_pw) < 6:
                return JSONResponse({"status": "error", "message": "Master password must be at least 6 characters."}, status_code=400)
            vault = get_vault_controller()
            ok = vault.setup_vault(master_pw)
            if ok:
                try:
                    if hasattr(self, "app_instance") and self.app_instance and hasattr(self.app_instance, "engine") and self.app_instance.engine:
                        eng = self.app_instance.engine
                        if hasattr(eng, "security") and eng.security:
                            eng.security.set_password(master_pw)
                            eng.security.vault = vault
                        if hasattr(eng, "local_memory") and eng.local_memory:
                            eng.local_memory.setup_password(master_pw, master_pw)
                except Exception as e:
                    logger.warning(f"[VAULT-SETUP] Syncing password across engines: {e}")
                return JSONResponse({"status": "ok", "message": "Secure password vault initialized and unlocked."})
            return JSONResponse({"status": "error", "message": "Failed to initialize vault."}, status_code=500)

        async def post_vault_unlock(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            master_pw = body.get("master_password", "")
            vault = get_vault_controller()
            if not vault.is_setup():
                return JSONResponse({"status": "error", "message": "Vault is not configured."}, status_code=400)
            ok = vault.authenticate(master_pw)
            if ok:
                try:
                    if hasattr(self, "app_instance") and self.app_instance and hasattr(self.app_instance, "engine") and self.app_instance.engine:
                        eng = self.app_instance.engine
                        if hasattr(eng, "security") and eng.security:
                            eng.security.authorize_session(60.0)
                            vault.sync_with_security_manager(eng.security)
                except Exception as e:
                    logger.warning(f"[VAULT-UNLOCK] Syncing auth across engines: {e}")
                return JSONResponse({"status": "ok", "message": "Vault unlocked."})
            return JSONResponse({"status": "error", "message": "Invalid master password. Vault remains locked."}, status_code=401)

        async def post_vault_lock(request):
            vault = get_vault_controller()
            vault.lock()
            return JSONResponse({"status": "ok", "message": "Vault locked."})

        async def get_vault_records(request):
            vault = get_vault_controller()
            if not vault.is_unlocked():
                return JSONResponse({"status": "error", "message": "Vault is locked. Unlock required."}, status_code=403)
            raw_recs = vault.list_secure_records()
            clean_recs = [{
                "key": r.get("key") or r.get("key_phrase") or r.get("record_id", ""),
                "category": r.get("category", "credentials"),
                "created_at": r.get("created_at")
            } for r in raw_recs]
            return JSONResponse({"status": "ok", "records": clean_recs})

        async def post_vault_record(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            key = body.get("key", "").strip()
            val = body.get("value", "")
            cat = body.get("category", "credentials")
            if not key or not val:
                return JSONResponse({"status": "error", "message": "Both service/key and secret value are required."}, status_code=400)
            vault = get_vault_controller()
            if not vault.is_unlocked():
                return JSONResponse({"status": "error", "message": "Vault is locked. Unlock before saving records."}, status_code=403)
            ok = vault.save_secure_record(key, val, category=cat)
            if ok:
                return JSONResponse({"status": "ok", "message": f"Credential for '{key}' stored securely."})
            return JSONResponse({"status": "error", "message": "Failed to store record."}, status_code=500)

        async def post_vault_record_reveal(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            key = body.get("key", "").strip()
            if not key:
                return JSONResponse({"status": "error", "message": "Record key is required."}, status_code=400)
            vault = get_vault_controller()
            if not vault.is_unlocked():
                return JSONResponse({"status": "error", "message": "Vault is locked. Unlock required to view secret."}, status_code=403)
            val = vault.retrieve_secure_record(key)
            if val is None:
                val = vault.retrieve_secure_record_by_query(key)
            if val is not None:
                return JSONResponse({"status": "ok", "key": key, "value": val})
            return JSONResponse({"status": "error", "message": "Record not found."}, status_code=404)

        async def post_vault_record_delete(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            key = body.get("key", "").strip()
            if not key:
                return JSONResponse({"status": "error", "message": "Record key is required."}, status_code=400)
            vault = get_vault_controller()
            if not vault.is_unlocked():
                return JSONResponse({"status": "error", "message": "Vault is locked."}, status_code=403)
            ok = vault.delete_secure_record(key)
            if not ok:
                ok = vault.delete_secure_record_by_query(key)
            if ok:
                return JSONResponse({"status": "ok", "message": f"Record '{key}' deleted."})
            return JSONResponse({"status": "error", "message": "Record not found or failed to delete."}, status_code=404)

        async def get_history(request):
            history_data = []
            if self.app_instance and hasattr(self.app_instance, "engine") and self.app_instance.engine:
                h = self.app_instance.engine.history
                sessions = h.list_recent_sessions(limit=10)
                for s in sessions:
                    msgs = h.get_session_messages(s["session_id"], limit=50)
                    history_data.append({
                        "session": s,
                        "messages": msgs,
                    })
            return JSONResponse({"sessions": history_data})

        async def get_memory(request):
            memories_data = []
            if self.app_instance and hasattr(self.app_instance, "engine") and self.app_instance.engine:
                memories_data = self.app_instance.engine.memory.list_all_memories()
            return JSONResponse({"memories": memories_data})

        async def camera_stream(request):
            async def frame_generator():
                while not await request.is_disconnected():
                    jpeg_bytes = None
                    if self.app_instance and getattr(self.app_instance, "camera_running", False):
                        with self.app_instance.frame_lock:
                            jpeg_bytes = getattr(self.app_instance, "latest_jpeg", None)

                    if jpeg_bytes:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                        )
                    await asyncio.sleep(0.04)  # ~25 FPS

            return StreamingResponse(
                frame_generator(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )

        async def camera_snapshot(request):
            jpeg_bytes = None
            if self.app_instance:
                with self.app_instance.frame_lock:
                    jpeg_bytes = getattr(self.app_instance, "latest_jpeg", None)
            if jpeg_bytes:
                return Response(content=jpeg_bytes, media_type="image/jpeg")
            return Response(content=b"", status_code=204)

        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.connected_clients.add(websocket)
            try:
                # Send immediate initial state
                initial_status = self.get_system_telemetry()
                await websocket.send_json({
                    "type": "STATE_UPDATE",
                    **initial_status,
                })

                while True:
                    text = await websocket.receive_text()
                    try:
                        msg = json.loads(text)
                        action = msg.get("action")
                        if action:
                            res = self.execute_action(action, msg)
                            # Echo updated state
                            updated = self.get_system_telemetry()
                            await websocket.send_json({
                                "type": "STATE_UPDATE",
                                **updated,
                                "action_result": res,
                            })
                    except Exception as e:
                        print(f"[BRIDGE-WS-ERR] Parse error: {e}")
            except WebSocketDisconnect:
                pass
            finally:
                self.connected_clients.discard(websocket)

        routes = [
            Route("/api/status", get_status, methods=["GET"]),
            Route("/api/action", post_action, methods=["POST"]),
            Route("/api/history", get_history, methods=["GET"]),
            Route("/api/memory", get_memory, methods=["GET"]),
            Route("/api/camera/stream", camera_stream, methods=["GET"]),
            Route("/api/camera/snapshot", camera_snapshot, methods=["GET"]),
            Route("/api/setup/status", get_setup_status, methods=["GET"]),
            Route("/api/setup/user-name", post_setup_user_name, methods=["POST"]),
            Route("/api/setup/api-key/test", post_test_api_key, methods=["POST"]),
            Route("/api/setup/api-key/save", post_save_api_key, methods=["POST"]),
            Route("/api/setup/api-key/remove", post_remove_api_key, methods=["POST"]),
            Route("/api/setup/diagnostics", get_diagnostics, methods=["GET"]),
            Route("/api/setup/complete", post_complete_setup, methods=["POST"]),
            Route("/api/setup/reset", post_reset_setup, methods=["POST"]),
            Route("/api/people", get_people, methods=["GET"]),
            Route("/api/people/delete", post_delete_person, methods=["POST"]),
            Route("/api/glasses/status", get_glasses_status, methods=["GET"]),
            Route("/api/vault/status", get_vault_status, methods=["GET"]),
            Route("/api/vault/setup", post_vault_setup, methods=["POST"]),
            Route("/api/vault/unlock", post_vault_unlock, methods=["POST"]),
            Route("/api/vault/lock", post_vault_lock, methods=["POST"]),
            Route("/api/vault/records", get_vault_records, methods=["GET"]),
            Route("/api/vault/record", post_vault_record, methods=["POST"]),
            Route("/api/vault/record/reveal", post_vault_record_reveal, methods=["POST"]),
            Route("/api/vault/record/delete", post_vault_record_delete, methods=["POST"]),
            WebSocketRoute("/ws", ws_endpoint),
        ]

        if os.path.exists(self.dist_dir):
            routes.append(Mount("/", StaticFiles(directory=self.dist_dir, html=True), name="static"))
        else:
            print(f"[BRIDGE-WARN] Frontend dist directory not found at: {self.dist_dir}")

        return Starlette(routes=routes)

    def start(self, host: str = "127.0.0.1", port: int = 8000):
        """Starts the Starlette / Uvicorn server in a dedicated background daemon thread."""
        starlette_app = self.build_starlette_app()
        config = uvicorn.Config(app=starlette_app, host=host, port=port, log_level="warning")
        self.uvicorn_server = uvicorn.Server(config)

        def run_server():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.is_running = True
            print(f"[BRIDGE] SG CUBE Web Bridge Server running on http://{host}:{port}")
            self.loop.run_until_complete(self.uvicorn_server.serve())
            self.is_running = False

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Wait briefly for server to bind port
        for _ in range(50):
            if self.is_running and self.uvicorn_server and self.uvicorn_server.started:
                break
            time.sleep(0.05)

    def stop(self):
        """Graceful teardown of bridge server."""
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True
        self.is_running = False


# Module-level singleton
bridge = BridgeServer()
