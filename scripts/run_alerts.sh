#!/bin/bash
# Smart Money Flow - Telegram Alerts Runner
# Run this script to start automated alerts

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "🚀 Starting Smart Money Flow Alert Service..."
echo "   - Morning alert: 8:30 AM"
echo "   - Midday check: 12:00 PM"
echo "   - Evening summary: 5:30 PM"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python scripts/scheduler.py
