import numpy as np
import networkx as nx
from scipy.sparse import csr_matrix
from ppr import ppr, uniformSeed


INSTRUCTOR_FACTION = {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 16, 17, 19, 21}
OFFICER_FACTION = {9, 14, 15, 18, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33}


def karateAdjacency():
    G = nx.karate_club_graph()
    A = nx.to_scipy_sparse_array(G, format='csr', dtype=np.float64)
    return A, G.number_of_nodes()


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'  [{status}] {name}{" — " + detail if detail else ""}')
    return condition


def testSumsToOne():
    print('test: PPR distribution sums to ~1.0')
    A, n = karateAdjacency()
    seed = uniformSeed(n, [0])
    scores = ppr(A, seed, alpha=0.15)
    s = float(scores.sum())
    return check('L1 mass preserved', abs(s - 1.0) < 1e-6, f'sum={s:.6f}')


def testSeedIsTopRanked():
    print('test: seed node ranks first when alpha is high')
    A, n = karateAdjacency()
    seed = uniformSeed(n, [0])
    scores = ppr(A, seed, alpha=0.5)
    top = int(np.argmax(scores))
    return check('argmax == seed', top == 0, f'top={top}')


def testFactionLeak():
    print('test: PPR from instructor concentrates mass in instructor faction')
    A, n = karateAdjacency()
    seed = uniformSeed(n, [0])
    scores = ppr(A, seed, alpha=0.15)
    inFaction = float(scores[list(INSTRUCTOR_FACTION)].sum())
    outFaction = float(scores[list(OFFICER_FACTION)].sum())
    return check(
        'instructor faction mass > officer faction mass',
        inFaction > outFaction,
        f'in={inFaction:.4f} out={outFaction:.4f}',
    )


def testTopNeighborsInFaction():
    print('test: top-5 ranked nodes all belong to instructor faction')
    A, n = karateAdjacency()
    seed = uniformSeed(n, [0])
    scores = ppr(A, seed, alpha=0.15)
    top5 = np.argsort(-scores)[:5].tolist()
    inFaction = all(int(i) in INSTRUCTOR_FACTION for i in top5)
    return check('top5 ⊆ instructor faction', inFaction, f'top5={top5}')


def testSwitchSeed():
    print('test: seeding officer node flips dominant faction')
    A, n = karateAdjacency()
    seed = uniformSeed(n, [33])
    scores = ppr(A, seed, alpha=0.15)
    inInstructor = float(scores[list(INSTRUCTOR_FACTION)].sum())
    inOfficer = float(scores[list(OFFICER_FACTION)].sum())
    return check(
        'officer faction mass > instructor faction mass',
        inOfficer > inInstructor,
        f'officer={inOfficer:.4f} instructor={inInstructor:.4f}',
    )


def testRegressesToPageRank():
    print('test: with uniform seed, PPR equals classical PageRank')
    A, n = karateAdjacency()
    uniform = np.ones(n) / n
    pprScores = ppr(A, uniform, alpha=0.15, nIter=500)
    nxScores = nx.pagerank(nx.karate_club_graph(), alpha=0.85)
    nxVec = np.array([nxScores[i] for i in range(n)])
    diff = float(np.linalg.norm(pprScores - nxVec, 1))
    return check('matches networkx.pagerank', diff < 1e-3, f'L1 diff={diff:.6f}')


def main():
    tests = [
        testSumsToOne,
        testSeedIsTopRanked,
        testFactionLeak,
        testTopNeighborsInFaction,
        testSwitchSeed,
        testRegressesToPageRank,
    ]
    results = []
    for t in tests:
        results.append(t())
        print()
    passed = sum(results)
    total = len(results)
    print(f'== {passed}/{total} passed ==')


if __name__ == '__main__':
    main()
