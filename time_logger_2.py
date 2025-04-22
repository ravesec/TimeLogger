import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from datetime import datetime
import pandas as pd
from openpyxl.styles import Font
import calendar

from storage import init_db, log_timecard, fetch_timecards, update_timecard, TimeCard
from config import RATE_PER_HOUR, NET_RATE, WINDOW_TITLE, THEME
from config import BG_COLOR, FG_COLOR, INVALID_COLOR, NO_DESC_COLOR, TREE_BG, BUTTON_COLOR, CONFIG_DIR, PAYMENT_METHOD_EMAIL
from reporting import export_to_csv, generate_pdf_report

# ensure DB is ready
init_db()


class WorkLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=BG_COLOR)

        # Hard‑code these to whatever fits your content:
        self.root.geometry("600x380")
        self.root.resizable(False, False)

        style = ttk.Style(root)
        # TreeView style
        # TreeView style
        style.configure("Custom.Treeview",
                        background=TREE_BG,
                        fieldbackground=TREE_BG,
                        foreground=FG_COLOR,
                        bordercolor=TREE_BG,
                        borderwidth=0)
        style.layout("Custom.Treeview", [
            ('Treeview.treearea', {'sticky': 'nswe'})
        ])

        # Heading style: flat, no border, fixed background even on hover
        style.configure("Custom.Treeview.Heading",
                        background=TREE_BG,
                        foreground=FG_COLOR,
                        borderwidth=0,
                        relief='flat')
        style.map("Custom.Treeview.Heading",
                  background=[('active', TREE_BG), ('!active', TREE_BG)],
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

        # Flat style: no border, no focus ring, flat relief
        style.configure("Flat.TButton",
                        borderwidth=0,
                        focusthickness=0,
                        highlightthickness=0,
                        relief='flat')
        style.map("Flat.TButton",
                  relief=[('pressed', 'flat'), ('!pressed', 'flat')])

        self.root.attributes("-topmost", True)
        self.rate_per_hour = RATE_PER_HOUR
        self.start_time = None

        self.build_header()
        self.build_filter_frame()
        self.build_tree()
        self.build_buttons()

        # 1) set selections to current month/year
        self.clear_filter()
        # 2) then load that view
        self.apply_filter()

        self.update_clock()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_header(self):
        hdr = tk.Frame(self.root, bg=BG_COLOR)
        hdr.pack(fill='x', pady=5)

        # left‑side: clock and elapsed
        self.time_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.time_lbl.pack(side='left', padx=10)
        self.elapsed_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.elapsed_lbl.pack(side='left', padx=10)

        # 2. Info button
        self.info_btn = tk.Button(
            hdr,
            text='Info ℹ',
            bg=TREE_BG,
            fg=BUTTON_COLOR,
            bd=0,
            highlightthickness=0,
            activebackground=BG_COLOR,
            activeforeground=FG_COLOR,
            command=self.show_rates
        )

        self.info_btn.pack(side='right', padx=5)

        # right‑side: pack in this order to get [Gross] [Info] [Net]
        # 1. Net (so it ends up at the far right)
        self.net_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.net_lbl.pack(side='right', padx=10)

        # 3. Gross
        self.gross_lbl = tk.Label(hdr, bg=BG_COLOR, fg=FG_COLOR)
        self.gross_lbl.pack(side='right', padx=10)

    def build_filter_frame(self):
        frm = tk.Frame(self.root, bg=BG_COLOR)
        frm.pack(fill='x', pady=5)

        # Month selector
        tk.Label(frm, text="Month:", bg=BG_COLOR, fg=FG_COLOR).pack(side='left', padx=5)
        months = [calendar.month_name[i] for i in range(1, 13)]
        self.month_cb = ttk.Combobox(frm, values=months, state='readonly', width=10)
        self.month_cb.pack(side='left', padx=5)

        # Year selector
        tk.Label(frm, text="Year:", bg=BG_COLOR, fg=FG_COLOR).pack(side='left', padx=5)
        years = list(range(datetime.now().year - 5, datetime.now().year + 1))
        self.year_cb = ttk.Combobox(frm, values=years, state='readonly', width=5)
        self.year_cb.pack(side='left', padx=5)

        # Filter / Clear (flat, default color)
        self.filter_btn = ttk.Button(
            frm, text="Filter", command=self.apply_filter,
            style="Flat.TButton", takefocus=False
        )
        self.filter_btn.pack(side='left', expand=True, fill='x', padx=5)

        self.clear_btn = ttk.Button(
            frm, text="Reset Filter", command=self.clear_filter,
            style="Flat.TButton", takefocus=False
        )
        self.clear_btn.pack(side='left', expand=True, fill='x', padx=5)

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

        # Each of these now expands equally and fills horizontally
        self.clock_btn = ttk.Button(frm, text="Clock In", command=self.toggle_logging,
                                    style="Accent.TButton", takefocus=False)
        self.clock_btn.pack(side='left', expand=True, fill='x', padx=5, pady=(0, 5))

        self.xlsx_btn = ttk.Button(frm, text="Generate XLSX", command=self.generate_xlsx,
                                   style="Accent.TButton", takefocus=False)
        self.xlsx_btn.pack(side='left', expand=True, fill='x', padx=5, pady=(0, 5))

        ttk.Button(frm, text="Add Entry", command=self.add_entry,
                   style="Accent.TButton", takefocus=False) \
            .pack(side='left', expand=True, fill='x', padx=5, pady=(0, 5))

        self.csv_btn = ttk.Button(frm, text="Export DB as CSV", command=self.export_csv,
                                  style="Accent.TButton", takefocus=False)
        self.csv_btn.pack(side='left', expand=True, fill='x', padx=5, pady=(0, 5))

        self.pdf_btn = ttk.Button(frm, text="PDF Report", command=self.export_pdf_report,
                                  style="Accent.TButton", takefocus=False)
        self.pdf_btn.pack(side='left', expand=True, fill='x', padx=5, pady=(0, 5))

    def update_clock(self):
        now = datetime.now()
        self.time_lbl.config(text=now.strftime('%b %d, %Y, %H:%M:%S'))
        if self.start_time:
            # compute elapsed hours, minutes, seconds
            elapsed = now - self.start_time
            total_seconds = int(elapsed.total_seconds())
            hrs, rem = divmod(total_seconds, 3600)
            mins, secs = divmod(rem, 60)
            elapsed_str = f"{hrs:02}:{mins:02}:{secs:02}"
            self.elapsed_lbl.config(text=f"Elapsed Time: {elapsed_str} (Logging)")
        else:
            self.elapsed_lbl.config(text="Elapsed Time: 00:00:00 (Not Logging)")
        self.update_earned()
        self.root.after(1000, self.update_clock)

    def load_tree(self, cards=None):
        # remember current cards for export/report
        # if cards is None => load everything, otherwise use exactly what was passed
        self.current_cards = fetch_timecards() if cards is None else cards

        for i in self.tree.get_children():
            self.tree.delete(i)
        for tc in self.current_cards:
            dt = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S')
            dur, hrs = tc.duration_hours()
            tag = 'invalid' if not tc.valid else ('no_desc' if not tc.description else '')
            self.tree.insert(
                '', 'end', iid=str(tc.id),
                values=(
                    dt.date(),
                    dt.time(),
                    datetime.strptime(tc.end_time, '%Y-%m-%d %H:%M:%S').time(),
                    f"{hrs:.2f}"
                ),
                tags=(tag,)
            )

    def apply_filter(self):
        # figure out selected month & year
        try:
            m = list(calendar.month_name).index(self.month_cb.get())
            y = int(self.year_cb.get())
        except ValueError:
            return

        # include cards whose start OR end is in that month/year
        filtered = []
        for tc in fetch_timecards():
            dt_start = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S')
            dt_end = datetime.strptime(tc.end_time, '%Y-%m-%d %H:%M:%S')
            if (dt_start.year == y and dt_start.month == m) or \
                    (dt_end.year == y and dt_end.month == m):
                filtered.append(tc)

        self.load_tree(filtered)

    def clear_filter(self):
        now = datetime.now()
        # reset comboboxes to this month/year, but do NOT reload yet
        self.month_cb.set(calendar.month_name[now.month])
        self.year_cb.set(str(now.year))
        self.apply_filter()

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
        win.attributes("-topmost", True)
        win.resizable(True, True)

        # use a tk.Frame so we can set bg/fg
        frm = tk.Frame(win, bg=BG_COLOR, padx=10, pady=10)
        frm.pack(fill='both', expand=True)

        # Start Time
        tk.Label(frm, text="Start Time:", bg=BG_COLOR, fg=FG_COLOR) \
            .grid(row=0, column=0, sticky='e', pady=2)
        start_var = tk.StringVar(value=tc.start_time)
        tk.Entry(frm, textvariable=start_var, width=25,
                 bg=TREE_BG, fg=FG_COLOR, insertbackground=FG_COLOR,
                 relief='flat') \
            .grid(row=0, column=1, pady=2)

        # End Time
        tk.Label(frm, text="End Time:", bg=BG_COLOR, fg=FG_COLOR) \
            .grid(row=1, column=0, sticky='e', pady=2)
        end_var = tk.StringVar(value=tc.end_time)
        tk.Entry(frm, textvariable=end_var, width=25,
                 bg=TREE_BG, fg=FG_COLOR, insertbackground=FG_COLOR,
                 relief='flat') \
            .grid(row=1, column=1, pady=2)

        # Valid checkbox
        valid_var = tk.BooleanVar(value=tc.valid)
        tk.Checkbutton(frm, text="Valid", variable=valid_var,
                       bg=BG_COLOR, fg=FG_COLOR,
                       activebackground=BG_COLOR,
                       selectcolor=TREE_BG) \
            .grid(row=2, column=1, sticky='w', pady=2)

        # Description
        tk.Label(frm, text="Description:", bg=BG_COLOR, fg=FG_COLOR) \
            .grid(row=3, column=0, sticky='ne', pady=2)
        desc_text = tk.Text(frm, width=40, height=5,
                            bg=TREE_BG, fg=FG_COLOR,
                            insertbackground=FG_COLOR,
                            relief='flat')
        desc_text.insert('1.0', tc.description)
        desc_text.grid(row=3, column=1, pady=2)

        # Buttons
        btn_frame = tk.Frame(win, bg=BG_COLOR, pady=10)
        btn_frame.pack(fill='x', padx=10)

        def save():
            new_s = start_var.get().strip()
            new_e = end_var.get().strip()
            try:
                datetime.strptime(new_s, '%Y-%m-%d %H:%M:%S')
                datetime.strptime(new_e, '%Y-%m-%d %H:%M:%S')
            except ValueError as ex:
                messagebox.showerror("Error", f"Invalid date/time: {ex}")
                return
            update_timecard(tc_id, new_s, new_e,
                            valid_var.get(),
                            desc_text.get('1.0', 'end-1c'))
            self.load_tree()
            messagebox.showinfo("Saved", "Entry updated")
            win.destroy()

        save_btn = tk.Button(
            btn_frame, text="Save", command=save,
            bg=BUTTON_COLOR, fg=BG_COLOR,
            bd=0, highlightthickness=0, relief='flat'
        )
        cancel_btn = tk.Button(
            btn_frame, text="Cancel", command=win.destroy,
            bg=BUTTON_COLOR, fg=BG_COLOR,
            bd=0, highlightthickness=0, relief='flat'
        )
        save_btn.pack(side='left', expand=True, fill='x', padx=(0, 5))
        cancel_btn.pack(side='left', expand=True, fill='x', padx=(5, 0))

    def start_logging(self):
        self.start_time = datetime.now()
        # disable controls while clocked in
        self.month_cb.config(state='disabled')
        self.year_cb.config(state='disabled')
        self.filter_btn.config(state='disabled')
        self.clear_btn.config(state='disabled')
        self.xlsx_btn.config(state='disabled')
        self.csv_btn.config(state='disabled')
        self.pdf_btn.config(state='disabled')

    def stop_logging(self):
        if not self.start_time:
            return
        end = datetime.now()
        tc = TimeCard(self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                      end.strftime('%Y-%m-%d %H:%M:%S'))
        log_timecard(tc)
        self.load_tree()
        self.start_time = None
        # re‑enable controls once stopped
        self.month_cb.config(state='readonly')
        self.year_cb.config(state='readonly')
        self.filter_btn.config(state='normal')
        self.clear_btn.config(state='normal')
        self.xlsx_btn.config(state='normal')
        self.csv_btn.config(state='normal')
        self.pdf_btn.config(state='normal')

    def toggle_logging(self):
        if not self.start_time:
            self.start_logging()
            self.clock_btn.config(text="Clock Out")
        else:
            self.stop_logging()
            self.clock_btn.config(text="Clock In")

    def generate_xlsx(self):
        # Ask where to save
        path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel Files', '*.xlsx')],
            title='Save XLSX Report'
        )
        if not path:
            return

        # Only valid entries from the current view
        raw = self.current_cards
        cards = [tc for tc in raw if tc.valid]

        # Aggregate hours & descriptions per date
        daily_hours = {}
        daily_desc = {}
        for tc in cards:
            date = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S').date()
            _, hrs = tc.duration_hours()
            daily_hours[date] = daily_hours.get(date, 0) + hrs
            if tc.description:
                daily_desc.setdefault(date, []).append(tc.description)

        # Determine selected month & year
        m = list(calendar.month_name).index(self.month_cb.get())
        y = int(self.year_cb.get())
        last_day = calendar.monthrange(y, m)[1]

        # Build every day of that month
        full_days = [datetime(y, m, d).date() for d in range(1, last_day + 1)]

        # Prepare rows with four columns: Date, Payment Method, Description, Hours
        rows = []
        for d in full_days:
            hrs = round(daily_hours.get(d, 0), 2)
            desc = "; ".join(daily_desc.get(d, []))
            rows.append({
                'Date': d.strftime('%Y-%m-%d'),
                'Payment Method': PAYMENT_METHOD_EMAIL,
                'Description': desc,
                'Hours': hrs
            })

        # Add the summary block...
        rows.append({'Date': '', 'Payment Method': '', 'Description': '', 'Hours': ''})
        rows.append({'Date': 'Pay per Hour', 'Payment Method': '', 'Description': '', 'Hours': round(self.rate_per_hour, 2)})
        total_hours = sum(daily_hours.values())
        gross_pay = total_hours * self.rate_per_hour
        net_pay = gross_pay * NET_RATE
        rows.extend([
            {'Date': 'Total Hours', 'Payment Method': '', 'Description': '', 'Hours': round(total_hours, 2)},
            {'Date': 'Gross Pay', 'Payment Method': '', 'Description': '', 'Hours': round(gross_pay, 2)},
            {'Date': 'Net Pay', 'Payment Method': '', 'Description': '', 'Hours': round(net_pay, 2)},
        ])

        # Create DataFrame with correct column order
        df = pd.DataFrame(rows, columns=['Date', 'Payment Method', 'Description', 'Hours'])

        # Write to Excel
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Summary')
            workbook = writer.book
            worksheet = writer.sheets['Summary']

            # Bold the header row
            header_font = Font(bold=True)
            for cell in worksheet[1]:
                cell.font = header_font

            # Auto‑size columns except "Description"
            for col_cells in worksheet.columns:
                header = col_cells[0].value
                if header == 'Description':
                    # skip resizing this column
                    continue
                max_length = max(len(str(cell.value)) for cell in col_cells)
                worksheet.column_dimensions[col_cells[0].column_letter].width = max_length + 2

        messagebox.showinfo("Export Complete", f"XLSX report saved to:\n{path}")

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
        # Always use the filtered view (even if it's empty),
        # only default to all cards if attribute isn't set yet.
        cards = getattr(self, 'current_cards', [])
        if cards is None:
            cards = fetch_timecards()

        total = sum(tc.duration_hours()[1] for tc in cards if tc.valid)
        gross = total * self.rate_per_hour
        net = gross * NET_RATE

        self.gross_lbl.config(text=f"Gross: ${gross:.2f}")
        self.net_lbl.config(text=f"Net:   ${net:.2f}")

    def on_closing(self):
        if self.start_time:
            messagebox.showwarning("Warning", "Stop logging first.")
            return
        self.root.destroy()

    def show_rates(self):
        """Display a popup with pay‑per‑hour and net‑rate details."""
        # RATE_PER_HOUR is stored in self.rate_per_hour,
        # NET_RATE is the fraction (e.g. 0.80)
        pct = int(NET_RATE * 100)
        messagebox.showinfo(
            "Program Details",
            f"Pay per hour: ${self.rate_per_hour:.2f}\n"
            f"Net rate: {pct}% of gross\n"
            f"Working Directory: {CONFIG_DIR}"
        )


class AddEntryWindow:
    def __init__(self, app: WorkLoggerApp):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Add Entry")
        self.win.configure(bg=BG_COLOR)
        self.win.transient(app.root)
        self.win.grab_set()
        self.win.focus_force()

        # -- use a tk.Frame so we can set bg/fg --
        frm = tk.Frame(self.win, bg=BG_COLOR, padx=10, pady=10)
        frm.pack(fill='both', expand=True)

        # Start time
        tk.Label(frm, text="Start Time:", bg=BG_COLOR, fg=FG_COLOR)\
            .grid(row=0, column=0, sticky='e', pady=2)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.start_var = tk.StringVar(value=now_str)
        tk.Entry(frm, textvariable=self.start_var, width=25,
                 bg=TREE_BG, fg=FG_COLOR, insertbackground=FG_COLOR,
                 relief='flat')\
            .grid(row=0, column=1, pady=2)

        # End time
        tk.Label(frm, text="End Time:", bg=BG_COLOR, fg=FG_COLOR)\
            .grid(row=1, column=0, sticky='e', pady=2)
        self.end_var = tk.StringVar(value=now_str)
        tk.Entry(frm, textvariable=self.end_var, width=25,
                 bg=TREE_BG, fg=FG_COLOR, insertbackground=FG_COLOR,
                 relief='flat')\
            .grid(row=1, column=1, pady=2)

        # Valid checkbox
        self.valid_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frm, text="Valid", variable=self.valid_var,
                       bg=BG_COLOR, fg=FG_COLOR,
                       activebackground=BG_COLOR,
                       selectcolor=TREE_BG)\
            .grid(row=2, column=1, sticky='w', pady=2)

        # Description
        tk.Label(frm, text="Description:", bg=BG_COLOR, fg=FG_COLOR)\
            .grid(row=3, column=0, sticky='ne', pady=2)
        self.desc_text = tk.Text(frm, width=40, height=5,
                                 bg=TREE_BG, fg=FG_COLOR,
                                 insertbackground=FG_COLOR,
                                 relief='flat')
        self.desc_text.grid(row=3, column=1, pady=2)

        # Buttons (use your Accent style)
        btn_frame = tk.Frame(self.win, bg=BG_COLOR, pady=10)
        btn_frame.pack(fill='x', padx=10, pady=(10, 0))  # make the frame stretch

        save_btn = tk.Button(
            btn_frame,
            text="Save",
            command=self.save,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            bd=0,
            highlightthickness=0,
            relief='flat'
        )
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=self.win.destroy,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            bd=0,
            highlightthickness=0,
            relief='flat'
        )

        # pack them side-by-side, equally expanding
        save_btn.pack(side='left', expand=True, fill='x', padx=(0, 5))
        cancel_btn.pack(side='left', expand=True, fill='x', padx=(5, 0))


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
