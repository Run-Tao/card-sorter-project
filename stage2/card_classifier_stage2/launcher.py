# -*- coding: utf-8 -*-
"""Small Windows launcher for the demo.

It starts demo_app.py with the Python on PATH and opens the browser.  This is a
convenience launcher, not a standalone Python bundle; install requirements first
(see README).  Build with:
    pyinstaller --onefile --name 启动识别系统 launcher.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def main():
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    app = base / "demo_app.py"
    if not app.exists():
        raise SystemExit(f"demo_app.py not found next to launcher: {app}")
    python = shutil.which("pythonw") or shutil.which("python")
    if not python:
        raise SystemExit("Python not found in PATH. Install Python 3.10–3.13 first.")
    env = os.environ.copy()
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    subprocess.Popen([python, str(app)], cwd=str(base), env=env,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:7860")
    print("Started demo_app.py; browser: http://127.0.0.1:7860")


if __name__ == "__main__":
    main()
