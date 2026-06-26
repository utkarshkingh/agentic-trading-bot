# start-backend.ps1 — install deps and start the trading bot backend
Set-Location $PSScriptRoot\backend

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment with uv..."
    uv venv --python 3.11
}

Write-Host "Installing dependencies..."
uv pip install -e ".[fastapi]" --extra-index-url https://pypi.org/simple

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "IMPORTANT: Edit backend\.env and add your API keys before running." -ForegroundColor Yellow
    Write-Host "  OPENROUTER_API_KEY=sk-or-v1-..." -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

Write-Host "Starting backend on http://localhost:8000 ..."
.\.venv\Scripts\python -m uvicorn src.main:app --host localhost --port 8000 --reload
