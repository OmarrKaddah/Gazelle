import _bootstrap  # noqa: F401
from pathlib import Path
from embedding import embedDoc

for chunk in sorted(Path("chunks").glob("*.json")):
    docName = chunk.stem
    print(f"[embed] {docName}")
    embedDoc(docName)
