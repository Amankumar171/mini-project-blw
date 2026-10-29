@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    if exist "C:\Program Files\Python312\python.exe" (
        "C:\Program Files\Python312\python.exe" app.py
    ) else (
        echo Python 3.12 is required.
        pause
    )
) else (
    python app.py
)
pause
