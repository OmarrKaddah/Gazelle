import _bootstrap  # noqa: F401
import sys
from communitySummary import summarizeHierarchy
from config import GRAPH_EXTRACT_BACKEND

# Stage 3 end-to-end: (:Community) skeleton -> LLM reports written onto the nodes.
# Run after runCommunities.py has built the skeleton for this corpus.
#
# Usage: python runners/runCommunitySummary.py <corpus> [backend]

corpus = sys.argv[1] if len(sys.argv) > 1 else 'apnews'
backend = sys.argv[2] if len(sys.argv) > 2 else GRAPH_EXTRACT_BACKEND
print(f'[communitySummary] corpus={corpus} backend={backend}')
summarizeHierarchy(corpus, backend=backend)
