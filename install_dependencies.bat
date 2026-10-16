@echo off
title Install Dependensi Otomasi FASIH-SM
cd /d "%~dp0"
echo ========================================================
echo       INSTALL DEPENDENSI OTOMASI FASIH-SM SE2026
echo             BPS KABUPATEN PANGKEP
echo ========================================================
echo.
echo Sedang menginstall library 'playwright' untuk Python...
python -m pip install playwright
if errorlevel 1 (
    echo.
    echo [INFO] Mencoba install menggunakan launcher 'py'...
    py -m pip install playwright
)
echo.
echo ========================================================
echo Instalasi selesai!
echo Pastikan Google Chrome sudah terpasang di PC ini.
echo Sekarang Anda dapat menjalankan 'jalankan_otomasi_fasih.bat'.
echo ========================================================
echo.
pause
