import _bootstrap  # noqa: F401
import numpy as np
from collections import defaultdict
from neo4j import GraphDatabase
from seeder import loadEntityEmbeddings, seedFromQuery
from loadGraph import fetchEdges, buildIndex, buildAdjacency
from ppr import ppr
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


# ── graph loading ────────────────────────────────────────────────

def scopeClause(scope, *aliases):
    # Restrict the given Entity aliases to a corpus scope. scope is one of:
    #   None  -> whole DB (every Entity, regardless of docName) = corpus-wide
    #   str   -> a single docName (back-compat with per-doc retrieval)
    #   list  -> a set of docNames belonging to one corpus
    # Returns a WHERE fragment ('' when unscoped) and the param dict.
    if scope is None:
        return '', {}
    op = '= $scope' if isinstance(scope, str) else 'IN $scope'
    val = scope if isinstance(scope, str) else list(scope)
    conds = ' AND '.join(f'{a}.docName {op}' for a in aliases)
    return 'WHERE ' + conds, {'scope': val}


def fetchCoMentionEdges(scope):
    where, params = scopeClause(scope, 'a', 'b')
    cypher = f'''
    MATCH (a:Entity)-[r:COOCCURS_WITH]->(b:Entity)
    {where}
    RETURN a.canonicalId AS src, b.canonicalId AS dst, r.count AS weight
    '''
    return fetchEdges(cypher, **params)


def fetchSynonymEdges(scope, weight):
    where, params = scopeClause(scope, 'a', 'b')
    cypher = f'''
    MATCH (a:Entity)-[r:SYNONYM]->(b:Entity)
    {where}
    RETURN a.canonicalId AS src, b.canonicalId AS dst, $weight AS weight
    '''
    return fetchEdges(cypher, weight=weight, **params)


def fetchTripleEdges(scope):
    where, params = scopeClause(scope, 'a', 'b')
    cypher = f'''
    MATCH (a:Entity)-[r:TRIPLE]->(b:Entity)
    {where}
    RETURN a.canonicalId AS src, b.canonicalId AS dst, r.count AS weight
    '''
    return fetchEdges(cypher, **params)


def fetchRelatedEdges(scope):
    where, params = scopeClause(scope, 'a', 'b')
    cypher = f'''
    MATCH (a:Entity)-[r:RELATED]->(b:Entity)
    {where}
    RETURN a.canonicalId AS src, b.canonicalId AS dst, r.weight AS weight
    '''
    return fetchEdges(cypher, **params)


def loadEntityGraph(scope, includeSynonyms=False, synonymWeight=1.0, useCoMention=False, useTriples=False, useRelated=True):
    # scope: a docName, a list of docNames, or None for the whole corpus.
    # Default layers reflect the Route 2 deployment: RELATED relations + (optional) SYNONYM.
    # co-mention is off by default (its v7b benefit was measured on bare TRIPLE edges, not RELATED).
    edges = []
    if useRelated:
        edges += fetchRelatedEdges(scope)
    if useCoMention:
        edges += fetchCoMentionEdges(scope)
    if useTriples:
        edges += fetchTripleEdges(scope)
    if includeSynonyms:
        edges += fetchSynonymEdges(scope, synonymWeight)
    idToIdx, idxToId = buildIndex(edges)
    adjacency = buildAdjacency(edges, idToIdx, undirected=True)
    return adjacency, idToIdx, idxToId


# ── chunk projection lookups ─────────────────────────────────────

def runCypher(cypher, **params):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            return list(session.run(cypher, **params))


def loadEntityToChunks(scope):
    where, params = scopeClause(scope, 'e')
    cypher = f'''
    MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk)
    {where}
    RETURN e.canonicalId AS entityId, c.chunkId AS chunkId
    '''
    entityToChunks = defaultdict(list)
    for r in runCypher(cypher, **params):
        entityToChunks[r['entityId']].append(r['chunkId'])
    return entityToChunks


def fetchChunkText(chunkIds):
    cypher = '''
    UNWIND $ids AS cid
    MATCH (c:Chunk {chunkId: cid})
    RETURN c.chunkId AS chunkId, c.text AS text
    '''
    return {r['chunkId']: r['text'] for r in runCypher(cypher, ids=chunkIds)}


# ── seed vector ──────────────────────────────────────────────────

def buildSeedVector(seeds, idToIdx):
    seedMass = np.zeros(len(idToIdx), dtype=np.float64)
    for canonicalId, _, mass in seeds:
        if canonicalId in idToIdx:
            seedMass[idToIdx[canonicalId]] = mass
    total = seedMass.sum()
    if total > 0:
        seedMass /= total
    return seedMass


def applyNodeSpecificity(seedMass, idxToId, entityToChunks):
    for i in np.where(seedMass > 0)[0]:
        seedMass[i] /= len(entityToChunks[idxToId[i]])
    total = seedMass.sum()
    if total > 0:
        seedMass /= total
    return seedMass


# ── retrieval index ──────────────────────────────────────────────

class RetrievalIndex:
    def __init__(self, docName, entityAlignment=True, synonymWeight=1.0, coMentionEdges=False, tripleEdges=False, relatedEdges=True):
        self.docName = docName
        self.embEntityIds, _, self.embs = loadEntityEmbeddings(docName)
        self.adjacency, self.idToIdx, self.idxToId = loadEntityGraph(
            docName,
            includeSynonyms=entityAlignment,
            synonymWeight=synonymWeight,
            useCoMention=coMentionEdges,
            useTriples=tripleEdges,
            useRelated=relatedEdges,
        )
        self.entityToChunks = loadEntityToChunks(docName)
        self.printSummary(entityAlignment, synonymWeight, coMentionEdges, tripleEdges, relatedEdges)

    def printSummary(self, entityAlignment, synonymWeight, coMentionEdges, tripleEdges, relatedEdges):
        mentions = sum(len(chunks) for chunks in self.entityToChunks.values())
        edgeParts = []
        if relatedEdges:
            edgeParts.append('related')
        if coMentionEdges:
            edgeParts.append('co-mention')
        if tripleEdges:
            edgeParts.append('triples')
        if entityAlignment:
            edgeParts.append(f'synonym(w={synonymWeight})')
        print(
            f'[index] {self.docName} [{"+".join(edgeParts)}]: '
            f'{len(self.embEntityIds)} embedded, '
            f'{len(self.idxToId)} in graph, '
            f'{mentions} mentions'
        )

    def retrieve(self, query, topK=10, eps=1e-6, alpha=0.15, seedTopK=5, nodeSpecificity=False):
        seeds = seedFromQuery(query, self.embEntityIds, self.embs, topK=seedTopK)
        seedMass = buildSeedVector(seeds, self.idToIdx)
        if nodeSpecificity:
            seedMass = applyNodeSpecificity(seedMass, self.idxToId, self.entityToChunks)
        entityScores = ppr(self.adjacency, seedMass, alpha=alpha)
        chunks = self.projectToChunks(entityScores, topK, eps)
        return seeds, chunks

    def projectToChunks(self, entityScores, topK, eps):
        chunkScore = defaultdict(float)
        chunkContribs = defaultdict(list)
        for i in np.where(entityScores > eps)[0]:
            entityId = self.idxToId[i]
            score = float(entityScores[i])
            for chunkId in self.entityToChunks.get(entityId, ()):
                chunkScore[chunkId] += score
                chunkContribs[chunkId].append((entityId, score))

        ranked = sorted(chunkScore.items(), key=lambda kv: -kv[1])[:topK]
        texts = fetchChunkText([chunkId for chunkId, _ in ranked])
        return [
            {
                'chunkId': chunkId,
                'score': score,
                'text': texts.get(chunkId, ''),
                'contributors': sorted(chunkContribs[chunkId], key=lambda kv: -kv[1])[:3],
            }
            for chunkId, score in ranked
        ]
