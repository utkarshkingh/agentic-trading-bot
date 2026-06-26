# Builds the Python backend into a Tauri sidecar binary.
#
# Output is named with the Rust host target triple, which is what Tauri's
# externalBin mechanism expects (e.g. trading-backend-x86_64-pc-windows-msvc.exe).
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"

Write-Host "Freezing backend with PyInstaller..." -ForegroundColor Cyan
uv run pyinstaller trading-backend.spec --noconfirm

# Resolve the Rust host triple (requires the Rust toolchain).
$triple = ((rustc -Vv) | Select-String "^host:").ToString().Split(" ")[1]
$ext = if ($env:OS -eq "Windows_NT") { ".exe" } else { "" }

$dest = "$root\frontend\src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$src = "dist\trading-backend$ext"
$out = "$dest\trading-backend-$triple$ext"
Copy-Item $src $out -Force

Write-Host "Sidecar ready: $out" -ForegroundColor Green
