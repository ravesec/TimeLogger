import csv
from datetime import datetime
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
from storage import fetch_timecards


def export_to_csv(filepath):
    """
    Dump the entire timecards list to CSV:
      id, start_time, end_time, valid, description
    """
    cards = fetch_timecards()

    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        # header matches table columns
        writer.writerow(['id', 'start_time', 'end_time', 'valid', 'description'])
        for tc in cards:
            writer.writerow([
                tc.id,
                tc.start_time,
                tc.end_time,
                int(tc.valid),
                tc.description
            ])


def generate_pdf_report(filepath, cards=None):
    """
    PDF report: bar chart of hours per day, ignoring invalid entries.
    """
    raw = cards or fetch_timecards()
    cards = [tc for tc in raw if tc.valid]

    # Aggregate hours per date
    daily = {}
    for tc in cards:
        date = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S').date()
        _, hrs = tc.duration_hours()
        daily[date] = daily.get(date, 0) + hrs

    dates = sorted(daily)
    hours = [daily[d] for d in dates]

    fig, ax = plt.subplots()
    ax.bar([d.strftime('%Y-%m-%d') for d in dates], hours)
    ax.set_title('Hours per Day')
    ax.set_xlabel('Date')
    ax.set_ylabel('Hours')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    with PdfPages(filepath) as pdf:
        pdf.savefig(fig)
        plt.close(fig)
