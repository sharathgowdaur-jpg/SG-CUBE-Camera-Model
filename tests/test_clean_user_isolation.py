import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tempfile
import shutil
import json
import time
import urllib.request

def test_clean_user_simulation():
    print("=== TESTING CLEAN NEW USER SIMULATION & ISOLATION ===")
    clean_dir = tempfile.mkdtemp(prefix="sgcube_clean_user_")
    old_key = os.environ.pop("GEMINI_API_KEY", None)

    try:
        # Set isolated user data environment variable
        os.environ["SGCUBE_USER_DATA"] = clean_dir

        from assistive.memory_store import MemoryStore
        from assistive.api_key_manager import APIKeyManager
        from bridge_server import BridgeServer

        store = MemoryStore(base_dir=clean_dir)
        km = APIKeyManager(pref_dir=os.path.join(clean_dir, "user_preferences"))

        # Verify brand new state
        first_run = store.get_setting("first_run_completed", False)
        user_name = store.get_setting("user_name", "")
        has_key = bool(km.get_active_api_key())

        print(f"Fresh profile check: first_run_completed={first_run}, user_name='{user_name}', has_key={has_key}")
        assert first_run is False, "Fresh profile must have first_run_completed == False"
        assert user_name == "", "Fresh profile must have empty user_name"
        assert has_key is False, "Fresh profile must have no active API key"

        # Start BridgeServer in isolated environment
        bs = BridgeServer(dist_dir=os.path.join(os.path.abspath('.'), 'frontend', 'dist'))
        bs.start(host='127.0.0.1', port=8009)
        time.sleep(1.0)
        base_url = 'http://127.0.0.1:8009'

        def get(path):
            req = urllib.request.Request(f'{base_url}{path}')
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode('utf-8'))

        def post(path, body):
            data = json.dumps(body).encode('utf-8')
            req = urllib.request.Request(f'{base_url}{path}', data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode('utf-8'))

        # 1. API Status shows first-launch required
        st = get('/api/status')
        assert st.get('first_run_completed') is False, f"Expected first_run_completed=False, got {st.get('first_run_completed')}"
        print("Step 1: First-launch detection verified (first_run_completed = False).")

        # 2. Complete Step 2: Set user name
        res_name = post('/api/setup/user-name', {'user_name': 'Eleanor Vance', 'user_display_name': 'Eleanor'})
        assert res_name.get('status') == 'ok', "User name save failed"
        print("Step 2: User name saved: Eleanor Vance.")

        # 3. Complete Step 4: Run diagnostics
        diag = get('/api/setup/diagnostics')
        print(f"Step 3: Diagnostics executed: {len(diag.get('checks', []))} checks completed. Overall: {diag.get('overall')}")

        # 4. Complete Step 5: Mark setup complete
        res_comp = post('/api/setup/complete', {})
        assert res_comp.get('first_run_completed') is True, "Complete setup failed"
        print("Step 4: Setup marked complete.")

        bs.stop()
        time.sleep(0.5)

        # 5. Reboot Simulation: Re-instantiate and restart BridgeServer with same isolated profile
        print("\n--- Simulating Application Restart / Reboot ---")
        store2 = MemoryStore(base_dir=clean_dir)
        assert store2.get_setting("first_run_completed") is True, "Setting did not persist across restart!"
        assert store2.get_setting("user_name") == "Eleanor Vance", "User name did not persist across restart!"

        bs2 = BridgeServer(dist_dir=os.path.join(os.path.abspath('.'), 'frontend', 'dist'))
        bs2.start(host='127.0.0.1', port=8009)
        time.sleep(1.0)

        st_reboot = get('/api/status')
        assert st_reboot.get('first_run_completed') is True, "Bridge status must report first_run_completed=True after reboot"
        assert st_reboot.get('user_name') == "Eleanor Vance", "Bridge status must report correct user_name after reboot"
        print("Step 5: Verified persistence after reboot (first_run_completed = True, user_name = Eleanor Vance).")

        bs2.stop()
        print("\n=== CLEAN USER SIMULATION PASSED COMPLETELY! ===")

    finally:
        if "SGCUBE_USER_DATA" in os.environ:
            del os.environ["SGCUBE_USER_DATA"]
        if old_key is not None:
            os.environ["GEMINI_API_KEY"] = old_key
        shutil.rmtree(clean_dir, ignore_errors=True)

if __name__ == "__main__":
    test_clean_user_simulation()
