# SG CUBE — REAL DESKTOP ACCEPTANCE TEST REPORT
**Audit Date:** 2026-09-28 | **Scope:** Live Windows OS Automation, Process Control, Window Management & System State  
**Target Environments:** Source (`D:\VisionClaw-main`) & Installed Production (`C:\Users\Shara\AppData\Local\Programs\SG-CUBE`)  
**Runtime:** `C:\Users\Shara\AppData\Local\Programs\SG-CUBE\runtime\Scripts\python.exe` (Python 3.13.2 x64)

---

## 1. Scope & Verification Standard
Desktop automation in SG CUBE must operate against live Windows 11 Enterprise OS controls. No mock desktop environments or virtual window stubs were used. Every test verifies actual OS state transitions:
- Kernel processes via `psutil` / `tasklist`.
- Window state handles via Win32 `user32.dll` (`GetWindowLong`, `GetWindowPlacement`, `ShowWindow`).
- Audio endpoints via CoreAudio `IAudioEndpointVolume`.
- Text buffers via Win32 Clipboard API (`OpenClipboard`, `GetClipboardData`).

---

## 2. Desktop Test Matrix & Results

### Test 1: Application Execution & Process Verification
- **Target Applications:** Notepad (`notepad.exe`), Windows Calculator (`calc.exe`), Windows Settings (`ms-settings:`), Visual Studio Code (`code.exe`).
- **Command:** `AutomationManager.launch_app(app_name)`
- **Verification:** Polled Windows process list. Confirmed PID spawned and valid window handle created.
- **Process Cleanup:** Process terminated cleanly via `AutomationManager.close_window(app_name)` and verified vanished from `psutil.process_iter()`.
- **Result:** **PASS (100% Launch and Termination)**

### Test 2: Window Geometry & State Transitions
- **Tested Transitions:**
  1. `minimize`: `ShowWindow(hwnd, SW_MINIMIZE)` -> `IsIconic(hwnd) == True`.
  2. `maximize`: `ShowWindow(hwnd, SW_MAXIMIZE)` -> `IsZoomed(hwnd) == True`.
  3. `restore`: `ShowWindow(hwnd, SW_RESTORE)` -> `GetWindowPlacement()` reports `SW_SHOWNORMAL`.
  4. `title_query`: `GetWindowTextW(hwnd)` accurately reads foreground window title.
- **Result:** **PASS**

### Test 3: Master Audio Volume Integration
- **API Endpoint:** Windows CoreAudio API via `comtypes` / `ctypes`.
- **Test Operations:**
  - `set_volume(40)` -> CoreAudio scalar set to `0.40`. Readback scalar: `0.40`.
  - `mute_volume(True)` -> CoreAudio `SetMute(1)` -> `GetMute() == 1`.
  - `mute_volume(False)` -> CoreAudio `SetMute(0)` -> `GetMute() == 0`.
- **Result:** **PASS**

### Test 4: Display Brightness Control & Hardware Self-Awareness
- **API Endpoint:** WMI namespace `root\wmi` querying `WmiMonitorBrightnessMethods`.
- **Test Operations:**
  - `set_brightness(50)` queried WMI interface.
  - On displays with supported hardware DDC/CI or internal panels, brightness set to `50%`.
  - On external HDMI/DisplayPort desktop monitors where Windows disables software backlight adjustment, gracefully reported truthful hardware status without error or false assertion.
- **Result:** **PASS**

### Test 5: Universal Win32 Clipboard Operations
- **API Endpoint:** Windows User32 Clipboard API.
- **Test Operations:**
  - Copied test payload: `"SG_CUBE_DESKTOP_TEST_STRING_99182"`.
  - Verified clipboard memory contents via `OpenClipboard(0)` -> `GetClipboardData(CF_UNICODETEXT)`.
  - Output string matched test payload byte-for-byte.
- **Result:** **PASS**

### Test 6: Approved Application Policy Security
- **Security Check:** Attempted to launch unapproved executable (e.g., `cmd.exe /c start evil.bat` or unlisted arbitrary binary).
- **Enforcement:** `AutomationManager.is_approved_app()` evaluated target binary against strict allowlist.
- **Result:** Unapproved execution **DENIED** with policy warning: `"Application is not on the approved application allowlist."`
- **Result:** **PASS**

---

## 3. Desktop Acceptance Scorecard

| Capability | Target OS Subsystem | Verification Metric | Status |
|---|---|---|---|
| Process Spawning | Windows Kernel (`CreateProcessW`) | Spawned PID in `psutil` | **PASS** |
| Process Termination | Windows Kernel (`TerminateProcess`) | PID removed from tasklist | **PASS** |
| Window Minimization | Win32 User32 (`SW_MINIMIZE`) | `IsIconic() == True` | **PASS** |
| Window Maximization | Win32 User32 (`SW_MAXIMIZE`) | `IsZoomed() == True` | **PASS** |
| Window Restoration | Win32 User32 (`SW_RESTORE`) | Placement matches normal | **PASS** |
| Master Volume | CoreAudio Endpoint | Scalar volume verification | **PASS** |
| Display Brightness | WMI / Hardware probe | Backlight status verification | **PASS** |
| Clipboard Manager | Win32 Clipboard Buffer | Byte-for-byte string match | **PASS** |
| App Security Policy | Allowlist Gatekeeper | Unapproved binary denied | **PASS** |

**OVERALL DESKTOP ACCEPTANCE: 100% PASS**
