import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext
from tkcalendar import Calendar
import os
import sqlite3
from datetime import datetime, timedelta

# Directory for storage
log_dir = os.path.join(os.path.expanduser("~"), "WorkLogger")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# SQLite database file path
db_path = os.path.join(log_dir, "timelog.db")

# Initialize SQLite database and table
def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS timecards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            valid INTEGER NOT NULL,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

class TimeCard:
    def __init__(self, start_time, end_time, valid=True, description=""):
        self.start_time = start_time
        self.end_time = end_time
        self.valid = valid
        self.description = description

    def get_duration(self):
        start = datetime.strptime(self.start_time, '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(self.end_time, '%Y-%m-%d %H:%M:%S')
        duration = end - start
        return duration, duration.total_seconds() / 3600

# Logging and retrieval now use SQLite
def log_timecard(timecard):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO timecards (start_time, end_time, valid, description) VALUES (?, ?, ?, ?)",
        (timecard.start_time, timecard.end_time, int(timecard.valid), timecard.description)
    )
    conn.commit()
    conn.close()


def get_timecards():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT start_time, end_time, valid, description FROM timecards ORDER BY start_time")
    rows = c.fetchall()
    conn.close()
    return [TimeCard(start_time=r[0], end_time=r[1], valid=bool(r[2]), description=r[3] or "") for r in rows]

class WorkLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Langley Data and Cyber Defense Time Accounting")
        self.root.configure(bg='#121212')
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.start_time = None
        self.rate_per_hour = 20.0

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Header labels
        self.current_time_label = tk.Label(
            root,
            text=f"Current Time: {datetime.now().strftime('%H:%M:%S %B %d, %Y')}",
            bg='#121212', fg='#f2e7fe'
        )
        self.current_time_label.pack()

        self.earned_today_label = tk.Label(root, text="Earned Today: $00.00", bg='#121212', fg='#f2e7fe')
        self.earned_today_label.pack()

        # Log display
        self.log_frame = tk.Frame(root, bg='#121212')
        self.log_frame.pack(pady=10)
        self.log_listbox = tk.Listbox(
            self.log_frame, width=80, height=10, bg='#1d1d1d', fg='#f2e7fe', bd=0, highlightthickness=0
        )
        self.log_listbox.pack(side=tk.LEFT)
        self.log_listbox.bind('<Double-1>', self.open_edit_window)

        self.elapsed_time_label = tk.Label(
            root, text="Elapsed Time: 00:00:00 (Not Logging)", bg='#121212', fg='#f2e7fe'
        )
        self.elapsed_time_label.pack()

        # Buttons
        buttons = [
            ("Clock In", self.start_logging),
            ("Clock Out", self.stop_logging),
            ("Manually Add Entry", self.add_entry),
            ("View Date", self.view_date),
        ]
        for text, cmd in buttons:
            widget_opts = {'bg': '#03dac5', 'fg': '#121212', 'text': text, 'command': cmd}
            pack_opts = {'side': 'left', 'padx': 10, 'pady': 10, 'expand': True, 'fill': 'x'}
            btn = tk.Button(root, **widget_opts)
            btn.pack(**pack_opts)

        self.update_time()
        self.load_logs()
        self.update_earned_today()

    def update_time(self):
        self.current_time_label.config(
            text=f"Current Time: {datetime.now().strftime('%H:%M:%S %B %d, %Y')}"
        )
        self.update_earned_today()
        self.root.after(1000, self.update_time)

    def start_logging(self):
        self.start_time = datetime.now()
        self.elapsed_time_label.config(text="Elapsed Time: 00:00:00 (Logging)")
        self.update_elapsed_time()

    def update_elapsed_time(self):
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            self.elapsed_time_label.config(text=f"Elapsed Time: {str(elapsed).split('.')[0]} (Logging)")
            self.root.after(1000, self.update_elapsed_time)

    def stop_logging(self):
        if self.start_time:
            end_time = datetime.now()
            tc = TimeCard(
                start_time=self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S')
            )
            self.add_timecard_to_listbox(tc)
            log_timecard(tc)
            self.start_time = None
            self.elapsed_time_label.config(text="Elapsed Time: 00:00:00 (Not Logging)")

    def add_entry(self):
        s = simpledialog.askstring("Input", "Enter start time (YYYY-MM-DD HH:MM:SS)")
        e = simpledialog.askstring("Input", "Enter end time (YYYY-MM-DD HH:MM:SS)")
        try:
            datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
            datetime.strptime(e, '%Y-%m-%d %H:%M:%S')
            tc = TimeCard(start_time=s, end_time=e)
            self.add_timecard_to_listbox(tc)
            log_timecard(tc)
        except Exception as ex:
            messagebox.showerror("Error", f"Invalid input: {ex}")

    def load_logs(self):
        self.log_listbox.delete(0, 'end')
        for tc in get_timecards():
            self.add_timecard_to_listbox(tc)

    def add_timecard_to_listbox(self, tc):
        dur, hrs = tc.get_duration()
        fmt_date = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
        text = f"[{fmt_date}] {hrs:.2f} hours ({dur})"
        self.log_listbox.insert('end', text)
        color = '#f2e7fe' if tc.valid else 'gray'
        if tc.description == "": color = '#cf6679'
        self.log_listbox.itemconfig('end', {'fg': color})

    def open_edit_window(self, event):
        sel = self.log_listbox.curselection()
        if not sel: return
        idx = sel[0]
        entries = get_timecards()
        EditLogWindow(tk.Toplevel(self.root), entries[idx], self.reload_and_refresh)

    def reload_and_refresh(self, _):
        self.load_logs()
        self.update_earned_today()

    def view_date(self):
        # ... (same as before, using get_timecards)
        pass

    def update_earned_today(self):
        total = 0
        today = datetime.now().date()
        for tc in get_timecards():
            if tc.valid and datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S').date() == today:
                total += tc.get_duration()[1]
        self.earned_today_label.config(text=f"Earned Today: ${total * self.rate_per_hour:.2f}")

    def on_closing(self):
        if self.start_time:
            messagebox.showwarning("Warning", "Stop logging before closing the application.")
        else:
            self.root.destroy()

class EditLogWindow:
    # ... (reuse code, ensure updates write back to SQLite)
    pass

if __name__ == "__main__":
    root = tk.Tk()
    app = WorkLoggerApp(root)
    root.mainloop()
