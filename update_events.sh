#!/bin/bash
# Daily event update script
# Run this with cron: crontab -e
# Add: 0 8 * * * /Users/harnoorkaur/boston-community-events/update_events.sh

cd /Users/harnoorkaur/boston-community-events

# Load environment variables
source .env 2>/dev/null

# Run scraper
python3 main.py

# Export to JSON for dashboard
python3 export_events.py

echo "Events updated at $(date)"
