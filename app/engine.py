"""Offline translation engine: OPUS-MT (Helsinki-NLP tc-big) models run with CTranslate2."""
import os
import re
import threading

from . import paths

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Split after sentence-ending punctuation followed by whitespace.
_SENT_END = re.compile(r"(?<=[.!?؟؛])\s+")
# Fallback split points for very long sentences.
_CLAUSE = re.compile(r"(?<=[،,;:])\s+")
_MAX_PIECES = 180


class _Model:
    def __init__(self, folder, prefix=None):
        import ctranslate2
        import sentencepiece as spm
        threads = max(1, (os.cpu_count() or 2) - 1)
        self.tr = ctranslate2.Translator(folder, device="cpu", compute_type="int8", intra_threads=threads)
        self.sp_src = spm.SentencePieceProcessor(model_file=os.path.join(folder, "source.spm"))
        self.sp_tgt = spm.SentencePieceProcessor(model_file=os.path.join(folder, "target.spm"))
        self.prefix = prefix

    def pieces(self, s):
        return self.sp_src.encode(s, out_type=str)

    def translate(self, sentences):
        batch = []
        for s in sentences:
            toks = self.pieces(s)
            if self.prefix:
                toks = [self.prefix] + toks
            batch.append(toks + ["</s>"])
        res = self.tr.translate_batch(batch, beam_size=4, max_batch_size=16,
                                      max_input_length=512, max_decoding_length=512,
                                      repetition_penalty=1.1)
        out = []
        for r in res:
            toks = [t for t in r.hypotheses[0] if not (t.startswith(">>") or t in ("</s>", "<pad>", "<s>"))]
            out.append(self.sp_tgt.decode(toks).strip())
        return out


class Engine:
    def __init__(self, glossary):
        self.glossary = glossary
        self.models = {}
        self.error = None
        self.ready = False
        self._lock = threading.Lock()

    def load(self):
        try:
            self.models["ar-en"] = _Model(os.path.join(paths.MODELS_DIR, "ar-en"))
            self.models["en-ar"] = _Model(os.path.join(paths.MODELS_DIR, "en-ar"), prefix=">>ara<<")
            self.ready = True
        except Exception as e:  # shown in the UI
            self.error = f"{type(e).__name__}: {e}"

    def load_async(self):
        threading.Thread(target=self.load, daemon=True).start()

    def _segments(self, model, line):
        sents = [s for s in _SENT_END.split(line) if s.strip()]
        out = []
        for s in sents:
            if len(model.pieces(s)) <= _MAX_PIECES:
                out.append(s)
                continue
            buf = ""
            for c in _CLAUSE.split(s):
                cand = (buf + " " + c).strip() if buf else c
                if buf and len(model.pieces(cand)) > _MAX_PIECES:
                    out.append(buf)
                    buf = c
                else:
                    buf = cand
            if buf:
                out.append(buf)
        return out

    def translate(self, text, direction="ar-en", enforce=True):
        if not self.ready:
            raise RuntimeError(self.error or "model still loading")
        model = self.models[direction]
        text = text.replace("\r\n", "\n")
        if direction == "ar-en":
            text = text.translate(AR_DIGITS)
        # Glossary terms are only injected into Arabic sources: the en-ar model has no
        # Arabic in its source vocabulary, so injected terms come out as unknown tokens.
        inject = enforce and direction == "ar-en"
        used = self.glossary.find(text, direction)

        lines = text.split("\n")
        plan, flat = [], []
        for line in lines:
            if not line.strip():
                plan.append(None)
                continue
            m = re.match(r"^(\s*(?:[-•*▪]|\d+[.)\-]|[a-zA-Z][.)])\s*)", line)
            lead = m.group(1) if m else ""
            segs = self._segments(model, line[len(lead):])
            plan.append((lead.translate(AR_DIGITS), len(flat), len(segs)))
            flat.extend(segs)

        with self._lock:
            plain = model.translate(flat) if flat else []
            if inject and flat:
                forced_src = [self.glossary.enforce(s, direction)[0] for s in flat]
                idx = [i for i, (a, b) in enumerate(zip(flat, forced_src)) if a != b]
                forced = model.translate([forced_src[i] for i in idx]) if idx else []
                done = list(plain)
                for i, f in zip(idx, forced):
                    # Keep the glossary version unless it visibly dropped content
                    # (injection occasionally makes the model skip part of the sentence).
                    if len(f.split()) >= 0.8 * len(plain[i].split()):
                        done[i] = f
            else:
                done = plain

        out_lines = []
        for p in plan:
            if p is None:
                out_lines.append("")
            else:
                lead, start, n = p
                out_lines.append(lead + " ".join(done[start:start + n]))
        return {"text": "\n".join(out_lines), "terms": used}
