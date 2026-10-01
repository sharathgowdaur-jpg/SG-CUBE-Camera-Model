import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import urllib.request
import json
import time
import tempfile
import shutil
from bridge_server import BridgeServer

print("=== STARTING BRIDGE SERVER TEST ===")
bs = BridgeServer(dist_dir=os.path.join(os.path.abspath('.'), 'frontend', 'dist'))
bs.start(host='127.0.0.1', port=8008)
time.sleep(1.0)

base_url = 'http://127.0.0.1:8008'

def get(path):
    req = urllib.request.Request(f'{base_url}{path}')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def post(path, body):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(f'{base_url}{path}', data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

try:
    # 1. Test /api/status
    st = get('/api/status')
    print('1. Status endpoint: OK, first_run_completed =', st.get('first_run_completed'))

    # 2. Test /api/setup/status
    setup_st = get('/api/setup/status')
    print('2. Setup status endpoint: OK, masked_key =', setup_st.get('masked_key'))

    # 3. Test /api/setup/user-name
    res_uname = post('/api/setup/user-name', {'user_name': 'TestUserSG', 'user_display_name': 'TestUserSG'})
    print('3. Save user name: OK, res =', res_uname)

    # 4. Test /api/setup/diagnostics
    diag = get('/api/setup/diagnostics')
    print('4. System diagnostics: OK, overall =', diag.get('overall'), 'checks count =', len(diag.get('checks', [])))
    for c in diag.get('checks', []):
        cname = c.get('name')
        cstat = c.get('status')
        cdet = c.get('details', '')[:50]
        print(f'   - {cname}: {cstat} ({cdet}...)')

    # 5. Test /api/setup/api-key/test with dummy invalid key
    test_key_res = post('/api/setup/api-key/test', {'api_key': 'AIzaSyInvalidKeyTest1234567890'})
    print('5. Test invalid API key: OK, valid =', test_key_res.get('valid'), 'msg =', test_key_res.get('message'))

    # 6. Test /api/people
    people_res = get('/api/people')
    print('6. People endpoint: OK, count =', len(people_res.get('people', [])))

    # 7. Test /api/glasses/status
    glasses_res = get('/api/glasses/status')
    print('7. Glasses endpoint: OK, bridge_state =', glasses_res.get('bridge_state'))

    # 8. Test /api/setup/complete
    comp_res = post('/api/setup/complete', {})
    print('8. Complete setup: OK, first_run_completed =', comp_res.get('first_run_completed'))

    # 9. Verify /api/status reflects completion
    st2 = get('/api/status')
    print('9. Verified /api/status after completion: first_run_completed =', st2.get('first_run_completed'))

finally:
    bs.stop()
    print('=== BRIDGE SERVER TEST COMPLETE ===')
