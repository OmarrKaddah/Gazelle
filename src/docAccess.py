# Per-document access levels. Edit DOC_ACCESS to mark a document as confidential or restricted.
# Documents not listed here default to 'internal'.

LEVELS = ['public', 'internal', 'confidential', 'restricted']

DEFAULT_LEVEL = 'internal'

DOC_ACCESS = {
    # Mock data — replace with real classifications.
    'Chapter_3': 'internal',
    'chapter_3': 'internal',
    'chapter_2': 'internal',
    'Gazma': 'public',
    'gazma2': 'confidential',
    'table_ar': 'restricted',
    'Documents/Phase - 1 document': 'confidential',
}


def levelRank(level):
    return LEVELS.index(level)


def docLevel(docName):
    return DOC_ACCESS.get(docName, DEFAULT_LEVEL)


def allowedDocs(userClearance):
    threshold = levelRank(userClearance)
    return [
        doc for doc, lvl in DOC_ACCESS.items()
        if levelRank(lvl) <= threshold
    ]


def canSeeDoc(docName, userClearance):
    return levelRank(docLevel(docName)) <= levelRank(userClearance)
