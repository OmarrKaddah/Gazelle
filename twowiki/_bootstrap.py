import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ('src', 'graphTraversal'):
    p = os.path.join(ROOT, d)
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT)
