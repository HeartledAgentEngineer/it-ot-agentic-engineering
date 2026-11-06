@echo off
title OrbitDesk Starter
setlocal
set "BASE=C:\Users\sebas\Desktop\workspace agentic engineering\02_Softwareentwicklung_IT\master-schalter"
cd /d "%BASE%"

:: 1. Verwaiste Alt-Prozesse beenden
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.Name -match 'master-(schalter|leiste)') -or ($_.Name -match 'python' -and $_.CommandLine -match 'master_schalter\.(uebersicht|leiste)') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: 2. Lock-Dateien aufraeumen
del /F /Q "%USERPROFILE%\.master-schalter\uebersicht.lock" >nul 2>&1
del /F /Q "%USERPROFILE%\.master-schalter\leiste.lock" >nul 2>&1

:: 3. Taskleisten-Dienst (Tray) starten
start "" "%BASE%\.venv\Scripts\pythonw.exe" -m master_schalter.leiste

:: 4. OrbitDesk Cockpit-Fenster starten
start "" "%BASE%\.venv\Scripts\pythonw.exe" -m master_schalter.uebersicht
endlocal
