@echo off
title typeFREE Einrichtung
chcp 65001 >nul

echo ============================================
echo   typeFREE - Einrichtung
echo ============================================
echo.

REM Prüfen, ob Python installiert ist
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Python ist nicht installiert.
    echo Bitte installiere Python von https://www.python.org/
    pause
    exit /b 1
)

echo Python gefunden.

REM Abhängigkeiten installieren
echo Installiere Abhängigkeiten...
pip install -r "%~dp0requirements.txt" >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Abhängigkeiten konnten nicht installiert werden.
    echo Versuche es manuell mit: pip install -r "%~dp0requirements.txt"
    pause
    exit /b 1
)

echo Abhängigkeiten installiert.

REM Prüfen ob pythonw.exe verfügbar ist
where pythonw >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNUNG: pythonw.exe nicht gefunden - typeFREE startet mit Terminal.
    set PYTHONW=python
) else (
    set PYTHONW=pythonw
)

REM Startverknüpfung erstellen
echo.
echo Erstelle Startverknüpfung...
(
    echo @echo off
    echo title typeFREE
    echo start /B %PYTHONW% "%~dp0typefree.py"
    echo exit
) > "%~dp0typeFREE_starten.cmd"

echo.
echo ============================================
echo   Fertig!
echo ============================================
echo.
echo Starte typeFREE mit:
echo   windows\typeFREE_starten.cmd
echo.
echo Oder per Doppelklick auf die neue Datei.
echo.
echo HINWEIS: typeFREE braucht Admin-Rechte fuer den Tastatur-Hook.
echo Starte die CMD als Administrator, falls der Hotkey nicht reagiert.
echo.
pause