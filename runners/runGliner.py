import _bootstrap  # noqa: F401
from glinerExtract import extractEntities, dumpEntities

docName = "chapter_3"

entities = extractEntities(docName)
dumpEntities(entities, docName)
print(f"Extracted {len(entities)} entities from {docName}")
print(f"Saved: extractions/{docName}_entities.json")
