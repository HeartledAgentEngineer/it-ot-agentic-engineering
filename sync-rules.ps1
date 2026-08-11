# ==============================================================================
# sync-rules.ps1
# KI-Regel-Compiler (OOP-Inheritance) für den Agenten-Workspace
# ==============================================================================

$GlobalBaseFile = Join-Path $PSScriptRoot 'AGENTS.md'

if (-not (Test-Path $GlobalBaseFile)) {
    Write-Error 'Globale AGENTS.md im Hauptverzeichnis nicht gefunden! Bitte erstelle sie im Hauptordner.'
    exit
}

Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '   KI-REGEL-COMPILER (OOP-Inheritance)           ' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host 'Pruefe globale Basisklasse (AGENTS.md)...' -ForegroundColor Yellow

# Suche nach allen CLAUDE_EXTENDS.md in den Unterordnern (max. 3 Ebenen tief)
$ExtendsFiles = Get-ChildItem -Path $PSScriptRoot -Filter 'CLAUDE_EXTENDS.md' -Recurse -Depth 3

if ($null -eq $ExtendsFiles -or $ExtendsFiles.Count -eq 0) {
    Write-Host 'Keine CLAUDE_EXTENDS.md Dateien in den Unterordnern gefunden!' -ForegroundColor Red
    Write-Host 'Bitte lege eine CLAUDE_EXTENDS.md in deinen Projektordnern an.' -ForegroundColor Yellow
    exit
}

$NL = [System.Environment]::NewLine

foreach ($ExtendsFile in $ExtendsFiles) {
    $ProjectDir = $ExtendsFile.DirectoryName
    $ProjectName = Split-Path $ProjectDir -Leaf
    $TargetFile = Join-Path $ProjectDir 'CLAUDE.md'
    
    Write-Host ''
    Write-Host "Kompiliere Regeln fuer Projekt: [$ProjectName]..." -ForegroundColor Green
    Write-Host "Lese Subclass: $($ExtendsFile.FullName)" -ForegroundColor DarkGray
    
    $ExtendsContent = Get-Content $ExtendsFile.FullName -Raw -Encoding utf8
    
    # Relativen Pfad zur globalen Basis ermitteln (z. B. ../CLAUDE.md)
    Push-Location $ProjectDir
    $RelBase = ((Resolve-Path -Relative $GlobalBaseFile) -replace '\\', '/') -replace '^\./', ''
    Pop-Location

    $Header = "<!--" + $NL
    $Header += "  DIESE DATEI WURDE AUTOMATISCH GENERIERT (sync-rules.ps1)" + $NL
    $Header += "  AENDERUNGEN IN DIESER DATEI WERDEN BEIM NAECHSTEN RUN UEBERSCHRIEBEN!" + $NL
    $Header += "  Bitte aendere die globale AGENTS.md im Hauptverzeichnis oder die lokale CLAUDE_EXTENDS.md." + $NL
    $Header += "-->" + $NL + $NL

    # Verweis statt Vollkopie: die Basisregeln stehen nur noch an einer Stelle.
    $Pointer = '> **Basis-Regelwerk:** Es gelten weiterhin die Kernregeln aus `' + $RelBase + '` (Workspace-Wurzel).' + $NL
    $Pointer += '> Sie sind hier bewusst nicht kopiert, damit es nur eine Quelle gibt. Claude Code zieht sie ueber die Wurzel-CLAUDE.md mit herein, Cline liest sie nativ.' + $NL

    $Separator = $NL + "<!-- LOKALE PROJEKT-ERWEITERUNGEN (EXTENDS) -->" + $NL + $NL

    $CombinedContent = $Header + $Pointer + $Separator + $ExtendsContent
    
    Set-Content -Path $TargetFile -Value $CombinedContent -Encoding utf8
    Write-Host "[OK] CLAUDE.md erfolgreich generiert in: $ProjectDir" -ForegroundColor Green
}

Write-Host ''
Write-Host 'Kompilierung erfolgreich abgeschlossen!' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
