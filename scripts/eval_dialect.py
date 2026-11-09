"""Compare direct vs two-step (dialect -> MSA -> English) translation on colloquial sentences."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APPDATA", os.path.join(os.getcwd(), ".appdata"))
from huggingface_hub import HfApi, hf_hub_download  # noqa: E402
from app.glossary import Glossary  # noqa: E402
from app.llm import LlamaServer, build_messages, msa_messages  # noqa: E402

server_exe, repo = sys.argv[1], sys.argv[2]
f = [x for x in HfApi().list_repo_files(repo) if x.lower().endswith("q4_k_m.gguf")][0]
srv = LlamaServer(server_exe, hf_hub_download(repo, f), gpu_layers=0, ctx=4096)
assert srv.start(timeout=600, log_path="srv.log"), srv.error
g = Glossary()
SENTS = [
    "نط من القطر على طول",
    "اركب القطر الساعة 5",
    "الواد ده بيشتغل على قده",
    "خلّص الشغل ده النهارده ضروري ومتتأخرش",
    "الحديد لسه ماوصلش وهنصب بكرة",
    "الصبة اتأجلت عشان الخلاطة عطلانة",
    "يا باشمهندس العمال مشيوا بدري امبارح",
    "وش القواعد محتاج يتظبط قبل الصب",
    "ترى المقاول ما جاب العمال اليوم",
    "ابغى التقرير قبل الظهر لو سمحت",
    "معلش يا باشمهندس، الحديد لسه موصلش الموقع، هنصب بكرة إن شاء الله.",
]
for s in SENTS:
    terms = g.find(s, "ar-en")
    t0 = time.time()
    direct = srv.chat(build_messages(s, "ar-en", "formal", terms), max_tokens=200)
    t1 = time.time()
    msa = srv.chat(msa_messages(s), max_tokens=200)
    two = srv.chat(build_messages(msa, "ar-en", "formal", g.find(msa, "ar-en")), max_tokens=200)
    t2 = time.time()
    print(f"\nSRC   : {s}\nDIRECT: {direct}   ({t1-t0:.0f}s)\nMSA   : {msa}\nTWO   : {two}   ({t2-t1:.0f}s)")
srv.stop()
