@echo off
title typeFREE deinstallieren
chcp 65001 >nul

echo ============================================
echo   typeFREE deinstallieren
echo ============================================
echo.
echo Entferne Registry-Eintrag (Apps & Features) ...
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\typeFREE" /f >nul 2>&1
echo.
echo Entferne Startmenue-Eintraege ...
rmdir /s /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\typeFREE" >nul 2>&1
echo.
echo Entferne Desktop-Verknuepfung ...
del "%USERPROFILE%\Desktop\typeFREE.lnk" >nul 2>&1
echo.
echo Entferne Aufgabenplanung ...
schtasks /Delete /TN "typeFREE" /F >nul 2>&1
schtasks /Delete /TN "typeFREE-Aufwachen" /F >nul 2>&1
echo.
echo Loesche Programmdateien ...
rmdir /s /q "%~dp0" >nul 2>&1
echo.
echo.
echo ✅ typeFREE wurde vollstaendig entfernt.
echo.
pause