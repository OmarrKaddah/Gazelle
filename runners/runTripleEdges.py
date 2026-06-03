import _bootstrap  # noqa: F401
import sys
from kgBuild import writeTripleEdges

docName = sys.argv[1] if len(sys.argv) > 1 else 'musique'
writeTripleEdges(docName)
