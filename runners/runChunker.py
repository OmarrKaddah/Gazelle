import _bootstrap  # noqa: F401
from pathlib import Path
from parser import loadParsed
from chunker import chunkDoc, dumpChunks

for parsed in sorted(Path("parsed").glob("*.json")):
    docName = parsed.stem
    out = Path(f"chunks/{docName}.json")
    if out.exists():
        print(f"[skip] {docName}")
        continue
    print(f"[chunk] {docName}")
    elements = loadParsed(docName)
    chunks = chunkDoc(elements)
    dumpChunks(chunks, docName)
    print(f"        -> chunks/{docName}.json  ({len(chunks)} chunks)")
