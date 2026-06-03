import _bootstrap
from loadGraph import buildIndex, buildAdjacency
from ppr import ppr, uniformSeed


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'  [{status}] {name}{" — " + detail if detail else ""}')
    return condition


def runTriangle(edges, alpha=0.15):
    idToIdx, idxToId = buildIndex(edges)
    adj = buildAdjacency(edges, idToIdx, undirected=True)
    seed = uniformSeed(len(idToIdx), [idToIdx['A']])
    scores = ppr(adj, seed, alpha=alpha)
    return {idxToId[i]: float(scores[i]) for i in range(len(idToIdx))}


def testSymmetricTriangle():
    print('test: symmetric triangle — B and C score equally when seeded at A')
    edges = [('A', 'B', 1.0), ('A', 'C', 1.0), ('B', 'C', 1.0)]
    scores = runTriangle(edges)
    return check(
        'scores[B] ≈ scores[C]',
        abs(scores['B'] - scores['C']) < 1e-6,
        f"B={scores['B']:.6f} C={scores['C']:.6f}",
    )


def testHeavierEdgeShiftsMass():
    print('test: A-C edge 10× heavier than A-B → C outranks B')
    edges = [('A', 'B', 1.0), ('A', 'C', 10.0), ('B', 'C', 1.0)]
    scores = runTriangle(edges)
    return check(
        'scores[C] > scores[B]',
        scores['C'] > scores['B'],
        f"B={scores['B']:.6f} C={scores['C']:.6f}",
    )


def testWeightRatioMonotonic():
    print('test: as A-C/A-B weight ratio grows, scores[C]/scores[B] grows monotonically')
    ratios = []
    for w in [1.0, 2.0, 5.0, 10.0, 100.0]:
        edges = [('A', 'B', 1.0), ('A', 'C', w), ('B', 'C', 1.0)]
        scores = runTriangle(edges)
        ratios.append((w, scores['C'] / scores['B']))
    monotonic = all(ratios[i][1] < ratios[i + 1][1] for i in range(len(ratios) - 1))
    detail = ' '.join(f'(w={w} C/B={r:.3f})' for w, r in ratios)
    return check('strictly increasing', monotonic, detail)


def testScaleInvariance():
    print('test: scaling all weights by a constant does not change PPR scores')
    base = [('A', 'B', 1.0), ('A', 'C', 10.0), ('B', 'C', 1.0)]
    scaled = [('A', 'B', 7.0), ('A', 'C', 70.0), ('B', 'C', 7.0)]
    baseScores = runTriangle(base)
    scaledScores = runTriangle(scaled)
    maxDiff = max(abs(baseScores[k] - scaledScores[k]) for k in baseScores)
    return check(
        'max abs diff < 1e-9',
        maxDiff < 1e-9,
        f'maxDiff={maxDiff:.2e}',
    )


def main():
    tests = [
        testSymmetricTriangle,
        testHeavierEdgeShiftsMass,
        testWeightRatioMonotonic,
        testScaleInvariance,
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
