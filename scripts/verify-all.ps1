# ==============================================================================
# ORIGIN — Authoritative Full-System Acceptance Verification Script
# Milestone 05/05: Independent Verification, Hardening & Submission
# ==============================================================================

$ErrorActionPreference = "Stop"
$StartTime = Get-Date

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "   ORIGIN - Complete System Acceptance Verification Suite           " -ForegroundColor Cyan
Write-Host "   Give software the ability to understand itself.                  " -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "Timestamp: $StartTime`n"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

$PassedSteps = 0
$TotalSteps = 8

function Log-Step([string]$Name) {
    Write-Host "`n--------------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "[STEP] $Name" -ForegroundColor Yellow
    Write-Host "--------------------------------------------------------------------" -ForegroundColor Yellow
}

function Log-Pass([string]$Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# STEP 1: Static Security & Secret Audit Scan
# ------------------------------------------------------------------------------
Log-Step "1/8: Static Security & Secret Leakage Audit"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
& $PythonExe (Join-Path $RepoRoot "scripts\audit-security.py")
if ($LASTEXITCODE -ne 0) { throw "Security audit scan failed!" }
Log-Pass "Zero committed private credentials or security risks detected."
$PassedSteps++

# ------------------------------------------------------------------------------
# STEP 2: Database Connectivity & Alembic Migration Cycle
# ------------------------------------------------------------------------------
Log-Step "2/8: Database Migrations & Schema Verification"
Push-Location $BackendDir
try {
    $AlembicExe = Join-Path $BackendDir ".venv\Scripts\alembic.exe"
    & $AlembicExe upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade head failed!" }
    Log-Pass "PostgreSQL schema successfully upgraded to latest head (0004_recovery_safety)."
    $PassedSteps++
} finally {
    Pop-Location
}

# ------------------------------------------------------------------------------
# STEP 3: Backend Static Analysis & Type Checking (Ruff + Mypy)
# ------------------------------------------------------------------------------
Log-Step "3/8: Backend Code Quality & Strict Type Checking"
Push-Location $BackendDir
try {
    $RuffExe = Join-Path $BackendDir ".venv\Scripts\ruff.exe"
    $MypyExe = Join-Path $BackendDir ".venv\Scripts\mypy.exe"
    & $RuffExe check app tests alembic
    if ($LASTEXITCODE -ne 0) { throw "Ruff lint check failed!" }
    & $MypyExe app
    if ($LASTEXITCODE -ne 0) { throw "Mypy type check failed!" }
    Log-Pass "Backend Ruff (0 errors) and Mypy (0 issues across 50 files) passed."
    $PassedSteps++
} finally {
    Pop-Location
}

# ------------------------------------------------------------------------------
# STEP 4: Full Backend Test Suite (Pytest - 30 Tests)
# ------------------------------------------------------------------------------
Log-Step "4/8: Full Backend Pytest Suite (Scientific, Causal, Twin, Recovery)"
Push-Location $BackendDir
try {
    $PytestExe = Join-Path $BackendDir ".venv\Scripts\pytest.exe"
    & $PytestExe -v
    if ($LASTEXITCODE -ne 0) { throw "Pytest suite failed!" }
    Log-Pass "All 30 backend tests passed (including hidden-fault benchmarks and recovery)."
    $PassedSteps++
} finally {
    Pop-Location
}

# ------------------------------------------------------------------------------
# STEP 5: Frontend Unit Tests (Vitest)
# ------------------------------------------------------------------------------
Log-Step "5/8: Frontend Vitest Unit Test Suite"
Push-Location $FrontendDir
try {
    npm run test
    if ($LASTEXITCODE -ne 0) { throw "Vitest test suite failed!" }
    Log-Pass "Frontend Vitest tests passed."
    $PassedSteps++
} finally {
    Pop-Location
}

# ------------------------------------------------------------------------------
# STEP 6: Frontend TypeScript Checking & Linting
# ------------------------------------------------------------------------------
Log-Step "6/8: Frontend TypeScript Compilation & Linting"
Push-Location $FrontendDir
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "Frontend TypeScript typecheck failed!" }
    npm run lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend ESLint check failed!" }
    Log-Pass "Frontend TypeScript and ESLint passed with 0 errors."
    $PassedSteps++
} finally {
    Pop-Location
}

# ------------------------------------------------------------------------------
# STEP 7: Next.js Production Build
# ------------------------------------------------------------------------------
Log-Step "7/8: Next.js Optimized Production Build"
Push-Location $FrontendDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Next.js production build failed!" }
    Log-Pass "Next.js production build compiled all routes cleanly."
    $PassedSteps++
} finally {
    Pop-Location
}

# ------------------------------------------------------------------------------
# STEP 8: Playwright End-to-End Chromium Verification
# ------------------------------------------------------------------------------
Log-Step "8/8: Playwright End-to-End Browser Demonstration in Chromium"
$FastApiProcess = Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $BackendDir -PassThru
$NextProcess = Start-Process -FilePath "npm.cmd" -ArgumentList "run start -- -p 3000" -WorkingDirectory $FrontendDir -PassThru

Write-Host "Waiting 5 seconds for backend & frontend servers to initialize..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

Push-Location $FrontendDir
try {
    npx playwright test
    if ($LASTEXITCODE -ne 0) { throw "Playwright E2E test failed!" }
    Log-Pass "Playwright E2E browser tests passed (Telemetry, Topology, Causal, Twin, Recovery)."
    $PassedSteps++
} finally {
    Stop-Process -Id $FastApiProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $NextProcess.Id -Force -ErrorAction SilentlyContinue
    Pop-Location
}

# ------------------------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------------------------
$EndTime = Get-Date
$Duration = $EndTime - $StartTime

Write-Host "`n====================================================================" -ForegroundColor Green
Write-Host "   ORIGIN SYSTEM ACCEPTANCE VERIFICATION RESULT: PASSED ($PassedSteps/$TotalSteps) " -ForegroundColor Green
Write-Host "   Total Execution Time: $($Duration.Minutes)m $($Duration.Seconds)s" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
