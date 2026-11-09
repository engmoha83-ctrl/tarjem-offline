"""Glossary: built-in terms (ui/data/*.js, shared with the UI) + the user's own terms."""
import glob
import json
import os
import re
import time
import uuid

from . import paths

_DIAC = "[ً-ٰٟـ]*"  # harakat + tatweel, allowed anywhere inside a word
_CHAR_CLASS = {
    "ا": "[اأإآٱ]", "أ": "[اأإآٱ]", "إ": "[اأإآٱ]", "آ": "[اأإآٱ]", "ٱ": "[اأإآٱ]",
    "ة": "[ةه]", "ه": "[ةه]",
    "ى": "[ىي]", "ي": "[ىي]",
    "ؤ": "[ؤو]", "ئ": "[ئي]",
}


def _strip(s: str) -> str:
    return re.sub(_DIAC, "", s)


def _word_pattern(word: str, first: bool) -> str:
    w = _strip(word)
    if w.startswith("ال") and len(w) > 3:
        w = w[2:]
    body = _DIAC.join(_CHAR_CLASS.get(c, re.escape(c)) for c in w)
    if first:
        prefix = "(?:[وفبكل]?ال|لل|[وف])?"
    else:
        prefix = "(?:ال|لل|[وفبكل]ال)?"
    return prefix + body + _DIAC


def arabic_regex(term: str):
    words = [w for w in re.split(r"\s+", term.strip()) if w]
    if not words:
        return None
    pat = r"\s+".join(_word_pattern(w, i == 0) for i, w in enumerate(words))
    return re.compile(r"(?<![\w؀-ۿ])" + pat + r"(?![\w؀-ۿ])")


def english_regex(term: str):
    words = [w for w in re.split(r"\s+", term.strip()) if w]
    if not words:
        return None
    pat = r"\s+".join(re.escape(w) for w in words)
    return re.compile(r"(?<![A-Za-z0-9])" + pat + r"(?![A-Za-z0-9])", re.IGNORECASE)


class Term:
    __slots__ = ("ar", "en", "abbr", "domain", "mine", "ar_main", "en_main", "ar_res", "en_res")

    def __init__(self, ar, en, abbr="", domain="general", mine=False):
        self.ar, self.en, self.abbr, self.domain, self.mine = ar, en, abbr, domain, mine
        self.ar_main = ar.split("/")[0].strip()
        self.en_main = en.split("/")[0].strip()
        self.ar_res = [arabic_regex(x) for x in ar.split("/") if len(_strip(x).strip()) > 1]
        self.en_res = [english_regex(x) for x in en.split("/") if len(x.strip()) > 1]
        self.ar_res = [r for r in self.ar_res if r]
        self.en_res = [r for r in self.en_res if r]


def load_builtin():
    terms = []
    for f in sorted(glob.glob(os.path.join(paths.DATA_DIR, "*.js"))):
        src = open(f, encoding="utf-8").read()
        m_id = re.search(r'id:\s*"([^"]+)"', src)
        m_terms = re.search(r"terms:\s*`(.*?)`", src, re.S)
        if not m_id or not m_terms:
            continue
        for line in m_terms.group(1).splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[0] and parts[1]:
                terms.append(Term(parts[0], parts[1], parts[2] if len(parts) > 2 else "", m_id.group(1)))
    return terms


class MyTerms:
    def __init__(self, path=paths.MY_TERMS_FILE):
        self.path = path
        try:
            with open(path, encoding="utf-8") as fh:
                self.items = json.load(fh)
        except Exception:
            self.items = []

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.items, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def add(self, ar, en, domain="general"):
        item = {"key": "t" + uuid.uuid4().hex[:10], "ar": ar.strip(), "en": en.strip(),
                "domain": domain or "general", "t": int(time.time() * 1000)}
        self.items.append(item)
        self._save()
        return item

    def delete(self, key):
        self.items = [i for i in self.items if i.get("key") != key]
        self._save()

    def terms(self):
        return [Term(i["ar"], i["en"], "", i.get("domain", "general"), True) for i in self.items if i.get("ar") and i.get("en")]


class Glossary:
    def __init__(self):
        self.builtin = load_builtin()
        self.mine = MyTerms()

    def all(self):
        # user terms first so they win over built-in ones
        return self.mine.terms() + self.builtin

    def enforce(self, text: str, direction: str):
        """Replace glossary terms in the source with their approved target-language form.

        Returns (new_text, used_terms). Longer terms are replaced first so that
        e.g. "خرسانة مسلحة" wins over "خرسانة".
        """
        terms = self.all()
        src_key = (lambda t: max((len(_strip(x)) for x in t.ar.split("/")), default=0)) if direction == "ar-en" \
            else (lambda t: max((len(x) for x in t.en.split("/")), default=0))
        terms = sorted(terms, key=lambda t: (not t.mine, -src_key(t)))
        used, seen = [], set()
        for t in terms:
            regs = t.ar_res if direction == "ar-en" else t.en_res
            repl = t.en_main if direction == "ar-en" else t.ar_main
            # Short single generic words (عقد، رد، موعد…) are only listed, not forced:
            # injecting them mid-sentence hurts the translation more than it helps.
            if direction == "ar-en":
                force = t.mine or " " in _strip(t.ar_main).strip() or src_key(t) >= 6
            else:
                force = t.mine or " " in t.en_main
            hit = False
            for r in regs:
                if force:
                    text, n = r.subn(lambda _m, s=repl: s, text)
                else:
                    n = 1 if r.search(text) else 0
                hit = hit or n > 0
            if hit and (t.ar_main, t.en_main) not in seen:
                seen.add((t.ar_main, t.en_main))
                used.append({"ar": t.ar_main, "en": t.en_main})
        return text, used

    def find(self, text: str, direction: str):
        """Which glossary terms appear in the text (without changing it)."""
        _, used = self.enforce(text, direction)
        return used
