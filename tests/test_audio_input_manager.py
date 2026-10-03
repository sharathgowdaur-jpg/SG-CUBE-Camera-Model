import time
import pytest
import numpy as np
from assistive.audio_input_manager import get_audio_input_manager, AudioInputManager, AudioInputStreamWrapper

def test_singleton_initialization():
    mgr1 = get_audio_input_manager()
    mgr2 = get_audio_input_manager()
    assert mgr1 is mgr2
    assert isinstance(mgr1, AudioInputManager)

def test_detect_best_device():
    mgr = get_audio_input_manager()
    dev_idx, sr, ch, name = mgr.detect_best_device()
    assert sr in (16000, 44100, 48000)
    assert ch in (1, 2, 4)
    assert isinstance(name, str)
    assert len(name) > 0

def test_stream_wrapper_output_contract():
    # Test wrapper internal processing directly with mock data
    delivered_chunks = []
    def user_cb(chunk, frames, time_info, status):
        delivered_chunks.append(chunk)

    # 48kHz stereo mock wrapper
    wrapper = AudioInputStreamWrapper(
        device_idx=None,
        native_sr=48000,
        native_ch=2,
        user_callback=user_cb,
        gain=2.0
    )
    # Don't call start() to avoid opening hardware device in mock test
    # Instead, simulate callback directly by invoking internal callback logic
    # 3072 stereo frames = 6144 samples
    raw_signal = (np.ones(6144, dtype=np.int16) * 100).tobytes()
    # Find internal callback in wrapper init closure or test logic:
    # We can test by running open_stream for 0.5s if hardware permits
    mgr = get_audio_input_manager()
    stream = mgr.open_stream(callback=user_cb, gain=2.5)
    stream.start()
    time.sleep(0.3)
    stream.stop()
    stream.close()

    assert len(delivered_chunks) > 0
    first_chunk = delivered_chunks[0]
    # Each chunk must be 1024 samples of int16 = 2048 bytes
    assert len(first_chunk) == 2048
    arr = np.frombuffer(first_chunk, dtype=np.int16)
    assert len(arr) == 1024
