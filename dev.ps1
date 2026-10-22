param([ValidateSet('agent', 'web', 'check', 'migrate', 'sync-java')][string]$Service = 'check')
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
if ($Service -eq 'sync-java') {
    & (Join-Path $projectRoot 'travel-agent\scripts\sync-java-preferences.ps1')
    return
}
if ($Service -eq 'web') {
    Push-Location (Join-Path $projectRoot 'hmdp-plus\hmdp-vue3')
    try { npm run dev } finally { Pop-Location }
    return
}
Push-Location (Join-Path $projectRoot 'travel-agent')
try {
    if ($Service -eq 'agent') { uv run --no-sync uvicorn app.main:app }
    elseif ($Service -eq 'migrate') { & '.\.venv\Scripts\python.exe' -m app.memory.admin init }
    else { & '.\.venv\Scripts\python.exe' scripts\check-stack.py }
} finally { Pop-Location }
