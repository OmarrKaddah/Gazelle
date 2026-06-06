import _bootstrap  # noqa: F401
import sys
from retrieve import loadEntityGraph
from leiden import leidenHierarchy
from community import writeCommunities
from config import COMMUNITY_RESOLUTION, CORPUS_NAME

# Stage 4 end-to-end: entity graph -> Leiden hierarchy -> Neo4j communities.
#
# Usage: python runCommunities.py [scope] [resolution] [corpusName]
#   scope = 'ALL' (or '*')      -> every Entity in the DB, corpus-wide (default)
#           'doc1,doc2,doc3'    -> a set of docNames (one corpus spanning many docs)
#           'musique'           -> one docName
# resolution defaults to COMMUNITY_RESOLUTION; corpusName tags the written
# (:Community {corpus}) and defaults to CORPUS_NAME.

arg = sys.argv[1] if len(sys.argv) > 1 else 'ALL'
resolution = float(sys.argv[2]) if len(sys.argv) > 2 else COMMUNITY_RESOLUTION

if arg.upper() in ('ALL', '*'):
    scope = None
elif ',' in arg:
    scope = [d.strip() for d in arg.split(',') if d.strip()]
else:
    scope = arg
corpus = sys.argv[3] if len(sys.argv) > 3 else CORPUS_NAME

# Global arm: Leiden over the semantic relation layer (RELATED) + identity bridging (SYNONYM).
# Co-mention is deliberately excluded — its density smears community structure.
adjacency, idToIdx, idxToId = loadEntityGraph(
    scope, includeSynonyms=True, useCoMention=False, useTriples=False, useRelated=True
)
hierarchy = leidenHierarchy(adjacency, resolution=resolution)
writeCommunities(hierarchy, idxToId, corpus)
