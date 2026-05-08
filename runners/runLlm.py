import _bootstrap  # noqa: F401
from llmExtract import extractDoc, dumpExtractions

docName = "chapter_3"

results = extractDoc(docName)
dumpExtractions(results, docName)
totalEnts = sum(len(r['entities']) for r in results)
totalRels = sum(len(r['relationships']) for r in results)
print(f"Done: {len(results)} chunks -> {totalEnts} entities, {totalRels} relationships")
print(f"Saved: extractions/{docName}.json")