@echo off
setlocal
cd /d "%~dp0"
set KMP_DUPLICATE_LIB_OK=TRUE
set PYTHONUTF8=1
echo ============================================================
echo  Poker Card Recognition and Sorting System
echo  Starting local demo server: http://127.0.0.1:7860
echo ============================================================
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH. Install Python 3.10-3.13 first.
  pause
  exit /b 1
)
python -c "import flask, cv2, torch" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing dependencies from requirements.txt ...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed. See README.md.
    pause
    exit /b 1
  )
)
start "" http://127.0.0.1:7860
python demo_app.py
pause
