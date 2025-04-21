import os
import sqlite3
from datetime import datetime
from config import DB_PATH


# --- MODEL ---
class TimeCard:
    def __init__(self, start_time, end_time, valid=True, description=""):
        self.start_time = start_time
        self.end_time = end_time
        self.valid = valid
        self.description = description
        self.id = None

    def duration_hours(self):
        start = datetime.strptime(self.start_time, '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(self.end_time, '%Y-%m-%d %H:%M:%S')
        delta = end - start
        return delta, delta.total_seconds() / 3600


# --- STORAGE SETUP ---
TMP_DIR = os.path.join(os.path.expanduser("~"), "WorkLogger")
if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR)


def init_db():
    """Ensure the timecards table exists."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS timecards (
            id INTEGER PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            valid INTEGER NOT NULL,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_timecard(tc: TimeCard):
    """Insert a new TimeCard into the DB."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO timecards(start_time,end_time,valid,description) VALUES(?,?,?,?)",
        (tc.start_time, tc.end_time, int(tc.valid), tc.description)
    )
    conn.commit()
    conn.close()


def fetch_timecards():
    """Return all TimeCards, oldest first."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, start_time, end_time, valid, description FROM timecards ORDER BY start_time")
    rows = c.fetchall()
    conn.close()

    cards = []
    for rid, s, e, v, d in rows:
        tc = TimeCard(s, e, bool(v), d)
        tc.id = rid
        cards.append(tc)
    return cards


def update_timecard(tc_id, start_time, end_time, valid, description):
    """Update an existing TimeCard by ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE timecards SET start_time=?, end_time=?, valid=?, description=? WHERE id=?",
        (start_time, end_time, int(valid), description, tc_id)
    )
    conn.commit()
    conn.close()


# Initialize on import
init_db()
