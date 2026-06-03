import numpy as np
from collections import Counter, defaultdict
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Stage 4 — persist a Leiden community hierarchy to Neo4j as the skeleton the
# global arm summarises later. leidenHierarchy returns partitions finest->root;
# we store them with level 0 = root (coarsest), matching GraphRAG's C0 convention
# (the level the global arm answers at). PARENT links are assigned by plurality
# vote, not containment: consecutive Leiden levels do not always strictly nest, so
# a finer community's entities can split across two coarser communities.


# ── pure builders ────────────────────────────────────────────────

def communityId(corpus, level, label):
    return f'{corpus}-L{level}-c{label}'


def orientLevels(hierarchy):
    # hierarchy is finest->root; reverse so index 0 is the root level.
    return [np.asarray(level) for level in reversed(hierarchy)]


def communityNodes(levels, corpus):
    nodes = []
    for level, labels in enumerate(levels):
        for label in sorted(set(int(l) for l in labels)):
            nodes.append({'id': communityId(corpus, level, label), 'level': level, 'corpus': corpus})
    return nodes


def memberships(levels, idxToId, corpus):
    rows = []
    for level, labels in enumerate(levels):
        for idx, label in enumerate(labels):
            rows.append({
                'entityId': idxToId[idx],
                'communityId': communityId(corpus, level, int(label)),
                'level': level,
            })
    return rows


def parentLinks(levels, corpus):
    links = []
    for level in range(len(levels) - 1):
        parent = levels[level]        # coarser
        child = levels[level + 1]     # finer
        votes = defaultdict(Counter)
        for idx in range(len(child)):
            votes[int(child[idx])][int(parent[idx])] += 1
        for childLabel, counter in votes.items():
            parentLabel = counter.most_common(1)[0][0]
            links.append({
                'childId': communityId(corpus, level + 1, childLabel),
                'parentId': communityId(corpus, level, parentLabel),
            })
    return links


# ── Neo4j writers ────────────────────────────────────────────────

def setupConstraints(tx):
    tx.run('CREATE CONSTRAINT IF NOT EXISTS FOR (c:Community) REQUIRE c.id IS UNIQUE')


def clearCommunities(tx, corpus):
    tx.run('MATCH (c:Community {corpus: $corpus}) DETACH DELETE c', corpus=corpus)


def writeCommunityNodes(tx, nodes):
    tx.run(
        '''
        UNWIND $nodes AS n
        MERGE (c:Community {id: n.id})
        SET c.level = n.level, c.corpus = n.corpus
        ''',
        nodes=nodes,
    )


def writeMemberships(tx, rows):
    tx.run(
        '''
        UNWIND $rows AS m
        MATCH (e:Entity {canonicalId: m.entityId})
        MATCH (c:Community {id: m.communityId})
        MERGE (e)-[r:IN_COMMUNITY]->(c)
        SET r.level = m.level
        ''',
        rows=rows,
    )


def writeParents(tx, links):
    tx.run(
        '''
        UNWIND $links AS l
        MATCH (child:Community {id: l.childId})
        MATCH (parent:Community {id: l.parentId})
        MERGE (child)-[:PARENT]->(parent)
        ''',
        links=links,
    )


# ── orchestrator ─────────────────────────────────────────────────

def writeCommunities(hierarchy, idxToId, corpus):
    levels = orientLevels(hierarchy)
    nodes = communityNodes(levels, corpus)
    members = memberships(levels, idxToId, corpus)
    links = parentLinks(levels, corpus)
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            session.execute_write(setupConstraints)
            session.execute_write(clearCommunities, corpus)
            session.execute_write(writeCommunityNodes, nodes)
            session.execute_write(writeMemberships, members)
            session.execute_write(writeParents, links)
    print(
        f'[community] {corpus}: {len(levels)} levels, {len(nodes)} communities, '
        f'{len(members)} memberships, {len(links)} parent links'
    )
    return nodes, members, links
