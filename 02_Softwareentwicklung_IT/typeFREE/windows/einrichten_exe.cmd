@echo off
title typeFREE Einrichtung (EXE-Modus)
chcp 65001 >nul

REM ============================================
REM   Automatische Admin-Erhöhung per UAC
REM ============================================
REM Prüfen, ob wir bereits Admin sind
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo typeFREE benoetigt Administrator-Rechte fuer:
    echo   - Tastatur-Hook (globaler Hotkey)
    echo   - Aufgabenplanung (Autostart)
    echo.
    echo Starte mit Administrator-Rechten neu ...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b 0
)

REM ============================================
REM   Ab hier: wir sind Administrator
REM ============================================
echo ============================================
echo   typeFREE - Einrichtung (EXE-Modus)
echo ============================================
echo.

REM EXE-Pfad ermitteln
set "PROJEKT=%~dp0..\"
set "EXE=%PROJEKT%dist\typeFREE.exe"

REM Prüfen, ob die EXE existiert
if not exist "%EXE%" (
    echo FEHLER: typeFREE.exe nicht gefunden.
    echo.
    echo Erwartet unter: %EXE%
    echo.
    echo Baue zuerst die EXE mit:
    echo   pyinstaller typeFREE.spec
    echo.
    pause
    exit /b 1
)

echo EXE gefunden: %EXE%
echo.

REM ============================================
REM   typeFREE starten
REM ============================================
echo ============================================
echo   typeFREE starten
echo ============================================
echo.
echo Starte typeFREE als Administrator ...
powershell -Command "Start-Process '%EXE%' -Verb RunAs"
if %errorlevel% equ 0 (
    echo typeFREE wurde gestartet (Admin).
    echo Das Tray-Icon erscheint in der Taskleiste.
) else (
    echo Konnte typeFREE nicht mit Admin-Rechten starten.
    echo Bitte die EXE manuell als Administrator ausfuehren.
)

echo.
echo ============================================
echo   Aufgabenplanung einrichten (Autostart)
echo ============================================
echo.
echo typeFREE kann automatisch starten bei:
echo   - Windows-Anmeldung (Neustart / Hochfahren)
echo   - Aufwachen aus Ruhezustand
echo.
echo Dafuer wird eine Aufgabe in der Windows Aufgabenplanung angelegt.
echo.
echo Soll typeFREE automatisch beim Anmelden starten?
choice /C JN /M "Autostart einrichten"
if %errorlevel% equ 1 (
    echo.
    echo Erstelle Aufgabenplanung fuer Benutzer %USERNAME%...

    REM Aufgabe 1: Start bei Anmeldung (logon)
    schtasks /Create /SC ONLOGON /TN "typeFREE" /TR "'%EXE%' --autostart" /RL HIGHEST /F /IT

    REM Aufgabe 2: Start beim Aufwachen aus Ruhezustand (Event 107)
    schtasks /Create /SC ONEVENT /EC System /MO "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and EventID=107]]" /TN "typeFREE-Aufwachen" /TR "'%EXE%' --autostart" /RL HIGHEST /F /IT

    echo.
    echo ✅ Aufgabenplanung eingerichtet:
    echo   - typeFREE  → Start bei Anmeldung
    echo   - typeFREE-Aufwachen → Start beim Aufwachen
    echo.
    echo Hinweis: Die Aufgaben werden ab dem naechsten Neustart wirksam.
) else (
    echo Autostart uebersprungen.
)

echo.
echo ============================================
echo   Fertig!
echo ============================================
echo.
echo typeFREE-EXE: %EXE%
echo.
echo Wichtige Dateien (neben der EXE):
echo   .env              - Hier kommen die API-Keys rein
echo   config.json       - Hotkey-Einstellungen
echo   typefree.log      - Fehler- und Ereignisprotokoll
echo.
echo Zum manuellen Start:
echo   EXE direkt als Admin ausfuehren (Rechtsklick - Als Administrator)
echo.
echo Zum Stoppen:
echo   Tray-Icon (Mikrofon) - Rechtsklick - Beenden
echo.
pause