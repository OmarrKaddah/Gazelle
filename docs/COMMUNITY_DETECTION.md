# Community Detection (Stage 4 of the global arm)

Community detection is the **foundation of the global arm** ([`docs/GLOBAL_PLAN.md`](GLOBAL_PLAN.md)): the global/sensemaking half of Gazelle answers corpus-wide questions ("what are the main themes/risks?") by summarising **communities of entities**. You can't summarise communities until you've found them — that's this stage.

It is **detection + persistence only** (the skeleton). Summaries (Stage 3) are written onto these nodes later, and they need entity/relationship *descriptions*, which only Route 2 produces.

Two pieces, in two places:

| File | Job |
|---|---|
| **`graphTraversal/leiden.py`** | **detect** the communities (from-scratch Leiden, hierarchical) |
| **`src/community.py`** | **persist** the hierarchy to Neo4j |
| `graphTraversal/runCommunities.py` | wire them end-to-end |
| `graphTraversal/testCommunity.py` | test the persistence builders |

## Why Leiden, and why entity-level

**Entity-level, not document-level.** Communities are detected over the **entity graph**, so a community = a *theme* that cuts across many documents (anti-money-laundering, capital adequacy…). Clustering documents directly would be too coarse (one regulation mixes many themes), would lose cross-document structure, and would leave nothing citable to summarise. The entity graph is the small *index*; chunks/docs are reached by projection (`MENTIONED_IN`). This mirrors the concept-vs-passage layering of the retrieval side ([`PROCESS.md`](PROCESS.md) §2.5).

**Leiden over Louvain.** Leiden (Traag, Waltman, van Eck 2019) adds a **refinement** pass that Louvain lacks, which *guarantees every detected community is internally connected*. Louvain can output a "community" that is secretly two disconnected blobs; Leiden cannot. For summarisation that matters — a disconnected community isn't a coherent theme.

## `leiden.py` — detection

Three passes per level, repeated:

1. **local move** — Louvain greedy: move each node to the neighbouring community that most increases **modularity**.
2. **refinement** — split each community into internally-*connected* sub-communities by re-running local move restricted to inside the community, from singletons. This is the Leiden-specific step that gives the connected guarantee.
3. **aggregation** — collapse each sub-community to one super-node and repeat on the smaller graph.

Each outer pass coarsens the partition, so **the sequence of partitions *is* the community hierarchy**: finest first, root (fewest communities) last.

| Function | Returns |
|---|---|
| `modularity(adj, labels, resolution)` | the modularity of a partition |
| `localMove` / `refine` / `aggregate` | the three passes |
| `leidenHierarchy(adj, resolution=1.0)` | **list of membership arrays, finest→root** (each projected back to original node indices) |
| `leiden(adj, resolution=1.0)` | flat convenience wrapper = the root level |

**Decisions:**
- **From scratch** (not `python-louvain`/`igraph`) — it's a thesis contribution and stays dependency-light.
- **Greedy refinement, not randomised** (the paper randomises). The connected guarantee comes from only ever merging *along an existing edge*, not from randomness — so we keep **determinism** (reproducible tests) and lose only a little partition-quality exploration. Documented inline.
- **Expose every level.** Earlier we threw away all but the root; `leidenHierarchy` keeps them, because the global arm answers at a chosen level and deeper levels stay available.

## `src/community.py` — persistence

`writeCommunities(hierarchy, idxToId, corpus)` turns a Leiden hierarchy into a Neo4j skeleton:

```
(:Community {id, level, corpus})
(:Entity)-[:IN_COMMUNITY {level}]->(:Community)
(:Community)-[:PARENT]->(:Community)        # child (finer) → parent (coarser)
```

Split into **pure builders** (unit-testable, no Neo4j) + **thin Neo4j writers** (matching `kgBuild.py` conventions):

| Pure builder | Does |
|---|---|
| `communityId(corpus, level, label)` | `f'{corpus}-L{level}-c{label}'` |
| `orientLevels(hierarchy)` | reverse finest→root so **index 0 = root** |
| `communityNodes(levels, corpus)` | one node dict per (level, label) |
| `memberships(levels, idxToId, corpus)` | one `IN_COMMUNITY` row per (entity, level) |
| `parentLinks(levels, corpus)` | child→parent links by **plurality vote** |

`writeCommunities` builds the payloads, then runs `setupConstraints → clearCommunities → writeCommunityNodes → writeMemberships → writeParents` in one session.

**Decisions:**
- **Scope key = `corpus`, not `docName`.** The global arm is corpus-wide; communities span all documents. (See the corpus-wide loader below.)
- **`level` 0 = root (coarsest).** `leidenHierarchy` returns finest→root, so `writeCommunities` reverses on write — matching GraphRAG's "C0 = root" convention, the level the global arm answers at.
- **`PARENT` by plurality vote, *not* containment.** Consecutive Leiden levels do **not** always strictly nest — verified empirically: on football the levels nest, but on email-Eu they do *not* (a finer community's entities split across two coarser ones). So each child is linked to the coarser community holding the **majority** of its members, which is always well-defined. Assuming containment would silently mis-link.
- **Clear-then-write per corpus.** `clearCommunities` wipes the corpus's communities first, so re-running with a different resolution leaves no stale nodes. This is intentional recompute, not defensive slop.
- **`MATCH` (not `MERGE`) on `:Entity`** — entities must already exist; isolated entities (no edges) appear in no community, which is correct.

## The corpus-wide loader

Community detection loads the entity graph via `loadEntityGraph(scope, …)` in `graphTraversal/retrieve.py`. Because the global arm is corpus-wide, the loader was generalised from single-`docName` to a **`scopeClause`** that accepts:

- `None` → the **whole DB** (every `:Entity`, corpus-wide),
- a `str` → one `docName` (back-compat with per-doc PPR retrieval),
- a `list` → a set of docNames belonging to one corpus.

`scopeClause(scope, *aliases)` returns a Cypher `WHERE` fragment (`''` when unscoped) + params, applied to every entity-edge and entity→chunk query. Verified on the `musique` graph: `'musique'`, `None`, and `['musique']` all load the identical graph (14,803 nodes, 158,544 edges).

> **Caveat for Route 2.** Today entity `canonicalId`s are `docName`-scoped, so the *same* real entity in two documents is two nodes — corpus-wide communities then only bridge documents via `SYNONYM` edges. For communities to *meaningfully* span documents, Route 2's `graphBuild` should canonicalize entities **corpus-wide** (see [`GLOBAL_PLAN.md`](GLOBAL_PLAN.md) and the two-route design).

## Validation data — and why

Leiden is validated on **labeled graphs where the right answer is known**, scored by **NMI** (normalised mutual information) and **ARI** against the ground-truth labels (`clusterMetrics.py`). This is graph-agnostic — no tuning per graph — and proves correctness independently of our own entity extraction.

| Data | Ground truth | Source |
|---|---|---|
| **Karate club** | the two real factions (instructor/officer) | `networkx` built-in (in-test) |
| **Football** | 12 college conferences | `datasets/football.gml` |
| **Email-Eu** | 42 departments | `datasets/email*.txt` |
| **Cora** | 7 paper subject classes | `datasets/cora/` |
| **LFR** | synthetic *planted* communities, swept over mixing μ | generated in-test |

Cora is the most relevant analogue — a real **document** graph (citations) where communities should recover document *topics*, exactly the global-arm goal, with no dependence on our extraction pipeline.

## Tests

| Test | Validates |
|---|---|
| **`testLeiden.py`** | our `modularity` matches `networkx`; two triangles → 2 communities; a ring of 4-cliques → 3 communities; karate modularity within 0.02 of `networkx` Louvain; karate NMI vs real factions > 0.5; and **every detected community is internally connected** (the Leiden guarantee). |
| **`testCommunity.py`** | the persistence builders on the real football hierarchy: root is coarsest; one node per (label, level); every entity has exactly one membership per level pointing at a real node; every non-root community has exactly one parent one level up; the **plurality vote** picks the majority parent on a hand-built non-nested case; and `scopeClause` builds the right filter for None/str/list. (6/6, pure — no Neo4j.) |
| **`validateLeiden.py`** | tier-1 benchmark run: NMI vs ground truth on LFR (swept μ), football, email — with `networkx` Louvain as the reference baseline — plus the **disconnected-community rate** comparison that exposes Leiden's structural advantage over Louvain directly. |
| **`cora.py`** | NMI on Cora + a **resolution sweep** (modularity over-segments at resolution 1.0; lowering it merges toward the 7 true classes). |
| **`plots.py`** | visual sanity figures (`figures/`): node fill = true label, green/red ring = correctly/incorrectly clustered, so every right/wrong call is readable at a glance. |

## Running it

```bash
# detection-only logic tests (no Neo4j)
python graphTraversal/testCommunity.py
python graphTraversal/testLeiden.py

# end-to-end on a real graph in Neo4j
python graphTraversal/runCommunities.py <scope> [resolution] [corpusName]
#   <scope> = 'musique' | 'doc1,doc2,...' | 'ALL'
```
