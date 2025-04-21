import os
import json

# --- CONFIGURATION LOADER ---
HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, "WorkLogger")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# default settings
defaults = {
    "rate_per_hour": 20.0,
    "db_path": os.path.join(CONFIG_DIR, "timelog.db"),
    "window_title": "WorkLogger 2.0",
    "theme": "clam",
    "ui": {
        "bg_color": "#121212",
        "fg_color": "#f2e7fe",
        "invalid_color": "gray",
        "no_desc_color": "#ff0000",
        "cal_bg": "#1d1d1d",
        "cal_fg": "#f2e7fe"
    }
}

# ensure config dir exists
os.makedirs(CONFIG_DIR, exist_ok=True)


# load or create config.json
def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(defaults, f, indent=2)
        return defaults
    with open(CONFIG_PATH, 'r') as f:
        user = json.load(f)
    # merge defaults with user overrides
    cfg = defaults.copy()
    cfg.update({k: v for k, v in user.items() if k != 'ui'})
    ui = defaults['ui'].copy()
    ui.update(user.get('ui', {}))
    cfg['ui'] = ui
    return cfg


CONFIG = load_config()

# expose top‑level constants
RATE_PER_HOUR = CONFIG['rate_per_hour']
DB_PATH = CONFIG['db_path']
WINDOW_TITLE = CONFIG['window_title']
THEME = CONFIG['theme']
# ui colors
BG_COLOR = CONFIG['ui']['bg_color']
FG_COLOR = CONFIG['ui']['fg_color']
INVALID_COLOR = CONFIG['ui']['invalid_color']
NO_DESC_COLOR = CONFIG['ui']['no_desc_color']
CAL_BG = CONFIG['ui']['cal_bg']
CAL_FG = CONFIG['ui']['cal_fg']
