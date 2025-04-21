import csv
from datetime import datetime
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
from storage import fetch_timecards


def export_to_csv(filepath, cards=None):
    """
    Export one row per day, ignoring invalid entries:
      Date (MM/DD/YYYY), blank column, combined Descriptions, total Hours.
    """
    # fetch if not provided, then drop invalid
    raw = cards or fetch_timecards()
    cards = [tc for tc in raw if tc.valid]

    # Aggregate by date
    daily = {}
    for tc in cards:
        date = datetime.strptime(tc.start_time, '%Y-%m-%d %H:%M:%S').date()
        desc = tc.description.strip()
        _, hrs = tc.duration_hours()
        if date not in daily:
            daily[date] = {'descs': [], 'hours': 0.0}
        if desc:
            daily[date]['descs'].append(desc)
        daily[date]['hours'] += hrs

    # Write CSV
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', '', 'Description', 'Hours'])
        for date in sorted(daily):
            date_str = date.strftime('%m/%d/%Y')
            combined_desc = ' | '.join(daily[date]['descs'])
            hours_str = f"{daily[date]['hours']:.2f}"
            writer.writerow([date_str, '', combined_desc, hours_str])


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
