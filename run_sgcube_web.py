"""
SG CUBE — Web UI Launcher
Launches SG CUBE with the modern React 18 + Three.js presentation layer.
"""

import sys
import os

if __name__ == "__main__":
    # Ensure current directory is on sys.path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    # Force web GUI mode
    if "--gui=tkinter" not in sys.argv and "--legacy" not in sys.argv:
        if "--gui" not in sys.argv:
            sys.argv.append("--gui=web")

    import visionclaw_gui
    visionclaw_gui.main()
