"""
Script to migrate TimeLogger v1 JSON data store to TimeLogger v2 SQLite database.

This script reads the JSON log file (timelog.log) from the WorkLogger directory,
parses each timecard entry, and inserts any missing records into the new SQLite
database using the existing storage API.
"""
import os
import json
import sys

from storage import init_db, log_timecard, fetch_timecards, TimeCard
from config import CONFIG_DIR


def migrate():
    """Perform migration of JSON timecards into SQLite database."""
    # Ensure database and table exist
    init_db()

    # Path to the old JSON log file
    log_file = os.path.join(CONFIG_DIR, "timelog.log")
    if not os.path.exists(log_file):
        print(f"Error: JSON log file not found at {log_file}")
        sys.exit(1)

    # Load JSON data
    try:
        with open(log_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file: {e}")
        sys.exit(1)

    # Fetch existing records to avoid duplicates
    existing = fetch_timecards()
    existing_keys = set((tc.start_time, tc.end_time) for tc in existing)

    migrated = 0
    for entry in data:
        start = entry.get("start_time")
        end = entry.get("end_time")
        valid = entry.get("valid", True)
        desc = entry.get("description", "")

        # Skip if already in database
        if (start, end) in existing_keys:
            continue

        # Create and insert new timecard
        tc = TimeCard(start, end, valid=valid, description=desc)
        log_timecard(tc)
        migrated += 1

    print(f"Migration complete: {migrated} timecards added.")


if __name__ == "__main__":
    migrate()
