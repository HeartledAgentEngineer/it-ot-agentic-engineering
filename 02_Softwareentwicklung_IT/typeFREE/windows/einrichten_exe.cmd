@echo off
title typeFREE Einrichtung (EXE-Modus)
chcp 65001 >nul

echo ============================================
echo   typeFREE - Einrichtung (EXE-Modus)
echo ============================================
echo.

REM Prüfen, ob die EXE existiert
set "PROJEKT=%~dp0..\"
set "EXE=%PROJEKT%dist\typeFREE.exe"

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

REM EXE als Admin testen – per Rechtsklick "Als Administrator ausführen"
echo ============================================
echo   typeFREE starten
echo ============================================
echo.
echo Starte typeFREE... (Admin-Rechte fuer Tastatur-Hook)
echo.

REM ShellRunAs für Admin-Rechte – startet die UAC-Abfrage
REM /runas startet als Administrator
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
echo Soll typeFREE automatisch beim Anmelden starten?
choice /C JN /M "Autostart einrichten"
if %errorlevel% equ 1 (
    echo.
    echo Erstelle Aufgabenplanung fuer Benutzer %USERNAME%...
    
    REM Aufgabenplanung: Start bei Anmeldung, max. Privilegien
    schtasks /Create /SC ONLOGON /TN "typeFREE" /TR "'%EXE%' --autostart" /RL HIGHEST /F /IT
    
    REM Zweite Aufgabe: Start beim Aufwachen aus Ruhezustand
    schtasks /Create /SC ONEVENT /EC System /MO "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and EventID=107]]" /TN "typeFREE-Aufwachen" /TR "'%EXE%' --autostart" /RL HIGHEST /F /IT
    
    if %errorlevel% equ 0 (
        echo.
        echo ✅ Aufgabenplanung eingerichtet:
        echo   - Start bei Anmeldung
        echo   - Start beim Aufwachen
        echo.
        echo HINWEIS: Die Aufgabenplanung startet typeFREE im Hintergrund.
        echo Ein Neustart oder eine erneute Anmeldung aktiviert den Autostart.
    ) else (
        echo.
        echo ⚠️  Fehler beim Einrichten der Aufgabenplanung.
        echo Bitte CMD als Administrator ausfuehren.
    )
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
echo Zum manuellen Start:
echo   EXE direkt als Admin ausfuehren (Rechtsklick - Als Administrator)
echo.
echo Zum Stoppen:
echo   Tray-Icon (Mikrofon) - Rechtsklick - Beenden
echo.
pause