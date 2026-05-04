@echo off
title SIGNAL OMEGA V2 — BRIDGE
color 0A
echo.
echo  ================================================
echo     BTCUSD SIGNAL OMEGA V2 — BRIDGE LAUNCHER
echo  ================================================
echo.
echo [1/3] Mengecek Python...
python --version 2>nul
if errorlevel 1 (
    echo.
    echo  [ERROR] Python tidak ditemukan!
    echo  Download di: https://python.org
    echo.
    pause
    exit /b 1
)
echo  Python OK!
echo.
echo [2/3] Install/Update dependencies...
pip install MetaTrader5 websockets --quiet --upgrade
if errorlevel 1 (
    echo.
    echo  [ERROR] Gagal install dependencies!
    pause
    exit /b 1
)
echo  Dependencies OK!
echo.
echo [3/3] Menjalankan Bridge...
echo.
echo  ================================================
echo   Bridge aktif di : ws://localhost:8765
echo   Cloudflare      : jalankan cloudflared.exe
echo   Tekan CTRL+C    : untuk berhenti
echo  ================================================
echo.
python bridge.py
echo.
echo  Bridge berhenti. Tekan tombol apapun untuk keluar...
pause > nul
