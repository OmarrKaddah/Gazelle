# Per-document access levels. Edit DOC_ACCESS to mark a document as confidential or restricted.
# Documents not listed here default to 'internal'.

LEVELS = ['public', 'internal', 'confidential', 'restricted']

DEFAULT_LEVEL = 'internal'

DOC_ACCESS = {
    # Mock data — replace with real classifications.
    'Chapter_1': 'internal',
    'Chapter_2': 'internal',
    'Chapter_3': 'internal',
    'Chapter_4': 'internal',
    'Chapter_5': 'internal',
    'Chapter_6': 'internal',
    'Chapter_7': 'internal',
    'Chapter_8': 'internal',
    'Phase - 1 document': 'confidential',

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
