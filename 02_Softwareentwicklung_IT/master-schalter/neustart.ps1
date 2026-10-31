<#
.SYNOPSIS
    Startet den Master-Schalter (Übersichtsfenster und/oder Taskleisten-Symbol) sauber neu.

.DESCRIPTION
    Beendet laufende Instanzen von master-schalter.exe und master-leiste.exe (sowie
    zugehörige python/pythonw-Instanzen), räumt Lock-Dateien auf und startet die
    Windows-Executables (.exe) entkoppelt neu.

.PARAMETER NurLeiste
    Startet ausschließlich das Taskleisten-Symbol (master-leiste-gui.exe) neu.

.PARAMETER NurUebersicht
    Startet ausschließlich das Übersichts-Dashboard (master-schalter-gui.exe) neu.

.PARAMETER Stop
    Beendet alle Master-Schalter-Prozesse, ohne sie neu zu starten.

.PARAMETER Status
    Zeigt nur den aktuellen Status der laufenden Prozesse an.
#>
[CmdletBinding()]
param(
    [switch]$NurLeiste,
    [switch]$NurUebersicht,
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "SilentlyContinue"

$ProjektDir = "C:\Users\sebas\Desktop\workspace agentic engineering\02_Softwareentwicklung_IT\master-schalter"
$ScriptsDir = Join-Path $ProjektDir ".venv\Scripts"
$DatenDir   = Join-Path $env:USERPROFILE ".master-schalter"

if (-not (Test-Path $DatenDir)) {
    New-Item -ItemType Directory -Path $DatenDir -Force | Out-Null
}

$SchalterExe = Join-Path $ScriptsDir "master-schalter-gui.exe"
$LeisteExe   = Join-Path $ScriptsDir "master-leiste-gui.exe"

function Get-MasterProzesse {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -match 'master-(schalter|leiste)') -or
        ($_.Name -match 'python' -and $_.CommandLine -match 'master_schalter\.(uebersicht|leiste)')
    }
}

if ($Status) {
    Write-Host "Laufende Master-Schalter Prozesse:" -ForegroundColor Cyan
    $aktive = Get-MasterProzesse
    if ($aktive) {
        $aktive | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize
    } else {
        Write-Host "  Keine aktiven Prozesse gefunden." -ForegroundColor Yellow
    }
    exit 0
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Master-Schalter Neustart-Dienst" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Laufende Prozesse beenden
Write-Host "[1/3] Suche laufende Master-Schalter Prozesse..." -ForegroundColor Yellow
$ZielProzesse = Get-MasterProzesse
if ($ZielProzesse) {
    foreach ($proc in $ZielProzesse) {
        Write-Host "  -> Beende PID $($proc.ProcessId) ($($proc.Name))..." -ForegroundColor DarkYellow
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 600
    Write-Host "  Alle Prozesse beendet." -ForegroundColor Green
} else {
    Write-Host "  Keine laufenden Prozesse gefunden." -ForegroundColor Gray
}

# 2. Lock-Dateien bereinigen
Write-Host "[2/3] Pruefe Instanz-Sperren..." -ForegroundColor Yellow
$Locks = @("uebersicht.lock", "leiste.lock")
foreach ($l in $Locks) {
    $lockPfad = Join-Path $DatenDir $l
    if (Test-Path $lockPfad) {
        Remove-Item -Path $lockPfad -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "  Sperren frei." -ForegroundColor Green

if ($Stop) {
    Write-Host "`nAlle Master-Schalter-Komponenten wurden gestoppt (-Stop)." -ForegroundColor Magenta
    exit 0
}

# 3. Entkoppelt neu starten
Write-Host "[3/3] Starte Komponenten als .exe neu..." -ForegroundColor Yellow
$gestartet = @()

# A) Leiste (Tray)
if (-not $NurUebersicht) {
    if (Test-Path $LeisteExe) {
        $logLeisteOut = Join-Path $DatenDir "leiste-ausgabe.log"
        $logLeisteErr = Join-Path $DatenDir "leiste.log"
        $pLeiste = Start-Process -FilePath $LeisteExe -WorkingDirectory $ProjektDir -RedirectStandardOutput $logLeisteOut -RedirectStandardError $logLeisteErr -PassThru
        Write-Host "  [OK] Master-Leiste gestartet (PID $($pLeiste.Id))" -ForegroundColor Green
        $gestartet += "Master-Leiste (PID $($pLeiste.Id))"
    } else {
        Write-Host "  [FEHLER] $LeisteExe nicht gefunden!" -ForegroundColor Red
    }
}

# B) Übersicht (GUI)
if (-not $NurLeiste) {
    if (Test-Path $SchalterExe) {
        $logSchalterOut = Join-Path $DatenDir "uebersicht-ausgabe.log"
        $logSchalterErr = Join-Path $DatenDir "uebersicht-fehler.log"
        $pSchalter = Start-Process -FilePath $SchalterExe -WorkingDirectory $ProjektDir -RedirectStandardOutput $logSchalterOut -RedirectStandardError $logSchalterErr -PassThru
        Write-Host "  [OK] Master-Schalter Übersicht gestartet (PID $($pSchalter.Id))" -ForegroundColor Green
        $gestartet += "Master-Schalter (PID $($pSchalter.Id))"
    } else {
        Write-Host "  [FEHLER] $SchalterExe nicht gefunden!" -ForegroundColor Red
    }
}

Write-Host "`nErfolgreich neu gestartet:" -ForegroundColor Cyan
foreach ($item in $gestartet) {
    Write-Host "  * $item" -ForegroundColor White
}
Write-Host "========================================`n" -ForegroundColor Cyan
