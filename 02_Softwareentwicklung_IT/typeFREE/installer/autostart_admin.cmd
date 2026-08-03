@echo off
title typeFREE Autostart einrichten
chcp 65001 >nul

REM Admin-Check und Erhöhung
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo Starte als Administrator neu ...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b 0
)

set "EXE=C:\Users\sebas\Desktop\workspace agentic engineering\02_Softwareentwicklung_IT\typeFREE\dist\typeFREE.exe"

echo ============================================
echo   typeFREE Autostart einrichten
echo ============================================
echo.
echo EXE: %EXE%
echo.

echo [1/2] Erstelle 'typeFREE' (Start bei Anmeldung) ...
schtasks /Create /SC ONLOGON /TN "typeFREE" /TR "'%EXE%' --autostart" /RL HIGHEST /F /IT
if %errorlevel% equ 0 (echo OK) else (echo FEHLER!)
echo.

echo [2/2] Erstelle 'typeFREE-Aufwachen' (Start beim Aufwachen) ...
schtasks /Create /SC ONEVENT /EC System /MO "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and EventID=107]]" /TN "typeFREE-Aufwachen" /TR "'%EXE%' --autostart" /RL HIGHEST /F /IT
if %errorlevel% equ 0 (echo OK) else (echo FEHLER!)
echo.

echo ============================================
echo   Pruefe erstellte Aufgaben ...
echo ============================================
echo.
schtasks /Query /TN "typeFREE" /FO LIST /V
echo.
schtasks /Query /TN "typeFREE-Aufwachen" /FO LIST /V

echo.
echo Fertig! Die Aufgaben werden nach dem naechsten Neustart wirksam.
echo.
pause