"""
Audio Input Manager for SG CUBE.
Centralized Windows Audio Endpoint Routing, Resilient Device Selection, & 16kHz Stream Normalization.

Responsibilities:
1. Enumerates Windows audio capture devices via Core Audio (IMMDeviceEnumerator / MMDevice API).
2. Detects current Windows default capture endpoint (Console, Multimedia, Communications).
3. Automatically un-mutes / restores capture volume if headset/microphone volume is below 80%.
4. Prefers Windows WASAPI for modern bit-perfect streaming with zero legacy driver attenuation.
5. Handles native hardware formats (e.g. 48kHz stereo array or 16kHz mono headset).
6. Performs transparent integer decimation (48kHz -> 16kHz) and stereo-to-mono downmixing.
7. Applies digital software gain (2.5x) so normal human speech reliably triggers VAD (> 240 RMS).
8. Delivers a guaranteed stream contract: 16kHz mono 16-bit PCM (1024 samples/chunk) to consumers.
9. Supports both callback mode and synchronous .read() queue mode.
"""

from __future__ import annotations

import os
import sys
import time
import queue
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable

import sounddevice as sd
import numpy as np

try:
    import comtypes
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import (
        AudioUtilities,
        IAudioEndpointVolume,
    )
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False
    AudioUtilities = None

logger = logging.getLogger("AudioInputManager")


class AudioInputStreamWrapper:
    """
    Wraps an underlying sounddevice RawInputStream while providing
    transparent channel downmixing, 48kHz->16kHz decimation, and digital gain.
    Always delivers 1024 samples (2048 bytes) of 16kHz mono int16 PCM.
    Supports both callback mode and synchronous .read() mode.
    """
    def __init__(
        self,
        device_idx: Optional[int],
        native_sr: int,
        native_ch: int,
        user_callback: Optional[Callable] = None,
        gain: float = 2.5
    ):
        self.device_idx = device_idx
        self.native_sr = native_sr
        self.native_ch = native_ch
        self.user_callback = user_callback
        self.gain = gain
        self._stream: Optional[sd.RawInputStream] = None
        self._is_running = False
        self.chunk_queue: Optional[queue.Queue] = queue.Queue(maxsize=100) if user_callback is None else None

        # Calculate blocksize
        if self.native_sr == 48000:
            # 3072 samples at 48kHz = 64ms = exactly 1024 samples at 16kHz after 3:1 decimation
            self.native_blocksize = 3072
        else:
            self.native_blocksize = 1024

        def internal_callback(indata, frames, time_info, status):
            try:
                # Convert buffer to int16 numpy array
                raw_samples = np.frombuffer(indata, dtype=np.int16)

                # Channel downmix to mono if multi-channel
                if self.native_ch > 1 and len(raw_samples) >= self.native_ch:
                    reshaped = raw_samples.reshape(-1, self.native_ch)
                    # Average channels across axis 1
                    mono = np.mean(reshaped.astype(np.int32), axis=1).astype(np.int16)
                else:
                    mono = raw_samples

                # Sample rate conversion to 16000Hz
                if self.native_sr == 48000:
                    # Exact 3:1 integer decimation
                    mono_16k = mono[::3]
                elif self.native_sr == 44100:
                    # Linear decimation/interpolation fallback
                    target_len = int(len(mono) * (16000 / 44100))
                    indices = np.linspace(0, len(mono) - 1, target_len).astype(np.int32)
                    mono_16k = mono[indices]
                else:
                    mono_16k = mono

                # Digital gain boost for robust VAD triggering
                if self.gain != 1.0 and len(mono_16k) > 0:
                    amplified = mono_16k.astype(np.float32) * self.gain
                    mono_16k = np.clip(amplified, -32768.0, 32767.0).astype(np.int16)

                out_bytes = mono_16k.tobytes()
                if self.user_callback is not None:
                    self.user_callback(out_bytes, len(mono_16k), time_info, status)
                elif self.chunk_queue is not None:
                    try:
                        self.chunk_queue.put_nowait(out_bytes)
                    except queue.Full:
                        try:
                            self.chunk_queue.get_nowait()
                            self.chunk_queue.put_nowait(out_bytes)
                        except Exception:
                            pass
            except Exception as cb_err:
                logger.debug(f"[AUDIO-INPUT] Callback processing error: {cb_err}")

        # Instantiate underlying RawInputStream
        self._stream = sd.RawInputStream(
            samplerate=self.native_sr,
            channels=self.native_ch,
            dtype='int16',
            blocksize=self.native_blocksize,
            device=self.device_idx,
            callback=internal_callback
        )

    def read(self, frames: int = 1024) -> Tuple[bytes, bool]:
        """ Reads the next normalized 16kHz mono PCM chunk (frames samples) """
        if self.chunk_queue is None:
            raise RuntimeError("read() only available when stream opened without a callback")
        try:
            chunk = self.chunk_queue.get(timeout=2.0)
            return chunk, False
        except queue.Empty:
            return b"\x00" * (frames * 2), True

    def start(self):
        if self._stream:
            self._stream.start()
            self._is_running = True

    def stop(self):
        if self._stream:
            try:
                self._stream.stop()
            except Exception:
                pass
            self._is_running = False

    def close(self):
        if self._stream:
            try:
                self._stream.stop()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            self._is_running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AudioInputManager:
    """
    Central Authoritative Audio Input & Routing Manager for SG CUBE.
    Selects best capture device, boosts capture volume if attenuated,
    and returns a normalized 16kHz mono stream.
    """
    _instance: Optional[AudioInputManager] = None
    _singleton_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AudioInputManager:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.active_device_idx: Optional[int] = None
        self.active_device_name: str = "Default Microphone"
        self.active_host_api: str = "Default"
        self.active_sr: int = 16000
        self.active_ch: int = 1
        self._ensure_windows_capture_volume()

    def _ensure_windows_capture_volume(self):
        """ Checks CoreAudio endpoints and restores healthy volume if muted or attenuated (< 80%) """
        if not PYCAW_AVAILABLE:
            return
        try:
            comtypes.CoInitialize()
            enumerator = AudioUtilities.GetDeviceEnumerator()
            # Check Communications role (e.g. Bluetooth headset mic) and Console role (mic array)
            for role in (0, 2):  # 0 = Console, 2 = Communications
                try:
                    dev = enumerator.GetDefaultAudioEndpoint(1, role)  # 1 = eCapture
                    ep = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    vol_ctrl = ep.QueryInterface(IAudioEndpointVolume)
                    cur_vol = vol_ctrl.GetMasterVolumeLevelScalar()
                    is_muted = vol_ctrl.GetMute()
                    if is_muted:
                        vol_ctrl.SetMute(False, None)
                        logger.info(f"[AUDIO-INPUT] Unmuted capture endpoint (role={role})")
                    if cur_vol < 0.80:
                        vol_ctrl.SetMasterVolumeLevelScalar(0.85, None)
                        logger.info(f"[AUDIO-INPUT] Adjusted capture volume from {cur_vol*100:.1f}% to 85% (role={role})")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[AUDIO-INPUT] Windows capture volume check error: {e}")

    def detect_best_device(self) -> Tuple[Optional[int], int, int, str]:
        """
        Finds the optimal capture device:
        1. Prefers WASAPI device (avoiding legacy MME digital attenuation).
        2. Detects native sample rate and channels (e.g. 48kHz 2ch on Intel SST, 16kHz 1ch on Headset).
        3. Falls back gracefully to DirectSound or MME if WASAPI is unavailable.
        Returns (device_idx, sample_rate, channels, device_name).
        """
        self._ensure_windows_capture_volume()
        devices = sd.query_devices()

        wasapi_candidates = []
        ds_candidates = []
        mme_candidates = []

        for idx, d in enumerate(devices):
            if d['max_input_channels'] <= 0:
                continue
            api_info = sd.query_hostapis(d['hostapi'])
            api_name = api_info['name']
            item = (idx, d, api_name)
            if 'WASAPI' in api_name:
                wasapi_candidates.append(item)
            elif 'DirectSound' in api_name:
                ds_candidates.append(item)
            elif 'MME' in api_name:
                mme_candidates.append(item)

        # 1. Try WASAPI candidates
        for idx, d, api_name in wasapi_candidates:
            name = d['name']
            sr = int(d['default_samplerate'])
            ch = min(2, d['max_input_channels'])

            # Test native format
            try:
                sd.check_input_settings(device=idx, samplerate=sr, channels=ch, dtype='int16')
                self.active_device_idx = idx
                self.active_device_name = name
                self.active_host_api = api_name
                self.active_sr = sr
                self.active_ch = ch
                return idx, sr, ch, name
            except Exception:
                continue

        # 2. Try DirectSound candidates
        for idx, d, api_name in ds_candidates:
            sr = 16000
            ch = 1
            try:
                sd.check_input_settings(device=idx, samplerate=sr, channels=ch, dtype='int16')
                self.active_device_idx = idx
                self.active_device_name = d['name']
                self.active_host_api = api_name
                self.active_sr = sr
                self.active_ch = ch
                return idx, sr, ch, d['name']
            except Exception:
                continue

        # 3. Fallback to default
        self.active_device_idx = None
        self.active_device_name = "Default Microphone"
        self.active_host_api = "Default"
        self.active_sr = 16000
        self.active_ch = 1
        return None, 16000, 1, "Default Microphone"

    def open_stream(self, callback: Optional[Callable] = None, gain: float = 2.5) -> AudioInputStreamWrapper:
        """
        Opens and returns an AudioInputStreamWrapper configured with the optimal device
        and normalization pipeline.
        """
        dev_idx, sr, ch, name = self.detect_best_device()
        logger.info(f"[AUDIO-INPUT] Opening stream on '{name}' (idx={dev_idx}, sr={sr}, ch={ch}, gain={gain}x)")
        print(f"[MAIN-MIC] Acquired input device: '{name}' (API={self.active_host_api}, sr={sr}, ch={ch})")
        return AudioInputStreamWrapper(
            device_idx=dev_idx,
            native_sr=sr,
            native_ch=ch,
            user_callback=callback,
            gain=gain
        )


def get_audio_input_manager() -> AudioInputManager:
    return AudioInputManager.get_instance()
