@echo off
title AI Creative Studio - Desktop App
cd /d "%~dp0frontend"

echo ================================================
echo   AI Creative Studio - Desktop App (Electron)
echo ================================================
echo.

if not exist "node_modules\" (
    echo Installing npm packages...
    npm install
)

echo Launching desktop app...
echo The AI backend will start automatically.
echo.

set NODE_ENV=development
start "Vite Dev Server" node node_modules/vite/bin/vite.js
timeout /t 5 /nobreak >nul
node node_modules/electron/cli.js .
pause
