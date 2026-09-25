@echo off
title typeFREE - Update einspielen
chcp 65001 >nul

REM ============================================
REM   Automatische Admin-Erhoehung per UAC
REM ============================================
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo typeFREE-Update braucht Administrator-Rechte:
    echo   - Schreiben nach %%ProgramFiles%%\typeFREE
    echo   - laufende Instanz beenden
    echo.
    echo Starte mit Administrator-Rechten neu ...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b 0
)

echo ============================================
echo   typeFREE - Update einspielen
echo ============================================
echo.

REM --- 1. Neue EXE muss gebaut sein -------------------------------------------
set "NEU=%~dp0..\dist\typeFREE.exe"
if not exist "%NEU%" (
    echo FEHLER: %NEU% fehlt.
    echo.
    echo Erst bauen:
    echo   py -3.12 -m PyInstaller typeFREE.spec
    echo.
    pause
    exit /b 1
)

REM --- 2. Installationsordner finden ------------------------------------------
set "ZIEL=%ProgramFiles%\typeFREE"
if not exist "%ZIEL%\typeFREE.exe" set "ZIEL=%USERPROFILE%\typeFREE"
if not exist "%ZIEL%\typeFREE.exe" (
    echo FEHLER: Keine typeFREE-Installation gefunden.
    echo Gesucht in: %%ProgramFiles%%\typeFREE und %%USERPROFILE%%\typeFREE
    echo.
    pause
    exit /b 1
)

for %%A in ("%NEU%") do set "NEU_GROESSE=%%~zA"
echo Neue EXE : %NEU%  ^(%NEU_GROESSE% Bytes^)
echo Ziel      : %ZIEL%
echo.

REM --- 3. Laufende Instanz beenden --------------------------------------------
echo [1/4] Laufendes typeFREE beenden ...
taskkill /IM typeFREE.exe /F >nul 2>&1
REM Der Einzelinstanz-Mutex wird vom Kernel freigegeben; kurz warten, bis die
REM Datei nicht mehr gesperrt ist.
timeout /t 2 /nobreak >nul

REM --- 4. EXE austauschen ------------------------------------------------------
echo [2/4] Neue EXE kopieren ...
copy /Y "%NEU%" "%ZIEL%\typeFREE.exe" >nul
if errorlevel 1 (
    echo   FEHLER: Kopieren fehlgeschlagen. Laeuft typeFREE noch?
    echo   Task-Manager: typeFREE.exe beenden, dann dieses Skript erneut starten.
    pause
    exit /b 1
)
echo   OK

REM --- 5. Fehlende Schluessel aus der Projekt-.env uebernehmen ----------------
REM Neue Anbieter brauchen neue Schluessel. Vorhandene Zeilen bleiben unberuehrt,
REM es wird nur ergaenzt, was fehlt.
echo [3/4] API-Schluessel pruefen ...
if not exist "%ZIEL%\.env" type nul > "%ZIEL%\.env"
for %%K in (OPENROUTER_API_KEY ELEVENLABS_API_KEY GROQ_API_KEY OPENAI_API_KEY) do (
    findstr /B /C:"%%K=" "%ZIEL%\.env" >nul 2>&1
    if errorlevel 1 (
        findstr /B /C:"%%K=" "%~dp0..\.env" >nul 2>&1
        if errorlevel 1 (
            echo   FEHLT: %%K - steht auch nicht in der Projekt-.env
        ) else (
            findstr /B /C:"%%K=" "%~dp0..\.env" >> "%ZIEL%\.env"
            echo   ergaenzt: %%K
        )
    )
)
echo   Pruefung fertig

REM --- 6. Neue Fassung starten -------------------------------------------------
echo [4/4] typeFREE neu starten ...
start "" "%ZIEL%\typeFREE.exe"

echo.
echo ============================================
echo   Fertig - neue Fassung laeuft
echo ============================================
echo.
echo Kontrolle (Log neben der EXE):
echo   findstr /C:"typeFREE gestartet" "%ZIEL%\typefree.log"
echo   findstr /C:"Zeiten:"             "%ZIEL%\typefree.log"
echo.
echo Erwartete Zeile beim Start: "Transkription ueber: groq, openrouter, openai"
echo.
pause
