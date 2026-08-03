@echo off
title typeFREE Setup (Installation)
chcp 65001 >nul

REM ============================================
REM   typeFREE – Installations-Assistent
REM ============================================
REM
REM   Dieser Installer kopiert typeFREE in ein
REM   Zielverzeichnis, fragt den API-Key ab und
REM   richtet den Autostart ein.
REM
REM   Verwendung: setup.cmd
REM   ODER:       setup.cmd /S (silent, für Paketierung)
REM ============================================

setlocal enabledelayedexpansion

REM --------------------------------------------------
REM  Silent-Modus?
REM --------------------------------------------------
set "SILENT="
if /I "%1"=="/S" set SILENT=1

REM --------------------------------------------------
REM  Admin-Prüfung (kein PowerShell-Neustart mehr!)
REM --------------------------------------------------
REM Früher wurde hier per PowerShell neu gestartet – das führte
REM auf Windows 11 mit Leerzeichen im Pfad zu einer Endlos-Schleife.
REM Daher jetzt: Nur eine klare Ansage.
REM Der Nutzer startet das Skript per Rechtsklick → "Als Administrator".
REM --------------------------------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    cls
    echo ============================================
    echo    Fehler: Keine Administrator-Rechte
    echo ============================================
    echo.
    echo   typeFREE benoetigt Administrator-Rechte fuer:
    echo     - Installation in Programme
    echo     - Tastatur-Hook (globaler Hotkey)
    echo     - Aufgabenplanung (Autostart)
    echo.
    echo   Bitte schliesse dieses Fenster und starte
    echo   das Skript mit Rechtsklick -^> "Als Administrator ausfuehren"
    echo.
    echo   Oder druecke 1, um den sicheren Weg zu waehlen
    echo   (kein Admin noetig – typeFREE wird in einen
    echo    Benutzer-Ordner installiert).
    echo.
    echo   Druecke 2 zum Beenden.
    echo.
    choice /C 12 /N /M "1 = Ohne Admin fortfahren  2 = Beenden"
    if !errorlevel! equ 2 exit /b 1
    REM Ohne Admin: Ziel auf Benutzerordner setzen
    set "DEFAULT_DIR=%USERPROFILE%\typeFREE"
    set "INSTALL_DIR=%DEFAULT_DIR%"
    echo.
    echo   Fahre ohne Admin-Rechte fort ...
    echo   Installiere nach: %INSTALL_DIR%
    echo.
    pause
)

REM --------------------------------------------------
REM  Titel
REM --------------------------------------------------
if not defined SILENT (
    cls
    echo ============================================
    echo    typeFREE - Voice-to-Text
    echo    Installations-Assistent
    echo ============================================
    echo.
    echo   typeFREE wandelt Sprache in Text um.
    echo   Druecke einen Hotkey, sprich, und der Text
    echo   erscheint automatisch in jeder Anwendung.
    echo.
    echo ============================================
    echo.
    pause
)

REM --------------------------------------------------
REM  Zielordner
REM --------------------------------------------------
set "DEFAULT_DIR=%ProgramFiles%\typeFREE"
set "INSTALL_DIR=%DEFAULT_DIR%"

if not defined SILENT (
    cls
    echo ============================================
    echo    Schritt 1/4: Zielordner
    echo ============================================
    echo.
    echo   Standard: %DEFAULT_DIR%
    echo.
    echo   Moechtest du einen anderen Ordner?
    echo.
    choice /C JN /M "Anderen Ordner waehlen"
    if !errorlevel! equ 1 (
        set /p "INSTALL_DIR= Zielordner: "
    )
    echo.
    echo   Installiere nach: %INSTALL_DIR%
)

REM --------------------------------------------------
REM  API-Key abfragen
REM --------------------------------------------------
set "OPENROUTER_KEY="
set "OPENAI_KEY="

if not defined SILENT (
    cls
    echo ============================================
    echo    Schritt 2/4: API-Key
    echo ============================================
    echo.
    echo   typeFREE nutzt OpenRouter fuer die
    echo   Sprach-zu-Text-Umwandlung.
    echo.
    echo   Du brauchst einen kostenlosen API-Key von:
    echo     https://openrouter.ai/keys
    echo.
    echo   Registrierung kostenlos, 1 Dollar Guthaben
    echo   gibt es gratis dazu.
    echo.
    echo ============================================
    echo.
    set /p "OPENROUTER_KEY= OpenRouter API-Key eingeben: "
    echo.
    echo ============================================
    echo   OpenAI API-Key (optional)
    echo ============================================
    echo.
    echo   Nur ausfuellen, wenn du eigenes OpenAI-
    echo   Guthaben hast. Sonst leer lassen – dann
    echo   transkribiert typeFREE automatisch ueber
    echo   OpenRouter.
    echo.
    set /p "OPENAI_KEY= OpenAI Key (Enter = leer): "
    echo.
)

REM --------------------------------------------------
REM  EXE-Pfad ermitteln (neben diesem Skript)
REM --------------------------------------------------
set "SOURCE=%~dp0"
if "%SOURCE:~-1%"=="\" set "SOURCE=%SOURCE:~0,-1%"

REM EXE liegt entweder im selben Ordner oder in ..\dist\
set "EXE_SRC=%SOURCE%\typeFREE.exe"
if not exist "%EXE_SRC%" set "EXE_SRC=%SOURCE%\..\dist\typeFREE.exe"
if not exist "%EXE_SRC%" set "EXE_SRC=%SOURCE%\..\..\dist\typeFREE.exe"

if not exist "%EXE_SRC%" (
    echo.
    echo   FEHLER: typeFREE.exe nicht gefunden!
    echo.
    echo   Erwartet an einem dieser Orte:
    echo     %SOURCE%\typeFREE.exe
    echo     %SOURCE%\..\dist\typeFREE.exe
    echo.
    if not defined SILENT pause
    exit /b 1
)

REM --------------------------------------------------
REM  Installation
REM --------------------------------------------------
if not defined SILENT (
    cls
    echo ============================================
    echo    Schritt 3/4: Installiere ...
    echo ============================================
    echo.
)

REM Zielordner erstellen
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Dateien kopieren
copy "%EXE_SRC%" "%INSTALL_DIR%\typeFREE.exe" >nul
copy "%SOURCE%\config.json" "%INSTALL_DIR%\config.json" >nul 2>&1

REM .env erstellen
(
    echo # typeFREE API-Keys
    echo # Erstellt am %DATE% um %TIME%
    echo.
    echo OPENROUTER_API_KEY=%OPENROUTER_KEY%
) > "%INSTALL_DIR%\.env"
if defined OPENAI_KEY (
    echo OPENAI_API_KEY=%OPENAI_KEY% >> "%INSTALL_DIR%\.env"
)

if not defined SILENT (
    echo   ✅ typeFREE.exe kopiert
    echo   ✅ config.json kopiert
    if defined OPENROUTER_KEY (
        echo   ✅ .env mit API-Key erstellt
    ) else (
        echo   ⚠️  Kein API-Key eingegeben – .env ist leer
    )
    echo.
)

REM --------------------------------------------------
REM  Desktop-Verknuepfung
REM --------------------------------------------------
set "DESKTOP=%USERPROFILE%\Desktop"
set "LINK=%DESKTOP%\typeFREE.lnk"

REM Pruefen, ob Desktop existiert
if exist "%DESKTOP%" (
    powershell -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%LINK%'); $SC.TargetPath = '%INSTALL_DIR%\typeFREE.exe'; $SC.WorkingDirectory = '%INSTALL_DIR%'; $SC.Description = 'typeFREE - Voice-to-Text'; $SC.Save()" >nul 2>&1
    if exist "%LINK%" (
        if not defined SILENT echo   ✅ Desktop-Verknuepfung erstellt
    )
)

REM --------------------------------------------------
REM  Startmenü
REM --------------------------------------------------
set "STARTMENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\typeFREE"
if not exist "%STARTMENU%" mkdir "%STARTMENU%" >nul 2>&1
if exist "%STARTMENU%" (
    copy "%LINK%" "%STARTMENU%\typeFREE.lnk" >nul 2>&1
    REM Uninstall-Verknüpfung
    powershell -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%STARTMENU%\typeFREE deinstallieren.lnk'); $SC.TargetPath = '%INSTALL_DIR%\deinstallieren.cmd'; $SC.Description = 'typeFREE entfernen'; $SC.Save()" >nul 2>&1
    if not defined SILENT echo   ✅ Startmenue-Eintrag erstellt
)

REM --------------------------------------------------
REM  Deinstallations-Skript
REM --------------------------------------------------
call :create_uninstall_script "%INSTALL_DIR%"
if not defined SILENT echo   ✅ Deinstallations-Skript erstellt

echo. >nul

REM --------------------------------------------------
REM  Autostart einrichten
REM --------------------------------------------------
set "AUTOSTART=0"
if not defined SILENT (
    cls
    echo ============================================
    echo    Schritt 4/4: Autostart
    echo ============================================
    echo.
    echo   Soll typeFREE automatisch starten bei:
    echo     - Windows-Anmeldung
    echo     - Aufwachen aus Ruhezustand
    echo.
    choice /C JN /M "Autostart einrichten"
    if !errorlevel! equ 1 set "AUTOSTART=1"
    echo.
) else (
    set "AUTOSTART=1"
)
echo   Autostart: %AUTOSTART%

REM Aufgaben anlegen
if %AUTOSTART% equ 1 (
    schtasks /Create /SC ONLOGON /TN "typeFREE" /TR "'%INSTALL_DIR%\typeFREE.exe' --autostart" /RL HIGHEST /F /IT >nul 2>&1
    schtasks /Create /SC ONEVENT /EC System /MO "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and EventID=107]]" /TN "typeFREE-Aufwachen" /TR "'%INSTALL_DIR%\typeFREE.exe' --autostart" /RL HIGHEST /F /IT >nul 2>&1
    if not defined SILENT (
        echo   ✅ Autostart eingerichtet
        echo     - Start bei Anmeldung
        echo     - Start beim Aufwachen
    )
)
echo.

REM --------------------------------------------------
REM  Windows "Apps & Features"-Eintrag
REM --------------------------------------------------
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\typeFREE" /v DisplayName /t REG_SZ /d "typeFREE - Voice-to-Text" /f >nul 2>&1
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\typeFREE" /v UninstallString /t REG_SZ /d "\"%INSTALL_DIR%\deinstallieren.cmd\"" /f >nul 2>&1
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\typeFREE" /v DisplayIcon /t REG_SZ /d "\"%INSTALL_DIR%\typeFREE.exe\",0" /f >nul 2>&1
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\typeFREE" /v DisplayVersion /t REG_SZ /d "2.0" /f >nul 2>&1
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\typeFREE" /v Publisher /t REG_SZ /d "typeFREE" /f >nul 2>&1
if not defined SILENT echo   ✅ In "Apps & Features" registriert

REM --------------------------------------------------
REM  Installations-Info speichern
REM --------------------------------------------------
echo { > "%INSTALL_DIR%\install.json"
echo   "install_dir": "%INSTALL_DIR:\=\\", >> "%INSTALL_DIR%\install.json"
echo   "installed_at": "%DATE% %TIME%", >> "%INSTALL_DIR%\install.json"
echo   "autostart": %AUTOSTART% >> "%INSTALL_DIR%\install.json"
echo } >> "%INSTALL_DIR%\install.json"

REM --------------------------------------------------
REM  Fertig
REM --------------------------------------------------
if not defined SILENT (
    cls
    echo ============================================
    echo    Installation abgeschlossen!
    echo ============================================
    echo.
    echo   typeFREE wurde installiert unter:
    echo     %INSTALL_DIR%
    echo.
    echo   Starte typeFREE jetzt?
    echo.
    choice /C JN /M "Jetzt starten"
    echo.
    if !errorlevel! equ 1 (
        echo Starte typeFREE ...
        powershell -Command "Start-Process '%INSTALL_DIR%\typeFREE.exe' -Verb RunAs"
        echo.
        echo   ✅ typeFREE gestartet
        echo   Das Mikrofon-Symbol erscheint in der Taskleiste.
    )
    echo.
    echo ============================================
    echo   Wichtige Hinweise:
    echo ============================================
    echo.
    echo   Hotkey: Alt + Ae (aendern im Tray-Menue)
    echo   Logdatei: %INSTALL_DIR%\typefree.log
    echo   .env-Datei: %INSTALL_DIR%\.env
    echo   Deinstallieren: %INSTALL_DIR%\deinstallieren.cmd
    echo.
    echo   API-Key aendern: %INSTALL_DIR%\.env editieren
    echo.
    pause
)

exit /b 0

REM ============================================
REM  Funktion: Deinstallations-Skript erstellen
REM ============================================
:create_uninstall_script
set "UNINSTALL_SCRIPT=%~1\deinstallieren.cmd"
set "INST_DIR=%~1"
(
echo @echo off
echo title typeFREE deinstallieren
echo chcp 65001 ^>nul
echo.
echo REM Admin erhoehen
echo openfiles ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 (
echo     echo Starte als Administrator ...
echo     powershell -Command "Start-Process cmd -ArgumentList '/c \"%%~f0\"' -Verb RunAs"
echo     exit /b 0
echo )
echo.
echo echo ============================================
echo echo   typeFREE deinstallieren
echo echo ============================================
echo echo.
echo echo Entferne Registry-Eintrag (Apps ^& Features) ...
echo reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\typeFREE" /f ^>nul 2^>^&1
echo.
echo echo Entferne Startmenue-Eintraege ...
echo rmdir /s /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\typeFREE" ^>nul 2^>^&1
echo.
echo echo Entferne Desktop-Verknuepfung ...
echo del "%USERPROFILE%\Desktop\typeFREE.lnk" ^>nul 2^>^&1
echo.
echo echo Entferne Aufgabenplanung ...
echo schtasks /Delete /TN "typeFREE" /F ^>nul 2^>^&1
echo schtasks /Delete /TN "typeFREE-Aufwachen" /F ^>nul 2^>^&1
echo.
echo echo Loesche Programmdateien ...
echo rmdir /s /q "%INST_DIR%" ^>nul 2^>^&1
echo.
echo echo.
echo echo ✅ typeFREE wurde vollstaendig entfernt.
echo echo.
echo pause
) > "%UNINSTALL_SCRIPT%"
exit /b 0