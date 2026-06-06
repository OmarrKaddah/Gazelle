import _bootstrap  # noqa: F401
import sys
import traceback
from pathlib import Path
from glinerExtract import extractEntities, dumpEntities
from config import EXTRACT_DIR

lang = sys.argv[1] if len(sys.argv) > 1 else 'ar'
onlyDoc = sys.argv[2] if len(sys.argv) > 2 else None
print(f"[gliner] language={lang}" + (f" doc={onlyDoc}" if onlyDoc else ""), flush=True)

chunksDir = Path("chunks")
if not chunksDir.exists():
    print(f"[gliner] ERROR: {chunksDir.resolve()} does not exist", flush=True)
    sys.exit(1)

allChunks = sorted(chunksDir.glob("*.json"))
print(f"[gliner] found {len(allChunks)} chunk file(s): {[c.stem for c in allChunks]}", flush=True)

if onlyDoc and not any(c.stem == onlyDoc for c in allChunks):
    print(f"[gliner] ERROR: no chunks/{onlyDoc}.json found", flush=True)
    sys.exit(1)

processed = 0
for chunk in allChunks:
    docName = chunk.stem
    if onlyDoc and docName != onlyDoc:
        continue
    out = Path(f"{EXTRACT_DIR}/{docName}_entities.json")
    if out.exists():
        print(f"[skip] {docName} (already at {out})", flush=True)
        continue
    print(f"[gliner] starting {docName}", flush=True)
    try:
        entities = extractEntities(docName, lang=lang)
        dumpEntities(entities, docName)
    except Exception:
        print(f"[gliner] FAILED on {docName}:", flush=True)
        traceback.print_exc()
        sys.exit(1)
    print(f"         -> {out}  ({len(entities)} entities)", flush=True)
    processed += 1

print(f"[gliner] done. processed={processed}", flush=True)
