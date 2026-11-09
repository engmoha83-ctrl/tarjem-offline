"""Where things live, both when running from source and from the built .exe."""
import os
import sys

FROZEN = getattr(sys, "frozen", False)

# Folder with the .exe (or the repo root when running from source)
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Bundled read-only resources (UI). PyInstaller puts them under sys._MEIPASS.
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)

UI_DIR = os.path.join(RES_DIR, "ui")
DATA_DIR = os.path.join(UI_DIR, "data")
MODELS_DIR = os.environ.get("TARJEM_MODELS", os.path.join(APP_DIR, "models"))


def user_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "Tarjem")
    os.makedirs(d, exist_ok=True)
    return d


MY_TERMS_FILE = os.path.join(user_dir(), "my_terms.json")
