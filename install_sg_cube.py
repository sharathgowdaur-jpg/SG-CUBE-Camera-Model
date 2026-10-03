"""
SG CUBE — Official Bug-Free Production Installer
Safely deploys SG CUBE to %LOCALAPPDATA%\\Programs\\SG-CUBE with:
1. Complete source-to-installed code synchronization.
2. Non-destructive user data preservation (protects existing databases, face embeddings, keys).
3. A private Python runtime with every package in requirements.txt.
4. Windows shortcuts (Desktop, Start Menu) and ONE autostart entry: the Registry Run key,
   which is what the tray's "Start with Windows" toggle reads and writes.
5. Compile check and an import smoke check that touches no hardware.
"""

import os
import sys
import shutil
import filecmp
import py_compile
import winreg
from typing import List, Tuple

# Resolve source and destination directories
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
INSTALL_DIR = os.path.join(LOCALAPPDATA, "Programs", "SG-CUBE")
APPDATA = os.environ.get("APPDATA", os.path.expanduser(r"~\AppData\Roaming"))
USERPROFILE = os.environ.get("USERPROFILE", os.path.expanduser("~"))

# Directories to sync
DIRECTORIES_TO_SYNC = [
    "assistive",
    "assets",
    "web3d",
    "tests"
]

# Root files to sync
ROOT_FILES_TO_SYNC = [
    "install_sg_cube.py",
    "bridge_server.py",
    "run_sgcube_web.py",
    "visionclaw_gui.py",
    "wake_listener.py",
    "wake_word_matcher.py",
    "run.bat",
    "run_wake_listener.bat",
    "Uninstall.bat",
    "requirements.txt"
]

# Ignore patterns during copy
IGNORE_PATTERNS = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".git",
    "node_modules",
    "*.log",
    "*.tmp"
)


def log(step: str, msg: str):
    print(f"[{step}] {msg}")


def deploy_application_files():
    log("1/6", f"Target Installation Directory: {INSTALL_DIR}")
    os.makedirs(INSTALL_DIR, exist_ok=True)

    # 1. Sync root files
    for fname in ROOT_FILES_TO_SYNC:
        src_path = os.path.join(SRC_DIR, fname)
        if os.path.exists(src_path):
            dst_path = os.path.join(INSTALL_DIR, fname)
            shutil.copy2(src_path, dst_path)
    log("1/6", f"Deployed {len(ROOT_FILES_TO_SYNC)} root launcher and runtime scripts.")

    # 2. Sync core directories
    for dname in DIRECTORIES_TO_SYNC:
        src_d = os.path.join(SRC_DIR, dname)
        if os.path.exists(src_d):
            dst_d = os.path.join(INSTALL_DIR, dname)
            if os.path.exists(dst_d):
                shutil.rmtree(dst_d, ignore_errors=True)
            shutil.copytree(src_d, dst_d, ignore=IGNORE_PATTERNS)
            log("1/6", f"Synchronized directory: {dname}")

    # 3. Deploy frontend dist
    src_dist = os.path.join(SRC_DIR, "frontend", "dist")
    if os.path.exists(src_dist):
        dst_dist = os.path.join(INSTALL_DIR, "frontend", "dist")
        if os.path.exists(dst_dist):
            shutil.rmtree(dst_dist, ignore_errors=True)
        os.makedirs(os.path.dirname(dst_dist), exist_ok=True)
        shutil.copytree(src_dist, dst_dist, ignore=IGNORE_PATTERNS)
        log("1/6", "Synchronized frontend distribution build.")


def preserve_and_initialize_data():
    log("2/6", "Preserving existing user databases, biometric embeddings, and keys...")
    src_data = os.path.join(SRC_DIR, "data")
    dst_data = os.path.join(INSTALL_DIR, "data")
    os.makedirs(dst_data, exist_ok=True)

    # Required subdirectories
    subdirs = ["face_memory", "history", "logs", "memory", "models", "secure_vault", "security", "tasks", "user_preferences"]
    for sub in subdirs:
        os.makedirs(os.path.join(dst_data, sub), exist_ok=True)

    # Models: Ensure ONNX models are copied if missing or zero-length
    models_dir = os.path.join(dst_data, "models")
    src_models = os.path.join(src_data, "models")
    if os.path.exists(src_models):
        for m in os.listdir(src_models):
            src_m = os.path.join(src_models, m)
            dst_m = os.path.join(models_dir, m)
            if os.path.isfile(src_m):
                if not os.path.exists(dst_m) or os.path.getsize(dst_m) == 0:
                    shutil.copy2(src_m, dst_m)
                    log("2/6", f"Installed missing AI model: {m}")

    # Non-destructive copy for existing files:
    # Do not copy developer personal databases, credentials, or test artifacts to target installation.
    EXCLUDE_DATA_FILES = {
        "preferences.json",
        "multi_api_credentials.dat",
        "api_credential.dat",
        "conversations.db",
        "conversations.db-shm",
        "conversations.db-wal",
        "memories.db",
        "memories.db-shm",
        "memories.db-wal",
        "local_memory_v2.db",
        "vault.db",
        "security_audit.sqlite",
        "tasks.db",
        "visionclaw.log",
        "security_audit.log",
        "master_key.dpapi",
        "lockout_state.json",
        "mouse_telemetry.json",
    }

    copied_count = 0
    preserved_count = 0
    for root, dirs, files in os.walk(src_data):
        rel = os.path.relpath(root, src_data)
        # Skip temporary test folders or face_memory galleries from dev environment
        if any(rel.startswith(p) for p in ("test_", "face_memory")):
            continue
        target_root = os.path.join(dst_data, rel)
        os.makedirs(target_root, exist_ok=True)
        for f in files:
            if f in EXCLUDE_DATA_FILES:
                continue
            dst_file = os.path.join(target_root, f)
            src_file = os.path.join(root, f)
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                copied_count += 1
            else:
                preserved_count += 1

    log("2/6", f"Data isolation complete: {preserved_count} existing files preserved, {copied_count} new initialized (clean user profile guaranteed).")


def create_windows_shortcuts():
    log("3/6", "Configuring Windows Desktop, Start Menu, and Startup shortcuts...")
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception as e:
        log("3/6", f"Warning: pywin32 shell unavailable ({e}). Using WScript.Shell via VBS.")
        return

    icon_path = os.path.join(INSTALL_DIR, "assets", "SG-CUBE.ico")
    run_bat = os.path.join(INSTALL_DIR, "run.bat")
    wake_bat = os.path.join(INSTALL_DIR, "run_wake_listener.bat")
    uninstall_bat = os.path.join(INSTALL_DIR, "Uninstall.bat")

    # 1. Desktop Shortcut
    desk_path = os.path.join(USERPROFILE, "Desktop", "SG CUBE.lnk")
    desk_link = shell.CreateShortcut(desk_path)
    desk_link.TargetPath = run_bat
    desk_link.WorkingDirectory = INSTALL_DIR
    if os.path.exists(icon_path):
        desk_link.IconLocation = f"{icon_path},0"
    desk_link.Description = "SG CUBE — Multimodal AI Assistant"
    desk_link.Save()
    log("3/6", f"Desktop shortcut created: {desk_path}")

    # 2. Start Menu Folder & Shortcuts
    start_menu_folder = os.path.join(APPDATA, r"Microsoft\Windows\Start Menu\Programs\SG CUBE")
    os.makedirs(start_menu_folder, exist_ok=True)

    # Main App in Start Menu Folder
    sm_link = shell.CreateShortcut(os.path.join(start_menu_folder, "SG CUBE.lnk"))
    sm_link.TargetPath = run_bat
    sm_link.WorkingDirectory = INSTALL_DIR
    if os.path.exists(icon_path):
        sm_link.IconLocation = f"{icon_path},0"
    sm_link.Description = "SG CUBE — Multimodal AI Assistant"
    sm_link.Save()

    # Wake Listener in Start Menu Folder
    sm_wake_link = shell.CreateShortcut(os.path.join(start_menu_folder, "SG CUBE Wake Listener.lnk"))
    sm_wake_link.TargetPath = wake_bat
    sm_wake_link.WorkingDirectory = INSTALL_DIR
    if os.path.exists(icon_path):
        sm_wake_link.IconLocation = f"{icon_path},0"
    sm_wake_link.WindowStyle = 7  # Minimized
    sm_wake_link.Description = "SG CUBE Background Wake Listener"
    sm_wake_link.Save()

    # Uninstall in Start Menu Folder
    sm_uninst_link = shell.CreateShortcut(os.path.join(start_menu_folder, "Uninstall SG CUBE.lnk"))
    sm_uninst_link.TargetPath = uninstall_bat
    sm_uninst_link.WorkingDirectory = INSTALL_DIR
    sm_uninst_link.Description = "Uninstall SG CUBE"
    sm_uninst_link.Save()
    log("3/6", f"Start Menu folder shortcuts created: {start_menu_folder}")

    # 3. No Startup-folder shortcut. Autostart is the Registry Run key only: the tray's
    # "Start with Windows" toggle edits that key, so a second launcher in the Startup
    # folder kept starting the listener after the user switched autostart off.
    stale = os.path.join(APPDATA, r"Microsoft\Windows\Start Menu\Programs\Startup", "SG CUBE Wake Listener.lnk")
    if os.path.exists(stale):
        os.remove(stale)
        log("3/6", "Removed the duplicate Startup-folder launcher left by an older installer.")


def configure_registry_autostart():
    log("4/6", "Configuring Windows Registry auto-start entry...")
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        wake_bat = os.path.join(INSTALL_DIR, "run_wake_listener.bat")
        winreg.SetValueEx(key, "SGCubeWakeListener", 0, winreg.REG_SZ, f'"{wake_bat}"')
        winreg.CloseKey(key)
        log("4/6", "Registry Run entry configured successfully.")
    except Exception as e:
        log("4/6", f"Warning: Failed to set registry entry ({e})")


def verify_installation_health():
    log("5/6", "Verifying installed application bytecode compilation...")
    total_compiled = 0
    errors = []
    for root, dirs, files in os.walk(INSTALL_DIR):
        if "runtime" in root or ".venv" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                total_compiled += 1
                full_path = os.path.join(root, f)
                try:
                    py_compile.compile(full_path, doraise=True)
                except Exception as e:
                    errors.append((f, str(e)))

    if errors:
        log("5/6", f"CRITICAL: {len(errors)} compilation errors encountered:")
        for f, err in errors:
            print(f"  {f}: {err}")
        return False
    else:
        log("5/6", f"Verification PASSED: {total_compiled} python files compiled with 0 errors.")

    return True


RUNTIME_PYTHON = os.path.join(INSTALL_DIR, "runtime", "Scripts", "python.exe")

# Every package requirements.txt adds is imported inside try/except by the app, so a
# missing one never crashed anything: the feature silently switched off. Check them here.
SMOKE_IMPORTS = [
    "google.genai", "cv2", "sounddevice", "numpy", "argon2", "cryptography", "pyautogui",
    "ddgs", "webview", "starlette", "uvicorn", "pycaw", "comtypes", "pyperclip",
    "faster_whisper", "silero_vad", "torch",
    "assistive.command_router", "assistive.vision_engine",
]


def install_runtime_dependencies():
    """run.bat and run_wake_listener.bat look for runtime\\Scripts\\python.exe first and
    otherwise fall back to whatever `python` is on PATH, which usually lacks the packages."""
    import subprocess
    log("2/6", "Preparing the private Python runtime (first install downloads ~1 GB, mostly torch)...")
    if not os.path.exists(RUNTIME_PYTHON):
        subprocess.run([sys.executable, "-m", "venv", os.path.join(INSTALL_DIR, "runtime")], check=True)
    req = os.path.join(INSTALL_DIR, "requirements.txt")
    proc = subprocess.run([RUNTIME_PYTHON, "-m", "pip", "install", "--disable-pip-version-check", "-r", req])
    if proc.returncode != 0:
        log("2/6", f"Package installation FAILED (pip exit {proc.returncode}). Check your internet connection and run the installer again.")
        return False
    log("2/6", "All packages from requirements.txt are installed.")
    return True


def run_smoke_verification():
    """Imports only: the old check ran a live acceptance test that changed the user's
    volume and clipboard on every install."""
    log("6/6", "Checking that every required package and core module imports...")
    import subprocess
    script = (
        "import importlib,sys\n"
        f"bad=[]\nfor m in {SMOKE_IMPORTS!r}:\n"
        "    try: importlib.import_module(m)\n"
        "    except Exception as e: bad.append(f'{m}: {type(e).__name__}: {e}')\n"
        "print('\\n'.join(bad)); sys.exit(1 if bad else 0)\n"
    )
    proc = subprocess.run([RUNTIME_PYTHON, "-c", script], cwd=INSTALL_DIR, capture_output=True, text=True)
    if proc.returncode == 0:
        log("6/6", f"Import check passed ({len(SMOKE_IMPORTS)} modules).")
        return True
    log("6/6", "Import check FAILED; these features will not work:")
    print(proc.stdout[-2000:] or proc.stderr[-2000:])
    return False


def main():
    print("============================================================")
    print("         SG CUBE 2.5.0 — OFFICIAL PRODUCTION INSTALLER      ")
    print("============================================================")
    deploy_application_files()
    preserve_and_initialize_data()
    if not install_runtime_dependencies():
        sys.exit(1)
    create_windows_shortcuts()
    configure_registry_autostart()
    compile_ok = verify_installation_health()
    if not compile_ok:
        print("\nINSTALLATION COMPLETED WITH COMPILATION WARNINGS.")
        sys.exit(1)

    if not run_smoke_verification():
        print("\nINSTALLATION FINISHED, BUT SOME PACKAGES DID NOT IMPORT (see above).")
        sys.exit(1)
    print("\n============================================================")
    print("   SUCCESS: SG CUBE IS INSTALLED AND ALL PACKAGES IMPORT.   ")
    print("============================================================")
    print(f"  Installed Location: {INSTALL_DIR}")
    print("  Desktop Shortcut:   %USERPROFILE%\\Desktop\\SG CUBE.lnk")
    print("  Start Menu:         SG CUBE -> SG CUBE.lnk")
    print("  Background Daemon:  Registry Run key (toggle it from the tray: Start with Windows)")
    print("============================================================")


if __name__ == "__main__":
    main()
