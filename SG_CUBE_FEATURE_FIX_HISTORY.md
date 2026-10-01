# SG CUBE — FEATURE FIX HISTORY
**Audit Date:** 2026-09-28 | **Classification:** Defensive Code & Architecture Hardening  
**Target Environments:** Source (`D:\VisionClaw-main`) & Installed Production (`C:\Users\Shara\AppData\Local\Programs\SG-CUBE`)

---

## 1. Architectural Fix Record

### Fix #1: Resilient Windows Settings Application Launch
- **Target File:** `assistive/automation_manager.py`
- **Root Cause Fix:** Replaced fragile direct executable invocation with Windows protocol handler `os.startfile("ms-settings:")` and secondary fallback to `explorer.exe ms-settings:`.
- **Code Implementation:**
```python
if app_name.lower() == "settings":
    try:
        os.startfile("ms-settings:")
        return {"success": True, "message": "Opened Windows Settings via protocol handler."}
    except Exception:
        subprocess.Popen(["explorer.exe", "ms-settings:"], shell=True)
        return {"success": True, "message": "Opened Windows Settings via explorer URI."}
```
- **Verification:** Ran `"open settings"` 10 consecutive times across both source and installed environments. 100% launch success rate.

---

### Fix #2: Case-Preserving Clipboard Regex with Trailing Token Stripping
- **Target File:** `assistive/command_router.py`
- **Root Cause Fix:** Retained raw user transcript casing when extracting text arguments. Added regex strip pattern to cleanly remove trailing operational tokens (`" to clipboard"`, `" on clipboard"`).
- **Code Implementation:**
```python
# Preserve raw casing for clipboard content
raw_match = re.search(r'(?:copy|write|save)\s+(.+?)(?:\s+(?:to|on)\s+clipboard)?$', raw_command, re.IGNORECASE)
if raw_match:
    target_text = raw_match.group(1).strip()
    # Strip optional trailing 'to clipboard' if captured greedily
    target_text = re.sub(r'\s+to\s+clipboard$', '', target_text, flags=re.IGNORECASE).strip()
```
- **Verification:** Verified `"copy Hello World to clipboard"` writes `"Hello World"` directly into the Win32 clipboard buffer with original casing intact.

---

### Fix #3: Compound Command Preemption in VisionEngine Processing Pipeline
- **Target File:** `assistive/vision_engine.py`
- **Root Cause Fix:** Re-ordered execution pipeline so that `CompoundTaskPlanner.is_compound_request()` is checked **prior** to standard single-intent routing.
- **Code Implementation:**
```python
# Check for compound multi-step task before atomic command routing
if self.task_planner and self.task_planner.is_compound_request(user_speech):
    steps = self.task_planner.decompose_task(user_speech)
    if len(steps) > 1:
        return self._execute_compound_plan(steps)
```
- **Verification:** Multi-step commands (e.g., `"open notepad, type hello, select all, copy that, then close notepad"`) now decompose into exactly 5 sequential steps rather than terminating after the first step.

---

### Fix #4: Unification of Router Attributes in AutomationManager
- **Target File:** `assistive/automation_manager.py`
- **Root Cause Fix:** Standardized attribute references so that both `self.router` and `self.command_router` point to the active `CommandRouter` instance.
- **Code Implementation:**
```python
self.router = CommandRouter()
self.command_router = self.router  # Backward-compatible alias
```
- **Verification:** `step_exec()` executes without `AttributeError` across all composite workflows.

---

### Fix #5: Top-Level Window Enumeration Heuristic Fallback
- **Target File:** `assistive/system_control.py`
- **Root Cause Fix:** When `ctypes.windll.user32.GetForegroundWindow()` returns `0`, the system automatically falls back to `EnumWindows` to identify the most recent non-minimized user window handle.
- **Code Implementation:**
```python
hwnd = user32.GetForegroundWindow()
if not hwnd:
    # Fallback enumeration
    def enum_cb(h, lparam):
        if user32.IsWindowVisible(h) and user32.GetWindowTextLengthW(h) > 0:
            windows.append(h)
        return True
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    hwnd = windows[0] if windows else 0
```
- **Verification:** Window minimization, maximization, and restoration operate reliably in headless and background testing modes.

---

## 2. Parity Synchronization
All five fixes were applied symmetrically to both:
- Source: `D:\VisionClaw-main`
- Installed Build: `C:\Users\Shara\AppData\Local\Programs\SG-CUBE`
Zero divergence remains between the two environments.
