#!/bin/bash
PROD_CONTAINER="open-trading-api-v2_trading-web_1"
STAGING_CONTAINER="open-trading-api-v2_trading-staging_1"
SOURCE_DB="data/prod/deep_dive.db"
DEST_DB="data/staging/deep_dive.db"

echo "$(date) - [AutoSync] Monitoring backfill process..." >> auto_sync.log

# Wait for backfill_data.py to stop running using podman top
while podman top $PROD_CONTAINER | grep "backfill_data.py" > /dev/null; do
    sleep 30
done

echo "$(date) - [AutoSync] Backfill finished." >> auto_sync.log

# 1. Restart Production to apply new Scheduler code (Midnight Job)
echo "$(date) - [AutoSync] Restarting Production container..." >> auto_sync.log
if podman restart $PROD_CONTAINER; then
    echo "$(date) - [AutoSync] Production container restarted." >> auto_sync.log
else
    echo "$(date) - [AutoSync] Failed to restart Production container." >> auto_sync.log
fi

# 2. Sync Database
echo "$(date) - [AutoSync] Syncing database to Staging..." >> auto_sync.log
mkdir -p $(dirname $DEST_DB)
if cp $SOURCE_DB $DEST_DB; then
    echo "$(date) - [AutoSync] Database copied successfully." >> auto_sync.log
else
    echo "$(date) - [AutoSync] Failed to copy database." >> auto_sync.log
fi

# 3. Rebuild and Restart Staging
# Staging image needs rebuild to include new python code (database.py, scheduler.py)
echo "$(date) - [AutoSync] Rebuilding and Restarting Staging..." >> auto_sync.log
# We can just restart if volumes are mounted, but Staging usually doesn't mount source.
# Let's check if we can trigger a rebuild via docker-compose or just restart.
# docker-compose up -d --build trading-staging would be best but might block.
# Let's try podman restart first, assuming user might have mounted volumes? 
# No, confirmed earlier Staging has NO source volumes. MUST REBUILD.

# Trigger rebuild in background or via docker-compose
/usr/local/bin/docker-compose -f docker-compose.yml up -d --build trading-staging >> auto_sync.log 2>&1

echo "$(date) - [AutoSync] Staging deployment triggered." >> auto_sync.log
