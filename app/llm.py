"""'Accurate' mode: a local instruction-following LLM served by a bundled llama.cpp server."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

STYLE_EN = {
    "formal": "Formal business correspondence (letters and emails): polite, clear and professional, as used by engineering and contracting companies in Saudi Arabia. Do not add a greeting or closing unless the source has one.",
    "email": "Rewrite it as a complete, ready-to-send professional English email: first line 'Subject: ...', then greeting, body and a professional closing. Keep every fact, figure, date and reference.",
    "technical": "Precise technical translation, faithful to the source, suitable for reports, specifications and method statements.",
    "literal": "Close translation that keeps the original sentence order as much as natural English allows.",
}
STYLE_AR = {
    "formal": "Formal Modern Standard Arabic suitable for official business correspondence in Saudi Arabia.",
    "email": "Rewrite it as a complete, ready-to-send formal Arabic letter: a 'الموضوع:' line, a proper greeting, the body and a formal closing. Keep every fact, figure, date and reference.",
    "technical": "Precise technical Modern Standard Arabic, faithful to the source.",
    "literal": "Close translation that keeps the original structure as much as natural Arabic allows.",
}


def build_messages(text, direction="ar-en", style="formal", terms=()):
    to_en = direction == "ar-en"
    lines = [
        "You are an expert professional translator between Arabic and English for engineering, construction contracting, "
        "contracts, project planning, finance and administration in Saudi Arabia.",
        ("Translate the user's text from Arabic into English." if to_en else "Translate the user's text from English into Arabic."),
        "Style: " + (STYLE_EN if to_en else STYLE_AR).get(style, STYLE_EN["formal"] if to_en else STYLE_AR["formal"]),
    ]
    if terms:
        lines.append("Mandatory terminology - when the concept appears, use exactly this equivalent:")
        for t in terms:
            lines.append(f"- {t['ar']} = {t['en']}" if to_en else f"- {t['en']} = {t['ar']}")
    lines += [
        "Rules:",
        "1. Output ONLY the translation. No notes, explanations, quotes or preamble.",
        "2. Keep numbers, amounts, dates, reference and drawing numbers, names and codes exactly." + (" Use Western digits." if to_en else ""),
        "3. Keep paragraph breaks and numbered lists.",
        "4. Never add information that is not in the source: no extra sentences, no attachments, no names, dates or [placeholders].",
        ("5. The source may be colloquial (Egyptian or Saudi dialect) or mixed with English words: translate the intended meaning into correct professional English. On a construction site 'قواعد' means footings, 'سملات' tie beams, 'طوبار/شدة' formwork, 'الحفر' excavation, 'صب/نصب' pour or cast concrete."
         if to_en else "5. Write correct Modern Standard Arabic."),
    ]
    return [{"role": "system", "content": "\n".join(lines)}, {"role": "user", "content": text}]


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class LlamaServer:
    """Starts llama-server.exe with a GGUF model and talks to its OpenAI-compatible API."""

    def __init__(self, server_exe, model_path, gpu_layers=99, ctx=4096, threads=None):
        self.server_exe, self.model_path = server_exe, model_path
        self.gpu_layers, self.ctx, self.threads = gpu_layers, ctx, threads
        self.proc, self.port, self.error = None, None, None
        self.log_path = None

    def start(self, timeout=180, log_path=None):
        self.port = _free_port()
        args = [self.server_exe, "-m", self.model_path, "--host", "127.0.0.1", "--port", str(self.port),
                "-c", str(self.ctx), "-ngl", str(self.gpu_layers), "--jinja"]
        if self.threads:
            args += ["-t", str(self.threads)]
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        self.log_path = log_path
        log = open(log_path, "w", encoding="utf-8", errors="replace") if log_path else subprocess.DEVNULL
        self.proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                self.error = f"llama-server exited with code {self.proc.returncode}"
                return False
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        self.error = "llama-server did not start in time"
        return False

    def chat(self, messages, max_tokens=1500, temperature=0.2, stream_cb=None):
        body = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                "top_p": 0.9, "stream": bool(stream_cb),
                "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions",
                                     data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            if not stream_cb:
                data = json.loads(r.read().decode("utf-8"))
                return clean(data["choices"][0]["message"].get("content") or "")
            out = []
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content") or ""
                except Exception:
                    continue
                if delta:
                    out.append(delta)
                    stream_cb(clean("".join(out)))
            return clean("".join(out))

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except Exception:
                self.proc.kill()


def clean(s):
    # Drop any reasoning block a model might emit despite enable_thinking=False
    if "</think>" in s:
        s = s.split("</think>", 1)[1]
    return s.replace("<think>", "").strip()
