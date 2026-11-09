"""Download the OPUS-MT models from Hugging Face and convert them to CTranslate2 int8.

Run once at build time (needs internet). The app itself never downloads anything.
"""
import os
import shutil

import ctranslate2
from huggingface_hub import snapshot_download

MODELS = [
    ("Helsinki-NLP/opus-mt-tc-big-ar-en", "ar-en"),
    ("Helsinki-NLP/opus-mt-tc-big-en-ar", "en-ar"),
]

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

for repo, name in MODELS:
    out = os.path.join(ROOT, name)
    print(f"== {repo} -> {out}")
    src = snapshot_download(repo, allow_patterns=["*.json", "*.spm", "*.txt", "*.bin", "*.safetensors"],
                            ignore_patterns=["*.h5", "*.msgpack", "*.ot"])
    ctranslate2.converters.TransformersConverter(src).convert(out, quantization="int8", force=True)
    for f in ("source.spm", "target.spm"):
        shutil.copy(os.path.join(src, f), os.path.join(out, f))
    readme = os.path.join(src, "README.md")
    with open(os.path.join(out, "LICENSE.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"{repo} — CC-BY-4.0, by Helsinki-NLP (OPUS-MT). https://huggingface.co/{repo}\n")
    print("   files:", sorted(os.listdir(out)))
