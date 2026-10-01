# SG CUBE vs rofiperlungoding/jarvis: Security Architecture Comparison & Mapping

## 1. Executive Summary

This document evaluates the security and authorization architecture of `rofiperlungoding/jarvis` against the existing SG CUBE security components. 

**Core Directive**:
- SG CUBE's **Secure Memory V2** (AES-256-GCM + Windows DPAPI Master Key + Argon2id/PBKDF2 Password Verification) is cryptographically superior for credential protection and **MUST BE PRESERVED**.
- `rofiperlungoding/jarvis` provides an elegant, structured **Authorization Policy**, a formal **Confirmation Protocol**, a strict append-only **Audit Log** with ordering invariants, and a process-wide **Log Redaction Filter**. These components will be **ADAPTED** to provide SG CUBE with a unified, authoritative decision point.

---

## 2. Component Mapping & Classification Matrix

| Component / Subsystem | Current SG CUBE Mechanism | Reference (JARVIS) Mechanism | Classification | Evidence & Justification |
|:---|:---|:---|:---:|:---|
| **Cryptographic Storage Engine** | `LocalMemoryCryptoEngine` (AES-256-GCM, 96-bit IV, 128-bit tag, DPAPI-wrapped VMK) | ChromaDB vector store + `WindowsDPAPI.protect` base64 document blobs | **KEEP (SG CUBE)** | SG CUBE's authenticated AES-256-GCM encryption with per-record random IV and tag prevents semantic embedding leakage and tampering. JARVIS calculates plaintext embeddings before encrypting, which leaks semantic approximations into vector space. |
| **Authentication & Gate** | `AuthenticationGate` with `SingleUseAuthToken` (30s TTL, single consumption) | None (Assumes logged-in OS user is authentic) | **KEEP (SG CUBE)** | JARVIS has no user authentication or voice password; any physical bystander can speak commands. SG CUBE's single-use tokens and voice password verification are critical for physical bystander defense. |
| **Speaker Biometrics** | ECAPA-TDNN speaker verification + Silero VAD local challenge | None | **KEEP (SG CUBE)** | Prevents voice replay and voice imitation by unauthorized physical bystanders. |
| **Sensitive Data Detection** | `SensitiveDataDetector` (Regex, Luhn algorithm for cards, Verhoeff for Aadhaar, PAN, PINs) | `PIIRedactor` (Regex scrubber for standard PII) | **KEEP (SG CUBE)** | SG CUBE's detector has algorithmic validation (Luhn + Verhoeff) and covers international/Indian banking and identity cards. |
| **Authorization Policy Layer** | Dispersed checks across `vision_engine.py`, `command_router.py`, and `automation_manager.py` | Unified `AuthorizationPolicy` with `SAFE` vs `DESTRUCTIVE` classification and allowlist | **ADAPT (from JARVIS)** | SG CUBE needs a single authoritative policy layer (`AuthorizationPolicy`) that acts as the sole decision point for memory reads, writes, deletions, and system control actions. |
| **Action Confirmation Protocol** | Ad-hoc voice challenge in `vision_engine.py` | Two-phase `confirm()` with spoken summary, affirmative parsing, and strict denial defaults | **ADAPT (from JARVIS)** | Formalizes spoken confirmation prompts, negation priority (`no` overrides `yes`), and timeout fail-closed semantics for destructive/protected operations. |
| **Append-Only Audit Log** | Simple text-based `security_audit.log` | Append-only SQLite `AuditLog` with `INTEGER PRIMARY KEY AUTOINCREMENT` and strict ID precedence | **ADAPT (from JARVIS)** | Upgrading SG CUBE's audit logger to an append-only SQLite schema guarantees tamper evidence and proves `confirmation_requested.id < executed.id`. |
| **Process-Wide Log Redaction** | Ad-hoc masking in GUI event queue | `LogRedactionFilter` attached to root `logging.Logger` scrubbing substrings and exception tracebacks | **ADAPT (from JARVIS)** | Prevents accidental logging of passwords, tokens, or decrypted secrets by any internal module or third-party dependency. |
| **Memory Architecture** | Strict duality: `memories.db` (Public SQLite) vs `vault.db` (AES-256-GCM Vault) | Monolithic ChromaDB storing chat turns and facts | **DO NOT USE (JARVIS)** | ChromaDB adds heavy binary dependencies and slow startup (~6s) without providing cryptographic segregation between public facts and high-security secrets. |
| **Network Egress Auditing** | None | Outbound request interceptor logging `network_egress` to audit log | **ADAPT (from JARVIS)** | Enhances visibility of outbound network calls to cloud providers (e.g., Gemini API). |

---

## 3. Detailed Component Classifications

### 1. `crypto_engine.py` & `secure_vault_controller.py`: **KEEP**
- **Rationale**: The reference project delegates all encryption to `win32crypt.CryptProtectData` on base64 strings in ChromaDB. In contrast, SG CUBE uses a random 256-bit AES Vault Master Key (VMK) protected by DPAPI, encrypting records with AES-256-GCM. Changing passwords does not re-encrypt the database.
- **Action**: Retain intact.

### 2. `authentication_gate.py` & `password_verifier.py`: **KEEP**
- **Rationale**: The reference repository does not support passwords or single-use authorization tokens. SG CUBE's `SingleUseAuthToken` ensures that unlocking one secret never leaves a persistent window open.
- **Action**: Retain intact; integrate into the new `AuthorizationPolicy`.

### 3. `AuthorizationPolicy` (`src/jarvis/security/authorization.py`): **ADAPT**
- **Rationale**: Currently, SG CUBE's decision logic for what requires authorization is spread between `vision_engine.py`, `command_router.py`, and `automation_manager.py`. By introducing `assistive/authorization_policy.py`, all requests pass through a single choke point.
- **Policy Classes**:
  - `NORMAL_MEMORY_READ`: Allowed without challenge.
  - `NORMAL_MEMORY_WRITE`: Allowed without challenge.
  - `PROTECTED_MEMORY_READ`: Requires Speaker Verification + Voice Password + Single-Use Token.
  - `PROTECTED_MEMORY_WRITE`: Requires Speaker Verification + Voice Password + Single-Use Token.
  - `PROTECTED_MEMORY_DELETE`: Requires Speaker Verification + Voice Password + Single-Use Token.
  - `SYSTEM_CONTROL` / `DESTRUCTIVE_ACTION`: Requires user confirmation dialog (or allowlist match).
  - `NETWORK_OPERATION`: Monitored and audited.

### 4. `AuditLog` (`src/jarvis/security/audit_log.py`): **ADAPT**
- **Rationale**: SG CUBE's current audit log is a simple text file (`security_audit.log`). Adopting JARVIS's SQLite append-only schema (`data/security/audit.sqlite`) allows structured queries, tamper resistance, and enforces that confirmation requests are committed *before* prompts are spoken.
- **Action**: Build `assistive/security_audit_log.py` wrapping SQLite with strict monotonicity.

### 5. `LogRedactionFilter` (`src/jarvis/security/log_redaction.py`): **ADAPT**
- **Rationale**: Prevents any logging call (`logger.info`, `logger.error`, `print`) from inadvertently echoing passwords or decrypted secrets in logs or exception tracebacks.
- **Action**: Implement `assistive/log_redaction.py` and register it on application startup.

### 6. ChromaDB Vector Store: **DO NOT USE**
- **Rationale**: ChromaDB computes embeddings on plaintext before storing ciphertext, introducing a semantic side-channel. Furthermore, ChromaDB is unnecessary for high-precision exact key retrieval and creates dependency bloat.
- **Action**: Exclude completely.

---

## 4. Architectural Target Pipeline

```
User Voice / Text Request
           │
           ▼
     Local VAD / STT
           │ (Plaintext User Speech Turn)
           ▼
     Intent Router (VisionEngine / CommandRouter)
           │ (Categorized Action Request)
           ▼
┌─────────────────────────────────────────────────────────────┐
│             SG CUBE AUTHORIZATION POLICY                    │
│           (The Single Authoritative Gatekeeper)             │
└─────────────────────────────────────────────────────────────┘
           │
           ├────────────────────────────┬────────────────────────────┐
           ▼ (NORMAL / SAFE)            ▼ (DESTRUCTIVE / SYSTEM)     ▼ (PROTECTED MEMORY)
     Dispatch Directly          Two-Phase Confirmation        Zero-Trust Gate:
                                (Audit: requested < executed) 1. Speaker Verification (ECAPA-TDNN)
                                                              2. Voice Password Verification
                                                              3. Single-Use Auth Token Issuance
                                                                       │
                                                                       ▼
                                                              Cryptographic Vault
                                                              (AES-256-GCM Decrypt in RAM)
                                                                       │
                                                                       ▼
                                                              Local SAPI5 TTS Output Only
                                                                       │
                                                                       ▼
                                                              Destroy Plaintext in RAM & Lock
```

This hybrid architecture preserves all of SG CUBE's superior cryptography and biometric security while gaining JARVIS's centralized policy authorization, audit ordering, and process-wide log redaction.
