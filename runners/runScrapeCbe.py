import _bootstrap  # noqa: F401
import sys
from scrapeCbe import scrapeCbe

# Usage: python runners/runScrapeCbe.py [maxDepth] [--headful]
# maxDepth = how many link-hops from the regulations overview to follow (default 1).
# --headful = show a real browser window (try this if headless is WAF-blocked).
# Requires: pip install playwright && playwright install chromium
headless = '--headful' not in sys.argv
maxDepth = next((int(a) for a in sys.argv[1:] if a.isdigit()), 1)
scrapeCbe(headless=headless, maxDepth=maxDepth)
