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


def _writable(d: str) -> bool:
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".write-test")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


# Portable layout: when the program folder is writable, everything the user creates
# (downloaded accurate model, my terms) lives inside it, so copying the folder to
# another computer brings it all along. Otherwise fall back to the user's profile.
PORTABLE_DATA = os.path.join(APP_DIR, "data")
PORTABLE = _writable(PORTABLE_DATA)
DATA_HOME = PORTABLE_DATA if PORTABLE else user_dir()

MY_TERMS_FILE = os.path.join(DATA_HOME, "my_terms.json")
_legacy_terms = os.path.join(user_dir(), "my_terms.json")
if PORTABLE and not os.path.exists(MY_TERMS_FILE) and os.path.exists(_legacy_terms):
    try:
        import shutil
        shutil.copyfile(_legacy_terms, MY_TERMS_FILE)
    except OSError:
        pass
