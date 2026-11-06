<#
.SYNOPSIS
    Startet und steuert OrbitDesk (Dashboard-Fenster und Taskleisten-Tray).

.DESCRIPTION
    Beendet bei Bedarf laufende Alt-Instanzen, räumt Locks auf und startet OrbitDesk sauber.

.PARAMETER NurLeiste
    Startet ausschließlich das Taskleisten-Symbol.

.PARAMETER NurUebersicht
    Startet ausschließlich das OrbitDesk-Dashboard.

.PARAMETER Stop
    Beendet alle OrbitDesk-Prozesse, ohne sie neu zu starten.

.PARAMETER Status
    Zeigt den aktuellen Status der laufenden Prozesse an.

.EXAMPLE
    .\orbitdesk.ps1
    Startet Tray und Dashboard frisch.
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
$PythonExe  = Join-Path $ScriptsDir "pythonw.exe"
$DatenDir   = Join-Path $env:USERPROFILE ".master-schalter"

if (-not (Test-Path $DatenDir)) {
    New-Item -ItemType Directory -Path $DatenDir -Force | Out-Null
}

function Get-OrbitDeskProzesse {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -match 'master-(schalter|leiste)|orbitdesk') -or
        ($_.Name -match 'python' -and $_.CommandLine -match 'master_schalter\.(uebersicht|leiste)|orbitdesk')
    }
}

if ($Status) {
    Write-Host "Laufende OrbitDesk-Prozesse:" -ForegroundColor Cyan
    $aktive = Get-OrbitDeskProzesse
    if ($aktive) {
        $aktive | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize
    } else {
        Write-Host "  Keine aktiven Prozesse gefunden." -ForegroundColor Yellow
    }
    exit 0
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " OrbitDesk: Steuerzentrale & Starter" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Bestehende Prozesse beenden
Write-Host "[1/3] Pruefe bestehende Prozesse..." -ForegroundColor Yellow
$ZielProzesse = Get-OrbitDeskProzesse
if ($ZielProzesse) {
    foreach ($proc in $ZielProzesse) {
        Write-Host "  -> Beende PID $($proc.ProcessId) ($($proc.Name))..." -ForegroundColor DarkYellow
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 600
    Write-Host "  Bestehende Prozesse beendet." -ForegroundColor Green
} else {
    Write-Host "  Keine bestehenden Prozesse gefunden." -ForegroundColor Gray
}

# 2. Sperren bereinigen
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
    Write-Host "`nAlle OrbitDesk-Komponenten wurden gestoppt (-Stop)." -ForegroundColor Magenta
    exit 0
}

# 3. Starten
Write-Host "[3/3] Starte OrbitDesk-Komponenten..." -ForegroundColor Yellow
$gestartet = @()

# A) Leiste (Tray)
if (-not $NurUebersicht) {
    $pLeiste = Start-Process -FilePath $PythonExe -ArgumentList "-m master_schalter.leiste" -WorkingDirectory $ProjektDir -PassThru
    Write-Host "  [OK] OrbitDesk Taskleisten-Symbol gestartet (PID $($pLeiste.Id))" -ForegroundColor Green
    $gestartet += "Taskleisten-Tray (PID $($pLeiste.Id))"
}

# B) Übersicht (Dashboard)
if (-not $NurLeiste) {
    $pSchalter = Start-Process -FilePath $PythonExe -ArgumentList "-m master_schalter.uebersicht" -WorkingDirectory $ProjektDir -PassThru
    Write-Host "  [OK] OrbitDesk Dashboard gestartet (PID $($pSchalter.Id))" -ForegroundColor Green
    $gestartet += "Dashboard (PID $($pSchalter.Id))"
}

Write-Host "`nErfolgreich gestartet:" -ForegroundColor Cyan
foreach ($item in $gestartet) {
    Write-Host "  * $item" -ForegroundColor White
}
Write-Host "========================================`n" -ForegroundColor Cyan
