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
        "bg_color": "#121212",  # main background
        "fg_color": "#f2e7fe",  # main text
        "invalid_color": "grey",  # invalid entry
        "no_desc_color": "#cf6679",  # no‑desc entry
        "tree_bg": "#1d1d1d",  # TreeView background
        "button_color": "#03dac5",  # button fill
        "cal_bg": "#1d1d1d",  # calendar bg (unchanged)
        "cal_fg": "#f2e7fe"  # calendar fg (unchanged)
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
TREE_BG = CONFIG['ui']['tree_bg']
BUTTON_COLOR = CONFIG['ui']['button_color']
