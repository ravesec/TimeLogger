import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkcalendar import DateEntry
from datetime import datetime, timedelta

from storage import init_db, log_timecard, fetch_timecards, update_timecard, TimeCard

# ensure DB ready
init_db()

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
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_header(self):
        hdr = tk.Frame(self.root, bg='#121212')
        hdr.pack(fill='x', pady=5)
        self.time_lbl = tk.Label(hdr, bg='#121212', fg='#f2e7fe')
        self.time_lbl.pack(side='left', padx=10)
        self.elapsed_lbl = tk.Label(hdr, bg='#121212', fg='#f2e7fe')
        self.elapsed_lbl.pack(side='left', padx=10)
        self.gross_lbl = tk.Label(hdr, bg='#121212', fg='#f2e7fe')
        self.gross_lbl.pack(side='right', padx=10)
        self.net_lbl = tk.Label(hdr, bg='#121212', fg='#f2e7fe')
        self.net_lbl.pack(side='right', padx=10)

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
        cols = ('date','start','end','hours')
        self.tree = ttk.Treeview(self.root, columns=cols, show='headings', height=10)
        for c in cols:
            self.tree.heading(c, text=c.title(), command=lambda _c=c: self.sort_tree(_c, False))
            self.tree.column(c, anchor='center')
        vsb = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True, padx=10)
        self.tree.bind('<Double-1>', self.edit_entry)
        self.tree.tag_configure('invalid', foreground='gray')
        self.tree.tag_configure('no_desc', foreground='#ff0000')

    def build_buttons(self):
        frm = tk.Frame(self.root, bg='#121212')
        frm.pack(fill='x', pady=5)
        for txt, cmd in [("Clock In", self.start_logging),
                         ("Clock Out", self.stop_logging),
                         ("Add Entry", self.add_entry)]:
            ttk.Button(frm, text=txt, command=cmd).pack(side='left', padx=10)

    def update_clock(self):
        now = datetime.now()
        self.time_lbl.config(text=now.strftime('%H:%M:%S %b %d, %Y'))
        if self.start_time:
            elapsed = now - self.start_time
            self.elapsed_lbl.config(text=f"Elapsed: {str(elapsed).split('.')[0]}")
        else:
            self.elapsed_lbl.config(text="Elapsed: 00:00:00")
        self.update_earned()
        self.root.after(1000, self.update_clock)

    def load_tree(self, cards=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        for tc in (cards or fetch_timecards()):
            dt = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S')
            dur, hrs = tc.duration_hours()
            tag = 'invalid' if not tc.valid else ('no_desc' if not tc.description else '')
            self.tree.insert('', 'end', iid=str(tc.id),
                             values=(dt.date(), dt.time(),
                                     datetime.strptime(tc.end_time, '%Y-%m-%d %H:%M:%S').time(),
                                     f"{hrs:.2f}",),
                             tags=(tag,))

    def apply_filter(self):
        frm, to = self.from_date.get_date(), self.to_date.get_date()
        filtered = [tc for tc in fetch_timecards()
                    if frm <= datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S').date() <= to]
        self.load_tree(filtered)

    def clear_filter(self):
        today = datetime.now()
        self.from_date.set_date(today)
        self.to_date.set_date(today)
        self.load_tree()

    def sort_tree(self, col, reverse):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data): self.tree.move(k, '', idx)
        self.tree.heading(col, command=lambda: self.sort_tree(col, not reverse))

    def edit_entry(self, event):
        sel = self.tree.selection()
        if not sel: return
        tc_id = int(sel[0])
        tc = next((t for t in fetch_timecards() if t.id == tc_id), None)
        if not tc: return

        win = tk.Toplevel(self.root)
        win.title("Edit Entry")
        win.configure(bg='#121212')
        frm = ttk.Frame(win, padding=10); frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="Start Time:").grid(row=0, column=0, sticky='e')
        start_var = tk.StringVar(value=tc.start_time)
        ttk.Entry(frm, textvariable=start_var, width=25).grid(row=0, column=1)

        ttk.Label(frm, text="End Time:").grid(row=1, column=0, sticky='e')
        end_var = tk.StringVar(value=tc.end_time)
        ttk.Entry(frm, textvariable=end_var, width=25).grid(row=1, column=1)

        valid_var = tk.BooleanVar(value=tc.valid)
        ttk.Checkbutton(frm, text="Valid", variable=valid_var).grid(row=2, column=1, sticky='w')

        ttk.Label(frm, text="Description:").grid(row=3, column=0, sticky='ne')
        desc_text = tk.Text(frm, width=40, height=5)
        desc_text.insert('1.0', tc.description)
        desc_text.grid(row=3, column=1)

        btn_frame = ttk.Frame(win, padding=10); btn_frame.pack()
        def save():
            new_s, new_e = start_var.get(), end_var.get()
            try:
                datetime.strptime(new_s, '%Y-%m-%d %H:%M:%S')
                datetime.strptime(new_e, '%Y-%m-%d %H:%M:%S')
            except ValueError as ex:
                messagebox.showerror("Error", f"Invalid date/time: {ex}")
                return
            update_timecard(tc_id, new_s, new_e, valid_var.get(), desc_text.get('1.0','end-1c'))
            self.load_tree()
            messagebox.showinfo("Saved", "Entry updated")
            win.destroy()

        ttk.Button(btn_frame, text="Save",   command=save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side='left', padx=5)

    def start_logging(self):
        self.start_time = datetime.now()

    def stop_logging(self):
        if not self.start_time: return
        end = datetime.now()
        tc = TimeCard(self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                      end.strftime('%Y-%m-%d %H:%M:%S'))
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
        except ValueError as ex:
            messagebox.showerror("Error", str(ex))
            return
        log_timecard(TimeCard(s, e))
        self.load_tree()

    def update_earned(self):
        total = sum(tc.duration_hours()[1] for tc in fetch_timecards() if tc.valid)
        gross = total * self.rate_per_hour
        net = gross * 0.80
        self.gross_lbl.config(text=f"Gross: ${gross:.2f}")
        self.net_lbl.config(text=f"Net (–20%): ${net:.2f}")

    def on_closing(self):
        if self.start_time:
            messagebox.showwarning("Warning", "Stop logging first.")
            return
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use('clam')
    app = WorkLoggerApp(root)
    root.mainloop()
