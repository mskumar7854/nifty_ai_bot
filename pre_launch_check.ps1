# ============================================
# 🧪 NIFTY AI AGENT - PRE-LAUNCH VERIFICATION
# PowerShell Version for Windows/Local Testing
# Verified the Persistence Pillar and State Recovery
# ============================================

$ErrorActionPreference = "Stop"

# 1. Start the container
Write-Host "🏗️  STEP 1: Starting container..." -ForegroundColor Cyan
docker-compose up -d --build

try {
    # 2. Wait for bot to initialize
    Write-Host "⏳ STEP 2: Waiting for bot to initialize (15s)..." -ForegroundColor Cyan
    Start-Sleep -Seconds 15

    # 3. Create a mock signal in the database
    Write-Host "📡 STEP 3: Inserting mock 'pending' signal into SQLite..." -ForegroundColor Cyan
    $timestamp = [DateTimeOffset]::Now.ToUnixTimeSeconds()
    $sql = "INSERT OR REPLACE INTO signals (id, symbol, signal_type, direction, entry_price, stop_loss, target_1, confidence, status, created_at) VALUES ('VFY-999', 'NIFTY', 'BUY_CE', 'BULLISH', 22700.0, 22650.0, 22800.0, 85.0, 'pending', $timestamp);"
    
    # We use docker exec to ensure we are writing into the container's volume mount
    docker exec nifty-trader-prod sqlite3 data/trading_v4.db "$sql"

    # 4. Verify host volume
    Write-Host "🔍 STEP 4: Verifying host volume..." -ForegroundColor Cyan
    if (Test-Path "data/trading_v4.db") {
        Write-Host "   ✅ Found data/trading_v4.db" -ForegroundColor Green
        Get-Item "data/trading_v4.db" | Select-Object Name, Length, LastWriteTime
    } else {
        Write-Error "   ❌ ERROR: Database file not found in host volume!"
    }

    # 5. Destroy the container
    Write-Host "💣 STEP 5: Destroying container completely..." -ForegroundColor Yellow
    docker-compose down
    
    # Optional: verify the file STAYS there after down
    if (Test-Path "data/trading_v4.db") {
        Write-Host "   ✅ Persistent file survived 'docker-compose down'" -ForegroundColor Green
    }

    # 6. Rebuild and restart
    Write-Host "🔄 STEP 6: Rebuilding and restarting..." -ForegroundColor Cyan
    docker-compose up -d --build
    Start-Sleep -Seconds 10

    # 7. Check if the bot recovers its state from the persistent volume
    Write-Host "📊 STEP 7: Checking bot recovery logs..." -ForegroundColor Cyan
    $logs = docker logs nifty-trader-prod 2>&1
    if ($logs -match "Recovery|Recovered|Loaded") {
        Write-Host "   ✅ Bot logs show recovery sequence!" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Recovery markers not found in logs. Check manual logs." -ForegroundColor Gray
    }

    # 8. Final DB verification
    Write-Host "🏁 STEP 8: Final DB verification..." -ForegroundColor Cyan
    $count = docker exec nifty-trader-prod sqlite3 data/trading_v4.db "SELECT COUNT(*) FROM signals WHERE id='VFY-999';"
    if ($count -eq "1") {
        Write-Host "   ✅ PERSISTENCE VERIFIED: Signal 'VFY-999' survived the container destruction!" -ForegroundColor Green
    } else {
        Write-Error "   ❌ ERROR: Signal 'VFY-999' was lost! Check volume mounting."
    }

} finally {
    Write-Host "🧹 Cleaning up..." -ForegroundColor Gray
    docker-compose down
    Write-Host "✅ PRE-LAUNCH CHECK COMPLETE." -ForegroundColor Green
}
