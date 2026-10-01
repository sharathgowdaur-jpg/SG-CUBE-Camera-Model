# SG CUBE — 12-FEATURE DEFECT & FAILURE LOG

**Date:** September 28, 2026  
**Component:** Real-World Voice Pipeline, System Controls, Router & Planner  
**Methodology:** Defensive Red-Team QA & Root Cause Analysis

---

## Failure 1: Windows Settings App Launch Failure (`FileNotFoundError`)
* **Severity:** High
* **Symptom:** Voice command `"open settings"` failed with `FileNotFoundError: [WinError 2] The system cannot find the file specified`.
* **Root Cause Analysis:** In `assistive/automation_manager.py`, `AutomationActionDefinition` for `settings` specified candidate `SystemSettings.exe`. In modern Windows 10/11, `SystemSettings.exe` is a UWP package located in `SystemApps` and is not exposed on system PATH. Attempting `subprocess.Popen(["SystemSettings.exe"], shell=False)` unconditionally failed because candidate fallback iteration was not implemented in `_exec_open_app()`.
* **Code Fix Applied:**
  1. Updated `_exec_open_app()` in `assistive/automation_manager.py` to recognize `defn.name == "settings"` and utilize `os.startfile("ms-settings:")` natively.
  2. Implemented resilient multi-candidate loop over `defn.executable_candidates` (trying `control.exe` if needed) instead of failing on the first index.
* **Verification:** Re-executed `"open settings"`. Spoken response: `"I've opened Windows Settings."` Confirmed `SystemSettings` window appeared. Status: **RESOLVED**.

---

## Failure 2: Clipboard Copy String Greediness & Case Degradation
* **Severity:** Medium
* **Symptom:** Voice command `"copy 'SG-CUBE-TEST-VALUE-42' to clipboard"` copied `'sg-cube-test-value-42' to clipboard` onto clipboard instead of `'SG-CUBE-TEST-VALUE-42'`.
* **Root Cause Analysis:** 
  1. In `assistive/command_router.py:820`, regex pattern had alternative 1 `(?:copy\s+.*(?:to\s+clipboard\s*)?:?\s*(.+))` before alternative 2 `(?:copy\s+(.+)\s+to\s+clipboard)`. Because `(?:to\s+clipboard\s*)?` was optional, alternative 1 greedily matched through the end of the sentence including the phrase `"to clipboard"`.
  2. Regex was matched against `clean_text` (`text.lower().strip()`), losing the original casing of the payload.
* **Code Fix Applied:**
  1. Re-ordered and anchored clipboard patterns in `assistive/command_router.py`:
     `r'^(?:please\s+)?(?:copy\s+(?:the\s+)?(?:following\s+)?text\s*:\s*(.+)|copy\s+(?:to\s+clipboard\s*:\s*|to\s+the\s+clipboard\s*:\s*)(.+)|copy\s+(.+?)\s+(?:in|on|to|into)\s+(?:the\s+|my\s+)?clipboard|copy\s+text\s+(.+))$'`
  2. Matched against original `text` using `flags=re.IGNORECASE` and stripped surrounding quotation marks.
* **Verification:** Re-executed query. Clipboard content verified via `SystemControl.get_clipboard_text()` as exact string `'SG-CUBE-TEST-VALUE-42'`. Status: **RESOLVED**.

---

## Failure 3: Compound Command Parser Preemption
* **Severity:** High
* **Symptom:** Voice command `"set volume to 30 and check diagnostics"` only set the volume and ignored `"check diagnostics"`.
* **Root Cause Analysis:** In `assistive/command_router.py`, Section 29 A (`vol_set_match`) was placed before `COMPOUND_TASK`. Because `vol_set_match` used `\b` word boundary instead of string anchor, it matched `"set volume to 30"` and discarded the remaining tokens. Additionally, `IMPERATIVE_VERBS` in `task_planner.py` lacked verbs `"set"`, `"check"`, `"turn"`, `"mute"`, `"read"`.
* **Code Fix Applied:**
  1. Moved `COMPOUND_TASK` priority check to the very beginning of Section 29 in `assistive/command_router.py`.
  2. Expanded `IMPERATIVE_VERBS` in `assistive/task_planner.py` to include `"set"`, `"check"`, `"turn"`, `"mute"`, `"unmute"`, `"read"`, `"scroll"`.
  3. Added conjunction lookahead `\s+and\s+(?=(?:` + `|`.join(IMPERATIVE_VERBS) + `)\b)` in `decompose_task()`.
* **Verification:** Re-executed `"set volume to 30 and check diagnostics"`. Command decomposed into Step 1 (`set volume to 30`) and Step 2 (`check diagnostics`). Both executed sequentially. Spoken summary: `"Completed all 2 steps successfully."` Status: **RESOLVED**.

---

## Failure 4: Router Reference Mismatch in Compound Step Executor
* **Severity:** Critical
* **Symptom:** Compound task planner halted at step 1 with `"Task encountered an error at step 1."`
* **Root Cause Analysis:** In `assistive/vision_engine.py:2360`, the inner `step_exec` closure referenced `self.command_router.route_command(cmd_str)`. In `VisionEngine.__init__`, the router attribute is named `self.router`, not `self.command_router`. This caused an `AttributeError`.
* **Code Fix Applied:**
  1. Corrected reference in `assistive/vision_engine.py:2360` to `self.router.route_command(cmd_str)`.
  2. Added alias `self.command_router = self.router` in `VisionEngine.__init__` for complete API robustness.
* **Verification:** Re-tested compound execution. Steps executed seamlessly without exceptions. Status: **RESOLVED**.

---

## Failure 5: Non-Interactive Window State Handling
* **Severity:** Medium
* **Symptom:** `SystemControl.minimize_active_window()` returned `False` (`"Unable to minimize window."`) when executed in background automation test runners.
* **Root Cause Analysis:** In automated or headless subprocesses, `ctypes.windll.user32.GetForegroundWindow()` can return `0` (NULL handle) if focus has not transitioned to the newly spawned window.
* **Code Fix Applied:**
  1. Updated `minimize_active_window()` and `maximize_active_window()` in `assistive/system_control.py` to fall back to `EnumWindows` and identify the topmost visible top-level application window if `GetForegroundWindow()` returns 0.
  2. Added targeted window methods `find_and_focus_window(app_title)` and `find_and_minimize_window(app_title)`.
* **Verification:** Window minimize, maximize, and app switching passed reliably under both interactive and test runner executions. Status: **RESOLVED**.
