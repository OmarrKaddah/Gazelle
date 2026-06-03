import _bootstrap  # noqa: F401
import sys
from kgBuild import buildEntityLayer

docName = sys.argv[1]
buildEntityLayer(docName)
