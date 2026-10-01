# SG CUBE — End-to-End Security & Protected Memory Data Flow

## 1. Overview & Threat Model

This document maps the complete data flow of SG CUBE's security and protected memory pipeline across all 12 runtime stages.

**Target Threat Model**:
- **Attacker Profile**: Physical bystander / secondary person near the workstation.
- **Attacker Capabilities**: Speaking commands, issuing wake words, asking memory queries, inspecting local network ports (e.g. WebSocket port 8000), examining SQLite databases on disk (`conversations.db`, `memories.db`), or exploiting conversational context turns.
- **Objective**: Ensure that protected memories (passwords, PINs, credentials, banking info, confidential notes) CANNOT be exfiltrated or disclosed to unauthorized persons under any circumstance.

---

## 2. The 12-Stage Data Flow Architecture

```
[Stage 1: Audio Capture] (Microphone / PyAudio / sounddevice)
           │ (Raw PCM 16kHz Mono)
           ▼
[Stage 2: Audio Arbitration & VAD] (Silero VAD / AudioArbitrator)
           ├────────────────────────────┬────────────────────────────┐
           ▼ (Gemini Active)            ▼ (Security Challenge)       ▼ (Challenge Complete)
     Gemini Live WS            Gemini Muted/Disconnected        Local Mic Re-engaged
                                        │ (Raw PCM)
                                        ▼
[Stage 3: Local Speech Recognition] (faster-whisper / Silero offline STT)
                                        │ (Plaintext User Speech Turn)
                                        ▼
[Stage 4: Intent Classification & Routing] (VisionEngine._execute_intent, MemoryManager, SensitiveDataDetector)
           ├────────────────────────────────────────┬────────────────────────────────────────┐
           ▼ (Public / Non-Sensitive)               ▼ (Credential / Forbidden)               ▼ (Protected / Vault)
      Normal Memory / Gemini                  Hard Rejection / Error                     Vault Challenge Gate
           │                                                                                 │
           │                                                                                 ▼
[Stage 5: Authentication Gate] ◄─────────────────────────────────────────────────────────────┘
           │ (SingleUseAuthToken / PasswordVerifier / Argon2id / LockoutManager)
           ├────────────────────────────┬────────────────────────────┐
           ▼ (Auth Failure)             ▼ (Lockout Triggered)        ▼ (Auth Success - 1x Token)
     Access Denied               Backoff Delay / Audio Alert         Proceed to Cryptographic Vault
                                                                     │
                                                                     ▼
[Stage 6: Cryptographic Engine] (LocalMemoryCryptoEngine / AES-256-GCM / DPAPI Master Key)
                                                                     │ (Decrypted Plaintext Secret)
                                                                     ▼
[Stage 7: Plaintext Handling in Engine] (VisionEngine: resp = f"Here is your protected information: ...")
                                                                     │
                                        ┌────────────────────────────┴───────────────────────────┐
                                        ▼                                                        ▼
[Stage 8: In-RAM Context Tracking] (ConversationContext)                 [Stage 9: Audio Output & Local TTS]
  Sanitized / Masked Turn Reference                                       Offline SAPI5 Speech Synthesis
                                        │                                                        │
                                        └────────────────────────────┬───────────────────────────┘
                                                                     │
                                                                     ▼
[Stage 10: GUI Event Queue] (gui_queue: TRANSCRIPT_AI / TRANSCRIPT_ASSISTIVE)
                                                                     │
                                        ┌────────────────────────────┴───────────────────────────┐
                                        ▼                                                        ▼
[Stage 11: Frontend WebSocket Broadcast]                                 [Stage 12: Persistent History DB]
  bridge_server.py (Port 8000)                                            conversations.db (SQLite + FTS5)
  *MUST BE REDACTED/MASKED*                                               *MUST BE FILTERED/BLOCKED*
```

---

## 3. Deep-Dive Stage Analysis

### Stage 1: Audio Capture
- **Component**: `AudioService`, PyAudio, sounddevice.
- **Input**: 16kHz 16-bit Mono PCM raw microphone stream.
- **Plaintext Exposure**: None (raw audio bytes in memory buffer).
- **Security Boundary**: Local workstation audio hardware.

### Stage 2: Audio Arbitration & VAD
- **Component**: `assistive/audio_arbitrator.py`, Silero VAD.
- **Function**: Manages microphone ownership between Gemini Live streaming WebSocket and local offline security challenge handlers.
- **Critical Control**: When `enter_security_challenge()` is invoked:
  1. Gemini Live microphone feed is immediately muted/suppressed via `return_to_gemini(False)`.
  2. Spoken passwords and passphrases bypass external cloud APIs entirely.
  3. Audio stream is redirected strictly to the local in-process STT engine.

### Stage 3: Local Speech Recognition (STT)
- **Component**: `faster-whisper`, `SpeechRecognizer`.
- **Input**: Audio PCM chunks captured during security state.
- **Output**: Transcribed text string (e.g., `"silver river moon"` or `"ATM PIN is 4827"`).
- **Plaintext Exposure**: Local string variable in current frame.

### Stage 4: Intent Classification & Routing
- **Component**: `assistive/vision_engine.py`, `assistive/memory_manager.py`, `assistive/secure_vault/sensitive_data_detector.py`.
- **Classification Rules**:
  1. **Category C (Authentication Secrets / Passwords)**: Blocked from regular memory; routed to Secure Vault or rejected outright.
  2. **Category B (Sensitive Personal Info / PINs / Cards / SSN / Aadhaar / PAN)**: Gated behind authentication; routed strictly to `LocalMemoryService` / `SecureVaultController`.
  3. **Category A (General Facts / Preferences / Locations)**: Saved in `memories.db` (unencrypted SQLite).
- **Vulnerability Found & Patched**: Plain `memory_manager.py` previously missed raw `"pin"` or `"ATM PIN"` because it lacked `SensitiveDataDetector` integration, allowing unformatted PINs to leak into Category A.

### Stage 5: Authentication Gate & Challenge
- **Component**: `assistive/local_memory_v2/authentication_gate.py`, `PasswordVerifier`, `LockoutManager`.
- **Mechanism**:
  - Verification uses PBKDF2/Argon2id hashing.
  - Upon successful authentication, a cryptographically random, ephemeral `SingleUseAuthToken` (UUIDv4 with 30s TTL) is issued.
  - Token consumption is atomic: once consumed by one vault read/write, it is invalidated immediately (`token.consume() -> False`).
  - Progressive lockout: 3 failed attempts result in progressive backoff lockout (5s -> 30s -> 300s).

### Stage 6: Cryptographic Engine & Storage
- **Component**: `assistive/local_memory_v2/crypto_engine.py`, `SecureVaultController`.
- **Encryption**: AES-256-GCM with unique 96-bit IV per record and 128-bit authentication tag.
- **Key Hierarchy**: Master key derived via Argon2id + protected at rest using Windows DPAPI (`CryptProtectData`).
- **Disk Persistence**: `vault.db` and `local_memory_v2.db` store strictly ciphertext, IV, tag, and key hashes. No plaintext secrets touch disk.

### Stage 7: Plaintext Handling in Engine
- **Component**: `assistive/vision_engine.py` (`_execute_intent`).
- **Operation**: Following single-use token consumption, the decrypted record (e.g., `"4827"`) is formatted:
  `resp = f"Here is your protected information: {recalled}"`.
- **Plaintext Exposure**: Resides temporarily in memory for local audio readback.

### Stage 8: In-RAM Context Tracking
- **Component**: `assistive/conversation_context.py` (`ConversationContext`).
- **Mechanism**: Tracks conversation state and turn history.
- **Critical Control**: Protected recall turns must NOT store raw secret values in entity locations or conversational memory buffers to prevent indirect conversational extraction.

### Stage 9: Audio Output & Local TTS
- **Component**: `visionclaw_gui.py` (`_speak_local_response`), SAPI5 / Windows Speech API.
- **Function**: Spoken locally to the authorized user sitting in front of the device.

### Stage 10: GUI Event Queue
- **Component**: `gui_queue` (`Queue`).
- **Messages**: `TRANSCRIPT_ASSISTIVE`, `TRANSCRIPT_AI`.
- **Data Flow**: Carries status and dialogue banners to the main GUI thread.

### Stage 11: Frontend WebSocket Broadcast
- **Component**: `bridge_server.py` (Port 8000).
- **Vulnerability Found & Patched**: Decrypted protected information was previously forwarded directly to WebSocket clients (`TRANSCRIPTION` and `NEW_MESSAGE`). Any client on the network could read decrypted secrets.
- **Hardening**: Mask protected responses as `"[Protected Information Disclosed Locally]"` before broadcasting over WebSocket.

### Stage 12: Persistent History Database
- **Component**: `assistive/conversation_history.py` (`conversations.db`, tables `messages` and `messages_fts`).
- **Vulnerability Found & Patched**: Assistant responses (`"Here is your protected information: ..."`) bypassed `is_sensitive_info()` regexes and were logged into SQLite and the full-text search index in plaintext.
- **Hardening**: Explicit detection and blocking of all protected disclosure patterns, vault intents, and sensitive data regexes.
