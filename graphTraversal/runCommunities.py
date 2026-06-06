import _bootstrap  # noqa: F401
import sys
from retrieve import loadEntityGraph
from leiden import leidenHierarchy
from community import writeCommunities
from config import COMMUNITY_RESOLUTION, CORPUS_NAME



arg = sys.argv[1] if len(sys.argv) > 1 else 'ALL'
resolution = float(sys.argv[2]) if len(sys.argv) > 2 else COMMUNITY_RESOLUTION

if arg.upper() in ('ALL', '*'):
    scope = None
elif ',' in arg:
    scope = [d.strip() for d in arg.split(',') if d.strip()]
else:
    scope = arg
corpus = sys.argv[3] if len(sys.argv) > 3 else CORPUS_NAME

# Global leiden 3ala related edges onlu

adjacency, idToIdx, idxToId = loadEntityGraph(
    scope, includeSynonyms=True, useCoMention=False, useTriples=False, useRelated=True
)
hierarchy = leidenHierarchy(adjacency, resolution=resolution)
writeCommunities(hierarchy, idxToId, corpus)
