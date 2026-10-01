import os
import re
import json
import time
import hmac
import hashlib
import secrets
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from .api_key_manager import _obfuscate, _deobfuscate, _resolve_pref_dir

class SecurityLevel(str, Enum):
    SAFE = "SAFE"
    PROTECTED = "PROTECTED"
    HIGH_RISK = "HIGH_RISK"

class SecurityState(str, Enum):
    IDLE = "IDLE"
    ENROLL_AWAIT_PHRASE = "ENROLL_AWAIT_PHRASE"
    ENROLL_AWAIT_REPEAT = "ENROLL_AWAIT_REPEAT"
    CHANGE_AWAIT_CURRENT = "CHANGE_AWAIT_CURRENT"
    CHANGE_AWAIT_NEW = "CHANGE_AWAIT_NEW"
    CHANGE_AWAIT_REPEAT = "CHANGE_AWAIT_REPEAT"
    RECOVERY_AWAIT_CODE = "RECOVERY_AWAIT_CODE"
    RECOVERY_AWAIT_NEW_PHRASE = "RECOVERY_AWAIT_NEW_PHRASE"
    RECOVERY_AWAIT_REPEAT = "RECOVERY_AWAIT_REPEAT"
    REMOVE_AWAIT_CURRENT = "REMOVE_AWAIT_CURRENT"
    REMOVE_AWAIT_CONFIRM = "REMOVE_AWAIT_CONFIRM"
    CHALLENGE_AWAIT_PHRASE = "CHALLENGE_AWAIT_PHRASE"

DIGIT_TO_WORD: Dict[str, str] = {
    '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
    '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten'
}
WORD_TO_DIGIT: Dict[str, str] = {v: k for k, v in DIGIT_TO_WORD.items()}

def get_candidate_forms(phrase: Optional[str]) -> List[str]:
    """
    Generates canonical candidate forms of a spoken security phrase:
    - Strips optional wake words / assistant address prefixes ('sg cube', 'hey sg cube', etc.)
    - Form 1: Raw normalized (stripped punctuation, lowercased)
    - Form 2: Word-to-digit converted (e.g. 'seven' -> '7')
    - Form 3: Digit-to-word converted (e.g. '7' -> 'seven')
    Enables speech recognition to match whether numbers are transcribed as words or digits,
    without any fuzzy matching or security degradation.
    """
    if not phrase:
        return []
    clean = phrase.strip().lower()
    # Strip optional wake words / assistant prefixes if spoken
    clean = re.sub(r'^(?:hey\s+)?(?:sg\s*cube|sgcube|assistant|computer)[,\s:]*', '', clean).strip()
    clean = re.sub(r'[^\w\s]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if not clean:
        return []

    tokens = clean.split()
    form_raw = " ".join(tokens)
    form_digits = " ".join(WORD_TO_DIGIT.get(t, t) for t in tokens)
    form_words = " ".join(DIGIT_TO_WORD.get(t, t) for t in tokens)

    return list(dict.fromkeys([form_raw, form_digits, form_words]))

def normalize_phrase(phrase: Optional[str]) -> str:
    """
    Normalizes a spoken phrase for deterministic comparison:
    - Lowercase
    - Strip leading/trailing whitespace
    - Strip optional wake-word prefixes
    - Remove punctuation (periods, commas, exclamation points, hyphens, colons, quotes)
    - Collapse multiple spaces into a single space
    """
    if not phrase:
        return ""
    text = phrase.strip().lower()
    # Strip optional wake words / assistant prefixes if spoken
    text = re.sub(r'^(?:hey\s+)?(?:sg\s*cube|sgcube|assistant|computer)[,\s:]*', '', text).strip()
    # Strip harmless punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Collapse multiple whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_recovery_code(code: Optional[str]) -> str:
    """ Normalizes alphanumeric recovery codes (strips spaces and hyphens, uppercase) """
    if not code:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9]', '', code.strip()).upper()
    return clean

class SecurityManager:
    """
    Central Voice Security Password & Authorization Manager for SG CUBE 2.5.
    
    Provides:
    - Local PBKDF2-HMAC-SHA256 password verifier storage (The raw Voice Security Password is not intentionally persisted, logged, sent to Gemini, or stored in conversation history.)
    - Secure recovery code generation and verifier verification
    - Stateful voice enrollment, change, reset/recovery, and removal flows
    - Centralized policy categorization (SAFE, PROTECTED, HIGH_RISK)
    - 60-second temporary authorization sessions with explicit revoke
    - Progressive failed-attempt lockouts (30s, 60s, 300s)
    - High-risk two-factor authentication (Voice Password + Confirmed Live Face)
    - Zero LLM leakage (intercepts passwords locally before LLM processing)
    """

    get_candidate_forms = staticmethod(get_candidate_forms)

    POLICY_MAP: Dict[str, SecurityLevel] = {
        # Safe perception, tasks & conversation
        "GENERAL": SecurityLevel.SAFE,
        "OCR": SecurityLevel.SAFE,
        "CURRENCY": SecurityLevel.SAFE,
        "COLOR_IDENTIFY": SecurityLevel.SAFE,
        "LIGHT_LEVEL_CHECK": SecurityLevel.SAFE,
        "OBJECT_SEARCH": SecurityLevel.SAFE,
        "SAFETY": SecurityLevel.SAFE,
        "ENVIRONMENT": SecurityLevel.SAFE,
        "INTRODUCE": SecurityLevel.SAFE,
        "FACE_IDENTIFY": SecurityLevel.SAFE,
        "SETTINGS": SecurityLevel.SAFE,
        "SLEEP": SecurityLevel.SAFE,
        "TASK_CREATE": SecurityLevel.SAFE,
        "REMINDER_CREATE": SecurityLevel.SAFE,
        "TASK_LIST": SecurityLevel.SAFE,
        "REMINDER_LIST": SecurityLevel.SAFE,
        "TASK_COMPLETE": SecurityLevel.SAFE,
        "TASK_SNOOZE": SecurityLevel.SAFE,
        "REMINDER_SNOOZE": SecurityLevel.SAFE,
        "TASK_SEARCH": SecurityLevel.SAFE,
        "PEOPLE_COUNT": SecurityLevel.SAFE,
        "PEOPLE_DESCRIPTION": SecurityLevel.SAFE,
        "PEOPLE_LOCATION": SecurityLevel.SAFE,
        "KNOWN_PEOPLE_QUERY": SecurityLevel.SAFE,
        "PERSON_LOCATION_QUERY": SecurityLevel.SAFE,
        "PEOPLE_BEHIND_QUERY": SecurityLevel.SAFE,
        "PERSON_ENTERED": SecurityLevel.SAFE,
        "PERSON_LEFT": SecurityLevel.SAFE,
        "DOCUMENT_READ": SecurityLevel.SAFE,
        "DOCUMENT_SUMMARY": SecurityLevel.SAFE,
        "DOCUMENT_TITLE": SecurityLevel.SAFE,
        "DOCUMENT_FIELDS": SecurityLevel.SAFE,
        "DOCUMENT_TABLE": SecurityLevel.SAFE,
        "DOCUMENT_TOTAL": SecurityLevel.SAFE,
        "DOCUMENT_SEARCH": SecurityLevel.SAFE,
        "DOCUMENT_REPEAT": SecurityLevel.SAFE,
        "DOCUMENT_CLEAR": SecurityLevel.SAFE,
        "AUTOMATION_OPEN_APP": SecurityLevel.SAFE,
        "AUTOMATION_OPEN_URL": SecurityLevel.SAFE,
        "AUTOMATION_COPY_TEXT": SecurityLevel.SAFE,
        "AUTOMATION_STATUS": SecurityLevel.SAFE,
        "AUTOMATION_CONFIRM": SecurityLevel.SAFE,
        "AUTOMATION_CANCEL": SecurityLevel.SAFE,
        "ALERTS_PAUSE": SecurityLevel.SAFE,
        "ALERTS_RESUME": SecurityLevel.SAFE,
        "ALERTS_SET_MODE": SecurityLevel.SAFE,
        "ALERTS_STATUS": SecurityLevel.SAFE,
        "ALERTS_EXPLAIN_LAST": SecurityLevel.SAFE,
        "MOUSE_MOVE": SecurityLevel.SAFE,
        "MOUSE_CLICK": SecurityLevel.SAFE,
        "MOUSE_DOUBLE_CLICK": SecurityLevel.SAFE,
        "MOUSE_RIGHT_CLICK": SecurityLevel.SAFE,
        "MOUSE_SCROLL": SecurityLevel.SAFE,
        "MOUSE_MOVE_ABSOLUTE": SecurityLevel.SAFE,
        "MOUSE_DRAG": SecurityLevel.SAFE,
        "MOUSE_POSITION": SecurityLevel.SAFE,
        "WINDOWS_SETTINGS": SecurityLevel.SAFE,
        "NOTEPAD_OPEN": SecurityLevel.SAFE,
        "NOTEPAD_WRITE": SecurityLevel.SAFE,
        "NOTEPAD_SELECT_ALL": SecurityLevel.SAFE,
        "NOTEPAD_COPY": SecurityLevel.SAFE,
        "NOTEPAD_PASTE": SecurityLevel.SAFE,
        "NOTEPAD_CLEAR": SecurityLevel.PROTECTED,

        # Protected operations (Single deletion, listings, personal memories, task edits, process closing)
        "MEMORY_RECALL": SecurityLevel.PROTECTED,
        "MEMORY_LIST": SecurityLevel.PROTECTED,
        "MEMORY_SAVE": SecurityLevel.SAFE,  # Saving facts is safe; recalling/listing is protected
        "MEMORY_FORGET": SecurityLevel.PROTECTED,
        "MEMORY_DELETE_CATEGORY": SecurityLevel.PROTECTED,
        "FACE_LIST": SecurityLevel.PROTECTED,
        "FACE_FORGET": SecurityLevel.PROTECTED,
        "FACE_REMEMBER": SecurityLevel.SAFE,
        "FACE_UPDATE_CONFIRM": SecurityLevel.PROTECTED,
        "CONVERSATION_HISTORY_VIEW": SecurityLevel.PROTECTED,
        "CONVERSATION_HISTORY_EXPORT": SecurityLevel.PROTECTED,
        "API_CONFIG_VIEW": SecurityLevel.PROTECTED,
        "TASK_DELETE": SecurityLevel.PROTECTED,
        "TASK_EDIT": SecurityLevel.PROTECTED,
        "REMINDER_CANCEL": SecurityLevel.PROTECTED,
        "REMINDER_EDIT": SecurityLevel.PROTECTED,
        "TASK_LIST_PRIVATE": SecurityLevel.PROTECTED,
        "AUTOMATION_CLOSE_APP": SecurityLevel.PROTECTED,
        "AUTOMATION_OPEN_FOLDER": SecurityLevel.PROTECTED,

        # High-Risk operations (Mass deletion, security modification, system workstation lock)
        "MEMORY_CLEAR": SecurityLevel.HIGH_RISK,
        "FACE_FORGET_ALL": SecurityLevel.HIGH_RISK,
        "HISTORY_CLEAR_ALL": SecurityLevel.HIGH_RISK,
        "TASK_CLEAR_ALL": SecurityLevel.HIGH_RISK,
        "REMINDER_CLEAR_ALL": SecurityLevel.HIGH_RISK,
        "SECURITY_REMOVE": SecurityLevel.HIGH_RISK,
        "SECURITY_RESET": SecurityLevel.HIGH_RISK,
        "SECURITY_CONFIG_CHANGE": SecurityLevel.HIGH_RISK,
        "AUTOMATION_LOCK_DEVICE": SecurityLevel.HIGH_RISK,
        "AUTOMATION_CONFIG_CHANGE": SecurityLevel.HIGH_RISK,
    }

    def __init__(self, pref_dir: Optional[str] = None, store: Optional[Any] = None, local_memory_service: Optional[Any] = None):
        self.pref_dir = _resolve_pref_dir(pref_dir)
        os.makedirs(self.pref_dir, exist_ok=True)
        self.store = store

        self.local_memory_service = local_memory_service
        if self.local_memory_service is None:
            try:
                base_data = os.path.dirname(self.pref_dir)
                from .local_memory_v2 import LocalMemoryService
                self.local_memory_service = LocalMemoryService(base_data)
            except Exception:
                self.local_memory_service = None

        self.verifier_file = os.path.join(self.pref_dir, "security_verifier.dat")
        self.recovery_file = os.path.join(self.pref_dir, "recovery_verifier.dat")

        # Session & Lockout state (in-memory only)
        self._authorized_until: float = 0.0
        self._session_ttl_seconds: float = 60.0
        self._failed_attempts: int = 0
        self._locked_until: float = 0.0
        self._last_activity_time: float = 0.0

        # Interactive state machine
        self.current_state: SecurityState = SecurityState.IDLE
        self._temp_phrase_buffer: Optional[str] = None
        self._temp_recovery_buffer: Optional[str] = None
        self._pending_action: Optional[Dict[str, Any]] = None
        self._pending_action_time: float = 0.0

        # Cached verifiers
        self._cached_verifier: Optional[Dict[str, Any]] = None
        self._cached_recovery: Optional[Dict[str, Any]] = None
        self._load_verifiers()

    def _load_verifiers(self):
        """ Loads encrypted verifiers from disk """
        self._cached_verifier = self._read_verifier_file(self.verifier_file)
        self._cached_recovery = self._read_verifier_file(self.recovery_file)

    def _read_verifier_file(self, filepath: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                encrypted_text = f.read().strip()
            if not encrypted_text:
                return None
            plain_json = _deobfuscate(encrypted_text)
            if not plain_json:
                return None
            return json.loads(plain_json)
        except Exception:
            return None

    def _write_verifier_file(self, filepath: str, data: Optional[Dict[str, Any]]) -> bool:
        if data is None:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            return True
        try:
            plain_json = json.dumps(data)
            encrypted_text = _obfuscate(plain_json)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(encrypted_text)
            return True
        except Exception:
            return False

    def is_configured(self) -> bool:
        """ Returns True if a valid Voice Security Password verifier is set """
        if self.local_memory_service and self.local_memory_service.is_password_configured():
            return True
        if hasattr(self, "vault") and self.vault and self.vault.is_setup():
            return True
        return self._cached_verifier is not None and "hash_hex" in self._cached_verifier

    def is_onboarding_completed(self) -> bool:
        """ Returns True if first-run security onboarding has been performed or skipped """
        if self.is_configured():
            return True
        if self.store:
            return bool(self.store.get_setting("security_onboarding_completed", False))
        return False

    def mark_onboarding_completed(self, completed: bool = True):
        """ Updates persistent onboarding state """
        if self.store:
            self.store.set_setting("security_onboarding_completed", completed)

    def is_face_2fa_required(self) -> bool:
        """ Returns True if High-Risk 2FA (Voice + Live Face) is enabled """
        if self.store:
            return bool(self.store.get_setting("security_require_face_2fa", True))
        return True

    def set_face_2fa_required(self, enabled: bool):
        """ Toggles High-Risk 2FA setting """
        if self.store:
            self.store.set_setting("security_require_face_2fa", enabled)

    # -------------------------------------------------------------------------
    # Cryptographic Hash & Verifier Generation
    # -------------------------------------------------------------------------
    def _create_verifier(self, normalized_text: str) -> Dict[str, Any]:
        """ Computes PBKDF2-HMAC-SHA256 verifier with 16-byte random salt """
        salt = secrets.token_bytes(16)
        iterations = 100000
        key_hash = hashlib.pbkdf2_hmac("sha256", normalized_text.encode("utf-8"), salt, iterations)
        return {
            "salt_hex": salt.hex(),
            "hash_hex": key_hash.hex(),
            "iterations": iterations,
            "algo": "pbkdf2_hmac_sha256",
            "version": "2.5",
            "created_at": time.time()
        }

    def _verify_against_record(self, normalized_text: str, record: Optional[Dict[str, Any]]) -> bool:
        """
        Verifies candidate text against stored salt + PBKDF2 hash using constant-time compare.
        Evaluates canonical equivalents (digits and number-words, wake-word stripped)
        to robustly accept speech recognition variations without fuzzy matching.
        """
        if not record or not normalized_text:
            return False
        try:
            salt = bytes.fromhex(record["salt_hex"])
            stored_hash = bytes.fromhex(record["hash_hex"])
            iterations = int(record.get("iterations", 100000))

            candidates = [normalized_text] + [c for c in get_candidate_forms(normalized_text) if c != normalized_text]
            if normalized_text.upper() not in candidates:
                candidates.append(normalized_text.upper())
            if normalized_text.lower() not in candidates:
                candidates.append(normalized_text.lower())
            for cand in candidates:
                computed_hash = hashlib.pbkdf2_hmac("sha256", cand.encode("utf-8"), salt, iterations)
                if hmac.compare_digest(stored_hash, computed_hash):
                    return True
            return False
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Authorization Session & Lockout Management
    # -------------------------------------------------------------------------
    def is_locked_out(self) -> Tuple[bool, int]:
        """ Returns (is_locked, remaining_seconds) """
        if self.local_memory_service:
            is_l, rem = self.local_memory_service.is_locked_out()
            if is_l:
                return True, int(rem) + 1
        now = time.time()
        if now < self._locked_until:
            rem = int(self._locked_until - now) + 1
            return True, rem
        return False, 0

    def is_session_authorized(self) -> bool:
        """ Returns True if current temporary session is within active TTL """
        now = time.time()
        is_locked, _ = self.is_locked_out()
        if is_locked:
            return False
        if now < self._authorized_until:
            # Slide window slightly on ongoing activity up to maximum TTL
            self._last_activity_time = now
            return True
        return False

    def authorize_session(self, duration: float = 60.0):
        """ Starts or extends an authorized session """
        self._authorized_until = time.time() + duration
        self._last_activity_time = time.time()
        self._failed_attempts = 0
        self._locked_until = 0.0

    def lock_session(self):
        """ Explicitly revokes the active authorization session """
        self._authorized_until = 0.0
        self.current_state = SecurityState.IDLE
        self._temp_phrase_buffer = None
        self._temp_recovery_buffer = None
        self._pending_action = None

    def _record_failure(self) -> Tuple[str, int]:
        """ Increments failed attempts and enforces progressive lockout """
        self._failed_attempts += 1
        now = time.time()
        if self._failed_attempts in (1, 2):
            lockout = 0
            msg = "Password incorrect."
        elif self._failed_attempts == 3:
            lockout = 30
            self._locked_until = now + 30
            msg = "Too many failed attempts. Security is temporarily locked for 30 seconds."
        elif self._failed_attempts == 4:
            lockout = 60
            self._locked_until = now + 60
            msg = "Too many failed attempts. Security is temporarily locked for 60 seconds."
        else:
            lockout = 300
            self._locked_until = now + 300
            msg = "Too many failed attempts. Security is temporarily locked for 5 minutes."

        return msg, lockout

    def reset_lockout_for_tests(self):
        """ Strictly for testing: clears attempt counters and lockout timers """
        self._failed_attempts = 0
        self._locked_until = 0.0
        if self.local_memory_service:
            self.local_memory_service.lockout.reset_for_tests()

    # -------------------------------------------------------------------------
    # Direct Password Verification
    # -------------------------------------------------------------------------
    def verify_password(self, phrase: str) -> Tuple[bool, str]:
        """
        Directly verifies a spoken phrase against the stored verifier.
        Returns (success: bool, spoken_message: str).
        """
        is_locked, rem = self.is_locked_out()
        if is_locked:
            return False, f"Security is temporarily locked. Please wait {rem} seconds."

        if not self.is_configured():
            return True, "Security password is not configured."

        if self.local_memory_service and self.local_memory_service.is_password_configured():
            ok, msg, token = self.local_memory_service.authenticate_voice_transcript(phrase)
            if ok:
                self.authorize_session(self._session_ttl_seconds)
                return True, "Password verified."
            else:
                msg_fail, _ = self._record_failure()
                return False, msg_fail or msg

        norm = normalize_phrase(phrase)
        if not norm:
            msg, _ = self._record_failure()
            return False, msg

        ok = self._verify_against_record(norm, self._cached_verifier) if self._cached_verifier else False
        if not ok and hasattr(self, "vault") and self.vault and self.vault.is_setup():
            for cand in self.get_candidate_forms(phrase):
                if self.vault.authenticate(cand):
                    ok = True
                    break
        if ok:
            self.authorize_session(self._session_ttl_seconds)
            if hasattr(self, "vault") and self.vault and self.vault.is_setup():
                self.vault.sync_with_security_manager(self)
            return True, "Password verified."
        else:
            msg, _ = self._record_failure()
            return False, msg

    # -------------------------------------------------------------------------
    # Setting, Changing, Recovering & Removing Passwords
    # -------------------------------------------------------------------------
    def set_password(self, phrase: str) -> Tuple[bool, str, Optional[str]]:
        """
        Sets a new Voice Security Password and generates a one-time recovery code.
        Returns (success: bool, spoken_message: str, raw_recovery_code: Optional[str]).
        """
        norm = normalize_phrase(phrase)
        if len(norm) < 3 or len(norm.split()) < 2:
            return False, "Password too short. Please choose a private multi-word phrase with at least two words.", None

        if self.local_memory_service:
            try:
                self.local_memory_service.setup_password(norm, norm)
            except Exception:
                pass

        verifier = self._create_verifier(norm)
        # Generate clean 8-character recovery code (e.g. RC-A7F2-9K4B)
        raw_rc_part1 = secrets.token_hex(2).upper()
        raw_rc_part2 = secrets.token_hex(2).upper()
        raw_recovery_code = f"RC-{raw_rc_part1}-{raw_rc_part2}"
        rec_norm = normalize_recovery_code(raw_recovery_code)
        rec_verifier = self._create_verifier(rec_norm)

        ok_v = self._write_verifier_file(self.verifier_file, verifier)
        ok_r = self._write_verifier_file(self.recovery_file, rec_verifier)

        if ok_v and ok_r:
            self._cached_verifier = verifier
            self._cached_recovery = rec_verifier
            self.mark_onboarding_completed(True)
            self.authorize_session(self._session_ttl_seconds)
            try:
                from .log_redaction import get_global_redactor
                get_global_redactor().register_secret(norm)
                get_global_redactor().register_secret(phrase)
                get_global_redactor().register_secret(raw_recovery_code)
            except Exception:
                pass
            return True, "Sensitive password set successfully.", raw_recovery_code
        else:
            return False, "Failed to save security verifier to secure storage.", None

    def change_password(self, current_phrase: str, new_phrase: str) -> Tuple[bool, str]:
        """ Changes password, requiring valid current password """
        is_locked, rem = self.is_locked_out()
        if is_locked:
            return False, f"Security is temporarily locked. Please wait {rem} seconds."

        # Verify current password
        norm_cur = normalize_phrase(current_phrase)
        if not self._verify_against_record(norm_cur, self._cached_verifier):
            msg, _ = self._record_failure()
            return False, msg

        norm_new = normalize_phrase(new_phrase)
        if len(norm_new) < 3 or len(norm_new.split()) < 2:
            return False, "New password too short. Please use at least two words."

        if self.local_memory_service:
            try:
                self.local_memory_service.change_password(norm_cur, norm_new, norm_new)
            except Exception:
                pass

        new_verifier = self._create_verifier(norm_new)
        ok = self._write_verifier_file(self.verifier_file, new_verifier)
        if ok:
            self._cached_verifier = new_verifier
            self.lock_session()
            self.authorize_session(self._session_ttl_seconds)
            return True, "Sensitive password changed successfully."
        return False, "Failed to update security verifier."

    def reset_with_recovery_code(self, recovery_code: str, new_phrase: str) -> Tuple[bool, str, Optional[str]]:
        """
        Resets password using a valid recovery code, invalidates old recovery code,
        and generates a fresh recovery code.
        """
        is_locked, rem = self.is_locked_out()
        if is_locked:
            return False, f"Security is temporarily locked. Please wait {rem} seconds.", None

        norm_rc = normalize_recovery_code(recovery_code)
        if not self._verify_against_record(norm_rc, self._cached_recovery):
            msg, _ = self._record_failure()
            return False, msg, None

        norm_new = normalize_phrase(new_phrase)
        if len(norm_new) < 3 or len(norm_new.split()) < 2:
            return False, "New password too short. Please use at least two words.", None

        # Create new password verifier & new recovery verifier
        new_v = self._create_verifier(norm_new)
        raw_rc_part1 = secrets.token_hex(2).upper()
        raw_rc_part2 = secrets.token_hex(2).upper()
        new_raw_rc = f"RC-{raw_rc_part1}-{raw_rc_part2}"
        new_rec_norm = normalize_recovery_code(new_raw_rc)
        new_r = self._create_verifier(new_rec_norm)

        ok_v = self._write_verifier_file(self.verifier_file, new_v)
        ok_r = self._write_verifier_file(self.recovery_file, new_r)

        if ok_v and ok_r:
            if self.local_memory_service:
                try:
                    self.local_memory_service.setup_password(norm_new, norm_new)
                except Exception:
                    pass
            self._cached_verifier = new_v
            self._cached_recovery = new_r
            self.lock_session()
            self.authorize_session(self._session_ttl_seconds)
            return True, "Your Voice Security Password has been reset.", new_raw_rc
        return False, "Failed to reset security verifier.", None

    def remove_password(self, current_phrase: str) -> Tuple[bool, str]:
        """ Removes password protection after verifying current password """
        is_locked, rem = self.is_locked_out()
        if is_locked:
            return False, f"Security is temporarily locked. Please wait {rem} seconds."

        norm_cur = normalize_phrase(current_phrase)
        if not self._verify_against_record(norm_cur, self._cached_verifier):
            msg, _ = self._record_failure()
            return False, msg

        self._write_verifier_file(self.verifier_file, None)
        self._write_verifier_file(self.recovery_file, None)
        if self.local_memory_service:
            try:
                self.local_memory_service.remove_password()
            except Exception:
                pass
        self._cached_verifier = None
        self._cached_recovery = None
        self.lock_session()
        self.mark_onboarding_completed(False)
        return True, "Voice Security Password protection has been removed."

    def generate_new_recovery_code_authenticated(self) -> Tuple[bool, str, Optional[str]]:
        """ Generates a new recovery code if active session is authorized """
        if not self.is_session_authorized():
            return False, "Authorization required to generate a recovery code.", None

        raw_rc_part1 = secrets.token_hex(2).upper()
        raw_rc_part2 = secrets.token_hex(2).upper()
        new_raw_rc = f"RC-{raw_rc_part1}-{raw_rc_part2}"
        new_rec_norm = normalize_recovery_code(new_raw_rc)
        new_r = self._create_verifier(new_rec_norm)

        ok_r = self._write_verifier_file(self.recovery_file, new_r)
        if ok_r:
            self._cached_recovery = new_r
            return True, "New recovery code generated successfully.", new_raw_rc
        return False, "Failed to save new recovery code.", None

    # -------------------------------------------------------------------------
    # Policy Evaluation & High-Risk 2FA
    # -------------------------------------------------------------------------
    def get_security_level(self, intent_name: str) -> SecurityLevel:
        """ Returns the SecurityLevel for a given intent """
        return self.POLICY_MAP.get(intent_name.upper(), SecurityLevel.SAFE)

    def evaluate_live_face_2fa(self, current_faces: Optional[List[Dict[str, Any]]]) -> Tuple[bool, str, Optional[str]]:
        """
        Evaluates Live Face 2FA for High-Risk actions.
        Requires:
        - state == KNOWN
        - is_confirmed == True
        - liveness_ok == True
        - quality_ok == True
        - valid non-empty identity name
        """
        if not current_faces:
            return False, "Face 2FA required: No face detected in camera view.", None

        for face in current_faces:
            state = face.get("match_state") or face.get("state")
            is_confirmed = face.get("is_confirmed", False)
            liveness_ok = face.get("liveness_ok", True)
            quality_ok = face.get("quality_ok", True)
            name = face.get("name")

            if state == "KNOWN" and is_confirmed and liveness_ok and quality_ok and name and name != "Unknown":
                return True, f"Face 2FA verified for {name}.", name
            elif state == "KNOWN" and not liveness_ok:
                return False, "Face 2FA rejected: Liveness / anti-spoof check failed.", None
            elif state == "KNOWN" and not quality_ok:
                return False, "Face 2FA rejected: Face image quality insufficient.", None

        return False, "Face 2FA rejected: Face is unknown or unconfirmed.", None

    # -------------------------------------------------------------------------
    # Interactive Multi-Turn State Handler
    # -------------------------------------------------------------------------
    def handle_speech_input(self, user_text: str, current_faces: Optional[List[Dict]] = None) -> Optional[Dict[str, Any]]:
        """
        Handles interactive security enrollment / challenge dialogs locally.
        Returns a response dict if handled, or None if the engine should process normal intents.
        """
        if self.current_state == SecurityState.IDLE:
            return None

        clean = user_text.strip()
        norm = normalize_phrase(clean)

        # Cancel flow
        if any(w in norm for w in ["cancel", "stop", "abort", "nevermind", "exit"]):
            self.current_state = SecurityState.IDLE
            self._temp_phrase_buffer = None
            self._temp_recovery_buffer = None
            self._pending_action = None
            return {
                "handled": True,
                "spoken_response": "Security setup cancelled.",
                "action": "CANCELLED"
            }

        # 1. First-Run / Set Password Flow
        elif self.current_state == SecurityState.ENROLL_AWAIT_PHRASE:
            if len(norm) < 3 or len(norm.split()) < 2:
                return {
                    "handled": True,
                    "spoken_response": "Password too short. Please say a private phrase with at least two words.",
                    "action": "RETRY"
                }
            self._temp_phrase_buffer = norm
            self.current_state = SecurityState.ENROLL_AWAIT_REPEAT
            return {
                "handled": True,
                "spoken_response": "Please repeat your sensitive password to confirm. Repeat your password to confirm.",
                "action": "AWAIT_REPEAT"
            }

        elif self.current_state == SecurityState.ENROLL_AWAIT_REPEAT:
            if norm == self._temp_phrase_buffer:
                ok, msg, rc = self.set_password(norm)
                self.current_state = SecurityState.IDLE
                self._temp_phrase_buffer = None
                return {
                    "handled": True,
                    "spoken_response": "Sensitive password set successfully." if ok else "Failed to save password.",
                    "action": "SET_SUCCESS" if ok else "SET_FAILED",
                    "recovery_code": rc
                }
            else:
                self.current_state = SecurityState.IDLE
                self._temp_phrase_buffer = None
                return {
                    "handled": True,
                    "spoken_response": "The passwords did not match. Please try again.",
                    "action": "MISMATCH"
                }

        # 2. Change Password Flow
        elif self.current_state == SecurityState.CHANGE_AWAIT_CURRENT:
            if not self._verify_against_record(norm, self._cached_verifier):
                msg, _ = self._record_failure()
                self.current_state = SecurityState.IDLE
                return {
                    "handled": True,
                    "spoken_response": msg,
                    "action": "AUTH_FAILED"
                }
            self.current_state = SecurityState.CHANGE_AWAIT_NEW
            return {
                "handled": True,
                "spoken_response": "Current password verified. Please say your new sensitive password.",
                "action": "AWAIT_NEW"
            }

        elif self.current_state == SecurityState.CHANGE_AWAIT_NEW:
            if len(norm) < 3 or len(norm.split()) < 2:
                return {
                    "handled": True,
                    "spoken_response": "New password is too short. Please say a phrase with at least two words.",
                    "action": "RETRY"
                }
            self._temp_phrase_buffer = norm
            self.current_state = SecurityState.CHANGE_AWAIT_REPEAT
            return {
                "handled": True,
                "spoken_response": "Please repeat your new sensitive password. Repeat your new password to confirm.",
                "action": "AWAIT_REPEAT"
            }

        elif self.current_state == SecurityState.CHANGE_AWAIT_REPEAT:
            if norm == self._temp_phrase_buffer:
                new_v = self._create_verifier(norm)
                ok = self._write_verifier_file(self.verifier_file, new_v)
                self._cached_verifier = new_v if ok else self._cached_verifier
                self.current_state = SecurityState.IDLE
                self._temp_phrase_buffer = None
                self.authorize_session(self._session_ttl_seconds)
                return {
                    "handled": True,
                    "spoken_response": "Sensitive password changed successfully." if ok else "Failed to save password.",
                    "action": "CHANGE_SUCCESS" if ok else "CHANGE_FAILED"
                }
            else:
                self.current_state = SecurityState.IDLE
                self._temp_phrase_buffer = None
                return {
                    "handled": True,
                    "spoken_response": "The passwords did not match. Please try again.",
                    "action": "MISMATCH"
                }

        # 3. Remove Password Flow
        elif self.current_state == SecurityState.REMOVE_AWAIT_CURRENT:
            if not self._verify_against_record(norm, self._cached_verifier):
                msg, _ = self._record_failure()
                self.current_state = SecurityState.IDLE
                return {
                    "handled": True,
                    "spoken_response": msg,
                    "action": "AUTH_FAILED"
                }
            self.current_state = SecurityState.REMOVE_AWAIT_CONFIRM
            return {
                "handled": True,
                "spoken_response": "Removing your Voice Security Password will disable protection for sensitive features. Say 'yes confirm' to proceed.",
                "action": "AWAIT_CONFIRM"
            }

        elif self.current_state == SecurityState.REMOVE_AWAIT_CONFIRM:
            if "yes" in norm or "confirm" in norm:
                self._write_verifier_file(self.verifier_file, None)
                self._write_verifier_file(self.recovery_file, None)
                self._cached_verifier = None
                self._cached_recovery = None
                self.lock_session()
                self.mark_onboarding_completed(False)
                self.current_state = SecurityState.IDLE
                return {
                    "handled": True,
                    "spoken_response": "Voice Security Password protection has been removed.",
                    "action": "REMOVE_SUCCESS"
                }
            else:
                self.current_state = SecurityState.IDLE
                return {
                    "handled": True,
                    "spoken_response": "Password removal cancelled.",
                    "action": "CANCELLED"
                }

        # 4. Challenge Verification for Pending Protected / High-Risk Action
        elif self.current_state == SecurityState.CHALLENGE_AWAIT_PHRASE:
            ok = self._verify_against_record(norm, self._cached_verifier) if self._cached_verifier else False
            if not ok and hasattr(self, "vault") and self.vault and self.vault.is_setup():
                for cand in self.get_candidate_forms(speech_text):
                    if self.vault.authenticate(cand):
                        ok = True
                        break
            if not ok:
                msg, _ = self._record_failure()
                self.current_state = SecurityState.IDLE
                self._pending_action = None
                return {
                    "handled": True,
                    "spoken_response": msg,
                    "action": "AUTH_FAILED"
                }

            # Passed voice passphrase check
            self.authorize_session(self._session_ttl_seconds)
            if hasattr(self, "vault") and self.vault and self.vault.is_setup():
                self.vault.sync_with_security_manager(self)
            pending = self._pending_action
            self.current_state = SecurityState.IDLE
            self._pending_action = None

            # Check if pending action is High-Risk and requires Face 2FA
            if pending and pending.get("level") == SecurityLevel.HIGH_RISK and self.is_face_2fa_required():
                face_ok, face_msg, face_user = self.evaluate_live_face_2fa(current_faces)
                if not face_ok:
                    return {
                        "handled": True,
                        "spoken_response": f"Voice password verified, but {face_msg}",
                        "action": "2FA_FACE_FAILED"
                    }

            return {
                "handled": True,
                "spoken_response": "Password verified.",
                "action": "EXECUTE_PENDING",
                "pending_action": pending
            }

        return None

    def start_challenge(self, pending_action: Dict[str, Any]) -> str:
        """ Initiates an authorization challenge for a protected or high-risk action """
        self.current_state = SecurityState.CHALLENGE_AWAIT_PHRASE
        self._pending_action = pending_action
        self._pending_action_time = time.time()
        return "Please speak your voice password."

    def start_enrollment(self) -> str:
        """ Starts interactive voice enrollment """
        self.current_state = SecurityState.ENROLL_AWAIT_PHRASE
        self._temp_phrase_buffer = None
        return "Please set your sensitive password. Let's set your sensitive password: say a private phrase with at least two words."

    def start_change(self) -> str:
        """ Starts interactive voice change """
        if not self.is_configured():
            return self.start_enrollment()
        self.current_state = SecurityState.CHANGE_AWAIT_CURRENT
        self._temp_phrase_buffer = None
        return "Please say your current sensitive password."

    def start_remove(self) -> str:
        """ Starts interactive voice removal """
        if not self.is_configured():
            return "Voice Security Password is not configured."
        self.current_state = SecurityState.REMOVE_AWAIT_CURRENT
        return "Please say your current security password to remove protection."
