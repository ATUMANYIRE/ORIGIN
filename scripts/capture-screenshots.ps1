$ErrorActionPreference = "Stop"

Write-Host "=== Capturing High-Resolution ORIGIN Hackathon Screenshots ===" -ForegroundColor Cyan

# 1. Start Backend Server
Write-Host "Starting Backend API Server on 127.0.0.1:8000..." -ForegroundColor Yellow
$backendProc = Start-Process -FilePath "backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory "backend" `
    -PassThru

# 2. Start Frontend Server
Write-Host "Starting Frontend Production Server on 127.0.0.1:3000..." -ForegroundColor Yellow
$frontendProc = Start-Process -FilePath "node.exe" `
    -ArgumentList "node_modules/next/dist/bin/next start -p 3000" `
    -WorkingDirectory "frontend" `
    -PassThru

try {
    Write-Host "Waiting 6 seconds for servers to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 6

    # 3. Execute Screenshot Capture via Playwright
    Write-Host "Executing Playwright Screenshot Capture..." -ForegroundColor Cyan
    Push-Location "frontend"
    try {
        npx playwright test e2e/screenshots.spec.ts
        if ($LASTEXITCODE -ne 0) {
            throw "Playwright screenshot capture failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }

    Write-Host "SUCCESS: All production screenshots captured into submission/SCREENSHOTS/" -ForegroundColor Green
} finally {
    Write-Host "Terminating background test servers..." -ForegroundColor Yellow
    if ($backendProc -and !$backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue }
    if ($frontendProc -and !$frontendProc.HasExited) { Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue }
}
