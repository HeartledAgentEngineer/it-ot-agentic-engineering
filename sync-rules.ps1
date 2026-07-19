# ==============================================================================
# sync-rules.ps1
# KI-Regel-Compiler (OOP-Inheritance) für den Agenten-Workspace
# ==============================================================================

$GlobalBaseFile = Join-Path $PSScriptRoot 'CLAUDE.md'

if (-not (Test-Path $GlobalBaseFile)) {
    Write-Error 'Globale CLAUDE.md im Hauptverzeichnis nicht gefunden! Bitte erstelle sie im Hauptordner.'
    exit
}

Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '   KI-REGEL-COMPILER (OOP-Inheritance)           ' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host 'Lese globale Basisklasse (CLAUDE.md)...' -ForegroundColor Yellow

$BaseContent = Get-Content $GlobalBaseFile -Raw -Encoding utf8

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
    
    $Header = "<!--" + $NL
    $Header += "  DIESE DATEI WURDE AUTOMATISCH GENERIERT (sync-rules.ps1)" + $NL
    $Header += "  AENDERUNGEN IN DIESER DATEI WERDEN BEIM NAECHSTEN RUN UEBERSCHRIEBEN!" + $NL
    $Header += "  Bitte aendere die globale CLAUDE.md im Hauptverzeichnis oder die lokale CLAUDE_EXTENDS.md." + $NL
    $Header += "-->" + $NL + $NL

    $Separator = $NL + $NL + "<!-- LOKALE PROJEKT-ERWEITERUNGEN (EXTENDS) -->" + $NL + $NL

    $CombinedContent = $Header + $BaseContent + $Separator + $ExtendsContent
    
    Set-Content -Path $TargetFile -Value $CombinedContent -Encoding utf8
    Write-Host "[OK] CLAUDE.md erfolgreich generiert in: $ProjectDir" -ForegroundColor Green
}

Write-Host ''
Write-Host 'Kompilierung erfolgreich abgeschlossen!' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
