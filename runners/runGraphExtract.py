import _bootstrap  # noqa: F401
import sys
from pathlib import Path

from graphExtract import extractDoc

docNames = sys.argv[1:] or [p.stem for p in sorted(Path('chunks').glob('*.json'))]

for docName in docNames:
    print(f'[graphExtract] {docName}')
    extractDoc(docName)  # resumes from the checkpoint file; instant if already complete
    print(f'           -> extractions/{docName}_graph.json')
