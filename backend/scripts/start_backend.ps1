# AI Workflow Orchestration Platform - Backend Startup Script

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "AI WORKFLOW ORCHESTRATION PLATFORM - BACKEND STARTUP" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Change to project root (this script lives in backend/scripts)
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

# Check PostgreSQL
Write-Host "Checking PostgreSQL..." -ForegroundColor Yellow
$postgres = Get-Process postgres -ErrorAction SilentlyContinue
if ($postgres) {
    Write-Host "[OK] PostgreSQL is running" -ForegroundColor Green
} else {
    Write-Host "[ERROR] PostgreSQL is not running!" -ForegroundColor Red
    Write-Host "Please start PostgreSQL first." -ForegroundColor Red
    exit 1
}

# Check Python virtual environment
Write-Host "Checking Python environment..." -ForegroundColor Yellow
if (Test-Path ".\backend\venv\Scripts\python.exe") {
    Write-Host "[OK] Virtual environment found" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run: python -m venv backend\venv" -ForegroundColor Red
    exit 1
}

# Check .env file
Write-Host "Checking configuration..." -ForegroundColor Yellow
if (Test-Path ".\.env") {
    Write-Host "[OK] .env file found" -ForegroundColor Green
} else {
    Write-Host "[WARNING] .env file not found! Using defaults." -ForegroundColor Yellow
}

# Run database migrations
Write-Host "Running database migrations..." -ForegroundColor Yellow
Set-Location ".\backend"
& .\venv\Scripts\python.exe -m alembic upgrade head
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Database migrations complete" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Migration failed!" -ForegroundColor Red
    exit 1
}

# Start the backend
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "STARTING BACKEND SERVER" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend will be available at: http://localhost:8000" -ForegroundColor Green
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Health Check: http://localhost:8000/health" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

Set-Location ..
& .\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
