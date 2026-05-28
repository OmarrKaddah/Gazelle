import _bootstrap  # noqa: F401
from pathlib import Path
from parser import parseDoc, dumpParsed

INPUT_DIR = Path("Doc_Out")

sources = sorted(INPUT_DIR.glob("*.md"))

for source in sources:
    docName = source.stem.lower()
    out = Path(f"parsed/{docName}.json")
    if out.exists():
        print(f"[skip] {source.name}")
        continue
    print(f"[parse] {source.name}")
    elements = parseDoc(str(source))
    dumpParsed(elements, docName)
    print(f"        -> parsed/{docName}.json")
