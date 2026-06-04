# Per-document access levels. Edit DOC_ACCESS to mark a document as confidential or restricted.
# Documents not listed here default to 'internal'.

from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

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


def allDocNames():
    # The universe of ingested docs is whatever exists in Neo4j, not just the DOC_ACCESS dict —
    # so the scraped corpus (unlisted -> DEFAULT_LEVEL) is included, not silently filtered out.
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            return [r['doc'] for r in session.run('MATCH (d:Document) RETURN d.docName AS doc')]


def allowedDocs(userClearance):
    threshold = levelRank(userClearance)
    return [doc for doc in allDocNames() if levelRank(docLevel(doc)) <= threshold]


def canSeeDoc(docName, userClearance):
    return levelRank(docLevel(docName)) <= levelRank(userClearance)
