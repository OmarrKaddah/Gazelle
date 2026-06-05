import _bootstrap  # noqa: F401  (puts src/ on sys.path, then chdir's to repo root)
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # restore cwd so 'datasets/' resolves
import numpy as np
import networkx as nx
from leiden import leidenHierarchy
from community import orientLevels, communityNodes, memberships, parentLinks, communityId
from retrieve import scopeClause
from validateLeiden import adjacencyOf, footballGraph

# Pure-function tests for the community-detection persistence (src/community.py).
# No Neo4j: we validate the payload builders against a real Leiden hierarchy
# (football) plus a hand-built non-nested hierarchy that exercises the plurality
# vote directly. The Neo4j write path is smoke-tested separately via runCommunities.


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'  [{status}] {name}{" — " + detail if detail else ""}')
    return condition


def footballHierarchy():
    G, _ = footballGraph()
    levels = orientLevels(leidenHierarchy(adjacencyOf(G), resolution=1.0))
    idxToId = [f'e{i}' for i in range(G.number_of_nodes())]
    return levels, idxToId, G.number_of_nodes()


def testRootIsCoarsest():
    print('test: level 0 is the root (fewest communities), levels grow finer')
    levels, _, _ = footballHierarchy()
    counts = [len(set(int(l) for l in lv)) for lv in levels]
    nonDecreasing = all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1))
    return check('community count non-decreasing from root', nonDecreasing, f'counts={counts}')


def testNodeCount():
    print('test: one community node per distinct label per level')
    levels, _, _ = footballHierarchy()
    nodes = communityNodes(levels, 'football')
    expected = sum(len(set(int(l) for l in lv)) for lv in levels)
    ids = {n['id'] for n in nodes}
    return check('node count == sum of per-level communities', len(nodes) == expected and len(ids) == expected,
                 f'nodes={len(nodes)} unique={len(ids)} expected={expected}')


def testMembershipsCoverEntities():
    print('test: every entity has exactly one membership per level, pointing at a real node')
    levels, idxToId, n = footballHierarchy()
    nodes = communityNodes(levels, 'football')
    nodeIds = {nd['id'] for nd in nodes}
    rows = memberships(levels, idxToId, 'football')
    perLevel = all(
        sum(1 for r in rows if r['level'] == lvl) == n for lvl in range(len(levels))
    )
    allResolve = all(r['communityId'] in nodeIds for r in rows)
    return check('n*levels rows, one per (entity,level), all resolve',
                 len(rows) == n * len(levels) and perLevel and allResolve,
                 f'rows={len(rows)} expected={n * len(levels)}')


def testParentsWellFormed():
    print('test: every non-root community has exactly one parent, one level up, that exists')
    levels, _, _ = footballHierarchy()
    nodes = communityNodes(levels, 'football')
    nodeIds = {n['id'] for n in nodes}
    links = parentLinks(levels, 'football')

    childIds = [l['childId'] for l in links]
    oneParentEach = len(childIds) == len(set(childIds))
    childCount = sum(len(set(int(l) for l in lv)) for lv in levels[1:])
    allExist = all(l['childId'] in nodeIds and l['parentId'] in nodeIds for l in links)
    parentOneUp = all(
        int(l['parentId'].rsplit('-L', 1)[1].split('-')[0]) ==
        int(l['childId'].rsplit('-L', 1)[1].split('-')[0]) - 1
        for l in links
    )
    return check('one parent per child, level-1, exists',
                 oneParentEach and len(links) == childCount and allExist and parentOneUp,
                 f'links={len(links)} childCommunities={childCount}')


def testPluralityVote():
    print('test: a child split across two parents is assigned the majority parent')
    # 2-level hierarchy, finest->root as leidenHierarchy returns it.
    # finest: entities {0,1,2} -> child community 0; {3} -> child community 1.
    # root:   {0,1} -> parent A(0); {2,3} -> parent B(1).
    # child 0 splits 2 entities to parent 0 and 1 entity to parent 1 -> majority 0.
    fine = np.array([0, 0, 0, 1])
    root = np.array([0, 0, 1, 1])
    levels = orientLevels([fine, root])   # -> [root, fine]
    links = parentLinks(levels, 'toy')
    byChild = {l['childId']: l['parentId'] for l in links}
    child0Parent = byChild[communityId('toy', 1, 0)]
    child1Parent = byChild[communityId('toy', 1, 1)]
    return check('child0->parentA(majority), child1->parentB',
                 child0Parent == communityId('toy', 0, 0) and child1Parent == communityId('toy', 0, 1),
                 f'child0->{child0Parent}, child1->{child1Parent}')


def testScopeClause():
    print('test: corpus-wide loader builds correct scope filters (None / docName / list)')
    none = scopeClause(None, 'a', 'b') == ('', {})
    single = scopeClause('musique', 'a', 'b') == (
        'WHERE a.docName = $scope AND b.docName = $scope', {'scope': 'musique'})
    lst = scopeClause(['d1', 'd2'], 'a', 'b') == (
        'WHERE a.docName IN $scope AND b.docName IN $scope', {'scope': ['d1', 'd2']})
    return check('None=unscoped, str=eq, list=IN', none and single and lst)


def main():
    tests = [
        testRootIsCoarsest,
        testNodeCount,
        testMembershipsCoverEntities,
        testParentsWellFormed,
        testPluralityVote,
        testScopeClause,
    ]
    results = []
    for t in tests:
        results.append(t())
        print()
    print(f'== {sum(results)}/{len(results)} passed ==')


if __name__ == '__main__':
    main()
