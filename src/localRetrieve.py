import threading
from collections import defaultdict

import numpy as np
from scipy.sparse import csr_matrix, diags
from neo4j import GraphDatabase

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, LOCAL_COMENTION_EDGES
from embedding import embedQuery

SYNONYM_WEIGHT = 1.0
ALPHA = 0.15

SEED_TOPK = 5
EPS = 1e-8


def driver():

    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def rowNormalize(adjacency):
    degrees = np.asarray(adjacency.sum(axis=1)).flatten()
    degrees[degrees == 0] = 1.0
    return diags(1.0 / degrees) @ adjacency


def ppr(adjacency, seedVector, alpha=ALPHA, nIter=100, tol=1e-9):
    Mt = rowNormalize(adjacency).T.tocsr()
    r = seedVector.astype(np.float64).copy()
    for _ in range(nIter):
        rNext = (1.0 - alpha) * (Mt @ r) + alpha * seedVector
        if np.linalg.norm(rNext - r, 1) < tol:
            return rNext
        r = rNext

    return r


class LocalIndex:
    """PPR over the RELATED + SYNONYM entity graph. Heavy state is loaded once at construction;
    per-query cost is query-embed + a sparse power iteration + chunk projection (~sub-second)."""

    def __init__(self, scope=None):
        where = '' if scope is None else 'AND e.docName IN $scope'
        params = {} if scope is None else {'scope': scope if isinstance(scope, list) else [scope]}
        with driver() as d, d.session() as s:
            ents = list(s.run(
                f'MATCH (e:Entity) WHERE e.embedding IS NOT NULL {where} '
                'RETURN e.canonicalId AS id, e.canonicalName AS name, e.docName AS doc, e.embedding AS emb',
                **params))
            related = list(s.run('MATCH (a:Entity)-[r:RELATED]->(b:Entity) RETURN a.canonicalId AS s, b.canonicalId AS t, r.weight AS w'))
            synonym = list(s.run('MATCH (a:Entity)-[r:SYNONYM]->(b:Entity) RETURN a.canonicalId AS s, b.canonicalId AS t'))
            comention = list(s.run('MATCH (a:Entity)-[r:COOCCURS_WITH]->(b:Entity) RETURN a.canonicalId AS s, b.canonicalId AS t, r.count AS w')) if LOCAL_COMENTION_EDGES else []
            ment = list(s.run('MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk) RETURN e.canonicalId AS e, c.chunkId AS c, c.docName AS doc'))

        self.idxToId = [r['id'] for r in ents]
        self.idxToName = [r['name'] for r in ents]
        self.idxToDoc = [r['doc'] for r in ents]
        self.idToIdx = {i: k for k, i in enumerate(self.idxToId)}
        embs = np.array([r['emb'] for r in ents], dtype=np.float32) if ents else np.zeros((0, 1), dtype=np.float32)
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.embs = embs / norms

        rows, cols, data = [], [], []

        # NOTE (franco): 3amalna .extend() badal el "+=" 3ashan da gowa function gowaneya (addEdge).
        # law katabna "rows += [i, j]" Python haye3teber rows variable local gowa addEdge, w hayrmy
        # UnboundLocalError 3ashan el "+=" beye2ra rows el-awel w e7na lessa msh 3arrafnaha gowa el function.
        # enama .extend() bey-modify nafs el list (in place) men gher ma ye-rebind el esm, fa beyzawwed
        # 3al rows el-barra (el f scope beta3 __init__) 3adi men gher mashakel.
        def addEdge(a, b, w):
            i, j = self.idToIdx.get(a), self.idToIdx.get(b)
            if i is None or j is None:
                return
            rows.extend((i, j))
            cols.extend((j, i))
            data.extend((w, w))

        for r in related:

            addEdge(r['s'], r['t'], float(r['w'] or 1.0))
        for r in synonym:
            addEdge(r['s'], r['t'], SYNONYM_WEIGHT)
        for r in comention:
            addEdge(r['s'], r['t'], float(r['w'] or 1.0))
        n = len(self.idxToId)
        self.adjacency = csr_matrix((data, (rows, cols)), shape=(n, n))

        self.entityChunks = defaultdict(list)
        self.chunkDoc = {}
        for r in ment:
            self.entityChunks[r['e']].append(r['c'])
            self.chunkDoc[r['c']] = r['doc']
        print(f'[localRetrieve] index built: {n} entities, {self.adjacency.nnz // 2} edges, {len(self.chunkDoc)} chunks', flush=True)

    def seedVector(self, query, allowedMask, topK=SEED_TOPK):
        q = np.array(embedQuery(query), dtype=np.float32)
        q = q / np.linalg.norm(q)
        sims = np.where(allowedMask, self.embs @ q, -np.inf)
        topK = min(topK, int(allowedMask.sum()))
        seedVec = np.zeros(len(self.idxToId))
        if topK <= 0:
            return [], seedVec
        topIdx = np.argpartition(-sims, topK - 1)[:topK]
        topIdx = topIdx[np.argsort(-sims[topIdx])]
        topSims = np.maximum(sims[topIdx], 0)
        if topSims.sum() > 0:
            for i, sm in zip(topIdx, topSims):
                seedVec[i] = sm
            seedVec /= seedVec.sum()
        seeds = [(self.idxToId[i], self.idxToName[i], float(sims[i])) for i in topIdx if sims[i] > 0]
        return seeds, seedVec

    def retrieve(self, query, k=5, allowedDocs=None):
        allowed = None if allowedDocs is None else set(allowedDocs)
        allowedMask = (np.ones(len(self.idxToId), dtype=bool) if allowed is None
                       else np.array([d in allowed for d in self.idxToDoc], dtype=bool))
        seeds, seedVec = self.seedVector(query, allowedMask)
        if seedVec.sum() == 0:
            return {'seeds': [], 'chunks': [], 'pathEdges': []}

        scores = ppr(self.adjacency, seedVec)
        chunkScore = defaultdict(float)
        chunkContribs = defaultdict(list)

        for i in np.where(scores > EPS)[0]:
            eid = self.idxToId[i]

            sc = float(scores[i])
            for cid in self.entityChunks.get(eid, ()):
                if allowed is not None and self.chunkDoc.get(cid) not in allowed:
                    continue
                chunkScore[cid] += sc
                chunkContribs[cid].append((eid, self.idxToName[i], sc))

        ranked = sorted(chunkScore.items(), key=lambda kv: -kv[1])[:k]
        meta = self.chunkMeta([c for c, _ in ranked])
        involved = {s[0] for s in seeds}
        chunks = []
        for cid, score in ranked:

            contribs = sorted(chunkContribs[cid], key=lambda x: -x[2])[:3]
            involved.update(e for e, _, _ in contribs)
            m = meta.get(cid, {})
            chunks.append({
                'chunkId': cid, 'score': score, 'text': m.get('text', ''),
                'docName': m.get('docName', ''), 'sectionPath': m.get('sectionPath'), 'pages': m.get('pages'),
                'contributors': [{'id': e, 'name': nm, 'score': sc} for e, nm, sc in contribs],
            })
        return {
            'seeds': [{'id': i, 'name': n, 'score': s} for i, n, s in seeds],
            'chunks': chunks,
            'pathEdges': self.pathEdges(list(involved)),
        }

    def chunkMeta(self, chunkIds):
        if not chunkIds:
            return {}
        
        with driver() as d, d.session() as s:
            rows = list(s.run(
                'UNWIND $ids AS cid MATCH (c:Chunk {chunkId: cid}) '
                'RETURN c.chunkId AS chunkId, c.text AS text, c.docName AS docName, c.sectionPath AS sectionPath, c.pages AS pages',
                ids=chunkIds))
        return {r['chunkId']: dict(r) for r in rows}

    def pathEdges(self, entityIds):

        if not entityIds:
            return []
        with driver() as d, d.session() as s:
            rows = list(s.run(
                'MATCH (a:Entity)-[r:RELATED]->(b:Entity) WHERE a.canonicalId IN $ids AND b.canonicalId IN $ids '
                'RETURN a.canonicalId AS src, a.canonicalName AS srcName, b.canonicalId AS dst, b.canonicalName AS dstName, r.predicate AS predicate',
                ids=entityIds))
        return [dict(r) for r in rows]


_index = None
_lock = threading.Lock()


def getLocalIndex():
    global _index
    if _index is None:

        with _lock:
            if _index is None:
                _index = LocalIndex()
    return _index


def reloadLocalIndex():         
    global _index
    with _lock:
        _index = LocalIndex()
    return _index
