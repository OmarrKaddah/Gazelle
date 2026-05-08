import _bootstrap  # noqa: F401
from parser import loadParsed
from chunker import chunkDoc, dumpChunks

docName = "chapter_3"

elements = loadParsed(docName)
chunks = chunkDoc(elements)
dumpChunks(chunks, docName)
print(f"Chunked {len(elements)} elements into {len(chunks)} chunks")
print(f"Saved: chunks/{docName}.json")
