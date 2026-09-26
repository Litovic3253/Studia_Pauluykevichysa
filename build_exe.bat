@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Сборка Mochi Desktop.exe

if not exist ".venv\Scripts\python.exe" (
    echo Сначала запустите start_app.bat — он создаст .venv и поставит зависимости.
    pause
    exit /b 1
)

echo Ставлю инструменты сборки...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto :fail

echo Собираю exe (1-3 минуты)...
set PYTHONPATH=.
".venv\Scripts\flet.exe" pack app\main.py --name "Mochi Desktop" --icon assets\icon.ico ^
    --product-name "Mochi Desktop" --file-description "Mochi Desktop - заказы 3D-печати" ^
    --product-version 1.1.0 --file-version 1.1.0.0 -y --distpath dist --add-data "assets;assets" ^
    "--pyinstaller-build-args=--collect-data=googleapiclient"
if errorlevel 1 goto :fail

echo Упаковываю архив для передачи...
if exist "dist\Mochi-Desktop-Windows.zip" del "dist\Mochi-Desktop-Windows.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Mochi Desktop.exe','packaging\Как установить.txt' -DestinationPath 'dist\Mochi-Desktop-Windows.zip'"
if errorlevel 1 goto :fail

echo.
echo Готово:
echo   dist\Mochi Desktop.exe          — сама программа
echo   dist\Mochi-Desktop-Windows.zip  — архив, чтобы отправить другу
pause
exit /b 0

:fail
echo [ОШИБКА] Сборка не удалась, смотрите сообщения выше.
pause
exit /b 1
