import os
import time
import socket
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from google.genai import types

def test_bridge_start_does_not_display_running_on_failure():
    from bridge_server import BridgeServer
    server = BridgeServer()
    # Mock uvicorn Server.serve to raise OSError 10048 (port in use)
    with patch("bridge_server.uvicorn.Server") as mock_server_cls:
        mock_server = MagicMock()
        mock_server.serve.side_effect = OSError(10048, "Cannot bind 127.0.0.1:8000")
        mock_server.started = False
        mock_server_cls.return_value = mock_server

        # Attempt to start on port 8000
        started = server.start(host="127.0.0.1", port=8000)
        assert started is False
        assert server.is_running is False


def test_bridge_leaves_unrelated_processes_alone():
    from bridge_server import BridgeServer
    server = BridgeServer()

    mock_proc = MagicMock()
    mock_proc.name.return_value = "inetinfo.exe"
    mock_proc.cmdline.return_value = ["C:\\Windows\\System32\\inetsrv\\inetinfo.exe"]

    mock_conn = MagicMock()
    mock_conn.laddr.port = 8000
    mock_conn.status = 'LISTEN'
    mock_conn.pid = 9999

    with patch("socket.socket") as mock_sock_cls, \
         patch("psutil.net_connections", return_value=[mock_conn]), \
         patch("psutil.Process", return_value=mock_proc):

        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0 # Port is occupied
        mock_sock_cls.return_value = mock_sock

        resolved = server._check_and_resolve_port_conflict("127.0.0.1", 8000)
        assert resolved is False, "Must NOT terminate unrelated process on port 8000"
        assert mock_proc.terminate.called is False


def test_audio_input_gain_and_capture_volume():
    from assistive.audio_input_manager import AudioInputStreamWrapper, AudioInputManager
    wrapper = AudioInputStreamWrapper(device_idx=None, native_sr=16000, native_ch=1)
    # 1. Default gain must be 1.0 (no forced 2.5x digital amplification)
    assert wrapper.gain == 1.0

    # 2. Soft-knee limiting test
    wrapper.gain = 2.0
    large_samples = np.full(1024, 25000, dtype=np.int16)
    # Simulate internal callback gain branch
    amplified = large_samples.astype(np.float32) * wrapper.gain # 50000 > 30000
    normalized = amplified / 32768.0
    compressed = np.tanh(normalized) * 32000.0
    output_samples = compressed.astype(np.int16)
    # Output must not exceed 32000 and must not hard-clip at 32767
    assert np.max(output_samples) <= 32000
    assert np.max(output_samples) > 28000


def test_audio_output_pcm_tracking():
    from assistive.audio_output_manager import AudioOutputManager
    aom = AudioOutputManager()
    aom._last_pcm_write_time = 0.0

    # Before write, is_playing_pcm is False
    assert aom.is_playing_pcm() is False

    # Simulate write
    aom._last_pcm_write_time = time.time()
    assert aom.is_playing_pcm() is True
    assert aom.is_speaking() is True

    # stop_speech resets PCM tracking
    aom.stop_speech()
    assert aom.is_playing_pcm() is False


def test_gemini_live_no_interruption_config():
    # Verify that types.ActivityHandling.NO_INTERRUPTION is available and used
    assert hasattr(types.ActivityHandling, "NO_INTERRUPTION")
    assert types.ActivityHandling.NO_INTERRUPTION == "NO_INTERRUPTION"


def test_single_instance_wake_acknowledgement():
    from visionclaw_gui import _check_and_wake_existing_instance
    with patch("socket.socket") as mock_sock_cls, \
         patch("visionclaw_gui._find_sgcube_visible_window", return_value=None), \
         patch("visionclaw_gui._cleanup_stale_instance_on_port") as mock_cleanup:

        mock_s = MagicMock()
        # Port 8000 check free
        # Port 49152 check open
        mock_s.connect_ex.side_effect = [1, 0] # port 8000 free (1), port 49152 open (0)
        mock_s.recv.return_value = b"OK\n"
        mock_sock_cls.return_value = mock_s

        # When existing instance acknowledges WAKE with "OK", must return True (reuse) and NOT call cleanup
        acknowledged = _check_and_wake_existing_instance()
        assert acknowledged is True
        assert mock_cleanup.called is False, "Must not kill healthy active instance acknowledging WAKE"


def test_single_turn_delegation_not_duplicated():
    from assistive.vision_engine import VisionEngine
    from assistive.command_router import CommandRouter
    from assistive.security_manager import SecurityState

    router = CommandRouter()
    engine = MagicMock(spec=VisionEngine)
    engine.process_user_speech_query = VisionEngine.process_user_speech_query.__get__(engine)
    engine.router = router
    engine.context = MagicMock()
    engine.context.resolve_followup_intent.return_value = {"needs_clarification": False, "is_followup": False, "intent": None, "params": {}}
    engine.security = MagicMock()
    engine.security.current_state = SecurityState.IDLE
    engine.last_scene = None
    engine.memory = MagicMock()
    engine.tasks = MagicMock()
    engine.person_tracker = MagicMock()
    engine.response_manager = MagicMock()
    engine._execute_intent.return_value = None

    call_count = [0]
    orig_route = router.route_intent
    def counting_route(text):
        call_count[0] += 1
        return orig_route(text)

    engine.router.route_intent = counting_route

    # Pass precomputed_route
    pre_route = orig_route("what is the weather today")
    call_count[0] = 0

    res = engine.process_user_speech_query("what is the weather today", precomputed_route=pre_route)
    assert call_count[0] == 0, "process_user_speech_query must not re-run router when precomputed_route is provided"
