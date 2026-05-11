import _bootstrap  # noqa: F401
from pathlib import Path
from ocr import runOcrAndDump

INPUT_DIR = Path("Documents")
OUT_DIR = Path("Doc_Out")
EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}

sources = sorted(p for p in INPUT_DIR.iterdir() if p.suffix.lower() in EXTENSIONS)

for source in sources:
    out = OUT_DIR / (source.stem + ".md")
    if out.exists():
        print(f"[skip] {source.name}")
        continue
    print(f"[ocr ] {source.name}")
    mdPath, sidecarPath = runOcrAndDump(str(source))
    print(f"       -> {mdPath}")
