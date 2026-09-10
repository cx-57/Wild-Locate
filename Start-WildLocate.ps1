$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    Write-Error 'Project environment missing. Follow the setup instructions in README.md first.'
}
Start-Process -FilePath $projectPython -ArgumentList ('"' + (Join-Path $PSScriptRoot 'launch.pyw') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
