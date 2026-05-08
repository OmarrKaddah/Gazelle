import _bootstrap  # noqa: F401
from pathlib import Path
from parser import parseDoc, dumpParsed

source = "Doc_Out/Chapter_3.md"

elements = parseDoc(source)
stem = Path(source).stem
dumpParsed(elements, stem)
print(f"Parsed {len(elements)} elements from {source}")
print(f"Saved: parsed/{stem}.json")
