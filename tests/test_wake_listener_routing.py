import os
import pytest
from unittest.mock import MagicMock, patch

from wake_listener import SGCubeWakeListener, CANONICAL_INSTALL_DIR, IPC_PORT_GUI

def test_canonical_install_dir_detection():
    listener = SGCubeWakeListener.__new__(SGCubeWakeListener)
    listener.app_dir = r"D:\SG-CUBE-GITHUB"

    target = listener.get_target_app_dir()
    if os.path.exists(os.path.join(CANONICAL_INSTALL_DIR, "visionclaw_gui.py")):
        assert target == CANONICAL_INSTALL_DIR, "Must prioritize canonical installed directory"
    else:
        assert target == listener.app_dir

def test_is_process_canonical():
    listener = SGCubeWakeListener.__new__(SGCubeWakeListener)
    canonical_dir = CANONICAL_INSTALL_DIR

    # Canonical installed process
    good_proc = {
        "pid": 1234,
        "exe": os.path.join(canonical_dir, "runtime", "Scripts", "python.exe"),
        "cwd": canonical_dir,
        "cmdline": [os.path.join(canonical_dir, "runtime", "Scripts", "python.exe"), "visionclaw_gui.py"]
    }
    assert listener.is_process_canonical(good_proc, canonical_dir) is True

    # Outdated process in an older folder
    old_proc = {
        "pid": 5678,
        "exe": r"D:\VisionClaw-main\.venv\Scripts\python.exe",
        "cwd": r"D:\VisionClaw-main",
        "cmdline": [r"D:\VisionClaw-main\.venv\Scripts\python.exe", "visionclaw_gui.py"]
    }
    assert listener.is_process_canonical(old_proc, canonical_dir) is False

def test_wake_routing_to_canonical_when_no_process_running():
    listener = SGCubeWakeListener.__new__(SGCubeWakeListener)
    listener.app_dir = r"D:\SG-CUBE-GITHUB"
    listener.last_wake_trigger_time = 0.0
    listener.activation_in_progress = False

    with patch.object(listener, "is_visionclaw_running", return_value=False), \
         patch.object(listener, "get_target_app_dir", return_value=CANONICAL_INSTALL_DIR), \
         patch.object(listener, "get_visionclaw_process_info", return_value=None), \
         patch("subprocess.Popen") as mock_popen:

        listener.launch_or_activate_visionclaw()

        assert mock_popen.called is True
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs.get("cwd") == CANONICAL_INSTALL_DIR, "Must launch with cwd=CANONICAL_INSTALL_DIR"

def test_wake_routing_reuses_canonical_running_process():
    listener = SGCubeWakeListener.__new__(SGCubeWakeListener)
    listener.app_dir = r"D:\SG-CUBE-GITHUB"
    listener.last_wake_trigger_time = 0.0
    listener.activation_in_progress = False

    canonical_proc = {
        "pid": 9999,
        "exe": os.path.join(CANONICAL_INSTALL_DIR, "runtime", "Scripts", "python.exe"),
        "cwd": CANONICAL_INSTALL_DIR,
        "cmdline": ["python.exe", "visionclaw_gui.py"]
    }

    with patch.object(listener, "is_visionclaw_running", return_value=True), \
         patch.object(listener, "get_target_app_dir", return_value=CANONICAL_INSTALL_DIR), \
         patch.object(listener, "get_visionclaw_process_info", return_value=canonical_proc), \
         patch.object(listener, "send_ipc_signal") as mock_ipc, \
         patch("subprocess.Popen") as mock_popen:

        listener.launch_or_activate_visionclaw()

        mock_ipc.assert_called_once_with("WAKE")
        assert mock_popen.called is False, "Must not launch a new process when canonical process is active"
