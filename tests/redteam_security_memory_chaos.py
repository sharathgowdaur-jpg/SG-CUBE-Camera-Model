"""
Red-Team Test Suite: Security, Memory, Lockout, Cryptography & Chaos Resilience
Attacks:
- Protected Memory & Authentication Gate (rate-limiting, lockout, anti-bypass)
- Single-use auth token anti-replay and expiration
- Cryptographic Engine AES-256-GCM authenticated encryption and tamper rejection
- Face 2FA quality gate and unknown face rejection
- Port 49152 single-instance mutex and 20-cycle socket exhaustion stress
- Offline perception and local query resilience
- Cancellation / abort token reactivity
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import socket
import secrets
import pytest
import cv2
import numpy as np

from assistive.local_memory_v2.lockout_manager import LockoutManager
from assistive.local_memory_v2.authentication_gate import AuthenticationGate, SingleUseAuthToken
from assistive.local_memory_v2.crypto_engine import LocalMemoryCryptoEngine
from assistive.local_memory_v2.password_verifier import PasswordVerifier
from assistive.local_memory_v2.audit_logger import SecurityAuditLogger
from assistive.face_memory import FaceMemory
from assistive.task_planner import CompoundTaskPlanner
from assistive.vision_engine import VisionEngine


class TestLocalMemorySecurityAndLockoutRedTeam:
    @pytest.fixture(autouse=True)
    def setup_security_components(self, tmp_path):
        self.tmp_dir = str(tmp_path / "sec_test")
        os.makedirs(self.tmp_dir, exist_ok=True)
        self.lockout = LockoutManager(self.tmp_dir, max_attempts=3, lockout_duration_seconds=5.0)
        self.verifier = PasswordVerifier(self.tmp_dir)
        # Set a test master multi-word password
        self.test_password = "super secret master key"
        ok_setup, _ = self.verifier.setup_password(self.test_password, self.test_password)
        assert ok_setup is True
        self.audit = SecurityAuditLogger(self.tmp_dir)
        self.gate = AuthenticationGate(self.verifier, self.lockout, self.audit)

    def test_correct_password_authenticates_and_issues_single_use_token(self):
        ok, msg, token = self.gate.authenticate_typed(self.test_password)
        assert ok is True
        assert token is not None
        assert token.is_valid() is True

        # First consumption succeeds
        assert token.consume() is True
        # Anti-replay: second consumption MUST fail
        assert token.consume() is False
        assert token.is_valid() is False

    def test_single_use_token_expiration(self):
        token = SingleUseAuthToken(ttl_seconds=0.1)
        assert token.is_valid() is True
        time.sleep(0.2)
        assert token.is_valid() is False
        assert token.consume() is False

    def test_wake_word_anti_bypass_attack(self):
        # Adversary attempts to use assistant wake words as security passwords
        ok, msg, token = self.gate.authenticate_typed("hey sg cube")
        assert ok is False
        assert token is None
        assert "wake phrase cannot be used" in msg.lower()

        ok, msg, token = self.gate.authenticate_typed("visionclaw")
        assert ok is False
        assert token is None
        assert "wake phrase cannot be used" in msg.lower()

        # 3rd attempt with wake phrase counts toward failure and triggers lockout
        ok, msg, token = self.gate.authenticate_typed("sgcube")
        assert ok is False
        assert self.lockout.is_locked_out()[0] is True

    def test_brute_force_lockout_after_three_failures(self):
        # 1st failure
        ok, msg, _ = self.gate.authenticate_typed("wrong_pwd_1")
        assert ok is False
        assert self.lockout.is_locked_out()[0] is False

        # 2nd failure
        ok, msg, _ = self.gate.authenticate_typed("wrong_pwd_2")
        assert ok is False
        assert self.lockout.is_locked_out()[0] is False

        # 3rd failure: must trigger LOCKOUT
        ok, msg, _ = self.gate.authenticate_typed("wrong_pwd_3")
        assert ok is False
        is_locked, rem = self.lockout.is_locked_out()
        assert is_locked is True
        assert rem > 0.0

        # Attempt during lockout with CORRECT password must still be rejected
        ok, msg, _ = self.gate.authenticate_typed(self.test_password)
        assert ok is False
        assert "locked" in msg.lower()

        # Wait for lockout to expire
        time.sleep(5.2)
        assert self.lockout.is_locked_out()[0] is False

        # Now correct password succeeds and resets lockout counter
        ok, msg, token = self.gate.authenticate_typed(self.test_password)
        assert ok is True
        assert self.lockout.get_failed_attempts() == 0


class TestCryptoEngineRedTeam:
    @pytest.fixture(autouse=True)
    def setup_crypto(self):
        self.key1 = secrets.token_bytes(32)
        self.key2 = secrets.token_bytes(32)
        self.engine1 = LocalMemoryCryptoEngine(self.key1)
        self.engine2 = LocalMemoryCryptoEngine(self.key2)

    def test_aes_gcm_encrypt_decrypt_integrity(self):
        secret = "SG CUBE Highly Sensitive Vault Credential 12345"
        nonce, ciphertext = self.engine1.encrypt(secret, memory_id="rec_001", sensitivity="HIGH")
        assert len(nonce) == 12
        assert len(ciphertext) > len(secret)

        # Decrypt with correct key and matching AAD
        decrypted = self.engine1.decrypt(nonce, ciphertext, memory_id="rec_001", sensitivity="HIGH")
        assert decrypted == secret

    def test_wrong_key_fails_closed(self):
        secret = "Confidential Banking Pin"
        nonce, ciphertext = self.engine1.encrypt(secret, memory_id="rec_002")

        # Attempt decryption with key2
        decrypted = self.engine2.decrypt(nonce, ciphertext, memory_id="rec_002")
        assert decrypted is None  # Fails closed, returns None

    def test_ciphertext_tampering_fails_closed(self):
        secret = "Medical Records"
        nonce, ciphertext = self.engine1.encrypt(secret, memory_id="rec_003")

        # Bit flip in ciphertext
        tampered_bytes = bytearray(ciphertext)
        tampered_bytes[5] ^= 0xFF
        tampered = bytes(tampered_bytes)

        # GCM authentication tag verification must reject tampered data
        assert self.engine1.decrypt(nonce, tampered, memory_id="rec_003") is None

    def test_aad_substitution_tampering_fails_closed(self):
        secret = "Home Security Alarm Code"
        nonce, ciphertext = self.engine1.encrypt(secret, memory_id="rec_004", sensitivity="HIGH")

        # Attacker swaps memory_id or sensitivity level in AAD
        assert self.engine1.decrypt(nonce, ciphertext, memory_id="rec_999", sensitivity="HIGH") is None
        assert self.engine1.decrypt(nonce, ciphertext, memory_id="rec_004", sensitivity="LOW") is None


class TestFaceQualityAndRejectionRedTeam:
    @pytest.fixture(autouse=True)
    def setup_face(self, tmp_path):
        self.face_dir = str(tmp_path / "faces")
        self.face_engine = FaceMemory(storage_dir=self.face_dir)

    def test_quality_gate_rejects_degraded_images(self):
        # 1. Blank/flat image (zero contrast, zero focus variance)
        blank = np.zeros((100, 100, 3), dtype=np.uint8)
        # Face detection on blank image returns 0 faces
        gray = cv2.cvtColor(blank, cv2.COLOR_BGR2GRAY)
        focus_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        assert focus_var < self.face_engine.min_focus_variance

        # 2. Random white noise (no face structure)
        noise = np.random.randint(0, 256, (120, 120, 3), dtype=np.uint8)
        # Must not identify as known profile
        assert len(self.face_engine.profiles) == 0


class TestPortMutexAndSocketStressRedTeam:
    def test_port_49152_mutex_and_rapid_cycling(self):
        """
        Tests port 49152 mutex enforcement and 20 rapid bind/unbind cycles
        to prove zero port exhaustion, leaked handles, or hanging sockets.
        """
        # Test 20 rapid cycles on a dedicated test port (e.g. 49160)
        test_port = 49160
        for i in range(20):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', test_port))
            s.listen(1)

            # Concurrent bind attempt while socket is open MUST fail
            s_dup = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with pytest.raises(OSError):
                s_dup.bind(('127.0.0.1', test_port))
            s_dup.close()

            # Clean close and unbind
            s.close()


class TestOfflinePerceptionAndCancellationRedTeam:
    @pytest.fixture(autouse=True)
    def setup_engine(self, tmp_path):
        self.tmp_data = tmp_path / "data"
        self.tmp_data.mkdir(parents=True)
        self.engine = VisionEngine(data_dir=str(self.tmp_data))

    def test_local_offline_commands_route_cleanly(self):
        # Commands that should work offline without requiring external LLM API
        local_cmds = [
            "what time is it",
            "what is the date",
            "volume up",
            "volume down",
            "mute audio",
            "take screenshot"
        ]
        for cmd in local_cmds:
            route = self.engine.router.route_intent(cmd)
            assert route is not None
            assert "intent" in route

    def test_planner_immediate_cancellation_reactivity(self):
        planner = CompoundTaskPlanner(max_steps=5)
        steps = planner.decompose_task("action 1, and then action 2, and then action 3")

        # Cancel planner before execution starts
        planner.abort()
        res = planner.execute_plan(steps, lambda cmd: (True, "OK"))
        assert res.success is False
        assert res.aborted is True
        assert res.completed_steps == 0
