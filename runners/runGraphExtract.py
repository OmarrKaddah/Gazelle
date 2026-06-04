import _bootstrap  # noqa: F401
import sys
from pathlib import Path

from graphExtract import extractDoc, dumpElements

docNames = sys.argv[1:] or [p.stem for p in sorted(Path('chunks').glob('*.json'))]

for docName in docNames:
    if Path(f'extractions/{docName}_graph.json').exists():
        print(f'[skip] {docName}')
        continue
    print(f'[graphExtract] {docName}')
    dumpElements(extractDoc(docName), docName)
    print(f'           -> extractions/{docName}_graph.json')
