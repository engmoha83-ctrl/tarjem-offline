"""CI check: start the bundled llama-server (Vulkan → CPU fallback) and translate with the real model."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.accurate import Accurate  # noqa: E402
from app.glossary import Glossary  # noqa: E402

a = Accurate(Glossary())
print("status:", a.status())
a.start()
t0 = time.time()
while a.state in ("loading", "idle") and time.time() - t0 < 400:
    time.sleep(1)
print("after start:", a.status(), f"{time.time() - t0:.0f}s")
if a.state != "ready":
    log = os.path.join(os.environ.get("APPDATA", "."), "Tarjem", "llama-server.log")
    if os.path.exists(log):
        print(open(log, encoding="utf-8", errors="replace").read()[-4000:])
    sys.exit(1)
for text, d, style in [
    ("نط", "ar-en", "formal"),
    ("نط من القطر على طول", "ar-en", "formal"),
    ("الصبة اتأجلت عشان الخلاطة عطلانة", "ar-en", "formal"),
    ("الآن جاري أعمال الحفر وبعد الانتهاء منها سنصب الخرسانة العادية تحت القواعد", "ar-en", "formal"),
    ("عايزين نبلغ الاستشاري إن المستخلص رقم 7 اتأخر شهرين ومحتاجين يتصرف بسرعة", "ar-en", "email"),
    ("The shop drawings for the ground floor footings were approved.", "en-ar", "formal"),
]:
    j = a.translate(text, d, style)["job"]
    while True:
        p = a.poll(j)
        if p["done"]:
            break
        time.sleep(0.5)
    print(f"[{d} {style} {p.get('secs')}s] {text}\n -> {p['text']}\n")
    if p.get("error") or not p["text"].strip():
        sys.exit(1)
    if len(text.split()) <= 3 and len(p["text"].split()) > 12:
        print("RUNAWAY OUTPUT for a short input"); sys.exit(1)
a.stop()
