import numpy as np
from scipy.sparse import csr_matrix, diags


def rowNormalize(adjacency):
    degrees = np.asarray(adjacency.sum(axis=1)).flatten()
    degrees[degrees == 0] = 1.0
    invDeg = diags(1.0 / degrees)
    return invDeg @ adjacency


def ppr(adjacency, seedVector, alpha=0.15, nIter=100, tol=1e-9):
    M = rowNormalize(adjacency)
    Mt = M.T.tocsr()
    r = seedVector.astype(np.float64).copy()
    for _ in range(nIter):
        rNext = (1.0 - alpha) * (Mt @ r) + alpha * seedVector
        if np.linalg.norm(rNext - r, 1) < tol:
            return rNext
        r = rNext
    return r


def uniformSeed(n, seedIndices):
    v = np.zeros(n, dtype=np.float64)
    for i in seedIndices:
        v[i] = 1.0
    v /= v.sum()
    return v
