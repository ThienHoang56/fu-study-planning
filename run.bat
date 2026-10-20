@echo off
title FU Study Planning
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Dang khoi tao moi truong ao .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Khong the tao moi truong ao. Vui long kiem tra Python da duoc cai dat.
        pause
        exit /b 1
    )
    echo [INFO] Dang cai dat cac thu vien tu requirements.txt...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Loi khi cai dat thu vien.
        pause
        exit /b 1
    )
)

echo [INFO] Dang khoi dong ung dung...
".venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Ung dung ket thuc voi loi.
    pause
)
