import _bootstrap  # noqa: F401
import sys
from synonyms import writeSynonymEdges
from config import SYNONYM_THRESHOLD

# Corpus-wide SYNONYM edges over every embedded entity in the DB.
# threshold defaults to SYNONYM_THRESHOLD from config.
threshold = float(sys.argv[1]) if len(sys.argv) > 1 else SYNONYM_THRESHOLD
writeSynonymEdges(threshold)
