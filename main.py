import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import ttk
from tkcalendar import Calendar, DateEntry
import os
import sqlite3
from datetime import datetime, timedelta

# Directory for storage
tmp_dir = os.path.join(os.path.expanduser("~"), "WorkLogger")
if not os.path.exists(tmp_dir):
    os.makedirs(tmp_dir)

# SQLite database file path
db_path = os.path.join(tmp_dir, "timelog.db")

# Initialize SQLite database and table
def init_db():
    conn = sqlite3.connect(db_path)
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

init_db()

class TimeCard:
    def __init__(self, start_time, end_time, valid=True, description=""):
        self.start_time = start_time
        self.end_time = end_time
        self.valid = valid
        self.description = description

    def duration_hours(self):
        start = datetime.strptime(self.start_time, '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(self.end_time, '%Y-%m-%d %H:%M:%S')
        delta = end - start
        return delta, delta.total_seconds() / 3600

# Storage functions
def log_timecard(tc):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO timecards(start_time,end_time,valid,description) VALUES(?,?,?,?)",
        (tc.start_time, tc.end_time, int(tc.valid), tc.description)
    )
    conn.commit(); conn.close()


def fetch_timecards():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id,start_time,end_time,valid,description FROM timecards ORDER BY start_time")
    rows = c.fetchall(); conn.close()
    cards = []
    for rid, s, e, v, d in rows:
        tc = TimeCard(s, e, bool(v), d)
        tc.id = rid
        cards.append(tc)
    return cards

class WorkLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WorkLogger 2.0")
        self.root.configure(bg='#121212')
        self.root.attributes("-topmost", True)
        self.rate_per_hour = 20.0
        self.start_time = None

        self.build_header()
        self.build_filter_frame()
        self.build_tree()
        self.build_buttons()

        self.load_tree()
        self.update_clock()

    def build_header(self):
        hdr = tk.Frame(self.root, bg='#121212')
        hdr.pack(fill='x', pady=5)
        self.time_lbl = tk.Label(hdr, bg='#121212', fg='#f2e7fe')
        self.time_lbl.pack(side='left', padx=10)
        self.earned_lbl = tk.Label(hdr, bg='#121212', fg='#f2e7fe')
        self.earned_lbl.pack(side='right', padx=10)

    def build_filter_frame(self):
        frm = tk.Frame(self.root, bg='#121212')
        frm.pack(fill='x', pady=5)
        tk.Label(frm, text="From:", bg='#121212', fg='#f2e7fe').pack(side='left', padx=5)
        self.from_date = DateEntry(frm, width=12, background='#1d1d1d', foreground='#f2e7fe')
        self.from_date.pack(side='left', padx=5)
        tk.Label(frm, text="To:", bg='#121212', fg='#f2e7fe').pack(side='left', padx=5)
        self.to_date = DateEntry(frm, width=12, background='#1d1d1d', foreground='#f2e7fe')
        self.to_date.pack(side='left', padx=5)
        ttk.Button(frm, text="Filter", command=self.apply_filter).pack(side='left', padx=10)
        ttk.Button(frm, text="Clear", command=self.clear_filter).pack(side='left')

    def build_tree(self):
        cols = ('date','start','end','hours','desc')
        self.tree = ttk.Treeview(self.root, columns=cols, show='headings', height=10)
        for c in cols:
            self.tree.heading(c, text=c.title(), command=lambda _c=c: self.sort_tree(_c, False))
            self.tree.column(c, anchor='center')
        vsb = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True, padx=10)
        self.tree.bind('<Double-1>', self.edit_entry)
        # Tag styles
        self.tree.tag_configure('invalid', foreground='gray')
        self.tree.tag_configure('no_desc', background='#2b1b1b')

    def build_buttons(self):
        frm = tk.Frame(self.root, bg='#121212')
        frm.pack(fill='x', pady=5)
        actions = [
            ("Clock In", self.start_logging),
            ("Clock Out", self.stop_logging),
            ("Add Entry", self.add_entry),
        ]
        for txt, cmd in actions:
            b = ttk.Button(frm, text=txt, command=cmd)
            b.pack(side='left', padx=10)

    def update_clock(self):
        now = datetime.now()
        self.time_lbl.config(text=now.strftime('%H:%M:%S %b %d, %Y'))
        self.update_earned()
        self.root.after(1000, self.update_clock)

    def load_tree(self, cards=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        for tc in (cards or fetch_timecards()):
            dt = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S')
            dur, hrs = tc.duration_hours()
            tag = 'invalid' if not tc.valid else ('no_desc' if not tc.description else '')
            self.tree.insert('', 'end', iid=tc.id,
                values=(dt.date(), dt.time(), datetime.strptime(tc.end_time,'%Y-%m-%d %H:%M:%S').time(), f"{hrs:.2f}", tc.description),
                tags=(tag,))

    def apply_filter(self):
        frm = self.from_date.get_date()
        to = self.to_date.get_date()
        filtered = [tc for tc in fetch_timecards()
                    if frm <= datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S').date() <= to]
        self.load_tree(filtered)

    def clear_filter(self):
        self.from_date.set_date(datetime.now())
        self.to_date.set_date(datetime.now())
        self.load_tree()

    def sort_tree(self, col, reverse):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            self.tree.move(k, '', idx)
        self.tree.heading(col, command=lambda: self.sort_tree(col, not reverse))

    def edit_entry(self, event):
        # pop-up editor…
        pass

    def start_logging(self):
        self.start_time = datetime.now()

    def stop_logging(self):
        if not self.start_time: return
        end = datetime.now()
        tc = TimeCard(self.start_time.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))
        log_timecard(tc)
        self.load_tree()
        self.start_time = None

    def add_entry(self):
        s = simpledialog.askstring("Start", "YYYY-MM-DD HH:MM:SS")
        e = simpledialog.askstring("End",   "YYYY-MM-DD HH:MM:SS")
        if not s or not e: return
        try:
            datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
            datetime.strptime(e, '%Y-%m-%d %H:%M:%S')
            log_timecard(TimeCard(s, e))
            self.load_tree()
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    def update_earned(self):
        total = sum(tc.duration_hours()[1] for tc in fetch_timecards())
        self.earned_lbl.config(text=f"Earned: ${total*self.rate_per_hour:.2f}")

    def on_closing(self):
        if self.start_time:
            messagebox.showwarning("Warning","Stop logging first.")
            return
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use('clam')
    app = WorkLoggerApp(root)
    root.mainloop()
