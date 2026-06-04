import os
import sys

os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')  # allow duplicate OpenMP runtime (gliner/torch vs mkl)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ('src', 'graphTraversal'):
    p = os.path.join(ROOT, d)
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT)
