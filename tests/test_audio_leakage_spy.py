"""
SG CUBE 2.5 — TEST-ONLY Audio Leakage Spy Instrumentation
Requirement 9:
Verifies that during:
A. Normal speech -> GEMINI_AUDIO_CHUNKS > 0
B. Security password enrollment -> GEMINI_AUDIO_CHUNKS == 0
C. Security password verification -> GEMINI_AUDIO_CHUNKS == 0

Records only:
- chunk count
- byte count
- whether a security-state chunk reached Gemini
NEVER records actual audio.
NEVER prints the password.
NEVER persists captured audio.
"""

import asyncio
import os
import queue
import tempfile
import numpy as np
import pytest
from unittest.mock import MagicMock

from assistive.security_manager import SecurityManager, SecurityState
from assistive.vision_engine import VisionEngine
from visionclaw_gui import SGCubeApp


class AudioLeakageSpy:
    """ Test-only instrumentation layer wrapping the Gemini input send path """
    def __init__(self):
        self.normal_chunk_count = 0
        self.normal_byte_count = 0
        self.security_chunk_count = 0
        self.security_byte_count = 0
        self.security_chunk_leaked_to_gemini = False

    async def instrumented_send_realtime_input(self, audio=None, security_active=False):
        if audio and hasattr(audio, 'data'):
            byte_len = len(audio.data)
            if security_active:
                self.security_chunk_count += 1
                self.security_byte_count += byte_len
                self.security_chunk_leaked_to_gemini = True
            else:
                self.normal_chunk_count += 1
                self.normal_byte_count += byte_len


def test_audio_leakage_spy_normal_and_security_modes():
    async def _async_test():
        spy = AudioLeakageSpy()
        app = SGCubeApp.__new__(SGCubeApp)
        app.ai_running = True
        app.active_session_id = "test_spy_session"
        app.pending_speech_prompt = None
        app.session_lock = MagicMock()
        app.session_lock.__enter__ = MagicMock(return_value=None)
        app.session_lock.__exit__ = MagicMock(return_value=None)
        app.gui_queue = MagicMock()

        test_dir = tempfile.mkdtemp()
        pref_dir = os.path.join(test_dir, "prefs")
        data_dir = os.path.join(test_dir, "data")
        os.makedirs(pref_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)

        app.engine = VisionEngine(data_dir=data_dir)
        app.engine.security = SecurityManager(pref_dir=pref_dir, store=app.engine.store)

        app.mic_queue = queue.Queue()

        # Create dummy 16kHz PCM audio chunk (1024 samples = 2048 bytes)
        sample_chunk = (np.ones(1024, dtype=np.int16) * 500).tobytes()

        mock_session = MagicMock()

        async def mock_send(audio=None):
            sec_active = hasattr(app.engine, 'security') and (app.engine.security.current_state != SecurityState.IDLE)
            await spy.instrumented_send_realtime_input(audio=audio, security_active=sec_active)

        mock_session.send_realtime_input = mock_send

        # -------------------------------------------------------------------------
        # Scenario A: Normal Speech (SecurityState.IDLE)
        # -------------------------------------------------------------------------
        app.engine.security.current_state = SecurityState.IDLE
        for _ in range(10):
            app.mic_queue.put(sample_chunk)

        task = asyncio.create_task(app._send_mic_loop(mock_session, "test_spy_session"))
        await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        print(f"\n[LEAKAGE SPY] Scenario A (Normal Speech):")
        print(f"  GEMINI_AUDIO_CHUNKS: {spy.normal_chunk_count}")
        print(f"  GEMINI_AUDIO_BYTES:  {spy.normal_byte_count}")
        print(f"  SECURITY_LEAK:       {spy.security_chunk_leaked_to_gemini}")

        assert spy.normal_chunk_count > 0, "Normal speech must stream chunks to Gemini Live"
        assert spy.normal_byte_count > 0
        assert not spy.security_chunk_leaked_to_gemini

        # -------------------------------------------------------------------------
        # Scenario B: Security Password Enrollment (SecurityState.ENROLL_AWAIT_PHRASE)
        # -------------------------------------------------------------------------
        spy_enroll_chunks_before = spy.normal_chunk_count
        app.engine.security.current_state = SecurityState.ENROLL_AWAIT_PHRASE
        for _ in range(10):
            app.mic_queue.put(sample_chunk)

        task = asyncio.create_task(app._send_mic_loop(mock_session, "test_spy_session"))
        await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        enroll_chunks_sent = spy.normal_chunk_count - spy_enroll_chunks_before
        print(f"\n[LEAKAGE SPY] Scenario B (Security Password Enrollment):")
        print(f"  GEMINI_AUDIO_CHUNKS: {enroll_chunks_sent}")
        print(f"  SECURITY_LEAK:       {spy.security_chunk_leaked_to_gemini}")

        assert enroll_chunks_sent == 0, f"Expected 0 chunks during enrollment, got {enroll_chunks_sent}"
        assert not spy.security_chunk_leaked_to_gemini

        # -------------------------------------------------------------------------
        # Scenario C: Security Password Verification (SecurityState.CHALLENGE_AWAIT_PHRASE)
        # -------------------------------------------------------------------------
        spy_challenge_chunks_before = spy.normal_chunk_count
        app.engine.security.current_state = SecurityState.CHALLENGE_AWAIT_PHRASE
        for _ in range(10):
            app.mic_queue.put(sample_chunk)

        task = asyncio.create_task(app._send_mic_loop(mock_session, "test_spy_session"))
        await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        challenge_chunks_sent = spy.normal_chunk_count - spy_challenge_chunks_before
        print(f"\n[LEAKAGE SPY] Scenario C (Security Password Verification):")
        print(f"  GEMINI_AUDIO_CHUNKS: {challenge_chunks_sent}")
        print(f"  SECURITY_LEAK:       {spy.security_chunk_leaked_to_gemini}")

        assert challenge_chunks_sent == 0, f"Expected 0 chunks during challenge, got {challenge_chunks_sent}"
        assert not spy.security_chunk_leaked_to_gemini

        # -------------------------------------------------------------------------
        # Scenario D: Resumption After Security State (SecurityState.IDLE)
        # -------------------------------------------------------------------------
        spy_resume_chunks_before = spy.normal_chunk_count
        app.engine.security.current_state = SecurityState.IDLE
        if hasattr(app.engine, 'audio_arbitrator'):
            app.engine.audio_arbitrator.return_to_gemini()
        for _ in range(5):
            app.mic_queue.put(sample_chunk)

        task = asyncio.create_task(app._send_mic_loop(mock_session, "test_spy_session"))
        await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        resume_chunks_sent = spy.normal_chunk_count - spy_resume_chunks_before
        print(f"\n[LEAKAGE SPY] Scenario D (Resumption after Security):")
        print(f"  GEMINI_AUDIO_CHUNKS: {resume_chunks_sent}")
        print(f"  SECURITY_LEAK:       {spy.security_chunk_leaked_to_gemini}")

        assert resume_chunks_sent > 0, "Normal streaming must resume once security state is IDLE"
        assert not spy.security_chunk_leaked_to_gemini

    asyncio.run(_async_test())
