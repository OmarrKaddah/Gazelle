import _bootstrap  # noqa: F401
import sys
from scrapeFra import scrapeFra

# Usage: python runners/runScrapeFra.py [maxPages]
# Omit maxPages to crawl all FRA regulation pages; pass e.g. 1 to test on page 1.
maxPages = int(sys.argv[1]) if len(sys.argv) > 1 else None
scrapeFra(maxPages=maxPages)
