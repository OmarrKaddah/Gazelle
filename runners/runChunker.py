import _bootstrap  # noqa: F401
import sys
from pathlib import Path
from parser import loadParsed
from config import CHUNKER_TYPE

# Chunk: parsed/<stem>.json -> chunks/<stem>.json  (honors CHUNKER_TYPE, like runPipeline/runAll)
# Optional args restrict to specific doc names: python runners/runChunker.py chapter_1
only = {a.lower() for a in sys.argv[1:]}

_chunker_loaded = False
chunkDoc = dumpChunks = None

for parsed in sorted(Path("parsed").glob("*.json")):
    docName = parsed.stem
    if only and docName.lower() not in only:
        continue
    if Path(f"chunks/{docName}.json").exists():
        print(f"[skip] {docName}")
        continue
    if not _chunker_loaded:
        if CHUNKER_TYPE == 'semantic':
            from semantic_chunker import chunkDoc, dumpChunks
        else:
            from chunker import chunkDoc, dumpChunks
        _chunker_loaded = True
    print(f"[chunk] {docName} ({CHUNKER_TYPE})")
    chunks = chunkDoc(loadParsed(docName))
    dumpChunks(chunks, docName)
    print(f"        -> chunks/{docName}.json  ({len(chunks)} chunks)")
