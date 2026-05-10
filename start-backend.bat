@echo off
title AI Creative Studio - Backend
cd /d "%~dp0backend"

echo ================================================
echo   AI Creative Studio - Python Backend
echo ================================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install PyTorch with CUDA first
echo.
echo Checking PyTorch installation...
python -c "import torch; print('PyTorch OK - CUDA:', torch.cuda.is_available())" 2>nul
if errorlevel 1 (
    echo Installing PyTorch with CUDA 11.8 support...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 --quiet
)

REM Install other requirements
echo Installing requirements...
pip install -r requirements.txt --quiet

echo.
echo ================================================
echo   Starting AI Backend on http://localhost:8000
echo ================================================
echo.

python main.py

pause
