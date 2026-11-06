<#
.SYNOPSIS
    Alias für masterschalter.ps1
#>
[CmdletBinding()]
param(
    [switch]$NurLeiste,
    [switch]$NurUebersicht,
    [switch]$Stop,
    [switch]$Status
)
& "$PSScriptRoot\masterschalter.ps1" @PSBoundParameters
