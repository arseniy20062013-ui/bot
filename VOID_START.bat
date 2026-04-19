@echo off
chcp 65001 >nul
title VOID HELPER - INSTALLER

echo ==========================================
echo        VOID HELPER - INSTALLER
echo ==========================================
echo.

echo [1/3] Обновление pip...
python -m pip install --upgrade pip

echo.
echo [2/3] Установка библиотек...
pip install aiogram aiosqlite aiofiles

echo.
echo [3/3] Запуск бота...
echo ------------------------------------------
python main.py

echo.
echo [ERROR] Бот завершился с ошибкой.
pause