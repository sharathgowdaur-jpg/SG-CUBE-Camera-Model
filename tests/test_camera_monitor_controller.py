import time
import numpy as np
import pytest
from assistive.camera_monitor_controller import CameraMonitorController


class MockApp:
    def __init__(self):
        self.current_state = "IDLE"
        self.is_speaking = False
        self.latest_raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.spoken_responses = []
        self.camera_monitoring_enabled = False

    def _speak_local_response(self, text):
        self.spoken_responses.append(text)


def test_monitoring_off_by_default():
    """Requirement 1: Monitoring is OFF after application startup."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)
    status = controller.get_status()

    assert status["enabled"] is False, "Camera monitoring must be disabled by default"
    assert status["intervalSeconds"] == 10
    assert status["status"] == "IDLE"
    assert status["lastObservationTime"] is None
    assert "inactive" in status["latestDescription"].lower()


def test_manual_camera_commands_work_when_off():
    """Requirement 2 & 3: Manual camera commands work with monitoring OFF."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    # Controller is OFF
    assert controller.enabled is False

    # Perform on-demand manual observation
    obs = controller.perform_observation(speak_if_idle=True)
    assert obs is not None
    assert obs["lastObservationTime"] is not None
    assert controller.latest_description != "Camera monitoring is inactive."
    # The controller should still remain disabled (not automatically turned on)
    assert controller.enabled is False


def test_enabling_and_worker_lifecycle():
    """Requirement 4 & 5: Enabling starts scene analysis and establishes 10-second worker."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    # Enable
    res = controller.enable()
    assert res["enabled"] is True
    assert controller.enabled is True
    assert controller._worker_thread is not None
    assert controller._worker_thread.is_alive()

    # Re-enabling does not create duplicate workers (Requirement 10)
    original_thread = controller._worker_thread
    controller.enable()
    assert controller._worker_thread is original_thread

    # Disable stops scheduled analysis (Requirement 9)
    res_off = controller.disable()
    assert res_off["enabled"] is False
    assert controller.enabled is False
    assert controller._worker_thread is None


def test_no_overlapping_requests():
    """Requirement 6: Long-running scene analysis does not create overlapping requests."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    # Simulate ongoing analysis
    controller._is_analyzing = True
    status_before = controller.get_status()

    # Try to perform a concurrent observation
    status_after = controller.perform_observation(speak_if_idle=True)

    # Should safely reject/skip without duplicate execution
    assert status_after["status"] == "ANALYZING"

    # Reset
    controller._is_analyzing = False


def test_absolute_voice_priority_user_speaking():
    """Requirement 7 & 8: Voice commands take priority over monitoring. Never interrupts speech."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    # User is currently speaking
    app.current_state = "USER_SPEAKING"
    app.spoken_responses.clear()

    # Perform observation
    controller.perform_observation(speak_if_idle=True)

    # Monitoring MUST NOT speak over the user
    assert len(app.spoken_responses) == 0, "Monitoring must NOT speak while user is speaking"
    # But description MUST still update silently in status
    assert controller.last_observation_time is not None


def test_absolute_voice_priority_assistant_speaking():
    """Requirement 8: Monitoring never interrupts assistant speech."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    # Assistant is currently speaking
    app.current_state = "AI_SPEAKING"
    app.is_speaking = True
    app.spoken_responses.clear()

    controller.perform_observation(speak_if_idle=True)

    # Monitoring MUST NOT speak over active assistant output
    assert len(app.spoken_responses) == 0, "Monitoring must NOT speak while assistant is speaking"


def test_speech_announcement_when_idle():
    """Requirement 8: Speaks concise scene update when voice assistant is idle."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    # Assistant is completely IDLE
    app.current_state = "IDLE"
    app.is_speaking = False
    app.spoken_responses.clear()

    controller.perform_observation(speak_if_idle=True)

    # Should speak when assistant is idle
    assert len(app.spoken_responses) == 1
    spoken = app.spoken_responses[0]
    assert len(spoken) > 0


def test_deduplication_unchanged_scene():
    """Requirement 3 & 5: Avoids repeating unchanged scene descriptions unnecessarily."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    app.current_state = "IDLE"
    app.spoken_responses.clear()

    # First observation speaks
    controller.perform_observation(speak_if_idle=True)
    assert len(app.spoken_responses) == 1

    # Second identical observation should be silent (deduplicated)
    controller.perform_observation(speak_if_idle=True)
    assert len(app.spoken_responses) == 1, "Identical scene must NOT be repeatedly announced"


def test_verified_movement_detection():
    """Requirement 3: Verified movement between successive observations, no invented movement."""
    app = MockApp()
    controller = CameraMonitorController(app=app, interval_seconds=10.0)

    # Frame 1: 0 people
    obs1 = {"people": [], "objects": []}
    mov1 = controller._detect_verified_movement(obs1)
    assert mov1["detected"] is False, "Initial observation has no prior baseline"

    # Frame 2: 1 person appears
    obs2 = {"people": [{"id": "1", "name": "A person", "zone": "center"}], "objects": []}
    mov2 = controller._detect_verified_movement(obs2)
    assert mov2["detected"] is True
    assert "entered" in mov2["movement_desc"].lower()

    # Frame 3: Person shifts to right
    obs3 = {"people": [{"id": "1", "name": "A person", "zone": "right"}], "objects": []}
    mov3 = controller._detect_verified_movement(obs3)
    assert mov3["detected"] is True
    assert "right" in mov3["movement_desc"].lower()

    # Frame 4: No change
    obs4 = {"people": [{"id": "1", "name": "A person", "zone": "right"}], "objects": []}
    mov4 = controller._detect_verified_movement(obs4)
    assert mov4["detected"] is False, "No movement when entities remain unchanged"
