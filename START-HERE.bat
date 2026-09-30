@echo off
title NEON//CORE - setup
cd /d "%~dp0"
echo.
echo  ==========================================
echo    NEON//CORE - starting on your computer
echo  ==========================================
echo.

set "PY=py"
where py >nul 2>nul || set "PY=python"
where %PY% >nul 2>nul
if errorlevel 1 goto no_python
where npm >nul 2>nul
if errorlevel 1 goto no_node

echo [1/4] Preparing the backend - first time takes 1-2 minutes...
cd /d "%~dp0backend"
if not exist .venv %PY% -m venv .venv
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements-dev.txt
if errorlevel 1 goto pip_failed

if exist .env goto env_ready
echo [2/4] Creating settings file backend\.env
for /f %%i in ('.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"') do set "NEON_SECRET=%%i"
(
  echo ENVIRONMENT=development
  echo SECRET_KEY=%NEON_SECRET%
  echo FRONTEND_ORIGINS=http://localhost:5173
  echo MONGODB_URI=mongomock://
  echo MONGODB_DB_NAME=neon_core
  echo OPENROUTER_API_KEY=
  echo OPENROUTER_MODEL=openrouter/free
  echo ADMIN_USERNAME=admin
  echo ADMIN_EMAIL=admin@example.com
  echo ADMIN_PASSWORD=admin12345
) > .env
goto env_done
:env_ready
echo [2/4] Using your existing settings file backend\.env
:env_done

echo [3/4] Preparing the frontend - first time takes 1-2 minutes...
cd /d "%~dp0frontend"
if not exist node_modules call npm install --no-audit --no-fund

echo [4/4] Starting the backend and frontend in two new windows...
start "NEON backend - keep open" /D "%~dp0backend" cmd /k ".venv\Scripts\python -m uvicorn app.main:app --reload"
start "NEON frontend - keep open" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo  Waiting for the servers to start...
timeout /t 12 /nobreak >nul
start "" http://localhost:5173

echo.
echo  ==========================================
echo    Opened http://localhost:5173 in your browser
echo.
echo    Log in with:   admin   /   admin12345
echo.
echo    To stop the app: close the two black windows.
echo  ==========================================
echo.
pause
exit /b

:no_python
echo [X] Python is not installed.
echo     Install it from https://www.python.org/downloads/
echo     and TICK "Add python.exe to PATH" in the installer, then run this again.
pause
exit /b

:no_node
echo [X] Node.js is not installed. Install it from https://nodejs.org then run this again.
pause
exit /b

:pip_failed
echo [X] Installing the Python packages failed. Check your internet connection and run this again.
pause
exit /b
