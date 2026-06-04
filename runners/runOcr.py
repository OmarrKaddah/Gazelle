import _bootstrap  # noqa: F401
import sys
from pathlib import Path
from ocr import runOcrAndDump

# OCR: source documents -> Doc_Out/<stem>.md  (runOcrAndDump writes Doc_Out + output/ sidecar).
# Usage:
#   python runners/runOcr.py                     # all docs under Documents/ (recursive)
#   python runners/runOcr.py Documents/cbe       # just one folder
#   python runners/runOcr.py path/to/one.pdf ... # specific files
EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
OUT_DIR = Path("Doc_Out")


def collectSources(args):
    if not args:
        return sorted(p for p in Path("Documents").rglob("*") if p.suffix.lower() in EXTENSIONS)
    sources = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            sources += sorted(q for q in p.rglob("*") if q.suffix.lower() in EXTENSIONS)
        elif p.is_file():
            sources.append(p)
        else:
            print(f"[warn] not found: {a}")
    return sources


for source in collectSources(sys.argv[1:]):
    out = OUT_DIR / (source.stem + ".md")
    if out.exists():
        print(f"[skip] {source.name}")
        continue
    print(f"[ocr ] {source.name}")
    mdPath, _ = runOcrAndDump(str(source))
    print(f"       -> {mdPath}")
