"""
Audio Output Manager for SG CUBE.
Centralized Windows Audio Endpoint Routing, Device Tracking, & Dynamic Stream Switching.

Responsibilities:
1. Enumerates Windows audio render devices via Core Audio (IMMDeviceEnumerator / MMDevice API).
2. Detects current Windows default playback endpoint.
3. Receives event-driven device change notifications via IMMNotificationClient:
   - Default device changed (e.g. Speakers -> Bluetooth -> HDMI Projector -> Speakers)
   - Device added / removed (e.g. Bluetooth connect/disconnect, HDMI plug/unplug)
   - Device state changes (Active, Unplugged, Disabled, NotPresent)
4. Provides lightweight background polling fallback to guarantee detection even if COM callbacks delay.
5. Dynamically re-binds PortAudio and SAPI output streams to the active Windows default endpoint.
6. Recovers from stale/disconnected audio streams with bounded single-retry failover.
7. Integrates with AudioArbiter for exclusive, prioritized speaker ownership.
8. Controls volume and mute against the CURRENT active default render endpoint.
9. Provides diagnostic introspection: current device, available devices, audio health.
"""

from __future__ import annotations

import os
import sys
import time
import re
import queue
import ctypes
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any

import sounddevice as sd
import numpy as np

try:
    import comtypes
    from comtypes import COMObject, CLSCTX_ALL
    from pycaw.pycaw import (
        AudioUtilities,
        IMMDeviceEnumerator,
        IMMNotificationClient,
        EDataFlow,
        ERole,
        AudioDeviceState,
        IAudioEndpointVolume,
    )
    PYCAW_AVAILABLE = True
except Exception as _pycaw_err:
    PYCAW_AVAILABLE = False
    AudioUtilities = None
    COMObject = object

from .audio_arbiter import AudioArbiter, get_audio_arbiter, PRIORITY_SPEECH, PRIORITY_SAFETY

logger = logging.getLogger("AudioOutputManager")


class DeviceChangeNotificationClient(COMObject):
    """
    Native Windows Core Audio IMMNotificationClient implementation.
    Receives OS events when audio endpoints are added, removed, default switched, or state toggled.
    """
    _com_interfaces_ = [IMMNotificationClient] if PYCAW_AVAILABLE else []

    def __init__(self, manager: AudioOutputManager):
        super().__init__()
        self.manager = manager

    def OnDefaultDeviceChanged(self, flow: int, role: int, default_device_id: str):
        # flow: 0=eRender, 1=eCapture. role: 0=eConsole, 1=eMultimedia, 2=eCommunications
        if flow == 0:  # eRender (Output playback)
            logger.info(f"[AUDIO-EVENT] Windows default playback endpoint changed: {default_device_id} (role={role})")
            self.manager.trigger_device_changed(reason=f"Default device changed (role={role})")

    def OnDeviceAdded(self, device_id: str):
        logger.info(f"[AUDIO-EVENT] Audio endpoint added: {device_id}")
        self.manager.trigger_device_changed(reason="Device added")

    def OnDeviceRemoved(self, device_id: str):
        logger.info(f"[AUDIO-EVENT] Audio endpoint removed: {device_id}")
        self.manager.trigger_device_changed(reason="Device removed")

    def OnDeviceStateChanged(self, device_id: str, new_state: int):
        logger.debug(f"[AUDIO-EVENT] Endpoint state changed: {device_id} -> state={new_state}")
        self.manager.trigger_device_changed(reason=f"Device state changed ({new_state})")

    def OnPropertyValueChanged(self, device_id: str, key):
        pass


class AudioOutputManager:
    """
    Central Authoritative Audio Output & Routing Manager for SG CUBE.
    Dynamically follows Windows default playback endpoint across Laptop Speakers,
    Bluetooth speakers/headsets, HDMI Projectors, and USB Audio devices.
    """
    _instance: Optional[AudioOutputManager] = None
    _singleton_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AudioOutputManager:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = AudioOutputManager()
            return cls._instance

    def __init__(self):
        self._lock = threading.RLock()
        self.arbiter = get_audio_arbiter()

        # Current Endpoint Telemetry
        self.current_device_id: str = ""
        self.current_device_name: str = "Default Audio Output"
        self.current_device_type: str = "LAPTOP_SPEAKER"
        self.current_device_state: str = "Active"
        self.current_pa_index: Optional[int] = None

        # Lifecycle & Stream Control
        self._active_stream: Optional[sd.RawOutputStream] = None
        self._stream_samplerate: int = 24000
        self._stream_channels: int = 1
        self._needs_rebind: bool = True
        self._running: bool = True
        self._com_initialized: bool = False

        # Diagnostic Counters
        self.total_switches_detected: int = 0
        self.total_recoveries_executed: int = 0
        self.last_switch_time: float = 0.0
        self.last_switch_reason: str = "Startup"

        # COM & Notification Client
        self._notification_client = None
        self._enumerator = None

        # Observers
        self._change_listeners: List[Any] = []

        # Initialize COM in current thread
        self._init_core_audio()

        # Start background watchdog for state synchronization
        self._watchdog_thread = threading.Thread(target=self._background_watchdog_loop, daemon=True)
        self._watchdog_thread.start()

        # Dedicated Non-Blocking SAPI TTS Pipeline (SG CUBE Fix 4)
        self._tts_queue: queue.Queue = queue.Queue()
        self._tts_stop_event: threading.Event = threading.Event()
        self._active_sapi_voice = None
        self._tts_thread = threading.Thread(target=self._tts_worker_loop, daemon=True, name="AudioOutputManager-TTS")
        self._tts_thread.start()

        # Initial Endpoint Resolution
        self.rebind(force=True, reason="Startup Initialization")
        logger.info(f"[AUDIO] AudioOutputManager initialized. Active endpoint: '{self.current_device_name}' ({self.current_device_type})")

    def _init_core_audio(self):
        """ Initializes COM and registers IMMNotificationClient for hardware events """
        if not PYCAW_AVAILABLE:
            logger.warning("[AUDIO] pycaw / Core Audio unavailable, using sounddevice fallback.")
            return

        try:
            comtypes.CoInitialize()
            self._com_initialized = True
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
            self._notification_client = DeviceChangeNotificationClient(self)
            self._enumerator.RegisterEndpointNotificationCallback(self._notification_client)
            logger.info("[AUDIO] Successfully registered IMMNotificationClient callback for OS audio events.")
        except Exception as e:
            logger.warning(f"[AUDIO] Warning registering Core Audio notification client: {e}")

    # =========================================================================
    # ENDPOINT CLASSIFICATION & DISCOVERY
    # =========================================================================

    @staticmethod
    def classify_device_type(name: str) -> str:
        """ Semantically identifies the audio hardware category from friendly name """
        n = (name or "").lower()
        if any(w in n for w in ["bluetooth", "hands-free", "bth", "headset", "airpods", "galaxy", "buds", "wireless", "nirvana", "earbuds"]):
            return "BLUETOOTH"
        if any(w in n for w in ["projector", "epson", "hdmi", "display audio", "benq", "optoma", "viewsonic", "tv", "monitor", "waf"]):
            return "HDMI_PROJECTOR"
        if any(w in n for w in ["usb", "dac", "scarlett", "focusrite", "external", "hyperx", "plantronics"]):
            return "USB_AUDIO"
        if any(w in n for w in ["headphone", "earphone", "jack"]):
            return "HEADPHONES"
        if any(w in n for w in ["speaker", "realtek", "internal", "built-in", "integrated"]):
            return "LAPTOP_SPEAKER"
        return "GENERIC_RENDER"

    def enumerate_render_devices(self) -> List[Dict[str, Any]]:
        """ Enumerates all Windows Core Audio render endpoints with full state introspection """
        devices = []
        if not PYCAW_AVAILABLE or not self._enumerator:
            # Fallback to sounddevice enumeration
            try:
                for i, d in enumerate(sd.query_devices()):
                    if d.get("max_output_channels", 0) > 0:
                        name = d.get("name", "Unknown")
                        devices.append({
                            "name": name,
                            "id": f"PA_{i}",
                            "type": self.classify_device_type(name),
                            "state": "Active",
                            "is_default": (i == sd.default.device[1]),
                            "pa_index": i
                        })
            except Exception:
                pass
            return devices

        try:
            # 0xF = DEVICE_STATEMASK_ALL (Active, Disabled, NotPresent, Unplugged)
            collection = self._enumerator.EnumAudioEndpoints(EDataFlow.eRender.value, 0xF)
            count = collection.GetCount()
            default_id = ""
            try:
                def_dev = self._enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
                default_id = def_dev.GetId()
            except Exception:
                pass

            for i in range(count):
                dev = collection.Item(i)
                wrapped = AudioUtilities.CreateDevice(dev)
                d_id = wrapped.id
                d_name = wrapped.FriendlyName
                raw_state = str(wrapped.state)
                # Parse AudioDeviceState enum
                clean_state = "Active"
                if "Unplugged" in raw_state:
                    clean_state = "Unplugged"
                elif "NotPresent" in raw_state:
                    clean_state = "NotPresent"
                elif "Disabled" in raw_state:
                    clean_state = "Disabled"

                dev_type = self.classify_device_type(d_name)
                is_def = (d_id == default_id)
                devices.append({
                    "name": d_name,
                    "id": d_id,
                    "type": dev_type,
                    "device_type": dev_type,
                    "state": clean_state,
                    "is_default": is_def,
                })
        except Exception as e:
            logger.error(f"[AUDIO] Error enumerating render endpoints: {e}")

        return devices

    def _resolve_default_endpoint_info(self) -> Tuple[str, str, str, str]:
        """ Queries Windows Core Audio for current default render endpoint (id, name, type, state) """
        if PYCAW_AVAILABLE and self._enumerator:
            try:
                def_dev = self._enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
                wrapped = AudioUtilities.CreateDevice(def_dev)
                d_id = wrapped.id
                d_name = wrapped.FriendlyName
                d_type = self.classify_device_type(d_name)
                return d_id, d_name, d_type, "Active"
            except Exception as e:
                logger.debug(f"[AUDIO] Core Audio GetDefaultAudioEndpoint error: {e}")

        # Fallback to sounddevice default
        try:
            pa_def = sd.default.device[1]
            if pa_def is not None and pa_def >= 0:
                dev = sd.query_devices(pa_def)
                name = dev.get("name", "Speaker (Realtek(R) Audio)")
                return f"PA_{pa_def}", name, self.classify_device_type(name), "Active"
        except Exception:
            pass

        return "DEFAULT", "Default Audio Endpoint", "LAPTOP_SPEAKER", "Active"

    def _map_to_portaudio_index(self, friendly_name: str) -> Optional[int]:
        """
        Finds the matching PortAudio output device index for a Windows endpoint name.
        Prefers exact friendly name match on WASAPI or MME host APIs.
        """
        try:
            pa_devs = sd.query_devices()
            clean_target = friendly_name.lower().strip()
            # Extract key tokens (e.g. 'realtek', 'nirvana', 'epson', 'headphone')
            keywords = re.findall(r'[a-zA-Z0-9]+', clean_target)
            significant = [k for k in keywords if len(k) > 2 and k not in ["audio", "output", "driver", "for", "with", "device"]]

            # 1. Exact Name Match on WASAPI (hostapi 3)
            for i, d in enumerate(pa_devs):
                if d.get("max_output_channels", 0) > 0 and d.get("hostapi") == 3:
                    if clean_target in d.get("name", "").lower():
                        return i

            # 2. Exact Name Match on MME (hostapi 0) or DirectSound (hostapi 1)
            for i, d in enumerate(pa_devs):
                if d.get("max_output_channels", 0) > 0:
                    d_name = d.get("name", "").lower()
                    if clean_target == d_name or clean_target in d_name:
                        return i

            # 3. Token-based matching on active output devices
            best_idx = None
            best_score = 0
            for i, d in enumerate(pa_devs):
                if d.get("max_output_channels", 0) > 0:
                    d_name = d.get("name", "").lower()
                    score = sum(1 for tok in significant if tok in d_name)
                    if score > best_score:
                        best_score = score
                        best_idx = i

            if best_idx is not None and best_score >= 1:
                return best_idx

        except Exception as e:
            logger.debug(f"[AUDIO] PortAudio mapping lookup error: {e}")

        # Fallback to PortAudio's default output index
        try:
            return sd.default.device[1]
        except Exception:
            return None

    # =========================================================================
    # DYNAMIC STREAM REBINDING & RECOVERY
    # =========================================================================

    def trigger_device_changed(self, reason: str = "Hardware event"):
        """ Called asynchronously by IMMNotificationClient or watchdog on device change """
        with self._lock:
            self._needs_rebind = True
            self.last_switch_reason = reason
            self.last_switch_time = time.time()
            self.total_switches_detected += 1
            logger.info(f"[AUDIO] Device change triggered: {reason}. Scheduling dynamic rebind...")

        # Notify registered observers (e.g. GUI status labels)
        for listener in list(self._change_listeners):
            try:
                listener(self.get_current_output_info())
            except Exception:
                pass

    def rebind(self, force: bool = False, reason: str = "Default check") -> bool:
        """
        Rebinds audio output to the CURRENT Windows default playback endpoint.
        Safely tears down stale PortAudio stream and establishes fresh binding.
        """
        with self._lock:
            new_id, new_name, new_type, new_state = self._resolve_default_endpoint_info()

            if not force and not self._needs_rebind and new_id == self.current_device_id and self._active_stream is not None:
                return False  # Already synchronized

            old_name = self.current_device_name
            self.current_device_id = new_id
            self.current_device_name = new_name
            self.current_device_type = new_type
            self.current_device_state = new_state
            self._needs_rebind = False

            logger.info(f"[AUDIO] Default endpoint changed: '{old_name}' -> '{new_name}' ({new_type}) [{reason}]")

            # 1. Close active PortAudio stream safely
            self._close_stream()

            # 2. Refresh PortAudio device table to see newly plugged Bluetooth/HDMI devices
            try:
                sd._terminate()
                sd._initialize()
            except Exception as pa_init_err:
                logger.debug(f"[AUDIO] PortAudio reinit error: {pa_init_err}")

            # 3. Resolve matching PortAudio device index
            self.current_pa_index = self._map_to_portaudio_index(new_name)
            logger.info(f"[AUDIO] PortAudio mapped device index: {self.current_pa_index}")

            # 4. Re-open stream on the newly resolved device
            self._open_stream()

            # 5. Rebind Windows SAPI SpVoice if needed
            self._rebind_sapi_tts()

            self.total_recoveries_executed += 1
            return True

    def _open_stream(self, samplerate: int = 24000) -> bool:
        """ Establishes fresh PortAudio output stream on currently mapped device """
        with self._lock:
            self._close_stream()
            self._stream_samplerate = samplerate

            try:
                self._active_stream = sd.RawOutputStream(
                    samplerate=samplerate,
                    channels=1,
                    dtype='int16',
                    device=self.current_pa_index
                )
                self._active_stream.start()
                # Warmup buffer to eliminate initial popping / latency
                self._active_stream.write(bytes(4800))
                logger.info(f"[AUDIO] Output stream opened successfully on '{self.current_device_name}' (device_idx={self.current_pa_index}, rate={samplerate}Hz)")
                return True
            except Exception as e:
                logger.warning(f"[AUDIO] Failed to open stream on device index {self.current_pa_index} ({e}). Retrying with default device...")
                try:
                    # Fallback to PortAudio default
                    self._active_stream = sd.RawOutputStream(
                        samplerate=samplerate,
                        channels=1,
                        dtype='int16',
                        device=None
                    )
                    self._active_stream.start()
                    logger.info("[AUDIO] Output stream opened on PortAudio default fallback.")
                    return True
                except Exception as fallback_err:
                    logger.error(f"[AUDIO] Critical: Output stream creation failed completely: {fallback_err}")
                    self._active_stream = None
                    return False

    def _close_stream(self):
        """ Closes existing stream safely without throwing exceptions """
        with self._lock:
            if self._active_stream is not None:
                try:
                    self._active_stream.stop()
                    self._active_stream.close()
                except Exception:
                    pass
                self._active_stream = None

    def _rebind_sapi_tts(self):
        """ Ensures SAPI.SpVoice output token follows the new Windows default playback device """
        if os.name != 'nt':
            return
        try:
            import win32com.client
            v = win32com.client.Dispatch("SAPI.SpVoice")
            # Setting AudioOutput to None resets SAPI to the current Windows default playback device
            v.AudioOutput = None
            logger.debug("[AUDIO] SAPI SpVoice audio output route rebound to current default.")
        except Exception as e:
            logger.debug(f"[AUDIO] SAPI rebind notice: {e}")

    # =========================================================================
    # AUDIO PLAYBACK (WITH BOUNDED SINGLE-RETRY RECOVERY)
    # =========================================================================

    def write_pcm(self, pcm_bytes: bytes, samplerate: int = 24000) -> bool:
        """
        Thread-safe, non-lossy 16-bit PCM playback with dynamic device switching & recovery.
        If the current endpoint was disconnected or changed, automatically recovers to the
        new default endpoint and retries the write without dropping audio.
        """
        if not pcm_bytes or len(pcm_bytes) == 0:
            return True

        with self._lock:
            # Check if device changed since last write
            if self._needs_rebind or self._active_stream is None:
                self.rebind(force=True, reason="Pre-write verification")

            if self._active_stream is None:
                self._open_stream(samplerate)

            if self._active_stream is None:
                logger.error("[AUDIO] Cannot write audio: no output stream available.")
                return False

            # Primary write attempt
            try:
                self._active_stream.write(pcm_bytes)
                return True
            except Exception as write_err:
                logger.warning(f"[AUDIO] Stream write error on '{self.current_device_name}' ({write_err}). Initiating dynamic recovery...")

            # Recovery: Invalidate current device, re-enumerate, rebind to active default, retry once
            try:
                self._close_stream()
                self.rebind(force=True, reason="Write error recovery")
                if self._active_stream is not None:
                    self._active_stream.write(pcm_bytes)
                    logger.info(f"[AUDIO] Playback successfully recovered and played through '{self.current_device_name}'.")
                    return True
            except Exception as retry_err:
                logger.error(f"[AUDIO] Recovery retry failed: {retry_err}")
                return False

        return False

    def _tts_worker_loop(self):
        """
        Dedicated Single-Threaded Apartment (STA) worker for Windows SAPI TTS.
        Ensures SAPI COM object is instantiated and pumped on a single persistent thread,
        eliminating COM cross-apartment deadlocks, blocking on asyncio loop, and multiple TTS instances.
        """
        if os.name != 'nt':
            return

        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
        except Exception as init_err:
            logger.warning(f"[AUDIO] Local TTS COM initialization warning: {init_err}")
            return

        voice = None
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.AudioOutput = None
            with self._lock:
                self._active_sapi_voice = voice
        except Exception as v_err:
            logger.warning(f"[AUDIO] Failed to dispatch SAPI.SpVoice in TTS worker: {v_err}")
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
            return

        logger.info("[AUDIO] Dedicated SAPI TTS worker thread active.")

        while self._running:
            try:
                item = self._tts_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            if item is None:
                break

            text, priority, done_evt = item
            self._tts_stop_event.clear()

            try:
                with self.arbiter.acquire(priority=priority, source_tag="LOCAL_TTS"):
                    self.rebind(reason="Pre-TTS verification")
                    try:
                        voice.AudioOutput = None  # Ensure dynamic route to current default endpoint
                    except Exception:
                        pass

                    # Asynchronous speak flag = 1
                    voice.Speak(text.strip(), 1)

                    # Poll completion in 25ms increments to honor stop/cancel without delay
                    while not voice.WaitUntilDone(25):
                        if self._tts_stop_event.is_set():
                            try:
                                voice.Speak("", 2)  # SVSFPurgeBeforeSpeak
                                logger.info("[AUDIO] Local speech successfully purged by stop event.")
                            except Exception:
                                pass
                            break
            except Exception as e:
                logger.error(f"[AUDIO] Error during local TTS playback: {e}")
            finally:
                if done_evt:
                    done_evt.set()
                self._tts_queue.task_done()

        try:
            with self._lock:
                self._active_sapi_voice = None
            pythoncom.CoUninitialize()
        except Exception:
            pass

    def speak_text_local(self, text: str, priority: int = PRIORITY_SPEECH, wait: bool = False) -> bool:
        """
        Speaks local text through dedicated SAPI worker with AudioArbiter exclusivity and endpoint verification.
        Non-blocking by default (wait=False), returning in < 1ms to prevent freezing asyncio event loop.
        """
        if not text or not text.strip():
            return False

        # Clear any stale speech in queue before queueing fresh response
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
            except Exception:
                break

        self._tts_stop_event.clear()

        done_evt = threading.Event() if wait else None
        self._tts_queue.put((text.strip(), priority, done_evt))

        if wait:
            return done_evt.wait(timeout=15.0)
        return True

    def stop_speech(self) -> bool:
        """
        Immediately interrupts active local speech and clears pending local TTS queue.
        Thread-safe and callable from any thread (e.g. STOP/CANCEL command or barge-in).
        """
        self._tts_stop_event.set()
        cleared = 0
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
                cleared += 1
            except Exception:
                break
        if cleared > 0:
            logger.info(f"[AUDIO] Purged {cleared} pending TTS queue items.")
        return True

    def is_speaking(self) -> bool:
        """ Returns True if local TTS playback is actively speaking """
        return self.arbiter.is_speaking()

    def is_busy(self) -> bool:
        """ Alias for is_speaking(): Returns True if local TTS or audio output is active """
        return self.is_speaking()

    # =========================================================================
    # VOLUME & MUTE CONTROL (BOUND TO ACTIVE DEFAULT ENDPOINT)
    # =========================================================================

    def _get_current_endpoint_volume(self):
        """ Acquires IAudioEndpointVolume interface for the CURRENT default endpoint """
        if not PYCAW_AVAILABLE or not self._enumerator:
            return None
        try:
            def_dev = self._enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            wrapped = AudioUtilities.CreateDevice(def_dev)
            return wrapped.EndpointVolume
        except Exception as e:
            logger.error(f"[AUDIO] Failed to acquire volume interface for active endpoint: {e}")
            return None

    def get_volume(self) -> int:
        """ Returns current master volume (0..100) of the CURRENT active playback device """
        ep = self._get_current_endpoint_volume()
        if ep:
            try:
                scalar = ep.GetMasterVolumeLevelScalar()
                return int(round(scalar * 100))
            except Exception as e:
                logger.error(f"[AUDIO] Error reading volume: {e}")
        return 50

    def set_volume(self, target_percent: int) -> Tuple[bool, int, str]:
        """ Sets master volume (0..100) on the CURRENT active playback device """
        try:
            target_percent = int(round(float(target_percent)))
        except (ValueError, TypeError):
            return False, self.get_volume(), "Invalid volume level."
        target_percent = max(0, min(100, target_percent))

        ep = self._get_current_endpoint_volume()
        if not ep:
            return False, 0, f"Cannot adjust volume: '{self.current_device_name}' unavailable."

        try:
            scalar = target_percent / 100.0
            ep.SetMasterVolumeLevelScalar(scalar, None)
            time.sleep(0.04)
            verified = int(round(ep.GetMasterVolumeLevelScalar() * 100))
            return True, verified, f"{self.current_device_name} volume set to {verified}%."
        except Exception as e:
            return False, self.get_volume(), f"Failed to set volume on {self.current_device_name}: {e}"

    def is_muted(self) -> bool:
        """ Returns True if current default endpoint is muted """
        ep = self._get_current_endpoint_volume()
        if ep:
            try:
                return bool(ep.GetMute())
            except Exception:
                pass
        return False

    def set_mute(self, mute: bool) -> Tuple[bool, str]:
        """ Mutes or unmutes the CURRENT active playback device """
        ep = self._get_current_endpoint_volume()
        if not ep:
            return False, "Audio device unavailable."
        try:
            ep.SetMute(1 if mute else 0, None)
            status_txt = "muted" if mute else "unmuted"
            return True, f"{self.current_device_name} is now {status_txt}."
        except Exception as e:
            return False, f"Failed to adjust mute state: {e}"

    # =========================================================================
    # DIAGNOSTICS & STATUS INTROSPECTION
    # =========================================================================

    def get_current_output_info(self) -> Dict[str, Any]:
        """ Returns real-time dictionary describing the active output endpoint """
        with self._lock:
            return {
                "name": self.current_device_name,
                "type": self.current_device_type,
                "device_type": self.current_device_type,
                "id": self.current_device_id,
                "state": self.current_device_state,
                "volume": self.get_volume(),
                "muted": self.is_muted(),
                "stream_active": (self._active_stream is not None),
                "pa_index": self.current_pa_index,
                "switches_detected": self.total_switches_detected,
                "recoveries_executed": self.total_recoveries_executed,
            }

    def run_audio_diagnostics(self) -> Dict[str, Any]:
        """ Comprehensive health audit of the audio output subsystem """
        with self._lock:
            info = self.get_current_output_info()
            available = self.enumerate_render_devices()

            # Verify PortAudio health
            pa_healthy = False
            try:
                cur_dev = sd.query_devices(self.current_pa_index) if self.current_pa_index is not None else None
                pa_healthy = (cur_dev is not None and cur_dev.get("max_output_channels", 0) > 0)
            except Exception:
                pa_healthy = False

            # Verify SAPI TTS health
            tts_healthy = False
            try:
                import win32com.client
                v = win32com.client.Dispatch("SAPI.SpVoice")
                tts_healthy = (v is not None)
            except Exception:
                tts_healthy = False

            overall_healthy = (info["state"] == "Active" and pa_healthy)

            return {
                "status": "HEALTHY" if overall_healthy else "DEGRADED",
                "active_device": info["name"],
                "active_type": info["type"],
                "volume_percent": info["volume"],
                "is_muted": info["muted"],
                "stream_ready": info["stream_active"],
                "portaudio_healthy": pa_healthy,
                "tts_healthy": tts_healthy,
                "available_devices_count": len(available),
                "available_devices": [f"{d['name']} ({d['type']}, {d['state']})" for d in available],
                "switches_detected": self.total_switches_detected,
                "recoveries_executed": self.total_recoveries_executed,
            }

    def register_change_listener(self, listener):
        """ Adds a callback invoked whenever the audio output changes """
        if listener not in self._change_listeners:
            self._change_listeners.append(listener)

    # =========================================================================
    # BACKGROUND WATCHDOG LOOP
    # =========================================================================

    def _background_watchdog_loop(self):
        """
        Lightweight background thread (runs every 1.5s) to guarantee state synchronization
        even if an OS event callback was delayed by Windows thread apartment scheduling.
        """
        if PYCAW_AVAILABLE:
            try:
                comtypes.CoInitialize()
            except Exception:
                pass

        while self._running:
            time.sleep(1.5)
            if not self._running:
                break
            try:
                new_id, _, _, _ = self._resolve_default_endpoint_info()
                if new_id and new_id != self.current_device_id:
                    logger.info(f"[AUDIO-WATCHDOG] Detected unsynchronized default endpoint change. Rebinding...")
                    self.rebind(force=True, reason="Watchdog discrepancy detected")
            except Exception:
                pass

    def close(self):
        """ Clean teardown on application shutdown """
        self._running = False
        with self._lock:
            self._close_stream()
            if self._enumerator and self._notification_client:
                try:
                    self._enumerator.UnregisterEndpointNotificationCallback(self._notification_client)
                except Exception:
                    pass


def get_audio_output_manager() -> AudioOutputManager:
    return AudioOutputManager.get_instance()
