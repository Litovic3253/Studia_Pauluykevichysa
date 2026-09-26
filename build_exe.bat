@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Сборка «Студия Паулюкевичуса.exe»

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
".venv\Scripts\flet.exe" pack app\main.py --name "Студия Паулюкевичуса" --icon assets\icon.ico ^
    --product-name "Студия Паулюкевичуса" --file-description "Студия Паулюкевичуса - заказы 3D-печати" ^
    --product-version 1.8.0 --file-version 1.8.0.0 -y --distpath dist --add-data "assets;assets" ^
    "--pyinstaller-build-args=--collect-data=googleapiclient"
if errorlevel 1 goto :fail

echo Упаковываю архив для передачи...
if exist "dist\Студия-Паулюкевичуса-Windows.zip" del "dist\Студия-Паулюкевичуса-Windows.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Студия Паулюкевичуса.exe','packaging\Как установить.txt' -DestinationPath 'dist\Студия-Паулюкевичуса-Windows.zip'"
if errorlevel 1 goto :fail

echo.
echo Готово:
echo   dist\Студия Паулюкевичуса.exe          — сама программа
echo   dist\Студия-Паулюкевичуса-Windows.zip  — архив, чтобы отправить другу
pause
exit /b 0

:fail
echo [ОШИБКА] Сборка не удалась, смотрите сообщения выше.
pause
exit /b 1
