"""Evaluate one GGUF model on the work test sentences (used by .github/workflows/eval-llm.yml).

usage: python scripts/eval_llm.py <llama-server path> <hf search query or repo> [quant]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APPDATA", os.path.join(os.getcwd(), ".appdata"))

from huggingface_hub import HfApi, hf_hub_download  # noqa: E402

from app.glossary import Glossary  # noqa: E402
from app.llm import LlamaServer, build_messages  # noqa: E402
from app.selftest import AR, EN  # noqa: E402

server_exe, query = sys.argv[1], sys.argv[2]
quant = (sys.argv[3] if len(sys.argv) > 3 else "Q4_K_M").lower()

api = HfApi()
repo = query if "/" in query else None
if not repo:
    hits = [m.id for m in api.list_models(search=query, sort="downloads", limit=20) if "gguf" in m.id.lower()]
    print("search hits:", hits[:5])
    repo = hits[0]
files = [f for f in api.list_repo_files(repo) if f.lower().endswith(".gguf") and quant in f.lower() and "mmproj" not in f.lower()]
print("repo:", repo, "files:", files)
path = hf_hub_download(repo, sorted(files, key=len)[0])
print(f"model file: {os.path.basename(path)}  {os.path.getsize(path) / 1e9:.2f} GB")

srv = LlamaServer(server_exe, path, gpu_layers=0, ctx=4096)
if not srv.start(timeout=600, log_path="llama-server.log"):
    print("SERVER FAILED:", srv.error)
    print(open("llama-server.log", encoding="utf-8", errors="replace").read()[-3000:])
    sys.exit(1)

g = Glossary()
extra_ar = [
    "اركب القطر الساعة 5",
    "قطر الماسورة 200 مم وطولها 6 متر",
    "السيارة عطلانة ومحتاجة ونش يقطرها للورشة",
    "هنتقابل بكرة الصبح في المكتب نراجع المستخلص",
    "تم صب الخرسانة العادية تحت القواعد أمس الساعة 7",
    "تم صب قواعد الدور الأرضي وجاري تجهيز طوبار السملات.",
    "الآن جاري أعمال الحفر وبعد الانتهاء منها سنصب الخرسانة العادية تحت القواعد",
]
cases = [("ar-en", s, "formal") for s in dict.fromkeys(AR + extra_ar)] + [("en-ar", s, "formal") for s in EN]
cases.append(("ar-en", "عايزين نبلغ الاستشاري إن المستخلص رقم 7 اتأخر شهرين ومحتاجين يتصرف بسرعة", "email"))

total_tok, total_t = 0, 0.0
for direction, text, style in cases:
    terms = g.find(text, direction)
    t0 = time.time()
    out = srv.chat(build_messages(text, direction, style, terms), max_tokens=600)
    dt = time.time() - t0
    total_t += dt
    total_tok += max(1, len(out.split())) * 1.4
    print(f"\n[{direction} {style} {dt:.1f}s]\nSRC: {text}\nOUT: {out}")

print(f"\nSUMMARY {repo}: {len(cases)} cases, {total_t:.0f}s total, ~{total_tok / total_t:.1f} tok/s on 4 vCPU (no GPU)")
srv.stop()
