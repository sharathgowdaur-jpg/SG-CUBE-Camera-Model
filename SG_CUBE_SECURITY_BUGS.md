# SG CUBE — Vulnerability Ledger & Defensive Audit Report

## Executive Summary
This document registers the confirmed security vulnerabilities identified in the SG CUBE protected memory and security pipeline during the real-world physical bystander threat model audit.

---

### BUG-SEC-01: Decrypted Protected Memory Plaintext Leak into `conversations.db` and FTS Index
- **Severity**: **CRITICAL**
- **Impact**: Any secret, password, or PIN recalled by an authorized user is written in plaintext to `data/history/conversations.db` (both `messages` table and `messages_fts` virtual full-text index). An attacker with local read access or using conversational follow-up history queries can extract the secret without knowing the password.
- **Affected Components**:
  - `assistive/conversation_history.py` (lines 12-39, lines 141-168)
  - `visionclaw_gui.py` (lines 15758, 16098)
  - `assistive/vision_engine.py` (line 1090)
- **Root Cause**:
  1. `assistive/vision_engine.py` formats recalled secrets as `resp = f"Here is your protected information: {recalled}"`.
  2. `visionclaw_gui.py` calls `self.engine.history.add_message(..., "assistant", resp)` with no `intent` parameter (defaults to `"GENERAL"`).
  3. `is_sensitive_info()` checks for specific keywords like `password`, `ssn`, `bank`, but does NOT match the disclosure prefix `Here is your protected information:` or arbitrary secrets (e.g. door codes, locker keys, notes).
- **Proof of Concept**:
  ```python
  from assistive.conversation_history import is_sensitive_info
  resp = "Here is your protected information: My door code is 9988."
  print(is_sensitive_info(resp))  # Returned False! Stored in SQLite!
  ```
- **Remediation**:
  1. In `assistive/conversation_history.py`, explicitly identify any text containing `Here is your protected information:` or starting with protected disclosure patterns, and block logging.
  2. In `visionclaw_gui.py`, pass `intent="VAULT_RECALL"` and replace the logged message with `"[Protected Information Disclosed Locally]"`.

---

### BUG-SEC-02: Plaintext Leakage of Decrypted Protected Data Over WebSocket Port 8000
- **Severity**: **HIGH**
- **Impact**: Decrypted vault contents are broadcast in plaintext JSON payloads over WebSocket port 8000 (`TRANSCRIPTION` and `NEW_MESSAGE` events) to any connected web client or LAN eavesdropper.
- **Affected Components**:
  - `bridge_server.py` (lines 84-97)
  - `visionclaw_gui.py` (lines 15746, 16078)
- **Root Cause**:
  `bridge_server.py` broadcasts `TRANSCRIPT_AI` and `TRANSCRIPT_ASSISTIVE` messages verbatim to all connected WebSocket clients. No check or redaction was performed on security-sensitive or protected messages.
- **Proof of Concept**:
  Connecting to `ws://localhost:8000/ws` while a user asks SG CUBE to recall a protected secret causes the client to receive:
  `{"type": "TRANSCRIPTION", "text": "SG CUBE: Here is your protected information: 4827"}`
- **Remediation**:
  1. In `bridge_server.py`, sanitize outgoing messages: if text contains protected prefixes or sensitive patterns, redact text to `"[Protected Information Disclosed Locally]"`.
  2. In `visionclaw_gui.py`, ensure queue payloads destined for remote broadcast are sanitized before enqueuing.

---

### BUG-SEC-03: Unformatted Numeric PINs and Financial Identifiers Bypass Vault Classification
- **Severity**: **HIGH**
- **Impact**: A user saying `"Remember my ATM PIN is 4827"` or `"Remember my door PIN is 1234"` has their secret saved into unencrypted `memories.db` instead of the cryptographic vault.
- **Affected Components**:
  - `assistive/memory_manager.py` (lines 15-28, 33-51)
- **Root Cause**:
  `CREDENTIAL_KEYWORDS` contained `"pin number"` but omitted `"pin"`, `"atm pin"`, `"door pin"`. Furthermore, `is_credential_secret()` and `is_sensitive_personal_info()` did not call `SensitiveDataDetector.is_sensitive()`, causing deterministic PIN pattern detection to be bypassed.
- **Proof of Concept**:
  ```python
  from assistive.memory_manager import is_credential_secret, is_sensitive_personal_info
  from assistive.secure_vault.sensitive_data_detector import SensitiveDataDetector
  q = "Remember my ATM PIN is 4827"
  print(is_credential_secret(q))          # False
  print(is_sensitive_personal_info(q))    # False
  print(SensitiveDataDetector.is_sensitive(q)) # True
  ```
- **Remediation**:
  Integrate `SensitiveDataDetector` into `is_credential_secret()` and `is_sensitive_personal_info()`, and expand keyword patterns to include `\b(?:atm\s*pin|door\s*pin|pin|upi\s*pin)\b`.

---

### BUG-SEC-04: 60-Second Sliding Authorization Window Allows Bystander Exfiltration
- **Severity**: **HIGH**
- **Impact**: If `per_request_auth` is `False` (the default when `SGCUBE_PER_REQUEST_AUTH` is unset), a single password entry unlocks all vault and protected memory operations for 60 seconds. A physical bystander can speak `"What is my bank password?"` within that window and obtain the secret without authentication.
- **Affected Components**:
  - `assistive/vision_engine.py` (lines 155-162, 1056-1058)
- **Root Cause**:
  In `vision_engine.py`, `per_request_auth` defaulted to `False` unless explicitly set in constructor or environment. In this mode, `self.security.is_session_authorized()` was used to auto-mint `SingleUseAuthToken` instances on the fly without user interaction.
- **Remediation**:
  Enforce `self.per_request_auth = True` as the unconditional default for all instances of `VisionEngine`. Every protected memory read, write, or recall must strictly consume an individually authorized single-use token.

---

### BUG-SEC-05: In-RAM Context Leakage in Conversation State Active Object
- **Severity**: **MEDIUM**
- **Impact**: When recalling protected memory, the full plaintext response was stored in `self.context.set_active_object(location_description=resp)`. Subsequent conversational queries could inadvertently reference or echo this information.
- **Affected Components**:
  - `assistive/vision_engine.py` (lines 1109-1113)
- **Root Cause**:
  `entity` and `location_description` assignment in `vision_engine.py` did not check if the current turn was a protected recall operation.
- **Remediation**:
  Do not attach protected recall responses to active object tracking in `ConversationContext`.
