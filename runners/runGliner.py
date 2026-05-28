import _bootstrap  # noqa: F401
from pathlib import Path
from glinerExtract import extractEntities, dumpEntities

for chunk in sorted(Path("chunks").glob("*.json")):
    docName = chunk.stem
    out = Path(f"extractions/{docName}_entities.json")
    if out.exists():
        print(f"[skip] {docName}")
        continue
    print(f"[gliner] {docName}")
    entities = extractEntities(docName)
    dumpEntities(entities, docName)
    print(f"         -> extractions/{docName}_entities.json  ({len(entities)} entities)")
