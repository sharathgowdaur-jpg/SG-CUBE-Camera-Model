# SG CUBE — HARDCORE DEFENSIVE RED-TEAM BUG LEDGER

**Inspection Target:** `D:\VisionClaw-main` & `C:\Users\Shara\AppData\Local\Programs\SG-CUBE`  
**Execution Runtime:** `C:\Users\Shara\AppData\Local\Programs\SG-CUBE\runtime\Scripts\python.exe` (Python 3.13.9 Win32)  
**Date:** September 28, 2026  
**Status:** All 9 Discovered Bugs Fixed, Regression-Tested, and Bit-for-Bit Synchronized (SHA-256 Verified)

---

## Executive Summary

During the hardcore defensive red-team campaign across 28 feature domains of SG CUBE, a comprehensive suite of 42 adversarial tests was created and executed. Real failures were intentionally hunted across voice perception, natural language wake detection, system control boundaries, clipboard payloads, compound multi-step execution, and Windows 11 packaged process lifecycles.

A total of **9 real bugs** were identified, root-caused, repaired, verified with zero user data loss, and synchronized with the installed application build.

---

## Detailed Bug Ledger

### BUG-001: TTS Normalizer Markdown Strikethrough Syntax Leakage
- **Severity:** Low (Audio Quality / Perception)
- **Component:** `assistive/tts_normalizer.py`
- **Root Cause:** Regex normalization stripped bold (`**`, `__`), italics (`*`, `_`), and backticks (`` ` ``), but lacked a rule for markdown strikethrough (`~~text~~`). When an LLM produced strikethrough text, the raw tildes were spoken as punctuation ("tilde tilde") or distorted speech cadence.
- **Fix:** Added `re.sub(r'~~([^~]+)~~', r'\1', s)` to the markdown cleanup stage in `TTSNormalizer.clean_markdown_for_speech()`.
- **Regression Test:** `tests/redteam_voice_and_stt.py::TestTTSNormalizationRedTeam::test_adversarial_markdown_stripping`
- **Verification Status:** PASS (Verified in 13/13 Voice Suite).

---

### BUG-002: WakeWordMatcher Lacked Instance `__init__` and `matches()` API
- **Severity:** Medium (Interface Compatibility)
- **Component:** `wake_word_matcher.py`
- **Root Cause:** `WakeWordMatcher` was authored purely with `@classmethod` methods (`evaluate`), but calling code and automated test runners attempted instantiation (`WakeWordMatcher()`) and invoked `matcher.matches(text)`.
- **Fix:** Implemented instance `__init__(self)` and `matches(self, text)` delegating directly to `cls.evaluate(text)`.
- **Regression Test:** `tests/redteam_voice_and_stt.py::TestWakeWordRedTeam::test_wake_variations_exact_and_case`
- **Verification Status:** PASS (Verified in 13/13 Voice Suite).

---

### BUG-003: Wake Word Rejection on Long Utterances with Natural Greetings
- **Severity:** High (Voice Perception Failure)
- **Component:** `wake_word_matcher.py`
- **Root Cause:** In `evaluate()`, utterances longer than 4 words (`word_count > 4`) were discarded as non-wake speech unless they strictly started with target tokens. Utterances beginning with natural greetings such as `"hello hey sg cube can you help me"` were rejected because `"hello"` preceded `"hey sg cube"`.
- **Fix:** Added greeting token stripping (`hello`, `hi`, `hey`, `okay`, `ok`, `excuse me`, `please`) and hotword phrase containment check (`if any(t in norm_text for t in [...])`) for utterances exceeding 4 words.
- **Regression Test:** `tests/redteam_voice_and_stt.py::TestWakeWordRedTeam::test_wake_with_embedded_phrases`
- **Verification Status:** PASS (Verified in 13/13 Voice Suite).

---

### BUG-004: Wake Word Rejection on "wake up cube please"
- **Severity:** Medium (Voice Trigger Coverage)
- **Component:** `wake_word_matcher.py`
- **Root Cause:** `"wake up cube please"` contains 4 words. In `evaluate()`, partial token combination matching was restricted to `word_count <= 3`, and `PREFIX_TOKENS` omitted `"wake"`. As a result, valid wake phrases involving "wake up" failed detection.
- **Fix:** Added `"wake"` to `PREFIX_TOKENS`, increased partial combination matching limit to `word_count <= 4`, and added explicit `"wake up" in norm_text` detection.
- **Regression Test:** `tests/redteam_voice_and_stt.py::TestWakeWordRedTeam::test_wake_with_embedded_phrases`
- **Verification Status:** PASS (Verified in 13/13 Voice Suite).

---

### BUG-005: Clipboard PowerShell Fallback Command Injection & Syntax Failure
- **Severity:** High (System Reliability & Security)
- **Component:** `assistive/system_control.py`
- **Root Cause:** In `SystemControl.copy_text_to_clipboard()`, the PowerShell fallback executed:
  `subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value \"{text}\""])`.
  If `text` contained quotes, apostrophes, shell metacharacters, or newlines, PowerShell threw a syntax parse error or failed to set the clipboard.
- **Fix:** Switched from command line string interpolation to stdin piping:
  `subprocess.run(["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"], input=text.encode("utf-8"))`.
  Also hardened `get_clipboard_text()` with UTF-8 decoding and `errors="replace"`.
- **Regression Test:** `tests/redteam_desktop_and_computer_use.py::TestSystemControlRedTeam::test_clipboard_adversarial_payloads`
- **Verification Status:** PASS (Verified in 17/17 Desktop Suite).

---

### BUG-006: System Volume and Brightness Non-Numeric Type Exception Crash
- **Severity:** Medium (Input Validation / Stability)
- **Component:** `assistive/system_control.py`
- **Root Cause:** `set_volume()` and `set_brightness()` executed `int(target_percent)` without exception handling. If malformed string inputs (`"invalid"`) or `None` were passed, unhandled `ValueError` or `TypeError` crashed the caller.
- **Fix:** Wrapped conversions in `try: target_percent = int(round(float(target_percent))) except (ValueError, TypeError): return False, ...` gracefully returning status without crashing.
- **Regression Test:** `tests/redteam_desktop_and_computer_use.py::TestSystemControlRedTeam::test_volume_bounds_and_invalid_inputs`
- **Verification Status:** PASS (Verified in 17/17 Desktop Suite).

---

### BUG-007: Missing Ordinal Resolution and Dict Access on Interaction Artifacts
- **Severity:** Medium (Conversational Context Degradation)
- **Component:** `assistive/interaction_artifacts.py`
- **Root Cause:** `InteractionArtifactCache` lacked a natural language resolver for phrases like `"open the second result"` or `"summarize the 1st link"`. Additionally, `ArtifactItem` objects were not subscriptable with `.get()`, causing `AttributeError` in caller routines expecting dict-like access.
- **Fix:** Implemented `resolve_ordinal_reference(phrase, artifact_type)` supporting ordinal numerals and word phrases (`first`, `second`, `3rd`, `last`), and implemented `__getitem__` and `get()` methods on `ArtifactItem`.
- **Regression Test:** `tests/redteam_desktop_and_computer_use.py::TestWebToolsAndArtifactsRedTeam::test_interaction_artifact_ordinal_retrieval`
- **Verification Status:** PASS (Verified in 17/17 Desktop Suite).

---

### BUG-008: CompoundTaskPlanner Overwrote Prior Cancellation / Abort Requests
- **Severity:** High (User Safety & Control)
- **Component:** `assistive/task_planner.py`
- **Root Cause:** At the start of `execute_plan()`, the planner unconditionally executed `self._interrupted = False`. If a user issued a STOP/CANCEL command or invoked `planner.abort()` prior to execution dispatch, the abort flag was wiped out, causing steps to execute regardless.
- **Fix:** Removed unconditional `self._interrupted = False` from `execute_plan()`, created an explicit `reset()` method, and verified immediate abortion if interrupted before or during step execution.
- **Regression Test:** `tests/redteam_security_memory_chaos.py::TestOfflinePerceptionAndCancellationRedTeam::test_planner_immediate_cancellation_reactivity`
- **Verification Status:** PASS (Verified in 12/12 Security Suite).

---

### BUG-009: Desktop Automation Notepad Process Lifecycle Incompatibility with Windows 11
- **Severity:** Medium (OS Compatibility / Flaky Test)
- **Component:** `tests/test_real_desktop_jarvis_suite.py` & `tests/redteam_desktop_and_computer_use.py`
- **Root Cause:** In Windows 11, `notepad.exe` in `C:\Windows\System32` acts as a short-lived UWP/MSIX launcher stub. It activates the packaged Notepad app and terminates its own process handle with returncode 0 immediately. Tests asserting `proc.poll() is None` failed despite Notepad visibly running on screen.
- **Fix:** Modernized lifecycle testing to verify active window title and state via `SystemControl.get_active_window_title()`, followed by clean termination via `close_active_window()` and PowerShell process sweeping to guarantee zero orphan background processes.
- **Regression Test:** `tests/test_real_desktop_jarvis_suite.py::test_real_desktop_notepad_scenario` and `tests/redteam_desktop_and_computer_use.py::TestRealWindowsDesktopAppLifecycleRedTeam::test_real_notepad_launch_focus_and_clean_termination`
- **Verification Status:** PASS (Verified in 19/19 Desktop Hardware Suite and 17/17 Desktop Suite).

---

## Synchronization Parity (SHA-256 Hashes)

| File | Source Hash (`D:\VisionClaw-main`) | Target Hash (`C:\Users\...\SG-CUBE`) | Match |
|---|---|---|---|
| `assistive/tts_normalizer.py` | `5954aa0b0fed89f0...60cfdad4` | `5954aa0b0fed89f0...60cfdad4` | YES |
| `wake_word_matcher.py` | `abafb024793910ff...03264750` | `abafb024793910ff...03264750` | YES |
| `assistive/system_control.py` | `5c5ff413d794612c...ccf02290` | `5c5ff413d794612c...ccf02290` | YES |
| `assistive/interaction_artifacts.py` | `ae79e85088c00cbd...d2fe5673` | `ae79e85088c00cbd...d2fe5673` | YES |
| `assistive/task_planner.py` | `6f0d946f0f02341d...a4e8a48e` | `6f0d946f0f02341d...a4e8a48e` | YES |
