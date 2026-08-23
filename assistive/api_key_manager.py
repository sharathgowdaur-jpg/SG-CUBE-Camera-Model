import os
import sys
import json
import time
import base64
import google.genai as genai
from typing import Optional, Tuple, List, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_PREF_DIR = os.path.join(PROJECT_ROOT, "data", "user_preferences")

def _resolve_pref_dir(pref_dir: Optional[str] = None) -> str:
    if pref_dir and pref_dir not in ("data/user_preferences", "user_preferences", "data"):
        return os.path.abspath(pref_dir)
    env_dir = os.getenv("SGCUBE_USER_DATA")
    if env_dir:
        p = os.path.join(os.path.abspath(env_dir), "user_preferences")
        os.makedirs(p, exist_ok=True)
        return p
    if os.name == 'nt':
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            p1 = os.path.join(local_appdata, "SG CUBE", "data", "user_preferences")
            if os.path.exists(os.path.join(local_appdata, "SG CUBE", "data")):
                os.makedirs(p1, exist_ok=True)
                return p1
            p2 = os.path.join(local_appdata, "Programs", "SG-CUBE", "data", "user_preferences")
            if os.path.exists(os.path.join(local_appdata, "Programs", "SG-CUBE", "data")):
                os.makedirs(p2, exist_ok=True)
                return p2
    return DEFAULT_PREF_DIR

def _obfuscate(text: str) -> str:
    if not text:
        return ""
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")

def _deobfuscate(encoded: str) -> str:
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""

class APIKeyManager:
    """
    Secure Desktop Multi-API-Key Manager for Gemini Live AI.
    Supports up to 3 Gemini API keys with priority ordering, automatic failover,
    temporary failure cooldown, masked representations, and isolated connection testing.
    """

    def __init__(self, pref_dir: str = None):
        self.pref_dir = _resolve_pref_dir(pref_dir)
        os.makedirs(self.pref_dir, exist_ok=True)
        self.cred_file = os.path.join(self.pref_dir, "multi_api_credentials.dat")
        self.legacy_file = os.path.join(self.pref_dir, "api_credential.dat")

        self.keys: Dict[int, str] = {1: "", 2: "", 3: ""}
        self.priority: List[int] = [1, 2, 3]
        self.active_key_num: Optional[int] = None
        self.key_cooldowns: Dict[int, float] = {}  # key_num -> expiry_timestamp
        self.cooldown_duration: float = 60.0       # 60s cooldown for failed keys

        self.load_all_credentials()

    def load_all_credentials(self):
        """ Loads all saved API keys and priority settings securely from disk """
        if os.path.exists(self.cred_file):
            try:
                with open(self.cred_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    keys_data = data.get("keys", {})
                    for k_str, val in keys_data.items():
                        try:
                            k_num = int(k_str)
                            if k_num in (1, 2, 3):
                                self.keys[k_num] = _deobfuscate(val)
                        except Exception:
                            pass

                    prio_data = data.get("priority", [1, 2, 3])
                    if isinstance(prio_data, list) and all(p in (1, 2, 3) for p in prio_data):
                        self.priority = prio_data
            except Exception as e:
                print(f"[API-KEY-ERROR] Error loading multi-key file: {e}")

        # Migration / fallback to single legacy key or environment variable
        if not any(self.keys.values()):
            env_key = os.getenv("GEMINI_API_KEY")
            if env_key and not env_key.startswith("your_key") and len(env_key.strip()) > 10:
                self.keys[1] = env_key.strip()
            elif os.path.exists(self.legacy_file):
                try:
                    with open(self.legacy_file, "r", encoding="utf-8") as f:
                        key = _deobfuscate(f.read().strip())
                        if key and len(key) > 10:
                            self.keys[1] = key
                except Exception:
                    pass

    def save_all_credentials(self) -> bool:
        """ Saves all keys and priority settings obfuscated to disk """
        try:
            data = {
                "keys": {str(k): _obfuscate(v) for k, v in self.keys.items()},
                "priority": self.priority
            }
            with open(self.cred_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            print("[API-KEY] Multi-API-Key credentials saved successfully.")
            return True
        except Exception as e:
            print(f"[API-KEY-ERROR] Error saving multi-key credential file: {e}")
            return False

    def set_key(self, key_num: int, api_key: str) -> bool:
        """ Sets a specific API key (1, 2, or 3) and persists to disk """
        if key_num not in (1, 2, 3):
            return False
        clean_key = api_key.strip() if api_key else ""
        self.keys[key_num] = clean_key
        # Clear any cooldown on key update
        if key_num in self.key_cooldowns:
            del self.key_cooldowns[key_num]
        return self.save_all_credentials()

    def clear_key(self, key_num: int) -> bool:
        """ Clears a specific key slot (1, 2, or 3) """
        if key_num in (1, 2, 3):
            self.keys[key_num] = ""
            if key_num in self.key_cooldowns:
                del self.key_cooldowns[key_num]
            if self.active_key_num == key_num:
                self.active_key_num = None
            return self.save_all_credentials()
        return False

    def set_priority(self, new_priority: List[int]) -> bool:
        """ Updates key priority order (e.g. [2, 1, 3]) """
        if isinstance(new_priority, list) and set(new_priority) == {1, 2, 3}:
            self.priority = new_priority
            return self.save_all_credentials()
        return False

    def get_masked_key(self, key_num: int = 1) -> str:
        """ Returns safe masked key representation (e.g. '••••••••••••a1b2') """
        key = self.keys.get(key_num, "")
        if not key:
            return "Not Configured"
        if len(key) <= 8:
            return "••••••••"
        return f"••••••••••••{key[-4:]}"

    def get_active_key_label(self) -> str:
        """ Returns safe active key indicator string (e.g. 'Gemini • Key 1') """
        if self.active_key_num in (1, 2, 3) and self.keys.get(self.active_key_num):
            return f"Gemini • Key {self.active_key_num}"
        return "Gemini Disconnected"

    def mark_key_failed(self, key_num: int):
        """ Temporarily marks a failed key as unavailable for cooldown period """
        if key_num in (1, 2, 3):
            self.key_cooldowns[key_num] = time.time() + self.cooldown_duration
            print(f"[API-KEY-FAILOVER] Key {key_num} marked temporarily unavailable (cooldown 60s).")
            if self.active_key_num == key_num:
                self.active_key_num = None

    def get_active_key(self) -> Optional[Tuple[int, str]]:
        """
        Returns currently active (key_num, key_value) in priority order,
        excluding keys under active cooldown.
        """
        now = time.time()
        # Clean expired cooldowns
        expired = [k for k, exp in self.key_cooldowns.items() if now >= exp]
        for k in expired:
            del self.key_cooldowns[k]

        # 1. Return current active key if still valid
        if self.active_key_num and self.keys.get(self.active_key_num) and (self.active_key_num not in self.key_cooldowns):
            return self.active_key_num, self.keys[self.active_key_num]

        # 2. Iterate through priority order for next available key
        for k_num in self.priority:
            k_val = self.keys.get(k_num, "").strip()
            if k_val and len(k_val) > 10 and k_num not in self.key_cooldowns:
                self.active_key_num = k_num
                os.environ["GEMINI_API_KEY"] = k_val
                print(f"[API-KEY] Activated Gemini Key {k_num}")
                return k_num, k_val

        self.active_key_num = None
        return None

    def get_next_failover_key(self, current_failed_num: int) -> Optional[Tuple[int, str]]:
        """ Marks current key as failed and returns next available key in priority order """
        self.mark_key_failed(current_failed_num)
        return self.get_active_key()

    def get_active_api_key(self) -> str:
        """ Returns the active API key string or empty string """
        key_tuple = self.get_active_key()
        if key_tuple:
            return key_tuple[1]
        return ""

    def load_api_key(self) -> str:
        """ Loads and returns primary active API key """
        return self.get_active_api_key()

    def test_connection(self, api_key: str) -> Tuple[bool, str]:
        """ Tests an individual Gemini API key using isolated test query without modifying active production key """
        if not api_key or not api_key.strip():
            return False, "API key cannot be empty."

        clean_key = api_key.strip()
        if len(clean_key) < 15 or clean_key.startswith("your_key"):
            return False, "The API key format is invalid."

        try:
            client = genai.Client(api_key=clean_key)
            models_iter = client.models.list_models()
            _ = next(iter(models_iter), None)
            print("[API-KEY] Connection test successful. Key validated with Gemini server.")
            return True, "Connection successful. Gemini API key is valid."
        except Exception as e:
            err_msg = str(e).lower()
            if "connect" in err_msg or "network" in err_msg or "resolution" in err_msg or "timeout" in err_msg:
                return False, "Could not reach Gemini server. Please check your network connection."
            else:
                return False, f"The API key could not be verified. Invalid key."

    # Backwards compatibility methods
    def load_api_key(self) -> Optional[str]:
        res = self.get_active_key()
        return res[1] if res else None

    def save_api_key(self, api_key: str) -> bool:
        return self.set_key(1, api_key)

    def remove_api_key(self) -> bool:
        return self.clear_key(1)
