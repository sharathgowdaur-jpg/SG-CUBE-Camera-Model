# SG CUBE — FEATURE FAILURE LOG
**Audit Date:** 2026-09-28 | **Scope:** Live Hardware, Desktop Automation & Security Testing  
**Target Environments:** Source (`D:\VisionClaw-main`) & Installed Production (`C:\Users\Shara\AppData\Local\Programs\SG-CUBE`)

---

## 1. Overview of Failure Hunting
During rigorous live end-to-end testing against real Windows 11 hardware, bare-metal audio, and real desktop APIs, five (5) distinct real-world defects were discovered and cataloged. None of these were theoretical or mocked issues; all were reproduced with actual user inputs and verified against OS state.

---

## 2. Catalog of Real-World Failures

### Issue #1: Windows Settings App Launch `FileNotFoundError`
- **Component:** `AutomationManager.launch_app("settings")`
- **Severity:** HIGH (Blocked essential OS settings access)
- **Reproducible Trigger:** Voice query `"open settings"`
- **Observed Behavior:** Application crashed with `FileNotFoundError: [WinError 2] The system cannot find the file specified: 'SystemSettings.exe'`.
- **Root Cause:** On modern Windows 10/11, Settings is a packaged UWP application. Direct invocation via `subprocess.Popen(["SystemSettings.exe"])` fails unless invoked through the Windows protocol shell URI or explorer.exe host.

---

### Issue #2: Clipboard Regex Greedy Token Swallowing & Casing Loss
- **Component:** `CommandRouter.route_command()`
- **Severity:** MEDIUM (Corrupted text copied to clipboard)
- **Reproducible Trigger:** Voice query `"copy Hello World to clipboard"`
- **Observed Behavior:** Clipboard buffer received `"hello world to clipboard"` or stripped text due to case-flattening (`cmd.lower()`) and non-anchored trailing token matching.
- **Root Cause:** Command router normalized the entire user transcript to lowercase before regex extraction, stripping original string capitalization. Additionally, greedy regex patterns failed to strip trailing control tokens like `" to clipboard"`.

---

### Issue #3: Compound Command Word-Boundary Preemption
- **Component:** `CommandRouter.route_command()` vs `CompoundTaskPlanner.is_compound_request()`
- **Severity:** HIGH (Multi-step requests aborted after step 1)
- **Reproducible Trigger:** Voice command `"open notepad, type hello, select all, copy that, then close notepad"`
- **Observed Behavior:** CommandRouter matched `"open notepad"` and immediately dispatched a single-app launch, ignoring the subsequent comma-separated instructions.
- **Root Cause:** In the routing pipeline, `route_command()` was called before `planner.is_compound_request()`. Because `"open notepad"` matched early, the compound task planner was never reached.

---

### Issue #4: Attribute Mismatch in Multi-Step Task Execution
- **Component:** `AutomationManager.step_exec()`
- **Severity:** HIGH (Compound execution runtime crash)
- **Reproducible Trigger:** Executing decomposed task sequence
- **Observed Behavior:** `AttributeError: 'AutomationManager' object has no attribute 'command_router'`.
- **Root Cause:** `AutomationManager` initialized its router reference as `self.router`, but internal method `step_exec` attempted to invoke `self.command_router.route_command()`.

---

### Issue #5: Non-Interactive Window Handle Fallback Failure
- **Component:** `SystemControl.minimize_window()` / `maximize_window()`
- **Severity:** MEDIUM (Window automation failed when terminal ran non-interactively)
- **Reproducible Trigger:** Running automated test suites via background processes or headless sessions
- **Observed Behavior:** `GetForegroundWindow()` returned `0` (NULL), causing window commands to fail with `"No active window found"`.
- **Root Cause:** Background or non-interactive execution does not maintain an active GUI foreground window focus. The method lacked an `EnumWindows` heuristic fallback to find the top-level visible user application window.

---

## 3. Summary of Failure Resolution Status
All five (5) issues have been fully resolved, regression-tested, and verified on both Source and Installed environments.
