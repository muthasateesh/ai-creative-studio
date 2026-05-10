@echo off
title AI Creative Studio - Web App
cd /d "%~dp0frontend"

echo ================================================
echo   AI Creative Studio - Web Frontend
echo ================================================
echo.

if not exist "node_modules\" (
    echo Installing npm packages...
    npm install
)

echo Starting web app at http://localhost:5173
echo Open your browser and go to: http://localhost:5173
echo.
echo Make sure start-backend.bat is running first!
echo.

node node_modules/vite/bin/vite.js
pause
