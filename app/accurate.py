"""Accurate mode manager: model download, bundled llama-server lifecycle, background translation jobs."""
import json
import os
import threading
import time
import urllib.request
import uuid

from . import paths
from .llm import LlamaServer, build_messages

# Chosen after evaluating candidates on work sentences (see .github/workflows/eval-llm.yml)
MODEL = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json"), encoding="utf-8"))


def models_dir():
    base = os.environ.get("LOCALAPPDATA") or paths.user_dir()
    d = os.path.join(base, "Tarjem", "models")
    os.makedirs(d, exist_ok=True)
    return d


def model_path():
    return os.path.join(models_dir(), MODEL["file"])


def server_candidates():
    """Bundled llama.cpp builds, best first (Vulkan uses the GPU; CPU build is the fallback)."""
    exe = "llama-server.exe" if os.name == "nt" else "llama-server"
    out = []
    for sub, ngl in (("llama-vulkan", 99), ("llama-vulkan", 16), ("llama-cpu", 0)):
        p = os.path.join(paths.APP_DIR, "llm", sub, exe)
        if os.path.exists(p):
            out.append((p, ngl))
    return out


class Accurate:
    def __init__(self, glossary):
        self.glossary = glossary
        self.state = "missing"      # missing | downloading | loading | ready | error
        self.progress = 0.0
        self.error = None
        self.device = ""
        self.server = None
        self.jobs = {}
        self._lock = threading.Lock()
        if self._model_ok():
            self.state = "idle"

    # ---------- status ----------
    def _model_ok(self):
        p = model_path()
        return os.path.exists(p) and os.path.getsize(p) >= MODEL["bytes"] * 0.98

    def status(self):
        return {"state": self.state, "progress": round(self.progress, 3), "error": self.error,
                "device": self.device, "name": MODEL["name"], "size_gb": round(MODEL["bytes"] / 1e9, 1),
                "path": model_path()}

    # ---------- download (one time, needs internet) ----------
    def download(self):
        if self.state in ("downloading", "loading", "ready"):
            return self.status()
        self.state, self.error, self.progress = "downloading", None, 0.0
        threading.Thread(target=self._download, daemon=True).start()
        return self.status()

    def _download(self):
        dst = model_path()
        part = dst + ".part"
        try:
            have = os.path.getsize(part) if os.path.exists(part) else 0
            req = urllib.request.Request(MODEL["url"], headers={"User-Agent": "Tarjem/1.0", **({"Range": f"bytes={have}-"} if have else {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:
                    have = 0  # server ignored the range: start over
                clen = int(r.headers.get("Content-Length") or 0)
                total = (have + clen) if clen else MODEL["bytes"]
                MODEL["bytes"] = total
                with open(part, "ab" if have else "wb") as fh:
                    done = have
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        self.progress = min(done / total, 1.0)
            if os.path.getsize(part) < total:
                raise IOError("التحميل اتقطع — دوس تحميل تاني وهيكمل من مكانه")
            os.replace(part, dst)
            self.state = "idle"
            self.start()
        except Exception as e:
            self.state, self.error = "missing", f"{type(e).__name__}: {e}"

    def use_file(self, path):
        """Use a GGUF file the user already has (e.g. copied from a USB stick)."""
        if not path or not path.lower().endswith(".gguf") or not os.path.exists(path):
            return {"error": "اختار ملف .gguf"}
        import shutil
        self.stop()
        shutil.copyfile(path, model_path())
        MODEL["bytes"] = os.path.getsize(model_path())
        self.state = "idle"
        self.start()
        return self.status()

    # ---------- server ----------
    def start(self):
        if self.state in ("loading", "ready"):
            return self.status()
        if not self._model_ok():
            self.state = "missing"
            return self.status()
        self.state, self.error = "loading", None
        threading.Thread(target=self._start, daemon=True).start()
        return self.status()

    def _start(self):
        log = os.path.join(paths.user_dir(), "llama-server.log")
        last = "llama.cpp غير موجود في البرنامج"
        for exe, ngl in server_candidates():
            srv = LlamaServer(exe, model_path(), gpu_layers=ngl, ctx=4096)
            if srv.start(timeout=240, log_path=log):
                try:  # a tiny warm-up catches GPU out-of-memory before the user's first request
                    srv.chat([{"role": "user", "content": "Say OK."}], max_tokens=4)
                except Exception as e:
                    srv.stop()
                    last = f"{type(e).__name__}: {e}"
                    continue
                self.server = srv
                self.device = "كارت الشاشة" if ngl >= 99 else ("كارت الشاشة + المعالج" if ngl else "المعالج")
                self.state = "ready"
                return
            last = srv.error or last
            srv.stop()
        self.state, self.error = "error", last

    def stop(self):
        if self.server:
            self.server.stop()
            self.server = None
        if self.state == "ready":
            self.state = "idle"

    # ---------- translation jobs (the UI polls) ----------
    def translate(self, text, direction, style):
        if self.state != "ready":
            return {"error": "الموديل الدقيق مش جاهز"}
        jid = uuid.uuid4().hex[:8]
        job = {"text": "", "done": False, "error": None, "terms": self.glossary.find(text, direction), "t0": time.time()}
        self.jobs[jid] = job

        def run():
            try:
                with self._lock:
                    msgs = build_messages(text, direction, style, job["terms"])
                    job["text"] = self.server.chat(msgs, max_tokens=2000, stream_cb=lambda s: job.__setitem__("text", s))
            except Exception as e:
                job["error"] = f"{type(e).__name__}: {e}"
            job["done"] = True
            job["secs"] = round(time.time() - job["t0"], 1)

        threading.Thread(target=run, daemon=True).start()
        return {"job": jid, "terms": job["terms"]}

    def poll(self, jid):
        j = self.jobs.get(jid)
        if not j:
            return {"error": "job not found", "done": True}
        out = {k: j.get(k) for k in ("text", "done", "error", "secs")}
        if j["done"]:
            self.jobs.pop(jid, None)
        return out
