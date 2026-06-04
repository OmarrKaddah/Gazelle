import _bootstrap  # noqa: F401
import sys
from pathlib import Path
from kgBuild import buildEntityLayer

# Route 1 graph build: extractions/<stem>_entities.json -> Neo4j Entity layer + COOCCURS_WITH.
# Usage:
#   python runners/runKgBuild.py                 # every doc with GLiNER entities
#   python runners/runKgBuild.py chapter_1 ...   # specific docs
docNames = sys.argv[1:] or [p.name[:-len('_entities.json')] for p in sorted(Path('extractions').glob('*_entities.json'))]

for docName in docNames:
    if not Path(f'extractions/{docName}_entities.json').exists():
        print(f'[skip] {docName} (no extractions/{docName}_entities.json)')
        continue
    print(f'[kgBuild] {docName}')
    buildEntityLayer(docName)
