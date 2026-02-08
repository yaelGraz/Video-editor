@echo off
chcp 65001 >nul 2>&1
title Video AI Studio

echo ============================================
echo        Video AI Studio - System Launcher
echo ============================================
echo.

:: -------------------------------------------
:: Check prerequisites
:: -------------------------------------------
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo         Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH!
    echo         Download from: https://nodejs.org/
    pause
    exit /b 1
)

:: -------------------------------------------
:: Check .env file exists
:: -------------------------------------------
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo           Copy .env.example to .env and fill in your API keys.
    echo.
)

:: -------------------------------------------
:: Step 1: Install Python dependencies
:: -------------------------------------------
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [WARNING] Some Python packages may have failed. Continuing...
)
echo       Done.
echo.

:: -------------------------------------------
:: Step 2: Install Frontend dependencies
:: -------------------------------------------
echo [2/4] Installing Frontend dependencies...
cd frontend
if not exist "node_modules" (
    echo       First run - installing all packages (this may take a minute)...
    call npm install
) else (
    echo       node_modules found, checking for updates...
    call npm install --silent
)
cd ..
echo       Done.
echo.

:: -------------------------------------------
:: Step 3: Start Backend (Python/FastAPI)
:: -------------------------------------------
echo [3/4] Starting Backend server (port 8000)...
start "Video AI - Backend" cmd /k "title Video AI - Backend && color 0A && python main.py"
echo       Backend starting...
echo.

:: -------------------------------------------
:: Wait for backend to be ready
:: -------------------------------------------
echo       Waiting for backend to be ready...
timeout /t 3 /nobreak >nul

:: -------------------------------------------
:: Step 4: Start Frontend (React/Vite)
:: -------------------------------------------
echo [4/4] Starting Frontend dev server (port 3000)...
start "Video AI - Frontend" cmd /k "title Video AI - Frontend && color 0B && cd frontend && npm run dev"
echo       Frontend starting...
echo.

:: -------------------------------------------
:: Wait and open browser
:: -------------------------------------------
timeout /t 4 /nobreak >nul
echo ============================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo ============================================
echo.
echo Opening browser...
start http://localhost:3000

echo.
echo System is running. Close this window or press any key to exit.
echo (The servers will keep running in their own windows)
pause >nul
