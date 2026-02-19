@echo off
:: Ensure window never closes on error - re-launch in a cmd /k window
if not "%LAUNCHED%"=="1" (
    set "LAUNCHED=1"
    cmd /k "%~f0"
    exit /b
)
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Video AI Studio - Setup ^& Launch
color 0F

echo.
echo  =============================================
echo     Video AI Studio - Full Setup ^& Launcher
echo  =============================================
echo.

set "INSTALLED_NEW=0"
set "HAS_ERROR=0"
set "HAS_WINGET=1"

:: Save the project directory (where this .bat lives)
set "PROJECT_DIR=%~dp0"
:: Remove trailing backslash
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: =============================================
:: PHASE 1: Check if winget is available
:: =============================================
where winget >nul 2>&1
if !errorlevel! neq 0 (
    set "HAS_WINGET=0"
    echo  [NOTE] winget is not available on this system.
    echo         Missing programs will need to be installed manually.
    echo.
)

:: =============================================
:: PHASE 2: Check ^& Install System Programs
:: =============================================
echo  --- Checking required programs ---
echo.

:: --- Python ---
echo  [CHECK] Python...
where python >nul 2>&1
if !errorlevel! neq 0 (
    if !HAS_WINGET! equ 1 (
        echo          Not found. Installing via winget...
        winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        if !errorlevel! neq 0 (
            echo  [ERROR]  Failed to install Python automatically.
            echo           Install manually: https://www.python.org/downloads/
            echo           IMPORTANT: Check "Add Python to PATH" during install.
            set "HAS_ERROR=1"
        ) else (
            echo  [OK]     Python installed successfully.
            set "INSTALLED_NEW=1"
        )
    ) else (
        echo  [ERROR]  Python is NOT installed.
        echo           Install from: https://www.python.org/downloads/
        echo           IMPORTANT: Check "Add Python to PATH" during install!
        set "HAS_ERROR=1"
    )
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [OK]     %%v
)
echo.

:: --- Node.js ---
echo  [CHECK] Node.js...
where node >nul 2>&1
if !errorlevel! neq 0 (
    if !HAS_WINGET! equ 1 (
        echo          Not found. Installing via winget...
        winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
        if !errorlevel! neq 0 (
            echo  [ERROR]  Failed to install Node.js automatically.
            echo           Install manually: https://nodejs.org/
            set "HAS_ERROR=1"
        ) else (
            echo  [OK]     Node.js installed successfully.
            set "INSTALLED_NEW=1"
        )
    ) else (
        echo  [ERROR]  Node.js is NOT installed.
        echo           Install from: https://nodejs.org/
        set "HAS_ERROR=1"
    )
) else (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo  [OK]     Node.js %%v
)
echo.

:: --- FFmpeg ---
echo  [CHECK] FFmpeg...
where ffmpeg >nul 2>&1
if !errorlevel! neq 0 (
    if !HAS_WINGET! equ 1 (
        echo          Not found. Installing via winget...
        winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
        if !errorlevel! neq 0 (
            echo  [ERROR]  Failed to install FFmpeg automatically.
            echo           Install manually: https://ffmpeg.org/download.html
            set "HAS_ERROR=1"
        ) else (
            echo  [OK]     FFmpeg installed successfully.
            set "INSTALLED_NEW=1"
        )
    ) else (
        echo  [ERROR]  FFmpeg is NOT installed.
        echo           Install from: https://ffmpeg.org/download.html
        set "HAS_ERROR=1"
    )
) else (
    echo  [OK]     FFmpeg found.
)
echo.

:: =============================================
:: If new programs were installed, PATH needs refresh
:: =============================================
if !INSTALLED_NEW! equ 1 (
    echo  =============================================
    echo    New programs were installed.
    echo    Please CLOSE this window and run
    echo    Run_System.bat again so PATH takes effect.
    echo  =============================================
    echo.
    pause
    exit /b 0
)

:: =============================================
:: If critical programs are missing, stop here
:: =============================================
if !HAS_ERROR! equ 1 (
    echo  =============================================
    echo  [ERROR] Required programs are missing.
    echo          Install them manually and run again.
    echo  =============================================
    echo.
    pause
    exit /b 1
)

echo  All required programs found!
echo.

:: =============================================
:: PHASE 3: Check .env file
:: =============================================
if not exist "%PROJECT_DIR%\.env" (
    echo  [WARNING] .env file not found.
    echo            Create a .env file in the project root with at least:
    echo              GROQ_API_KEY=your_key_here
    echo              GEMINI_API_KEY=your_key_here
    echo            Some features may not work without API keys.
    echo.
)

:: =============================================
:: PHASE 4: Python Virtual Environment
:: =============================================
echo  [1/5] Python virtual environment...
if not exist "%PROJECT_DIR%\venv\Scripts\activate.bat" (
    echo         Creating new virtual environment...
    python -m venv "%PROJECT_DIR%\venv"
    if !errorlevel! neq 0 (
        echo.
        echo  [ERROR] Failed to create Python virtual environment.
        echo          Try manually: python -m venv venv
        echo.
        pause
        exit /b 1
    )
    echo         Created successfully.
) else (
    echo         Already exists.
)
call "%PROJECT_DIR%\venv\Scripts\activate.bat"
echo         Activated: venv
echo.

:: =============================================
:: PHASE 5: Python dependencies
:: =============================================
echo  [2/5] Python dependencies...
:: Compare requirements.txt with cached copy to skip if unchanged
set "PIP_NEEDS_INSTALL=0"
if not exist "%PROJECT_DIR%\.deps\requirements.installed.txt" (
    set "PIP_NEEDS_INSTALL=1"
) else (
    fc /b "%PROJECT_DIR%\requirements.txt" "%PROJECT_DIR%\.deps\requirements.installed.txt" >nul 2>&1
    if !errorlevel! neq 0 set "PIP_NEEDS_INSTALL=1"
)
if !PIP_NEEDS_INSTALL! equ 1 (
    echo         Installing packages...
    pip install -r "%PROJECT_DIR%\requirements.txt" --quiet --disable-pip-version-check 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo  [ERROR] pip install failed. Retrying with full output...
        echo  -------------------------------------------------
        pip install -r "%PROJECT_DIR%\requirements.txt" --disable-pip-version-check
        echo  -------------------------------------------------
        if !errorlevel! neq 0 (
            echo.
            echo  [ERROR] Python dependencies failed to install.
            echo          Check the errors above.
            echo          You can try manually:
            echo            venv\Scripts\activate ^&^& pip install -r requirements.txt
            echo.
            pause
            exit /b 1
        )
    )
    rem Save fingerprint on success
    if not exist "%PROJECT_DIR%\.deps" mkdir "%PROJECT_DIR%\.deps"
    copy /y "%PROJECT_DIR%\requirements.txt" "%PROJECT_DIR%\.deps\requirements.installed.txt" >nul
    echo         Done.
) else (
    echo         Already installed - requirements.txt unchanged. Skipping.
)
echo.

:: =============================================
:: PHASE 6: Frontend dependencies
:: =============================================
echo  [3/5] Frontend dependencies...
if not exist "%PROJECT_DIR%\frontend\package.json" (
    echo  [ERROR] frontend\package.json not found
    echo          Make sure you copied the entire project folder.
    echo.
    pause
    exit /b 1
)
set "NPM_FRONT_NEEDS=0"
if not exist "%PROJECT_DIR%\frontend\node_modules" set "NPM_FRONT_NEEDS=1"
if not exist "%PROJECT_DIR%\.deps\frontend.package.installed.json" set "NPM_FRONT_NEEDS=1"
if !NPM_FRONT_NEEDS! equ 0 (
    fc /b "%PROJECT_DIR%\frontend\package.json" "%PROJECT_DIR%\.deps\frontend.package.installed.json" >nul 2>&1
    if !errorlevel! neq 0 set "NPM_FRONT_NEEDS=1"
)
if !NPM_FRONT_NEEDS! equ 1 (
    echo         Installing packages, this may take a minute...
    cd /d "%PROJECT_DIR%\frontend"
    call npm install 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo  [ERROR] Frontend npm install failed. See errors above.
        echo          You can try manually:
        echo            cd frontend ^&^& npm install
        echo.
        cd /d "%PROJECT_DIR%"
        pause
        exit /b 1
    )
    cd /d "%PROJECT_DIR%"
    if not exist "%PROJECT_DIR%\.deps" mkdir "%PROJECT_DIR%\.deps"
    copy /y "%PROJECT_DIR%\frontend\package.json" "%PROJECT_DIR%\.deps\frontend.package.installed.json" >nul
    echo         Done.
) else (
    echo         Already installed - package.json unchanged. Skipping.
)
echo.

:: =============================================
:: PHASE 7: Remotion Renderer dependencies
:: =============================================
echo  [4/5] Remotion Renderer dependencies...
if not exist "%PROJECT_DIR%\remotion-renderer\package.json" (
    echo         remotion-renderer not found, skipping.
    goto :remotion_done
)
set "NPM_REM_NEEDS=0"
if not exist "%PROJECT_DIR%\remotion-renderer\node_modules" set "NPM_REM_NEEDS=1"
if not exist "%PROJECT_DIR%\.deps\remotion.package.installed.json" set "NPM_REM_NEEDS=1"
if !NPM_REM_NEEDS! equ 0 (
    fc /b "%PROJECT_DIR%\remotion-renderer\package.json" "%PROJECT_DIR%\.deps\remotion.package.installed.json" >nul 2>&1
    if !errorlevel! neq 0 set "NPM_REM_NEEDS=1"
)
if !NPM_REM_NEEDS! equ 1 (
    echo         Installing packages...
    cd /d "%PROJECT_DIR%\remotion-renderer"
    call npm install 2>&1
    if !errorlevel! neq 0 (
        echo  [WARNING] Remotion install had errors. Effects Studio may not work.
        echo            Main features will still work fine.
    ) else (
        if not exist "%PROJECT_DIR%\.deps" mkdir "%PROJECT_DIR%\.deps"
        copy /y "%PROJECT_DIR%\remotion-renderer\package.json" "%PROJECT_DIR%\.deps\remotion.package.installed.json" >nul
    )
    cd /d "%PROJECT_DIR%"
    echo         Done.
) else (
    echo         Already installed - package.json unchanged. Skipping.
)
:remotion_done
echo.

:: =============================================
:: PHASE 8: Create required directories
:: =============================================
echo  [5/5] Checking project directories...
if not exist "%PROJECT_DIR%\inputs" mkdir "%PROJECT_DIR%\inputs"
if not exist "%PROJECT_DIR%\outputs" mkdir "%PROJECT_DIR%\outputs"
if not exist "%PROJECT_DIR%\assets\music" mkdir "%PROJECT_DIR%\assets\music"
if not exist "%PROJECT_DIR%\assets\fonts" mkdir "%PROJECT_DIR%\assets\fonts"
echo         Done.
echo.

:: =============================================
:: PHASE 9: Launch servers
:: =============================================
echo  =============================================
echo     Starting servers...
echo  =============================================
echo.

:: Start Backend
echo  Starting Backend (port 8000)...
start "Video AI - Backend" /d "%PROJECT_DIR%" cmd /k "title Video AI - Backend && color 0A && call venv\Scripts\activate.bat && echo. && echo  Starting FastAPI backend... && echo. && python main.py || (echo. && echo [ERROR] Backend crashed! See error above. && pause)"

:: Wait for backend
echo  Waiting for backend to initialize...
timeout /t 4 /nobreak >nul

:: Start Frontend
echo  Starting Frontend (port 3000)...
start "Video AI - Frontend" /d "%PROJECT_DIR%\frontend" cmd /k "title Video AI - Frontend && color 0B && echo. && echo  Starting Vite dev server... && echo. && npm run dev || (echo. && echo [ERROR] Frontend crashed! See error above. && pause)"

:: Wait and open browser
timeout /t 5 /nobreak >nul

echo.
echo  =============================================
echo        System is running!
echo  =============================================
echo.
echo    Backend:  http://localhost:8000
echo    Frontend: http://localhost:3000
echo.
echo  =============================================
echo.

:: Open browser
start http://localhost:3000

echo  Press any key to close this launcher.
echo  (Backend and Frontend will keep running)
echo.
pause >nul
