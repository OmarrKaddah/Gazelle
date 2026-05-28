import _bootstrap  # noqa: F401
from pathlib import Path
from kgWriter import writeDoc, writeDocEntitiesOnly, clearDb

clearDb()

for chunk in sorted(Path("chunks").glob("*.json")):
    docName = chunk.stem
    llmFile = Path(f"extractions/{docName}.json")
    glinerFile = Path(f"extractions/{docName}_entities.json")

    if llmFile.exists():
        print(f"[kg+rels ] {docName}")
        writeDoc(docName)
    elif glinerFile.exists():
        print(f"[kg+ents ] {docName}")
        writeDocEntitiesOnly(docName)
    else:
        print(f"[wait    ] {docName}  (no extractions yet)")
