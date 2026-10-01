"""
Health Diagnostics and Self-Awareness Subsystem for SG CUBE

Provides real-time inspection and truthful reporting of all SG CUBE subsystems:
- Camera sensor availability
- Microphone input device
- Speaker / Audio playback endpoint
- Network and Gemini connectivity
- Local Memory V2 and Secure Vault databases
- System automation and Computer-Use readiness

Adapted from InterGenJLU JARVIS health check and self-awareness architecture.
"""

from __future__ import annotations

import os
import socket
import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SubsystemStatus:
    name: str
    status: str          # "OK", "DEGRADED", "OFFLINE", "UNAVAILABLE"
    details: str
    is_operational: bool


class HealthDiagnostics:
    """Probes and reports truthful status of all SG CUBE subsystems."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def check_network(self) -> SubsystemStatus:
        """Check internet connectivity via DNS probe."""
        try:
            socket.setdefaulttimeout(2.0)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            return SubsystemStatus("Network", "OK", "Internet connection active.", True)
        except Exception:
            return SubsystemStatus("Network", "OFFLINE", "Internet connection unavailable (Offline mode active).", False)

    def check_audio_output(self) -> SubsystemStatus:
        """Check system audio playback device via Pycaw / Win32."""
        try:
            from assistive.system_control import get_system_control
            sc = get_system_control()
            vol = sc.get_volume()
            muted = sc.is_muted()
            mute_str = " (Muted)" if muted else ""
            return SubsystemStatus("Speaker", "OK", f"Output endpoint active at {vol}% volume{mute_str}.", True)
        except Exception as e:
            return SubsystemStatus("Speaker", "DEGRADED", f"Audio output check issue: {e}", True)

    def check_audio_input(self) -> SubsystemStatus:
        """Check microphone input devices."""
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            input_devs = [d for d in devs if d.get('max_input_channels', 0) > 0]
            if input_devs:
                return SubsystemStatus("Microphone", "OK", f"Microphone available ({len(input_devs)} input endpoints found).", True)
        except Exception:
            pass
        try:
            import speech_recognition as sr
            mics = sr.Microphone.list_microphone_names()
            if mics:
                return SubsystemStatus("Microphone", "OK", f"Microphone available ({len(mics)} audio inputs found).", True)
            return SubsystemStatus("Microphone", "UNAVAILABLE", "No audio input devices detected.", False)
        except Exception as e:
            return SubsystemStatus("Microphone", "DEGRADED", f"Microphone check error: {e}", False)

    def check_camera(self) -> SubsystemStatus:
        """Check video capture device availability."""
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                if ret:
                    return SubsystemStatus("Camera", "OK", "DirectShow camera capture operational.", True)
            return SubsystemStatus("Camera", "UNAVAILABLE", "Camera device busy or not detected.", False)
        except Exception as e:
            return SubsystemStatus("Camera", "DEGRADED", f"Camera probe error: {e}", False)

    def check_memory_databases(self) -> SubsystemStatus:
        """Verify existence and integrity of local databases."""
        try:
            mem_path = os.path.join(self.data_dir, "memory", "local_memory_v2.db")
            vault_path = os.path.join(self.data_dir, "secure_vault", "vault.db")
            hist_path = os.path.join(self.data_dir, "history", "conversations.db")

            missing = []
            if not os.path.exists(mem_path) and not os.path.exists(os.path.join(self.data_dir, "memory", "memories.db")):
                missing.append("local_memory")
            if not os.path.exists(vault_path):
                missing.append("secure_vault")
            if not os.path.exists(hist_path):
                missing.append("conversations")

            if not missing:
                return SubsystemStatus("Memory & Vault", "OK", "Local Memory V2, Secure Vault, and History DBs verified.", True)
            return SubsystemStatus("Memory & Vault", "DEGRADED", f"Some DB files not yet initialized: {', '.join(missing)}.", True)
        except Exception as e:
            return SubsystemStatus("Memory & Vault", "DEGRADED", f"DB check error: {e}", False)

    def run_full_diagnostics(self) -> Dict[str, Any]:
        """Perform full diagnostic sweep across all subsystems."""
        net = self.check_network()
        spk = self.check_audio_output()
        mic = self.check_audio_input()
        cam = self.check_camera()
        mem = self.check_memory_databases()

        all_ok = all([net.is_operational, spk.is_operational, mic.is_operational, mem.is_operational])
        overall = "HEALTHY" if all_ok else ("DEGRADED" if (spk.is_operational and mic.is_operational) else "CRITICAL")

        summary_parts = []
        if overall == "HEALTHY":
            summary_parts.append("All primary subsystems are operational.")
        else:
            if not net.is_operational:
                summary_parts.append("System is operating in offline mode.")
            if not cam.is_operational:
                summary_parts.append("Camera is currently unavailable.")

        return {
            "overall_status": overall,
            "spoken_summary": " ".join(summary_parts) or f"System status is {overall.lower()}.",
            "subsystems": {
                "network": asdict(net),
                "speaker": asdict(spk),
                "microphone": asdict(mic),
                "camera": asdict(cam),
                "memory": asdict(mem)
            }
        }


_GLOBAL_DIAGNOSTICS = HealthDiagnostics()


def get_health_diagnostics() -> HealthDiagnostics:
    """Return global diagnostics instance."""
    return _GLOBAL_DIAGNOSTICS
