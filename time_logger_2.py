import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkcalendar import DateEntry
from datetime import datetime, timedelta

from storage import init_db, log_timecard, fetch_timecards, update_timecard, TimeCard
from config import RATE_PER_HOUR, NET_RATE, WINDOW_TITLE, THEME
from config import BG_COLOR, FG_COLOR, INVALID_COLOR, NO_DESC_COLOR, CAL_BG, CAL_FG, TREE_BG, BUTTON_COLOR
from reporting import export_to_csv, generate_pdf_report

# ensure DB is ready
init_db()


class WorkLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=BG_COLOR)

        # Hard‑code these to whatever fits your content:
        self.root.geometry("480x380")
        self.root.resizable(False, False)

        style = ttk.Style(root)
        # TreeView style
        style.configure("Custom.Treeview",
                        background=TREE_BG,
                        fieldbackground=TREE_BG,
                        foreground=FG_COLOR,
                        bordercolor=TREE_BG,  # same as bg
                        borderwidth=0)
        style.layout("Custom.Treeview", [
            ('Treeview.treearea', {'sticky': 'nswe'})  # drop all other elements
        ])
        style.configure("Custom.Treeview.Heading",
                        background=TREE_BG,
                        foreground=FG_COLOR,
                        borderwidth=0,
                        relief='flat')
        style.map("Custom.Treeview.Heading",
                  relief=[('active', 'flat'), ('!active', 'flat')])
        # Button style
        style.configure("Accent.TButton",
                        background=BUTTON_COLOR,
                        foreground=BG_COLOR,
                        borderwidth=0,  # no border
                        focusthickness=0,  # no focus ring
                        highlightthickness=0,  # no highlight
                        relief='flat')
        style.map("Accent.TButton",
                  relief=[('pressed', 'flat'), ('!pressed', 'flat')],
                  background=[('active', BUTTON_COLOR)])

        self.root.attributes("-topmost", True)
        self.rate_per_hour = RATE_PER_HOUR
        self.start_time = None

        self.build_header()
        self.build_filter_frame()
        self.build_tree()
        self.build_buttons()

        self.load_tree()
        self.update_clock()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_header(self):
        hdr = tk.Frame(self.root, bg=BG_COLOR)
        hdr.pack(fill='x', pady=5)
        self.time_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.time_lbl.pack(side='left', padx=10)
        self.elapsed_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.elapsed_lbl.pack(side='left', padx=10)
        self.gross_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.gross_lbl.pack(side='right', padx=10)
        self.net_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.net_lbl.pack(side='right', padx=10)

    def build_filter_frame(self):
        frm = tk.Frame(self.root, bg=BG_COLOR)
        frm.pack(fill='x', pady=5)
        tk.Label(frm, text="From:", bg=BG_COLOR, fg=FG_COLOR).pack(side='left', padx=5)
        self.from_date = DateEntry(frm, width=12, background=CAL_BG, foreground=CAL_FG)
        self.from_date.pack(side='left', padx=5)
        tk.Label(frm, text="To:", bg=BG_COLOR, fg=FG_COLOR).pack(side='left', padx=5)
        self.to_date = DateEntry(frm, width=12, background=CAL_BG, foreground=CAL_FG)
        self.to_date.pack(side='left', padx=5)
        ttk.Button(frm, text="Filter", command=self.apply_filter).pack(side='left', padx=10)
        ttk.Button(frm, text="Clear", command=self.clear_filter).pack(side='left')

    def build_tree(self):
        cols = ('date', 'start time', 'end time', 'hours earned')
        self.tree = ttk.Treeview(self.root,
                                 columns=cols,
                                 show='headings',
                                 style="Custom.Treeview")
        for c in cols:
            # make each column stretch to fill available space
            self.tree.heading(c, text=c.title(), command=lambda _c=c: self.sort_tree(_c, False))
            self.tree.column(c, anchor='center', stretch=True)

        self.tree.pack(fill='both', expand=True, pady=5)

        # bind mousewheel / touchpad scroll
        self.tree.bind("<MouseWheel>", self._on_mousewheel)  # Windows / macOS
        self.tree.bind("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self.tree.bind("<Button-5>", self._on_mousewheel)  # Linux scroll down

        # whenever the treeview is resized, redistribute column widths
        self.tree.bind('<Configure>', self._on_tree_resize)

        self.tree.bind('<Double-1>', self.edit_entry)
        self.tree.tag_configure('invalid', foreground=INVALID_COLOR)
        self.tree.tag_configure('no_desc', foreground=NO_DESC_COLOR)

    def _on_mousewheel(self, event):
        # Windows and macOS: event.delta is positive on scroll up, negative on scroll down
        if hasattr(event, 'delta') and event.delta:
            # delta is a multiple of 120 on Windows
            direction = -1 if event.delta > 0 else 1
        else:
            # Linux: Button-4 = up, Button-5 = down
            direction = -1 if event.num == 4 else 1

        self.tree.yview_scroll(direction, "units")

    def _on_tree_resize(self, event):
        # total width available for all columns
        total_width = event.width
        cols = self.tree["columns"]
        if not cols:
            return
        # divide equally
        width_per_col = total_width // len(cols)
        for c in cols:
            self.tree.column(c, width=width_per_col)

    def build_buttons(self):
        frm = tk.Frame(self.root, bg=BG_COLOR)
        frm.pack(fill='x', pady=5)

        # Toggle clock button (no focus ring)
        self.clock_btn = ttk.Button(
            frm,
            text="Clock In",
            command=self.toggle_logging,
            style="Accent.TButton",
            takefocus=False
        )
        self.clock_btn.pack(side='left', padx=10, pady=(0, 5))

        # Generate XLSX stub
        ttk.Button(
            frm,
            text="Generate XLSX",
            command=self.generate_xlsx,
            style="Accent.TButton",
            takefocus=False
        ).pack(side='left', padx=10, pady=(0, 5))

        # Add Entry
        ttk.Button(
            frm,
            text="Add Entry",
            command=self.add_entry,
            style="Accent.TButton",
            takefocus=False
        ).pack(side='left', padx=10, pady=(0, 5))

        # Export CSV
        ttk.Button(
            frm,
            text="Export CSV",
            command=self.export_csv,
            style="Accent.TButton",
            takefocus=False
        ).pack(side='left', padx=10, pady=(0, 5))

        # PDF Report
        ttk.Button(
            frm,
            text="PDF Report",
            command=self.export_pdf_report,
            style="Accent.TButton",
            takefocus=False
        ).pack(side='left', padx=10, pady=(0, 5))

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
        # remember current cards for export/report
        self.current_cards = cards or fetch_timecards()
        for i in self.tree.get_children():
            self.tree.delete(i)
        for tc in self.current_cards:
            dt = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S')
            dur, hrs = tc.duration_hours()
            tag = 'invalid' if not tc.valid else ('no_desc' if not tc.description else '')
            self.tree.insert('', 'end', iid=str(tc.id),
                             values=(dt.date(),
                                     dt.time(),
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
        for idx, (_, k) in enumerate(data):
            self.tree.move(k, '', idx)
        self.tree.heading(col, command=lambda: self.sort_tree(col, not reverse))

    def edit_entry(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        tc_id = int(sel[0])
        tc = next((t for t in fetch_timecards() if t.id == tc_id), None)
        if not tc:
            return

        win = tk.Toplevel(self.root)
        win.title("Edit Entry")
        win.configure(bg=BG_COLOR)

        win.attributes("-topmost", True)  # keep this window on top
        win.resizable(True, True)

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="Start Time:").grid(row=0, column=0, sticky='e', pady=2)
        start_var = tk.StringVar(value=tc.start_time)
        ttk.Entry(frm, textvariable=start_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(frm, text="End Time:").grid(row=1, column=0, sticky='e', pady=2)
        end_var = tk.StringVar(value=tc.end_time)
        ttk.Entry(frm, textvariable=end_var, width=25).grid(row=1, column=1, pady=2)

        valid_var = tk.BooleanVar(value=tc.valid)
        ttk.Checkbutton(frm, text="Valid", variable=valid_var).grid(row=2, column=1, sticky='w', pady=2)

        ttk.Label(frm, text="Description:").grid(row=3, column=0, sticky='ne', pady=2)
        desc_text = tk.Text(frm, width=40, height=5)
        desc_text.insert('1.0', tc.description)
        desc_text.grid(row=3, column=1, pady=2)

        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.pack()

        def save():
            new_s = start_var.get()
            new_e = end_var.get()
            try:
                datetime.strptime(new_s, '%Y-%m-%d %H:%M:%S')
                datetime.strptime(new_e, '%Y-%m-%d %H:%M:%S')
            except ValueError as ex:
                messagebox.showerror("Error", f"Invalid date/time: {ex}")
                return
            update_timecard(tc_id, new_s, new_e, valid_var.get(), desc_text.get('1.0', 'end-1c'))
            self.load_tree()
            messagebox.showinfo("Saved", "Entry updated")
            win.destroy()

        ttk.Button(btn_frame, text="Save", command=save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side='left', padx=5)

    def start_logging(self):
        self.start_time = datetime.now()

    def stop_logging(self):
        if not self.start_time:
            return
        end = datetime.now()
        tc = TimeCard(self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                      end.strftime('%Y-%m-%d %H:%M:%S'))
        log_timecard(tc)
        self.load_tree()
        self.start_time = None

    def toggle_logging(self):
        if not self.start_time:
            self.start_logging()
            self.clock_btn.config(text="Clock Out")
        else:
            self.stop_logging()
            self.clock_btn.config(text="Clock In")

    def generate_xlsx(self):
        # TODO: implement XLSX export
        messagebox.showinfo("Generate XLSX", "This feature isn’t implemented yet.")

    def add_entry(self):
        AddEntryWindow(self)

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV Files', '*.csv')],
            title='Save CSV Export'
        )
        if not path:
            return
        export_to_csv(path)
        messagebox.showinfo("Export Complete", f"CSV exported to:\n{path}")

    def export_pdf_report(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.pdf',
            filetypes=[('PDF Files', '*.pdf')],
            title='Save PDF Report'
        )
        if not path:
            return
        generate_pdf_report(path, self.current_cards)
        messagebox.showinfo("Report Complete", f"PDF report saved to:\n{path}")

    def update_earned(self):
        total = sum(tc.duration_hours()[1] for tc in fetch_timecards() if tc.valid)
        gross = total * self.rate_per_hour
        net = gross * NET_RATE
        self.gross_lbl.config(text=f"Gross: ${gross:.2f}")
        self.net_lbl.config(text=f"Net: ${net:.2f}")

    def on_closing(self):
        if self.start_time:
            messagebox.showwarning("Warning", "Stop logging first.")
            return
        self.root.destroy()


class AddEntryWindow:
    def __init__(self, app: WorkLoggerApp):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Add Entry")
        self.win.configure(bg=BG_COLOR)
        frm = ttk.Frame(self.win, padding=10)
        frm.pack(fill='both', expand=True)

        # Start time
        ttk.Label(frm, text="Start Time:").grid(row=0, column=0, sticky='e', pady=2)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.start_var = tk.StringVar(value=now_str)
        ttk.Entry(frm, textvariable=self.start_var, width=25).grid(row=0, column=1, pady=2)

        # End time
        ttk.Label(frm, text="End Time:").grid(row=1, column=0, sticky='e', pady=2)
        self.end_var = tk.StringVar(value=now_str)
        ttk.Entry(frm, textvariable=self.end_var, width=25).grid(row=1, column=1, pady=2)

        # Valid checkbox
        self.valid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Valid", variable=self.valid_var).grid(row=2, column=1, sticky='w', pady=2)

        # Description
        ttk.Label(frm, text="Description:").grid(row=3, column=0, sticky='ne', pady=2)
        self.desc_text = tk.Text(frm, width=40, height=5)
        self.desc_text.grid(row=3, column=1, pady=2)

        # Buttons
        btn_frame = ttk.Frame(self.win, padding=10)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.win.destroy).pack(side='left', padx=5)

    def save(self):
        s = self.start_var.get().strip()
        e = self.end_var.get().strip()
        try:
            datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
            datetime.strptime(e, '%Y-%m-%d %H:%M:%S')
        except ValueError as ex:
            messagebox.showerror("Error", f"Invalid date/time: {ex}")
            return

        tc = TimeCard(s, e,
                      valid=self.valid_var.get(),
                      description=self.desc_text.get('1.0', 'end-1c'))
        log_timecard(tc)
        self.app.load_tree()
        messagebox.showinfo("Added", "New entry saved")
        self.win.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use(THEME)
    app = WorkLoggerApp(root)
    root.mainloop()
