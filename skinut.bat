@echo off
title Установка main.exe в автозагрузку
setlocal enabledelayedexpansion

:: Определяем путь к этому скрипту и к main.exe (они лежат рядом)
set "CURR=%~dp0"
set "SRC=%CURR%test.exe"
set "DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo ---------------------------------------------
echo Очистка папки автозагрузки...
del /q "%DST%\*" >nul 2>&1

echo Копирование main.exe в автозагрузку...
copy "%SRC%" "%DST%" /Y >nul


echo ---------------------------------------------
echo Готово! При следующем запуске Windows файл main.exe запустится автоматически.
pause
