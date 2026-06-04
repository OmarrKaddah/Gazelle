import _bootstrap  # noqa: F401
import sys
from pathlib import Path
import embedding
from embedding import embedDoc

# Embed: chunks/<stem>.json -> Neo4j vector index (re-runs are idempotent: vectors overwrite).
# Optional args restrict to specific doc names: python runners/runEmbed.py chapter_1
only = {a.lower() for a in sys.argv[1:]}

for chunk in sorted(Path("chunks").glob("*.json")):
    docName = chunk.stem
    if only and docName.lower() not in only:
        continue
    print(f"[embed] {docName}")
    embedDoc(docName)

print(f"[embed] done. total chunks needing NaN rescue: {embedding.nanRescued}", flush=True)
