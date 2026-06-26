# start-frontend.ps1 — install deps and start the Next.js trading dashboard
Set-Location $PSScriptRoot\frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..."
    npm install
}

Write-Host "Starting frontend on http://localhost:3000 ..."
$env:TRADING_BACKEND_URL = "http://localhost:8000/"
npm run dev
