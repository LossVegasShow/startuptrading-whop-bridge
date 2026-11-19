@echo off
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv)
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if not exist .env (
  copy .env.example .env >nul
  echo Created .env. Please set ADMIN_PASSWORD and relevant integration credentials.
)
start "" "http://127.0.0.1:8000"
.venv\Scripts\python.exe start_local.py
pause
