@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title Mochi Desktop

echo ============================================
echo    Запуск Mochi Desktop
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден на компьютере.
    echo Установите Python 3.10 или новее с https://www.python.org/downloads/
    echo При установке поставьте галочку "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: создаю окружение, подождите...
    python -m venv .venv
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение ".venv".
        pause
        exit /b 1
    )
)

echo Проверяю необходимые библиотеки...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить библиотеки. Проверьте интернет-соединение.
    pause
    exit /b 1
)

if not exist ".env" (
    echo Файл .env не найден — приложение всё равно запустится, но скачивание
    echo файлов из Telegram будет недоступно, пока не заполните BOT_TOKEN.
    echo Скопируйте .env.example в .env, если нужен доступ к файлам из Telegram.
    echo.
)

echo Запускаю Mochi Desktop...
".venv\Scripts\python.exe" app\main.py

echo.
echo ============================================
echo Приложение закрыто.
echo ============================================
pause
