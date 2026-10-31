# Run script for Legend Discord Bot in PowerShell
$host.UI.RawUI.WindowTitle = "Legend Discord Bot"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     Starting Legend Discord Bot        " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[Error] Virtual environment not found." -ForegroundColor Red
    Pause
    exit 1
}

if (-not (Test-Path ".\.env")) {
    Write-Host "[Notice] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item .\.env.example .\.env
    Write-Host "Please edit .env and configure your DISCORD_BOT_TOKEN before starting." -ForegroundColor Yellow
    Pause
    exit 1
}

& ".\.venv\Scripts\python.exe" "src/main.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[Notice] Bot stopped. Check logs/bot.log for detailed output." -ForegroundColor Yellow
    Pause
}
