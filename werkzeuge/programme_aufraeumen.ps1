<#
.SYNOPSIS
  Programme aufräumen: alle installierten Programme anzeigen, „Brauche ich" merken,
  ausgewählte Programme deinstallieren (08.10.2026).

.DESCRIPTION
  Ein Fenster listet alle deinstallierbaren Programme (klassische Programme aus der
  Registry und auf Wunsch Store-Apps) mit Größe, Herausgeber, Installationsdatum und
  einer Empfehlung:
    - "Deine Liste"      : Programme, die du laut 08.10.2026 brauchst (Hermes, Claude, DeepL,
                           PowerShell, pCloud, Google Drive, OneDrive, Teams, Git, Python, …)
    - "Laufzeit/Treiber" : Visual-C++-Pakete, .NET, WebView2, Treiber — davon hängen andere
                           Programme ab
    - "Arbeit/Studium"   : Beckhoff/TwinCAT, Visual Studio, Office, SQL Server, …
    - "Du entscheidest"  : alles andere
  "Deine Liste" und "Laufzeit/Treiber" sind vorab als "Brauche ich" geschützt.

  Bedienung:
    1. "Brauche ich" anhaken schützt ein Programm. Die Auswahl wird sofort gespeichert und
       beim nächsten Start wieder geladen.
    2. "Deinstallieren" bei allem anhaken, was weg darf. Geschützte Programme lassen sich
       erst nach dem Abhaken von "Brauche ich" auswählen.
    3. "Ausgewählte deinstallieren …" fragt noch einmal nach. Dann startet für jedes
       Programm dessen eigenes Deinstallationsprogramm nacheinander (mit dessen Rückfragen,
       nichts läuft still im Hintergrund).
  Es wird nichts deinstalliert, ohne dass du es angehakt und bestätigt hast.

  Ablage (außerhalb des Repos): %LOCALAPPDATA%\ProgrammAufraeumen\
    brauche_ich.json  — deine Schutzliste
    protokoll.csv     — was wann deinstalliert wurde (Name, Version, Befehl, Exit-Code).
                        Eine Deinstallation lässt sich nicht rückgängig machen; das
                        Protokoll sagt, was neu zu installieren wäre.

.PARAMETER NurListe
  Ohne Fenster und ohne Deinstallation: die Liste als Tabelle in der Konsole
  (kein Administrator nötig).

.PARAMETER MitWindowsApps
  Store-Apps von Microsoft (Rechner, Fotos, …) mit anzeigen. Standard: aus.

.EXAMPLE
  # Als Administrator (Rechtsklick auf PowerShell -> "Als Administrator ausführen"):
  & "C:\Users\sebas\Desktop\workspace agentic engineering\werkzeuge\programme_aufraeumen.ps1"

.EXAMPLE
  # Nur anschauen, ohne Admin:
  & ".\werkzeuge\programme_aufraeumen.ps1" -NurListe
#>
param(
    [switch]$NurListe,
    [switch]$MitWindowsApps
)

$ErrorActionPreference = 'Stop'
$Ablage = Join-Path $env:LOCALAPPDATA 'ProgrammAufraeumen'
$SchutzDatei = Join-Path $Ablage 'brauche_ich.json'
$ProtokollDatei = Join-Path $Ablage 'protokoll.csv'

# ── Empfehlung (reine Funktion) ──────────────────────────────────────────────

$MusterMeineListe = '(?i)\b(Hermes|Claude|DeepL|PowerShell|pCloud|Google Drive|OneDrive|Teams|Windows Terminal|' +
    'Bitwarden|Git|GitHub|Python|Node\.js|Android Studio|Microsoft Edge|Google Chrome|Comet|Visual Studio Code|' +
    'WhatsApp|uv|Codex|Antigravity|Cursor|scrcpy|FFmpeg|Android SDK|Platform-Tools)\b'
$MusterLaufzeit = '(?i)(Redistributable|Runtime|Laufzeit|WebView2|\.NET|Driver|Treiber|Chipset|Firmware|Realtek|' +
    'Intel\(R\)|Intel®|NVIDIA|AMD Software|Synaptics|Dolby|Bluetooth|Wireless|Wi-?Fi|WLAN|Thunderbolt|' +
    'Update Health|Microsoft Update|Windows App Runtime|VCLibs|UI\.Xaml|DirectX)'
$MusterArbeit = '(?i)(Beckhoff|TwinCAT|Visual Studio(?! Code)|SQL Server|Microsoft Office|Microsoft 365|OneNote|' +
    'Outlook|DIALux|CEWE|MATLAB|MiKTeX|\bTeX\b|TeXstudio|Siemens|\bTIA\b|CODESYS|Docker|VirtualBox|VMware|Java|JDK|' +
    'Windows Software Development Kit|Windows SDK)'

function Get-Empfehlung {
    param([string]$Name, [string]$Herausgeber)
    $text = "$Name $Herausgeber"
    if ($Name -match $MusterLaufzeit) { return 'Laufzeit/Treiber' }
    # Herstellerpakete zuerst: "TwinCAT Multiuser Git" ist SPS-Werkzeug, nicht dein Git.
    if ($text -match '(?i)Beckhoff|TwinCAT|Siemens|CODESYS') { return 'Arbeit/Studium' }
    if ($Name -match $MusterMeineListe) { return 'Deine Liste' }
    if ($text -match $MusterArbeit) { return 'Arbeit/Studium' }
    return 'Du entscheidest'
}

function Test-StandardGeschuetzt {
    param([string]$Empfehlung)
    return ($Empfehlung -eq 'Deine Liste' -or $Empfehlung -eq 'Laufzeit/Treiber' -or $Empfehlung -eq 'Windows-App')
}

# ── Programme einsammeln ─────────────────────────────────────────────────────

function Get-OrdnerGroesseMB {
    param([string]$Pfad)
    if (-not $Pfad) { return $null }
    $sauber = $Pfad.Trim().Trim('"')
    if (-not $sauber -or -not (Test-Path -LiteralPath $sauber -PathType Container)) { return $null }
    $summe = (Get-ChildItem -LiteralPath $sauber -Recurse -Force -File -ErrorAction SilentlyContinue |
              Measure-Object -Property Length -Sum).Sum
    if (-not $summe) { return $null }
    return [math]::Round($summe / 1MB, 0)
}

function Format-Datum {
    param($Wert)
    $t = "$Wert"
    if ($t -match '^(\d{4})(\d{2})(\d{2})$') { return "$($Matches[3]).$($Matches[2]).$($Matches[1])" }
    return $t
}

function Get-KlassischeProgramme {
    $quellen = @(
        @{ Pfad = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'; Bereich = 'alle Benutzer' },
        @{ Pfad = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'; Bereich = 'alle Benutzer (32 Bit)' },
        @{ Pfad = 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'; Bereich = 'nur du' }
    )
    $gesehen = @{}
    foreach ($q in $quellen) {
        $eintraege = @(Get-ItemProperty -Path $q.Pfad -ErrorAction SilentlyContinue)
        foreach ($e in $eintraege) {
            if (-not $e.DisplayName) { continue }
            if (-not ($e.UninstallString -or $e.QuietUninstallString)) { continue }
            if ($e.SystemComponent -eq 1 -or $e.ParentKeyName) { continue }
            if (@('Update', 'Hotfix', 'Security Update') -contains $e.ReleaseType) { continue }
            $name = "$($e.DisplayName)".Trim()
            $schluessel = "Programm|$name|$($e.DisplayVersion)"
            if ($gesehen.ContainsKey($schluessel)) { continue }
            $gesehen[$schluessel] = $true
            $mb = $null
            if ($e.EstimatedSize) { $mb = [math]::Round([double]$e.EstimatedSize / 1024, 0) }
            [pscustomobject]@{
                Schluessel  = "Programm|$name"
                Name        = $name
                Version     = "$($e.DisplayVersion)"
                Herausgeber = "$($e.Publisher)".Trim()
                Installiert = (Format-Datum $e.InstallDate)
                GroesseMB   = $mb
                Ort         = "$($e.InstallLocation)"
                Art         = 'Programm'
                Bereich     = $q.Bereich
                Befehl      = "$($e.UninstallString)"
                Paket       = ''
            }
        }
    }
}

function Get-StoreApps {
    param([switch]$MitWindowsApps)
    $pakete = @(Get-AppxPackage -ErrorAction SilentlyContinue | Where-Object {
        -not $_.IsFramework -and -not $_.NonRemovable -and "$($_.SignatureKind)" -eq 'Store'
    })
    foreach ($p in $pakete) {
        $vonMicrosoft = "$($p.Publisher)" -match 'CN=Microsoft Corporation'
        $name = "$($p.Name)"
        $wichtigVonMicrosoft = $name -match '(?i)Teams|OneNote|OfficeHub|Outlook|Clipchamp|Todos|BingNews|BingWeather|GamingApp|Xbox|Solitaire|ZuneMusic|ZuneVideo|People|YourPhone|PowerAutomate|QuickAssist|Copilot'
        if ($vonMicrosoft -and -not $MitWindowsApps -and -not $wichtigVonMicrosoft) { continue }
        $herausgeber = "$($p.Publisher)" -replace '^CN=([^,]+).*$', '$1'
        [pscustomobject]@{
            Schluessel  = "Store-App|$name"
            Name        = $name
            Version     = "$($p.Version)"
            Herausgeber = $herausgeber
            Installiert = ''
            GroesseMB   = $null
            Ort         = "$($p.InstallLocation)"
            Art         = 'Store-App'
            Bereich     = 'nur du'
            Befehl      = "Remove-AppxPackage -Package $($p.PackageFullName)"
            Paket       = "$($p.PackageFullName)"
            VonMicrosoft = $vonMicrosoft
        }
    }
}

function Get-AlleProgramme {
    param([switch]$MitWindowsApps)
    $liste = @(Get-KlassischeProgramme) + @(Get-StoreApps -MitWindowsApps:$MitWindowsApps)
    $i = 0
    foreach ($p in $liste) {
        $i++
        if ($null -eq $p.GroesseMB -and $p.Ort) {
            Write-Progress -Activity 'Größen ermitteln' -Status $p.Name -PercentComplete ([int](100 * $i / [math]::Max(1, $liste.Count)))
            $p.GroesseMB = Get-OrdnerGroesseMB $p.Ort
        }
        $empfehlung = Get-Empfehlung -Name $p.Name -Herausgeber $p.Herausgeber
        if ($p.Art -eq 'Store-App' -and $p.VonMicrosoft -and $empfehlung -eq 'Du entscheidest') { $empfehlung = 'Windows-App' }
        $p | Add-Member -NotePropertyName Empfehlung -NotePropertyValue $empfehlung -Force
    }
    Write-Progress -Activity 'Größen ermitteln' -Completed
    return $liste
}

# ── Schutzliste ("Brauche ich") ──────────────────────────────────────────────

function Read-Schutzliste {
    $ergebnis = @{}
    if (Test-Path -LiteralPath $SchutzDatei) {
        try {
            $daten = Get-Content -LiteralPath $SchutzDatei -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($eig in $daten.PSObject.Properties) { $ergebnis[$eig.Name] = [bool]$eig.Value }
        } catch {
            Write-Warning "Schutzliste nicht lesbar, es gelten die Vorgaben: $($_.Exception.Message)"
        }
    }
    return $ergebnis
}

function Save-Schutzliste {
    param([hashtable]$Liste)
    if (-not (Test-Path -LiteralPath $Ablage)) { New-Item -ItemType Directory -Path $Ablage | Out-Null }
    $objekt = [ordered]@{}
    foreach ($k in ($Liste.Keys | Sort-Object)) { $objekt[$k] = $Liste[$k] }
    ($objekt | ConvertTo-Json) | Set-Content -LiteralPath $SchutzDatei -Encoding UTF8
}

function Test-Geschuetzt {
    param($Programm, [hashtable]$Schutz)
    if ($Schutz.ContainsKey($Programm.Schluessel)) { return $Schutz[$Programm.Schluessel] }
    return (Test-StandardGeschuetzt $Programm.Empfehlung)
}

# ── Deinstallation ───────────────────────────────────────────────────────────

function Split-Befehl {
    <# "C:\Pfad\uninst.exe" /x  ->  (Programm, Argumente). Reine Funktion. #>
    param([string]$Befehl)
    $s = "$Befehl".Trim()
    if ($s -match '(?i)^"?msiexec(\.exe)?"?\s+/[IX]\s*(\{[0-9A-F\-]+\})') {
        return @('msiexec.exe', "/X$($Matches[2])")
    }
    if ($s.StartsWith('"')) {
        $ende = $s.IndexOf('"', 1)
        if ($ende -gt 0) { return @($s.Substring(1, $ende - 1), $s.Substring($ende + 1).Trim()) }
    }
    $i = $s.ToLower().IndexOf('.exe')
    if ($i -ge 0) { return @($s.Substring(0, $i + 4), $s.Substring($i + 4).Trim()) }
    return @($s, '')
}

function Invoke-Deinstallation {
    param($Programm)
    if ($Programm.Art -eq 'Store-App') {
        Remove-AppxPackage -Package $Programm.Paket
        return 0
    }
    $teile = Split-Befehl $Programm.Befehl
    if ($teile[1]) {
        $prozess = Start-Process -FilePath $teile[0] -ArgumentList $teile[1] -Wait -PassThru
    } else {
        $prozess = Start-Process -FilePath $teile[0] -Wait -PassThru
    }
    return $prozess.ExitCode
}

function Write-Protokoll {
    param($Programm, $ExitCode, [string]$Meldung)
    if (-not (Test-Path -LiteralPath $Ablage)) { New-Item -ItemType Directory -Path $Ablage | Out-Null }
    [pscustomobject]@{
        Zeit = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'); Name = $Programm.Name; Version = $Programm.Version
        Art = $Programm.Art; Herausgeber = $Programm.Herausgeber; GroesseMB = $Programm.GroesseMB
        Befehl = $Programm.Befehl; ExitCode = $ExitCode; Meldung = $Meldung
    } | Export-Csv -LiteralPath $ProtokollDatei -Append -NoTypeInformation -Encoding UTF8 -Delimiter ';'
}

function Get-FreiGB {
    $laufwerk = Get-PSDrive -Name C -ErrorAction SilentlyContinue
    if (-not $laufwerk) { return '?' }
    return ('{0:N1}' -f ($laufwerk.Free / 1GB))
}

# ── Nur anschauen ────────────────────────────────────────────────────────────

if ($NurListe) {
    $schutz = Read-Schutzliste
    Get-AlleProgramme -MitWindowsApps:$MitWindowsApps |
        Sort-Object @{ Expression = { if ($null -eq $_.GroesseMB) { -1 } else { $_.GroesseMB } } } -Descending |
        Select-Object @{ n = 'MB'; e = { $_.GroesseMB } }, Name, Empfehlung,
                      @{ n = 'Geschützt'; e = { if (Test-Geschuetzt $_ $schutz) { 'ja' } else { '' } } }, Art |
        Format-Table -AutoSize | Out-String -Width 220
    "C: frei: $(Get-FreiGB) GB"
    return
}

# ── Fenster ──────────────────────────────────────────────────────────────────

$istAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $istAdmin) {
    Write-Host 'Bitte PowerShell als Administrator starten (Rechtsklick -> "Als Administrator ausführen").' -ForegroundColor Yellow
    Write-Host 'Nur anschauen geht ohne Admin:  -NurListe'
    exit 1
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$schutz = Read-Schutzliste
$programme = @()
$tabelle = New-Object System.Data.DataTable
[void]$tabelle.Columns.Add('Deinstallieren', [bool])
[void]$tabelle.Columns.Add('BraucheIch', [bool])
[void]$tabelle.Columns.Add('Name', [string])
[void]$tabelle.Columns.Add('MB', [double])
[void]$tabelle.Columns.Add('Empfehlung', [string])
[void]$tabelle.Columns.Add('Herausgeber', [string])
[void]$tabelle.Columns.Add('Installiert', [string])
[void]$tabelle.Columns.Add('Art', [string])
[void]$tabelle.Columns.Add('Schluessel', [string])

function Update-Tabelle {
    $script:programme = @(Get-AlleProgramme -MitWindowsApps:$script:zeigeWindowsApps)
    $tabelle.Rows.Clear()
    foreach ($p in $script:programme) {
        $zeile = $tabelle.NewRow()
        $zeile.Deinstallieren = $false
        $zeile.BraucheIch = [bool](Test-Geschuetzt $p $schutz)
        $zeile.Name = $p.Name
        if ($null -ne $p.GroesseMB) { $zeile.MB = [double]$p.GroesseMB } else { $zeile.MB = [DBNull]::Value }
        $zeile.Empfehlung = $p.Empfehlung
        $zeile.Herausgeber = $p.Herausgeber
        $zeile.Installiert = $p.Installiert
        $zeile.Art = $p.Art
        $zeile.Schluessel = $p.Schluessel
        $tabelle.Rows.Add($zeile)
    }
}

$script:zeigeWindowsApps = [bool]$MitWindowsApps
$fenster = New-Object System.Windows.Forms.Form
$fenster.Text = 'Programme aufräumen'
$fenster.Size = New-Object System.Drawing.Size(1180, 760)
$fenster.StartPosition = 'CenterScreen'
$fenster.Font = New-Object System.Drawing.Font('Segoe UI', 9.5)

$hinweis = New-Object System.Windows.Forms.Label
$hinweis.Dock = 'Top'
$hinweis.Height = 46
$hinweis.Padding = New-Object System.Windows.Forms.Padding(8, 6, 8, 0)
$hinweis.Text = '„Brauche ich" schützt ein Programm (wird gespeichert). „Deinstallieren" anhaken, was weg darf. ' +
    'Nichts passiert ohne deine Bestätigung; jedes Programm fragt mit seinem eigenen Deinstallationsprogramm nach.'

$leiste = New-Object System.Windows.Forms.FlowLayoutPanel
$leiste.Dock = 'Top'
$leiste.Height = 38
$leiste.Padding = New-Object System.Windows.Forms.Padding(6, 4, 6, 0)
$sucheLabel = New-Object System.Windows.Forms.Label
$sucheLabel.Text = 'Suchen:'
$sucheLabel.AutoSize = $true
$sucheLabel.Margin = New-Object System.Windows.Forms.Padding(0, 6, 4, 0)
$suche = New-Object System.Windows.Forms.TextBox
$suche.Width = 260
$windowsApps = New-Object System.Windows.Forms.CheckBox
$windowsApps.Text = 'Auch Windows-Apps zeigen'
$windowsApps.AutoSize = $true
$windowsApps.Checked = $script:zeigeWindowsApps
$windowsApps.Margin = New-Object System.Windows.Forms.Padding(16, 4, 0, 0)
$leiste.Controls.AddRange(@($sucheLabel, $suche, $windowsApps))

$raster = New-Object System.Windows.Forms.DataGridView
$raster.Dock = 'Fill'
$raster.AllowUserToAddRows = $false
$raster.AllowUserToDeleteRows = $false
$raster.RowHeadersVisible = $false
$raster.SelectionMode = 'FullRowSelect'
$raster.AutoSizeColumnsMode = 'Fill'
$ansicht = New-Object System.Data.DataView($tabelle)
$ansicht.Sort = 'MB DESC'
$raster.DataSource = $ansicht

$unten = New-Object System.Windows.Forms.FlowLayoutPanel
$unten.Dock = 'Bottom'
$unten.Height = 46
$unten.Padding = New-Object System.Windows.Forms.Padding(6)
$status = New-Object System.Windows.Forms.Label
$status.AutoSize = $true
$status.Margin = New-Object System.Windows.Forms.Padding(0, 8, 24, 0)
$knopfLos = New-Object System.Windows.Forms.Button
$knopfLos.Text = 'Ausgewählte deinstallieren …'
$knopfLos.AutoSize = $true
$knopfZu = New-Object System.Windows.Forms.Button
$knopfZu.Text = 'Schließen'
$knopfZu.AutoSize = $true
$unten.Controls.AddRange(@($status, $knopfLos, $knopfZu))

$fenster.Controls.Add($raster)
$fenster.Controls.Add($leiste)
$fenster.Controls.Add($hinweis)
$fenster.Controls.Add($unten)

function Update-Status {
    $anzahl = 0; $mb = 0
    foreach ($z in $tabelle.Rows) {
        if ($z.Deinstallieren) { $anzahl++; if ($z.MB -isnot [DBNull]) { $mb += $z.MB } }
    }
    $status.Text = "Ausgewählt: $anzahl Programme, ca. $('{0:N1}' -f ($mb / 1024)) GB   ·   C: frei: $(Get-FreiGB) GB"
}

$raster.add_DataBindingComplete({
    foreach ($spalte in $raster.Columns) { $spalte.ReadOnly = $true }
    $raster.Columns['Deinstallieren'].ReadOnly = $false
    $raster.Columns['BraucheIch'].ReadOnly = $false
    $raster.Columns['BraucheIch'].HeaderText = 'Brauche ich'
    $raster.Columns['MB'].HeaderText = 'Größe (MB)'
    $raster.Columns['Schluessel'].Visible = $false
    $raster.Columns['Deinstallieren'].FillWeight = 45
    $raster.Columns['BraucheIch'].FillWeight = 45
    $raster.Columns['Name'].FillWeight = 220
    $raster.Columns['MB'].FillWeight = 50
    $raster.Columns['MB'].DefaultCellStyle.Format = 'N0'
    foreach ($zeile in $raster.Rows) {
        if ($zeile.Cells['BraucheIch'].Value -eq $true) {
            $zeile.DefaultCellStyle.ForeColor = [System.Drawing.Color]::DimGray
        } else {
            $zeile.DefaultCellStyle.ForeColor = [System.Drawing.Color]::Black
        }
    }
})

# Häkchen sofort übernehmen (sonst erst beim Verlassen der Zelle)
$raster.add_CurrentCellDirtyStateChanged({
    if ($raster.IsCurrentCellDirty) { $raster.CommitEdit([System.Windows.Forms.DataGridViewDataErrorContexts]::Commit) }
})

$raster.add_CellValueChanged({
    param($absender, $e)
    if ($e.RowIndex -lt 0) { return }
    $spalte = $raster.Columns[$e.ColumnIndex].Name
    $zeile = $ansicht[$e.RowIndex].Row
    if ($spalte -eq 'BraucheIch') {
        $schutz[$zeile.Schluessel] = [bool]$zeile.BraucheIch
        Save-Schutzliste $schutz
        if ($zeile.BraucheIch -and $zeile.Deinstallieren) { $zeile.Deinstallieren = $false }
    } elseif ($spalte -eq 'Deinstallieren' -and $zeile.Deinstallieren -and $zeile.BraucheIch) {
        $zeile.Deinstallieren = $false
        # Achtung: „ “ ” gelten in PowerShell als Anführungszeichen — in "…"-Texten nur ' verwenden.
        [System.Windows.Forms.MessageBox]::Show("'$($zeile.Name)' ist als 'Brauche ich' geschützt. Erst dort den Haken entfernen.",
            'Geschützt', 'OK', 'Information') | Out-Null
    }
    Update-Status
})

$suche.add_TextChanged({
    $t = $suche.Text.Replace("'", "''").Replace('[', '[[]').Replace('%', '[%]').Replace('*', '[*]')
    if ($t) { $ansicht.RowFilter = "Name LIKE '%$t%' OR Herausgeber LIKE '%$t%' OR Empfehlung LIKE '%$t%'" }
    else { $ansicht.RowFilter = '' }
})

$windowsApps.add_CheckedChanged({
    $script:zeigeWindowsApps = $windowsApps.Checked
    $fenster.Cursor = 'WaitCursor'
    Update-Tabelle
    $fenster.Cursor = 'Default'
    Update-Status
})

$knopfZu.add_Click({ $fenster.Close() })

$knopfLos.add_Click({
    $auswahl = @()
    foreach ($z in $tabelle.Rows) {
        if ($z.Deinstallieren -and -not $z.BraucheIch) {
            $treffer = $script:programme | Where-Object { $_.Schluessel -eq $z.Schluessel } | Select-Object -First 1
            if ($treffer) { $auswahl += $treffer }
        }
    }
    if (-not $auswahl.Count) {
        [System.Windows.Forms.MessageBox]::Show('Nichts ausgewählt.', 'Programme aufräumen') | Out-Null
        return
    }
    $namen = ($auswahl | Select-Object -First 25 | ForEach-Object { " • $($_.Name)" }) -join "`n"
    if ($auswahl.Count -gt 25) { $namen += "`n … und $($auswahl.Count - 25) weitere" }
    $antwort = [System.Windows.Forms.MessageBox]::Show(
        "Diese $($auswahl.Count) Programme deinstallieren?`n`n$namen`n`nJedes Programm startet sein eigenes Deinstallationsprogramm. " +
        'Eine Deinstallation lässt sich nicht rückgängig machen (das Protokoll sagt, was neu zu installieren wäre).',
        'Wirklich deinstallieren?', 'YesNo', 'Warning')
    if ($antwort -ne 'Yes') { return }
    $ok = 0; $fehler = 0
    foreach ($p in $auswahl) {
        $status.Text = "Deinstalliere: $($p.Name) …"
        $fenster.Refresh()
        try {
            $code = Invoke-Deinstallation $p
            Write-Protokoll $p $code ''
            if ($code -eq 0 -or $code -eq 3010 -or $code -eq 1641) { $ok++ } else { $fehler++ }
        } catch {
            Write-Protokoll $p $null $_.Exception.Message
            $fehler++
        }
    }
    $fenster.Cursor = 'WaitCursor'
    Update-Tabelle
    $fenster.Cursor = 'Default'
    Update-Status
    [System.Windows.Forms.MessageBox]::Show(
        "Fertig: $ok ohne Fehler, $fehler mit Fehler oder abgebrochen.`nC: frei: $(Get-FreiGB) GB`n`nProtokoll: $ProtokollDatei",
        'Programme aufräumen') | Out-Null
})

$fenster.Cursor = 'WaitCursor'
Update-Tabelle
$fenster.Cursor = 'Default'
Update-Status
[void]$fenster.ShowDialog()
