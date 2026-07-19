@echo off
title SetlistMixPrepper
cd /d "%~dp0"
echo ================================================
echo   SetlistMixPrepper wird gestartet...
echo   Browser oeffnet sich automatisch.
echo   Dieses Fenster offen lassen solange du die App nutzt.
echo   Zum Beenden: Strg+C oder Fenster schliessen.
echo ================================================
python app.py
pause
