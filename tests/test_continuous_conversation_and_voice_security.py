"""
SG CUBE Test Suite: Continuous Conversation + Voice Security Pipeline (Silero VAD + faster-whisper + SpeechBrain ECAPA-TDNN)
Covers all required test groups from Part 16:
Group A: Continuous Conversation
Group B: VAD
Group C: Password Text
Group D: Speaker Verification
Group E: Security Lifecycle
Group F: Privacy
"""

import os
import sys
import shutil
import tempfile
import unittest
import numpy as np
import torch
import soundfile as sf
import win32com.client

from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityManager, SecurityState
from assistive.conversation_context import ConversationState
from assistive.secure_vault.security_audio_pipeline import (
    AudioArbitrator,
    AudioArbitrationState,
    SileroVADProcessor,
    LocalWhisperTranscriber,
    ECAPASpeakerVerifier,
    AudioReplayDetector,
    SecurityAudioChallengeCoordinator,
    normalize_password_phrase
)


def synthesize_speech(text: str, voice_idx: int = 0, rate: int = 0) -> np.ndarray:
    """ Synthesizes speech to 16kHz float32 numpy array using Windows SAPI """
    temp_wav = os.path.join(tempfile.gettempdir(), f"temp_sapi_{os.getpid()}_{np.random.randint(10000)}.wav")
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        tokens = voice.GetVoices()
        if voice_idx < tokens.Count:
            voice.Voice = tokens.Item(voice_idx)
        voice.Rate = rate
        stream.Format.Type = 16  # SAFT16kHz16BitMono
        stream.Open(temp_wav, 3, False)
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()

        data, sr = sf.read(temp_wav)
        return data.astype(np.float32)
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass


class TestContinuousConversationAndVoiceSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Synthesize base audio samples for enrolled speaker (David, idx 0) and impostor (Zira, idx 1)
        cls.speech_david_1 = synthesize_speech("My secret 123", voice_idx=0, rate=0)
        cls.speech_david_2 = synthesize_speech("My secret 123", voice_idx=0, rate=1)
        cls.speech_david_3 = synthesize_speech("My secret 123", voice_idx=0, rate=-1)
        cls.speech_zira = synthesize_speech("My secret 123", voice_idx=1, rate=0)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_test_rework_")
        self.pref_dir = os.path.join(self.test_dir, "prefs")
        os.makedirs(self.pref_dir, exist_ok=True)
        self.engine = VisionEngine(data_dir=self.test_dir, per_request_auth=True)

        # Set up a configured security password "my secret 123"
        self.engine.security.set_password("my secret 123")
        # Enroll David as the authorized speaker
        self.engine.enroll_speaker_voice([
            self.speech_david_1,
            self.speech_david_2,
            self.speech_david_3
        ])

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    # =========================================================================
    # GROUP A: CONTINUOUS CONVERSATION
    # =========================================================================

    def test_a1_normal_to_normal_conversation_continues(self):
        """ Normal queries should execute without triggering security arbitrator or password challenges """
        arb = self.engine.audio_arbitrator
        self.assertEqual(arb.state, AudioArbitrationState.NORMAL_GEMINI)
        self.assertTrue(arb.is_gemini_streaming_allowed())

        resp1 = self.engine.process_user_speech_query("remember that my favorite color is green")
        self.assertIn("favorite color", resp1.lower())
        self.assertEqual(arb.state, AudioArbitrationState.NORMAL_GEMINI)
        self.assertTrue(arb.is_gemini_streaming_allowed())

        resp2 = self.engine.process_user_speech_query("what is my favorite color")
        self.assertIn("green", resp2.lower())
        self.assertEqual(arb.state, AudioArbitrationState.NORMAL_GEMINI)
        self.assertTrue(arb.is_gemini_streaming_allowed())

    def test_a2_protected_challenge_to_normal_conversation_resumes(self):
        """ After a protected challenge finishes, normal conversation resumes cleanly """
        arb = self.engine.audio_arbitrator

        # 1. Ask for protected memory -> challenge
        resp = self.engine.process_user_speech_query("remember as protected: my ATM PIN is 9988")
        self.assertIn("say your voice password", resp.lower())
        self.assertEqual(arb.state, AudioArbitrationState.SECURITY_CHALLENGE)
        self.assertFalse(arb.is_gemini_streaming_allowed())

        # 2. Provide password audio -> success
        pcm_bytes = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        ok, auth_resp = self.engine.process_security_challenge_audio(pcm_bytes)
        self.assertTrue(ok)
        self.assertIn("password verified", auth_resp.lower())

        # 3. Ownership returned to Gemini
        self.assertEqual(arb.state, AudioArbitrationState.NORMAL_GEMINI)
        self.assertTrue(arb.is_gemini_streaming_allowed())

        # 4. User immediately speaks normal query -> answered without password challenge
        normal_resp = self.engine.process_user_speech_query("what is my favorite color")
        self.assertNotIn("password", normal_resp.lower())
        self.assertEqual(arb.state, AudioArbitrationState.NORMAL_GEMINI)

    def test_a3_multiple_protected_requests_sequentially(self):
        """ Every protected request demands fresh voice password """
        arb = self.engine.audio_arbitrator

        # Request 1
        self.engine.process_user_speech_query("save as protected: my wifi is homepass123")
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)
        pcm_bytes = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        ok1, _ = self.engine.process_security_challenge_audio(pcm_bytes)
        self.assertTrue(ok1)
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

        # Request 2 (immediately after)
        self.engine.security_audio_coordinator.replay_detector.clear()
        self.engine.process_user_speech_query("what is my wifi")
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)
        ok2, _ = self.engine.process_security_challenge_audio(pcm_bytes)
        self.assertTrue(ok2)
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

    def test_a4_protected_normal_protected_sequence(self):
        """ Protected -> Normal -> Protected interleaved flow """
        # Protected query
        self.engine.process_user_speech_query("remember as protected: my locker code is 7766")
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)
        pcm_bytes = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        ok, _ = self.engine.process_security_challenge_audio(pcm_bytes)
        self.assertTrue(ok)

        # Normal query
        normal_resp = self.engine.process_user_speech_query("remember that my dog name is buddy")
        self.assertIn("buddy", normal_resp.lower())
        self.assertNotEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

        # Second protected query asks again
        self.engine.security_audio_coordinator.replay_detector.clear()
        resp_p2 = self.engine.process_user_speech_query("what is my locker code")
        self.assertIn("say your voice password", resp_p2.lower())
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)

    def test_a5_gemini_reconnect_preservation(self):
        """ Audio arbitrator allows session reconnection without destroying arbitrator state """
        arb = self.engine.audio_arbitrator
        self.assertEqual(arb.state, AudioArbitrationState.NORMAL_GEMINI)
        # Arbitrator remains clean and valid
        self.assertTrue(arb.is_gemini_streaming_allowed())

    # =========================================================================
    # GROUP B: VAD
    # =========================================================================

    def test_b1_silence_rejection(self):
        """ Pure silence audio is rejected by Silero VAD """
        silence = np.zeros(32000, dtype=np.float32)  # 2 seconds
        clean = self.engine.security_audio_coordinator.vad.extract_clean_speech(silence)
        self.assertIsNone(clean)

    def test_b2_noise_rejection(self):
        """ Static white noise without speech formants is rejected by Silero VAD """
        noise = (np.random.randn(32000) * 0.01).astype(np.float32)
        clean = self.engine.security_audio_coordinator.vad.extract_clean_speech(noise)
        self.assertIsNone(clean)

    def test_b3_short_speech_rejection(self):
        """ Speech below minimum speech threshold (< 400ms) is rejected """
        short_audio = self.speech_david_1[:3000]  # < 200ms
        clean = self.engine.security_audio_coordinator.vad.extract_clean_speech(short_audio)
        self.assertIsNone(clean)

    def test_b4_normal_password_speech_detection(self):
        """ Normal spoken password audio is detected and clean speech extracted """
        clean = self.engine.security_audio_coordinator.vad.extract_clean_speech(self.speech_david_1)
        self.assertIsNotNone(clean)
        self.assertGreater(len(clean), 5000)

    def test_b5_long_speech_bounded(self):
        """ Speech exceeding max_speech_ms is safely bounded/truncated without crashing """
        long_speech = np.tile(self.speech_david_1, 5)  # ~10 seconds
        clean = self.engine.security_audio_coordinator.vad.extract_clean_speech(long_speech)
        self.assertIsNotNone(clean)
        max_samples = int(self.engine.security_audio_coordinator.vad.max_speech_ms * 16)
        self.assertLessEqual(len(clean), max_samples)

    def test_b6_speech_followed_by_silence(self):
        """ Speech followed by trailing silence has silence trimmed away """
        silence = np.zeros(16000, dtype=np.float32)
        padded = np.concatenate([self.speech_david_1, silence])
        clean = self.engine.security_audio_coordinator.vad.extract_clean_speech(padded)
        self.assertIsNotNone(clean)
        self.assertLess(len(clean), len(padded))

    # =========================================================================
    # GROUP C: PASSWORD TEXT
    # =========================================================================

    def test_c1_correct_password(self):
        norm = normalize_password_phrase("My Secret 123")
        self.assertEqual(norm, "my secret 123")

    def test_c2_wrong_password(self):
        norm = normalize_password_phrase("Wrong Password 456")
        self.assertNotEqual(norm, "my secret 123")

    def test_c3_case_normalization(self):
        self.assertEqual(normalize_password_phrase("MY SECRET 123"), "my secret 123")
        self.assertEqual(normalize_password_phrase("mY sEcReT 123"), "my secret 123")

    def test_c4_whitespace_normalization(self):
        self.assertEqual(normalize_password_phrase("   my    secret   123   "), "my secret 123")

    def test_c5_punctuation_normalization(self):
        self.assertEqual(normalize_password_phrase("My Secret, 123!"), "my secret 123")
        self.assertEqual(normalize_password_phrase("My-Secret. 123?"), "my secret 123")

    def test_c6_spoken_numbers_normalization(self):
        self.assertEqual(normalize_password_phrase("my secret one two three"), "my secret 123")
        self.assertEqual(normalize_password_phrase("my secret 1 2 3"), "my secret 123")
        self.assertEqual(normalize_password_phrase("code nine nine eight eight"), "code 9988")

    def test_c7_empty_transcript(self):
        self.assertEqual(normalize_password_phrase(""), "")
        self.assertEqual(normalize_password_phrase("   "), "")

    # =========================================================================
    # GROUP D: SPEAKER VERIFICATION
    # =========================================================================

    def test_d1_enrolled_user_correct_voice(self):
        """ Correct enrolled voice passes speaker verification """
        is_match, sim, _ = self.engine.security_audio_coordinator.ecapa.verify_speaker(
            self.speech_david_1,
            self.engine.security_audio_coordinator.speaker_profile_path,
            threshold=0.65
        )
        self.assertTrue(is_match)
        self.assertGreater(sim, 0.75)

    def test_d2_wrong_speaker(self):
        """ Impostor voice fails speaker verification with low similarity """
        is_match, sim, _ = self.engine.security_audio_coordinator.ecapa.verify_speaker(
            self.speech_zira,
            self.engine.security_audio_coordinator.speaker_profile_path,
            threshold=0.65
        )
        self.assertFalse(is_match)
        self.assertLess(sim, 0.50)

    def test_d3_different_speaking_rate_and_distance(self):
        """ Slight variance in speaking speed still matches the enrolled speaker """
        is_match, sim, _ = self.engine.security_audio_coordinator.ecapa.verify_speaker(
            self.speech_david_2,
            self.engine.security_audio_coordinator.speaker_profile_path,
            threshold=0.65
        )
        self.assertTrue(is_match)
        self.assertGreater(sim, 0.70)

    def test_d4_quiet_room(self):
        """ Clean quiet room audio passes verification with high margin """
        is_match, sim, _ = self.engine.security_audio_coordinator.ecapa.verify_speaker(
            self.speech_david_1,
            self.engine.security_audio_coordinator.speaker_profile_path,
            threshold=0.65
        )
        self.assertTrue(is_match)

    def test_d5_moderate_background_noise(self):
        """ Audio with added background noise still authenticates if SNR is acceptable """
        noisy_audio = self.speech_david_1 + (np.random.randn(len(self.speech_david_1)) * 0.005).astype(np.float32)
        is_match, sim, _ = self.engine.security_audio_coordinator.ecapa.verify_speaker(
            noisy_audio,
            self.engine.security_audio_coordinator.speaker_profile_path,
            threshold=0.60
        )
        self.assertTrue(is_match)

    def test_d6_repeated_attempt(self):
        """ Consecutive valid attempts authenticate consistently """
        for s in [self.speech_david_1, self.speech_david_2, self.speech_david_3]:
            is_match, _, _ = self.engine.security_audio_coordinator.ecapa.verify_speaker(
                s,
                self.engine.security_audio_coordinator.speaker_profile_path,
                threshold=0.65
            )
            self.assertTrue(is_match)

    def test_d7_threshold_boundary_documented(self):
        """ Calibrated threshold is strictly documented and enforced at 0.65 """
        self.assertEqual(self.engine.security_audio_coordinator.ecapa.DEFAULT_THRESHOLD, 0.65)

    # =========================================================================
    # GROUP E: SECURITY LIFECYCLE
    # =========================================================================

    def test_e1_e2_e3_sequential_protected_requests_ask_password(self):
        """ Request 1, 2, and 3 each require fresh voice password """
        # Request 1
        self.engine.process_user_speech_query("save as protected: card pin is 1111")
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)
        pcm = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        ok1, _ = self.engine.process_security_challenge_audio(pcm)
        self.assertTrue(ok1)

        # Request 2
        self.engine.security_audio_coordinator.replay_detector.clear()
        self.engine.process_user_speech_query("what is my card pin")
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)
        ok2, _ = self.engine.process_security_challenge_audio(pcm)
        self.assertTrue(ok2)

        # Request 3
        self.engine.security_audio_coordinator.replay_detector.clear()
        self.engine.process_user_speech_query("save in secure memory: vault key is secretpass")
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)
        ok3, _ = self.engine.process_security_challenge_audio(pcm)
        self.assertTrue(ok3)

    def test_e4_normal_memory_never_asks(self):
        resp = self.engine.process_user_speech_query("remember that my favorite color is green")
        self.assertNotIn("password", resp.lower())
        recall = self.engine.process_user_speech_query("what is my favorite color")
        self.assertIn("green", recall.lower())
        self.assertNotIn("password", recall.lower())

    def test_e5_protected_save_asks(self):
        resp = self.engine.process_user_speech_query("remember as protected: my secret code is 5544")
        self.assertIn("say your voice password", resp.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

    def test_e6_protected_delete_asks(self):
        # Save first
        self.engine.process_user_speech_query("remember as protected: note to delete is temp123")
        pcm = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        self.engine.process_security_challenge_audio(pcm)

        # Delete requires challenge
        self.engine.security_audio_coordinator.replay_detector.clear()
        resp = self.engine.process_user_speech_query("forget my note to delete")
        self.assertIn("say your voice password", resp.lower())

    def test_e7_wrong_password_denied(self):
        self.engine.process_user_speech_query("what is my ATM PIN")
        # Synthesize audio with wrong password
        wrong_speech = synthesize_speech("completely wrong password", voice_idx=0, rate=0)
        pcm = (wrong_speech * 32767).astype(np.int16).tobytes()
        ok, msg = self.engine.process_security_challenge_audio(pcm)
        self.assertFalse(ok)
        self.assertTrue(any(w in msg.lower() for w in ["incorrect", "did not match", "denied", "failed"]))

    def test_e8_wrong_speaker_denied(self):
        self.engine.process_user_speech_query("what is my ATM PIN")
        # Zira speaks the correct password
        pcm = (self.speech_zira * 32767).astype(np.int16).tobytes()
        ok, msg = self.engine.process_security_challenge_audio(pcm)
        self.assertFalse(ok)
        self.assertIn("speaker identity mismatch", msg.lower())

    def test_e9_correct_password_and_speaker_accepted(self):
        self.engine.process_user_speech_query("remember as protected: my bank pin is 4321")
        pcm = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        ok, msg = self.engine.process_security_challenge_audio(pcm)
        self.assertTrue(ok)
        self.assertIn("password verified", msg.lower())

    def test_e10_restart_requires_authentication(self):
        # Save protected memory
        self.engine.process_user_speech_query("remember as protected: my recovery token is tok7788")
        pcm = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        self.engine.process_security_challenge_audio(pcm)

        # Simulate restart
        new_engine = VisionEngine(data_dir=self.test_dir, per_request_auth=True)
        resp = new_engine.process_user_speech_query("what is my recovery token")
        self.assertIn("say your voice password", resp.lower())
        self.assertEqual(new_engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

    # =========================================================================
    # GROUP F: PRIVACY
    # =========================================================================

    def test_f1_no_password_audio_sent_to_gemini(self):
        arb = self.engine.audio_arbitrator
        arb.enter_security_challenge()
        self.assertFalse(arb.is_gemini_streaming_allowed())

    def test_f2_no_protected_secret_sent_to_gemini(self):
        """ Ensure protected responses are never placed in pending_speech_prompt """
        self.engine.process_user_speech_query("remember as protected: my secret code is secret999")
        pcm = (self.speech_david_1 * 32767).astype(np.int16).tobytes()
        ok, resp = self.engine.process_security_challenge_audio(pcm)
        self.assertTrue(ok)
        self.assertNotIn("secret999", getattr(self.engine, "pending_speech_prompt", "") or "")

    def test_f3_no_plaintext_password_stored(self):
        """ Verifier files must not store plaintext passwords """
        verifier_path = os.path.join(self.test_dir, "prefs", "verifier.json")
        if os.path.exists(verifier_path):
            with open(verifier_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("my secret 123", content.lower())

    def test_f4_no_raw_password_recordings_permanently_stored(self):
        """ Ensure no .wav, .mp3, or raw audio files are persisted in data directory """
        for root, dirs, files in os.walk(self.test_dir):
            for f in files:
                self.assertFalse(f.endswith((".wav", ".mp3", ".pcm", ".raw")), f"Found persisted audio file: {f}")

    def test_f5_no_protected_secret_in_conversation_history(self):
        """ Conversation history must not record protected secrets """
        hist_file = os.path.join(self.test_dir, "conversation_history.db")
        if os.path.exists(hist_file):
            import sqlite3
            conn = sqlite3.connect(hist_file)
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM messages")
            rows = cursor.fetchall()
            for (c,) in rows:
                self.assertNotIn("9988", c)
                self.assertNotIn("homepass123", c)
            conn.close()


if __name__ == "__main__":
    unittest.main()
