@echo off
title Otomasi Penandaan KBLI FASIH-SM (Multi-PC)
cd /d "%~dp0"
echo ========================================================
echo       OTOMASI PENANDAAN KBLI FASIH-SM SE2026
echo             BPS KABUPATEN PANGKEP
echo ========================================================
echo.
python otomasi_fasih.py
if errorlevel 1 (
    echo.
    echo [INFO] Mencoba menjalankan dengan launcher 'py'...
    py otomasi_fasih.py
)
echo.
pause
