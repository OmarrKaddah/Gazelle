import _bootstrap  # noqa: F401
import sys
from retrieve import loadEntityGraph
from leiden import leidenHierarchy
from community import writeCommunities

# Stage 4 end-to-end: entity graph -> Leiden hierarchy -> Neo4j communities.
#
# Usage: python runCommunities.py <scope> [resolution] [corpusName]
#   scope = 'musique'           -> one docName
#           'doc1,doc2,doc3'    -> a set of docNames (one corpus spanning many docs)
#           'ALL' (or '*')      -> every Entity in the DB, corpus-wide
# corpusName tags the written (:Community {corpus}); defaults to the scope, or
# 'all' when scope is the whole DB.

arg = sys.argv[1] if len(sys.argv) > 1 else 'musique'
resolution = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

if arg.upper() in ('ALL', '*'):
    scope = None
    defaultName = 'all'
elif ',' in arg:
    scope = [d.strip() for d in arg.split(',') if d.strip()]
    defaultName = scope[0]
else:
    scope = arg
    defaultName = arg
corpus = sys.argv[3] if len(sys.argv) > 3 else defaultName

# Global arm: Leiden over the semantic relation layer (RELATED) + identity bridging (SYNONYM).
# Co-mention is deliberately excluded — its density smears community structure.
adjacency, idToIdx, idxToId = loadEntityGraph(
    scope, includeSynonyms=True, useCoMention=False, useTriples=False, useRelated=True
)
hierarchy = leidenHierarchy(adjacency, resolution=resolution)
writeCommunities(hierarchy, idxToId, corpus)
