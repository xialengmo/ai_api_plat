param()

$backendDir = $PSScriptRoot
$template = Join-Path $backendDir '.env.mysql8'
$target = Join-Path $backendDir '.env'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if (!(Test-Path $template)) {
    Write-Error "Template not found: $template"
    exit 1
}

if (Test-Path $target) {
    $backup = Join-Path $backendDir (".env.backup-" + $timestamp)
    Copy-Item $target $backup -Force
    Write-Host "Backup created: $backup"
}

Copy-Item $template $target -Force
Write-Host 'Switched backend env to MySQL 8+ mode.'
Write-Host "Active file: $target"
Write-Host 'Next step: restart the Django backend service.'
