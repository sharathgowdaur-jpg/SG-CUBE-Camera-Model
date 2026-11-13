import json
import pytest
from bridge_server import BridgeServer


class DummyApp:
    def __init__(self):
        self.camera_monitoring_enabled = False
        self.camera_monitor_controller = None
        self.latest_raw_frame = None


def test_bridge_camera_monitoring_endpoints():
    app = DummyApp()
    from assistive.camera_monitor_controller import CameraMonitorController
    app.camera_monitor_controller = CameraMonitorController(app=app, interval_seconds=10.0)

    server = BridgeServer(sgcube_app=app)

    # 1. Telemetry includes camera_monitoring
    telemetry = server.get_system_telemetry()
    assert "camera_monitoring" in telemetry
    assert telemetry["camera_monitoring"]["enabled"] is False
    assert telemetry["camera_monitoring"]["intervalSeconds"] == 10

    # 2. Action GET_CAMERA_MONITORING
    resp = server.execute_action("GET_CAMERA_MONITORING", {})
    assert resp["status"] == "ok"
    assert resp["camera_monitoring"]["enabled"] is False

    # 3. Action TOGGLE_CAMERA_MONITORING
    resp_toggle = server.execute_action("TOGGLE_CAMERA_MONITORING", {})
    assert resp_toggle["status"] == "ok"
    assert resp_toggle["camera_monitoring"]["enabled"] is True
    assert app.camera_monitoring_enabled is True

    # 4. Action SET_CAMERA_MONITORING (turn off)
    resp_set = server.execute_action("SET_CAMERA_MONITORING", {"enabled": False})
    assert resp_set["status"] == "ok"
    assert resp_set["camera_monitoring"]["enabled"] is False
    assert app.camera_monitoring_enabled is False

    # 5. Action MANUAL_DESCRIBE_SCENE
    resp_desc = server.execute_action("MANUAL_DESCRIBE_SCENE", {})
    assert resp_desc["status"] == "ok"
    assert "camera_monitoring" in resp_desc
