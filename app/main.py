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


def selftest(out_path):
    """Used by the build to check the packaged .exe really loads the models."""
    try:
        return _selftest(out_path)
    except BaseException:
        import traceback
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("FAIL\n" + traceback.format_exc())
        return 1


def _selftest(out_path):
    unblock_bundle()
    import webview  # noqa: F401  (make sure the GUI library is bundled too)
    if sys.platform == "win32":
        import clr  # noqa: F401  (the .NET bridge the window needs; fails if Python.Runtime.dll can't load)
        from webview.platforms import winforms  # noqa: F401
    g = Glossary()
    e = Engine(g)
    e.load()
    with open(out_path, "w", encoding="utf-8") as fh:
        if not e.ready:
            fh.write("FAIL " + str(e.error))
            return 1
        fh.write("OK ar-en: " + e.translate("تم اعتماد جدول الكميات والمخططات التنفيذية.", "ar-en")["text"] + "\n")
        fh.write("OK en-ar: " + e.translate("The shop drawings were approved.", "en-ar")["text"] + "\n")
    return 0


def unblock_bundle():
    """Remove Windows' "downloaded from the internet" mark from our own files.

    When the portable zip is extracted with Explorer, every file inherits a
    Zone.Identifier stream, and .NET then refuses to load Python.Runtime.dll
    ("Failed to resolve Python.Runtime.Loader.Initialize").
    """
    if sys.platform != "win32" or not paths.FROZEN or os.environ.get("TARJEM_NO_UNBLOCK"):
        return
    for root, _dirs, files in os.walk(paths.RES_DIR):
        for f in files:
            if f.lower().endswith((".dll", ".exe", ".pyd")):
                try:
                    os.remove(os.path.join(root, f) + ":Zone.Identifier")
                except OSError:
                    pass


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))
    unblock_bundle()
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
