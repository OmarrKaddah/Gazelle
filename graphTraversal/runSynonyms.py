import _bootstrap  # noqa: F401
import sys
from synonyms import writeSynonymEdges

docName = sys.argv[1]
threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.85
writeSynonymEdges(docName, threshold)
