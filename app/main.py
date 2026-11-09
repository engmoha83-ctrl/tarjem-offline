"""Tarjem — offline Arabic ⇄ English work translator (desktop window)."""
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import paths
    from app.engine import Engine
    from app.glossary import Glossary
else:
    from . import paths
    from .engine import Engine
    from .glossary import Glossary


class Api:
    def __init__(self):
        self.glossary = Glossary()
        self.engine = Engine(self.glossary)
        self.engine.load_async()

    # --- translation ---
    def status(self):
        return {"ready": self.engine.ready, "error": self.engine.error}

    def translate(self, text, direction, enforce=True):
        try:
            return self.engine.translate(text or "", direction, bool(enforce))
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    # --- my terms ---
    def get_terms(self):
        return self.glossary.mine.items

    def add_term(self, ar, en, domain):
        if not (ar or "").strip() or not (en or "").strip():
            return {"error": "empty"}
        return self.glossary.mine.add(ar, en, domain)

    def delete_term(self, key):
        self.glossary.mine.delete(key)
        return True

    # --- clipboard (fallback when the web clipboard is unavailable) ---
    def copy(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            return False


def main():
    import webview
    api = Api()
    webview.create_window(
        "مُترجم الشغل — أوفلاين",
        url=os.path.join(paths.UI_DIR, "index.html"),
        js_api=api, width=1240, height=860, min_size=(820, 600),
    )
    webview.start(gui="edgechromium" if sys.platform == "win32" else None)


if __name__ == "__main__":
    main()
