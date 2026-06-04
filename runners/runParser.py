import _bootstrap  # noqa: F401
import sys
from pathlib import Path
from parser import parseDoc, dumpParsed

# Parse: Doc_Out/<stem>.md -> parsed/<stem>.json
# Optional args restrict to specific doc names: python runners/runParser.py chapter_1 chapter_2
only = {a.lower() for a in sys.argv[1:]}

for source in sorted(Path("Doc_Out").glob("*.md")):
    docName = source.stem.lower()
    if only and docName not in only:
        continue
    if Path(f"parsed/{docName}.json").exists():
        print(f"[skip] {source.name}")
        continue
    print(f"[parse] {source.name}")
    dumpParsed(parseDoc(str(source)), docName)
    print(f"        -> parsed/{docName}.json")
