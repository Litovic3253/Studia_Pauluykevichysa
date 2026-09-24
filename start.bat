@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title Запуск Telegram-бота

echo ============================================
echo    Запуск Telegram-бота
echo ============================================
echo.

set "ERRLOG=%~dp0bot_last_error.log"

REM --- 1. Python installed? ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден на компьютере.
    echo.
    echo Что делать: установите Python 3.10 или новее с сайта
    echo     https://www.python.org/downloads/
    echo При установке обязательно поставьте галочку "Add python.exe to PATH",
    echo иначе Windows не увидит Python.
    echo.
    pause
    exit /b 1
)

REM --- 2. Virtual environment ---
if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: создаю окружение для бота, подождите...
    python -m venv .venv
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение ".venv".
        echo Что делать: проверьте, что Python установлен корректно, и запустите файл ещё раз.
        pause
        exit /b 1
    )
)

REM --- 3. Dependencies ---
echo Проверяю необходимые библиотеки...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить необходимые библиотеки.
    echo Что делать: проверьте подключение к интернету и запустите файл ещё раз.
    pause
    exit /b 1
)

REM --- 4. .env / token ---
if not exist ".env" (
    echo [ОШИБКА] Не найден файл .env с токеном бота.
    echo Что делать: скопируйте .env.example в .env и впишите туда токен,
    echo полученный от @BotFather в Telegram.
    echo.
    pause
    exit /b 1
)

findstr /r /c:"^BOT_TOKEN=.\+" ".env" >nul
if errorlevel 1 (
    echo [ОШИБКА] В файле .env не заполнен BOT_TOKEN.
    echo Что делать: откройте .env в блокноте и впишите токен от @BotFather
    echo в строку BOT_TOKEN= ^(без пробелов и кавычек^).
    echo.
    pause
    exit /b 1
)

REM --- 5. Run the bot ---
echo.
echo Бот запускается и подключается к Telegram...
echo Если в консоли пойдут строки про "ClientConnectorError" или
echo "Sleep for ... and try again" - это не поломка, бот сам
echo переподключается. Если это не проходит несколько минут -
echo смотрите пояснение ниже после остановки бота.
echo.
echo Чтобы ОСТАНОВИТЬ бота - закройте это окно или нажмите Ctrl+C.
echo ============================================
echo.

".venv\Scripts\python.exe" bot.py 2> "%ERRLOG%"
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ============================================
if "%EXITCODE%"=="0" (
    echo Бот остановлен.
    del "%ERRLOG%" >nul 2>&1
) else (
    echo [ОШИБКА] Бот завершился с ошибкой ^(код %EXITCODE%^).
    echo.

    set "KNOWN=0"

    findstr /c:"ClientConnectorError" "%ERRLOG%" >nul 2>&1
    if not errorlevel 1 (
        set "KNOWN=1"
        echo Причина: не получается подключиться к серверам Telegram
        echo ^(api.telegram.org^).
        echo.
        echo Что делать:
        echo   1. Проверьте, что на компьютере вообще есть интернет.
        echo   2. Скорее всего Telegram заблокирован провайдером - включите
        echo      VPN и запустите бота заново.
        echo   3. Если стоит антивирус/файрвол - разрешите Python выход в сеть.
        echo.
    )

    findstr /c:"Unauthorized" "%ERRLOG%" >nul 2>&1
    if not errorlevel 1 (
        set "KNOWN=1"
        echo Причина: неверный токен бота.
        echo.
        echo Что делать: получите новый токен у @BotFather в Telegram и
        echo впишите его в файл .env в строку BOT_TOKEN=
        echo.
    )

    findstr /c:"ModuleNotFoundError" "%ERRLOG%" >nul 2>&1
    if not errorlevel 1 (
        set "KNOWN=1"
        echo Причина: не хватает нужных библиотек Python.
        echo.
        echo Что делать: удалите папку .venv рядом с ботом и запустите
        echo этот файл заново - библиотеки установятся автоматически.
        echo.
    )

    if "!KNOWN!"=="0" (
        echo Точную причину определить не удалось. Ниже - последние строки
        echo ошибки, их можно показать разработчику:
        echo.
        more "%ERRLOG%"
        echo.
    )

    echo Полный текст ошибки сохранён в файле:
    echo   %ERRLOG%
)
echo ============================================
echo.
pause
