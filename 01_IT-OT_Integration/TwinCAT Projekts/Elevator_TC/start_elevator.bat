@echo off
echo ============================================
echo   Elevator Digital Twin - ADS Bridge Start
echo ============================================
echo.
echo Stelle sicher, dass TwinCAT im Run-Modus ist!
echo (Simulation Mode, gruenes Badge in XAE)
echo.
pause
start "" "%~dp0elevator_3d_demo.html"
cd /d "%~dp0ads_bridge"
npm start
