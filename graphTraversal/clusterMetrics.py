from math import log, comb
from collections import Counter

# Comparing a detected partition against a ground-truth one. Both are flat
# label lists over the same nodes (label values are arbitrary). NMI is the
# standard community-detection score; ARI is the chance-corrected complement.


def mutualInfo(a, b):
    n = len(a)
    joint = Counter(zip(a, b))
    ca, cb = Counter(a), Counter(b)
    return sum((nxy / n) * log(n * nxy / (ca[x] * cb[y])) for (x, y), nxy in joint.items())


def entropy(a):
    n = len(a)
    return -sum((c / n) * log(c / n) for c in Counter(a).values())


def nmi(a, b):
    denom = entropy(a) + entropy(b)
    return 1.0 if denom == 0 else 2 * mutualInfo(a, b) / denom


def ari(a, b):
    n = len(a)
    joint = Counter(zip(a, b))
    ca, cb = Counter(a), Counter(b)
    index = sum(comb(v, 2) for v in joint.values())
    sa = sum(comb(v, 2) for v in ca.values())
    sb = sum(comb(v, 2) for v in cb.values())
    expected = sa * sb / comb(n, 2)
    maxIndex = (sa + sb) / 2
    return 1.0 if maxIndex == expected else (index - expected) / (maxIndex - expected)
