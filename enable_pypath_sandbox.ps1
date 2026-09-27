<#
.SYNOPSIS
  Append Python site-packages to the current Trae CN session sandbox whitelist.

.DESCRIPTION
  Trae CN sandbox config is per-session:
    C:\Users\<user>\AppData\Roaming\Trae CN\ModularData\ai-agent\sandbox\<session_id>.json
  Restarting IDE creates a new session-id file and resets to defaults.
  This script scans that dir for the latest *.json (excluding -hooks suffix),
  and injects:
    C:\Python314\Lib\site-packages
  Idempotent: skips if already present.

.NOTES
  Python 3.14. If you later install a new Python version (e.g. 3.15),
  change $PySitePackages to its Lib\site-packages path.
#>

param(
    [string]$PySitePackages = "C:\Python314\Lib\site-packages",
    [string]$DirType = "lang_deps"
)

$ErrorActionPreference = "Stop"
$SandboxDir = Join-Path $env:APPDATA "Trae CN\ModularData\ai-agent\sandbox"

if (-not (Test-Path $SandboxDir)) {
    Write-Host "[!] Sandbox dir not found: $SandboxDir" -ForegroundColor Yellow
    Write-Host "    Make sure Trae CN has been started at least once." -ForegroundColor Yellow
    exit 1
}

$Latest = Get-ChildItem -Path $SandboxDir -Filter "*.json" -File |
    Where-Object { $_.Name -notmatch "-hooks\.json$" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $Latest) {
    Write-Host "[!] No session json found in sandbox dir." -ForegroundColor Yellow
    exit 1
}

Write-Host "[*] Target file: $($Latest.FullName)" -ForegroundColor Cyan
Write-Host "[*] Last write : $($Latest.LastWriteTime)" -ForegroundColor Cyan

$Raw = Get-Content -Path $Latest.FullName -Raw -Encoding UTF8

# Idempotency check: scan raw text for the exact path. JSON escapes each
# backslash as two, so build the needle in JSON-escaped form and use a
# literal Contains() — this avoids JSON object comparison quirks in PS 5.1.
$NeedleInJson = $PySitePackages.Replace('\', '\\')
if ($Raw.Contains($NeedleInJson)) {
    Write-Host "[=] Whitelist already contains $PySitePackages, no change." -ForegroundColor Green
    exit 0
}

$Config = $Raw | ConvertFrom-Json

$NewEntry = [PSCustomObject]@{
    file_inherit_user = $PySitePackages
    dir_type          = $DirType
}

$UpdatedPermission = @($Config.permission) + $NewEntry
$Config.permission = $UpdatedPermission

$Out = $Config | ConvertTo-Json -Depth 100
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($Latest.FullName, $Out, $Utf8NoBom)

Write-Host "[+] Appended whitelist entry:" -ForegroundColor Green
Write-Host "    Path: $PySitePackages" -ForegroundColor Green
Write-Host "    Type: $DirType" -ForegroundColor Green
Write-Host ""
Write-Host "[i] Note: if Trae CN is currently using this session, you may need to restart IDE to load new config." -ForegroundColor Yellow
