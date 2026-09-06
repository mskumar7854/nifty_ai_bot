#!/bin/bash

# ============================================
# 🏥 NIFTY AI AGENT - HEALTH CHECK & RECOVERY
# Designed for Mumbai VPS (Docker)
# ============================================

# Load environment variables for Telegram notifications
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

CONTAINER_NAME="nifty-trader-prod"

# 1. Check if Docker container is running
if ! docker ps --filter "status=running" | grep -q "$CONTAINER_NAME"; then
    echo "🚨 ERROR: Container $CONTAINER_NAME is down. Attempting recovery..."
    
    # 2. Restart container
    docker start "$CONTAINER_NAME"
    
    # 3. Notify Admin via Telegram (if token exists)
    if [ ! -z "$TELEGRAM_BOT_TOKEN" ] && [ ! -z "$TELEGRAM_CHAT_ID" ]; then
        MESSAGE="🚨 <b>Nifty AI Alert:</b> Container was down and has been restarted on Mumbai VPS."
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
             -d "chat_id=$TELEGRAM_CHAT_ID" \
             -d "text=$MESSAGE" \
             -d "parse_mode=HTML"
    fi
else
    echo "✅ Container $CONTAINER_NAME is healthy."
fi
