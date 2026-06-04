import _bootstrap  # noqa: F401
from pathlib import Path
from typedOntologyExtract import extractDoc, dumpExtractions

for chunk in sorted(Path("chunks").glob("*.json")):
    docName = chunk.stem
    if not Path(f"extractions/{docName}_entities.json").exists():
        print(f"[wait ] {docName}  (no GLiNER output yet)")
        continue
    out = Path(f"extractions/{docName}.json")
    if out.exists():
        print(f"[skip] {docName}")
        continue
    print(f"[llm ] {docName}")
    results = extractDoc(docName)
    dumpExtractions(results, docName)
    totalEnts = sum(len(r['entities']) for r in results)
    totalRels = sum(len(r['relationships']) for r in results)
    print(f"        -> extractions/{docName}.json  ({totalEnts} ents, {totalRels} rels)")
