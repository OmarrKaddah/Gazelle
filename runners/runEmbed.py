import _bootstrap  # noqa: F401
from embedding import embedDoc

docName = "chapter_3"

embedDoc(docName)
print(f"Done: {docName}")
