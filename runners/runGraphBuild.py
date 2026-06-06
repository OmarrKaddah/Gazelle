import _bootstrap  # noqa: F401
import sys
from pathlib import Path

from graphBuild import buildGraph
from config import EXTRACT_DIR

# Route 2 graph build: {EXTRACT_DIR}/<stem>_graph.json -> Neo4j (:Entity)-[:RELATED]->(:Entity).
# Usage:
#   python runners/runGraphBuild.py                 # every doc with a graph extraction
#   python runners/runGraphBuild.py chapter_1 ...   # specific docs
docNames = sys.argv[1:] or [p.name[:-len('_graph.json')] for p in sorted(Path(EXTRACT_DIR).glob('*_graph.json'))]

for docName in docNames:
    if not Path(f'{EXTRACT_DIR}/{docName}_graph.json').exists():
        print(f'[skip] {docName} (no {EXTRACT_DIR}/{docName}_graph.json)')
        continue
    print(f'[graphBuild] {docName}')
    buildGraph(docName)
