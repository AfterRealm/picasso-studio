@echo off
REM Launcher for Picasso Studio — keeps the window open so you can see output/errors.
cd /d "%~dp0"
python scripts\start_studio.py
echo.
echo --- Server stopped. Press any key to close this window. ---
pause >nul
