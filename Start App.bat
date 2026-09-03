@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ==================================================
echo DataForge AI - Starting Up
echo AI-Powered Data Analysis, Insights and Reporting
echo Was made by Oleh Datsyk
echo ==================================================
echo.

REM --- 1. Verify this looks like the DataForge AI project folder ---
if not exist "app.py" (
    echo [ERROR] app.py was not found in this folder.
    echo Please make sure this script is inside the DataForge AI project folder.
    pause
    exit /b 1
)
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt was not found in this folder.
    pause
    exit /b 1
)

REM --- 2. Detect Python ---
set "PYTHON_CMD="
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=py -3"
    )
)
if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python was not found on this system.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo and make sure "Add Python to PATH" is checked during installation.
    pause
    exit /b 1
)
echo [OK] Found Python: %PYTHON_CMD%

REM --- 3. Detect broken/missing virtual environment ---
set "NEED_VENV_REBUILD=0"
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] No virtual environment found. Creating one...
    set "NEED_VENV_REBUILD=1"
) else (
    ".venv\Scripts\python.exe" -c "import fastapi" >nul 2>nul
    if errorlevel 1 (
        echo [WARN] Existing virtual environment looks broken. Rebuilding...
        rmdir /s /q ".venv"
        set "NEED_VENV_REBUILD=1"
    )
)

if "%NEED_VENV_REBUILD%"=="1" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

REM --- 4. Activate the virtual environment ---
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate the virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.

REM --- 5. Upgrade pip and install requirements ---
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip >nul
echo [INFO] Installing/checking requirements (this can take a minute the first time)...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements. See the errors above.
    pause
    exit /b 1
)
echo [OK] Requirements installed.

REM --- 6. Check for .env, copy from .env.example if missing ---
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [INFO] Created .env from .env.example.
    ) else (
        echo [WARN] No .env or .env.example file found. The app will run without AI features.
    )
)

echo.
echo ===========================================================
echo AI PROVIDER CONFIGURATION
echo ===========================================================
echo DataForge AI works fully WITHOUT any AI keys - all data
echo analysis, profiling, cleaning, charts, and exports work with
echo Python alone.
echo.
echo To enable AI-generated explanations and insights, open the
echo ".env" file in a text editor and add one or more of:
echo   OPENAI_API_KEY=...
echo   ANTHROPIC_API_KEY=...
echo   GEMINI_API_KEY=...
echo Then restart this script.
echo ===========================================================
echo.

REM --- 7. Launch Uvicorn in a separate window so logs stay visible ---
echo [INFO] Launching DataForge AI server in a new window...
start "DataForge AI - Server (do not close)" cmd /k ".venv\Scripts\activate.bat && uvicorn app:app --host 127.0.0.1 --port 8000 --reload"

REM --- 8. Wait for the health endpoint to respond ---
echo [INFO] Waiting for the server to become healthy...
set "READY=0"
for /L %%i in (1,1,30) do (
    if "!READY!"=="0" (
        powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            set "READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)

if "%READY%"=="1" (
    echo [OK] Server is healthy.
) else (
    echo [WARN] Server did not respond within 30 seconds. Check the server window for errors.
)

REM --- 9. Open in Chrome if installed, otherwise the default browser ---
set "CHROME_PATH="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if not "%CHROME_PATH%"=="" (
    echo [INFO] Opening DataForge AI in Google Chrome...
    start "" "%CHROME_PATH%" "http://localhost:8000"
) else (
    echo [INFO] Google Chrome not found - opening in your default browser...
    start "" "http://localhost:8000"
)

echo.
echo ===========================================================
echo DataForge AI is running at http://localhost:8000
echo Keep the server window open while using the app.
echo Close the server window (or press Ctrl+C in it) to stop.
echo ===========================================================
pause
