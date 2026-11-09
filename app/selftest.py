"""Smoke test run by the build: loads both models and prints sample translations."""
import sys
import time

from .engine import Engine
from .glossary import Glossary

AR = [
    "بالإشارة إلى خطابنا رقم ١٢٣ بخصوص المستخلص رقم 5، نود إفادتكم بأن صب الخرسانة المسلحة لبلاطة الدور الأول تأخر بسبب عدم اعتماد المخططات التنفيذية حتى الآن.",
    "نرجو التكرم باعتماد طريقة التنفيذ المرفقة وإفادتنا في موعد أقصاه يوم الخميس القادم.",
    "يرجى العلم بأن غرامة التأخير ستطبق وفقا لأحكام العقد في حال عدم الالتزام بالبرنامج الزمني المعتمد.",
    "المقاول مسؤول عن أعمال العزل المائي للأساسات وردم الحفر بعد اختبار الدمك.",
    "تم صب قواعد الدور الأرضي وجاري تجهيز طوبار السملات.",
    "يجب الالتزام بقواعد السلامة في الموقع.",
    "معلش يا باشمهندس، الحديد لسه موصلش الموقع، هنصب بكرة إن شاء الله.",
    "تم تحديث البرنامج الزمني وإضافة نسبة الإنجاز الفعلية لكل نشاط، والمسار الحرج تأثر بتأخير أعمال التكييف.",
]
EN = [
    "Please find attached the updated baseline schedule for your review and approval.",
    "The contractor shall submit the shop drawings and the method statement before starting the concrete works.",
    "We regret to inform you that the interim payment certificate has not been paid yet.",
]


def main():
    g = Glossary()
    print(f"glossary: {len(g.builtin)} built-in terms")
    e = Engine(g)
    t0 = time.time()
    e.load()
    if not e.ready:
        print("LOAD FAILED:", e.error)
        sys.exit(1)
    print(f"models loaded in {time.time() - t0:.1f}s\n")
    for direction, samples in (("ar-en", AR), ("en-ar", EN)):
        for s in samples:
            for enforce in (False, True):
                t0 = time.time()
                r = e.translate(s, direction, enforce)
                tag = "glossary" if enforce else "plain   "
                print(f"[{direction} {tag} {time.time() - t0:.1f}s] {r['text']}")
            print("   terms:", ", ".join(f"{t['ar']}={t['en']}" for t in r["terms"]))
            print("   src  :", s, "\n")
    # multi-paragraph / list structure
    r = e.translate("الموضوع: طلب تمديد المدة\n\n1- تأخر اعتماد المواد.\n2- تأخر استلام الموقع.", "ar-en", True)
    print("[structure]\n" + r["text"])
    if not r["text"].strip():
        sys.exit(1)


if __name__ == "__main__":
    main()
