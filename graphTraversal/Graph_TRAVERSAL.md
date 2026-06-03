# `graphTraversal/` — PPR retrieval subsystem

A **self-contained subsystem** for the retrieval upgrade: it replaces the old fixed-depth k-hop traversal in `src/retriever.py` with **Personalized PageRank (PPR) over the entity graph**, following HippoRAG. It is benchmarked on **MuSiQue** (gold supporting paragraphs → recall@K), not the CBE corpus.

This file is the **file-by-file map**. For the *why* behind the retrieval design and the full versioned evaluation log (v0–v7b), read [`docs/PROCESS.md`](../docs/PROCESS.md) — it is the authority on rationale. Community detection (`leiden.py` + `src/community.py`) has its own companion: [`docs/COMMUNITY_DETECTION.md`](../docs/COMMUNITY_DETECTION.md).

## Bootstrap convention

Every script here starts with `import _bootstrap`. [`_bootstrap.py`](_bootstrap.py) inserts `src/` onto `sys.path` and `chdir`s to the repo root, so these modules import freely from `src/` (`config`, `embedding`, `llmTriples`, …) and resolve repo-relative paths. The pure-algorithm + plotting scripts that only need local imports (`leiden`, `clusterMetrics`, `validateLeiden`, `cora`, `plots`, `testLeiden`, `testPpr`, `testWeightedPpr`) skip the bootstrap and are run from inside this directory.

## The pipeline at a glance

```
query ──embed──▶ seeder.py ──top-K entities──▶ seed mass vector
                                                     │
   Neo4j entity graph ──loadGraph/retrieve──▶ CSR adjacency
                                                     │
                                          ppr.py (power iteration)
                                                     │
                              entity scores ──MENTIONED_IN──▶ chunk scores ──▶ top-K chunks
```

## Files

### Core retrieval

| File | Role |
|---|---|
| **`ppr.py`** | Personalized PageRank. `ppr(adj, seedVector, alpha)` row-normalises the adjacency and iterates `r ← (1-α)·Mᵀr + α·s` to convergence (L1 tol `1e-9`, ≤100 iters). `rowNormalize` guards zero-degree rows; `uniformSeed` builds a flat seed over given indices (used by tests). PPR is global and mass-conserving — no fixed hop depth, `O(N)` storage. |
| **`seeder.py`** | Query → seed entities. `loadEntityEmbeddings(scope)` pulls L2-normalised `:Entity.embedding` vectors from Neo4j; `seedFromQuery(query, …, topK)` embeds the query (BGE-M3 via `embedQuery`), cosine-ranks all entities, takes top-K, clamps negatives to 0, and **linear-normalises** the K similarities to a seed mass that sums to 1. |
| **`loadGraph.py`** | Generic Cypher → sparse adjacency. `fetchEdges` runs an edge query (`src,dst[,weight]` rows); `buildIndex` assigns contiguous integer indices to canonicalIds (sorted, deterministic); `buildAdjacency` builds a `scipy` CSR matrix, **symmetrised when `undirected=True`** (each stored edge is added in both directions). `loadAdjacency` chains all three. |
| **`retrieve.py`** | The production retrieval index. `RetrievalIndex` loads all heavy state **once** (entity embeddings, entity-entity CSR adjacency, entity→chunk map) so per-query cost is ~300 ms. Edge layers toggle via flags (`coMentionEdges`, `tripleEdges`, `entityAlignment`). `retrieve()` = seed → seed vector → PPR → project to chunks. **Also home to the corpus-wide loader** (`scopeClause` + the `fetch*Edges`/`loadEntityGraph`/`loadEntityToChunks` family) — see [COMMUNITY_DETECTION.md](../docs/COMMUNITY_DETECTION.md). |
| **`synonyms.py`** | Entity alignment. `findSynonymPairs(scope, threshold)` blocks entity embeddings in chunks, keeps pairs with cosine ≥ threshold **AND same `type` AND a token-subset relation** (one name's tokens ⊆ the other's) — the subset filter kills structural false positives like "1968 Democratic Convention" vs "1968 Republican Convention". `writeSynonymEdges` persists them as `(:Entity)-[:SYNONYM {cosine}]->(:Entity)`. |

### Baseline

| File | Role |
|---|---|
| **`khop.py`** | The **old k-hop algorithm**, reimplemented standalone for the apples-to-apples v0 comparison on the *same* MuSiQue KG. Cosine-seeds K=8 entities, enumerates paths up to depth 3 (cap 300), scores each path by mean entity-query cosine, and projects path scores onto chunks (max wins). It does **not** reuse `src/retriever.py` because that filters by the CBE `RELATIONSHIP_DESCRIPTIONS` ontology and projects via typed-edge `chunkIds` — neither of which exists on MuSiQue edges (the module docstring explains this). `KhopIndex` mirrors `RetrievalIndex`'s interface so the eval harness can swap them. |

### Community detection

| File | Role |
|---|---|
| **`leiden.py`** | From-scratch Leiden community detection. `leidenHierarchy(adj)` returns the partition at every level (finest→root); `leiden()` wraps the root level. Detailed in [COMMUNITY_DETECTION.md](../docs/COMMUNITY_DETECTION.md). |

## The loaders — what reads what

There are **four** distinct graph-loading paths, each scoped to a purpose. This separation is deliberate: PPR walks **only** the concept layer (entity-entity edges); chunks are reached separately by projection.

| Loader | In | Reads | Used for |
|---|---|---|---|
| `loadEntityGraph(scope, …)` | `retrieve.py` | `COOCCURS_WITH` / `TRIPLE` / `SYNONYM` entity-entity edges → CSR | the graph PPR (and Leiden) walks |
| `loadEntityToChunks(scope)` | `retrieve.py` | `(:Entity)-[:MENTIONED_IN]->(:Chunk)` | **projection only** — maps entity scores onto chunks; PPR never walks these |
| `loadEntityEmbeddings(scope)` | `seeder.py` | `:Entity.embedding` | query→seed cosine ranking |
| `extractPaths` etc. | `khop.py` | path traversal over the same edges | the baseline only |

**`scope`** is `None` (whole corpus), a single `docName`, or a list of docNames — built by `scopeClause` (see [COMMUNITY_DETECTION.md](../docs/COMMUNITY_DETECTION.md) for why corpus-wide scoping exists). The `MENTIONED_IN` separation is enforced **in the query**, not the graph topology: the same Neo4j graph serves both the concept layer and the passage layer.

## Benchmark & validation data — and why

Two completely different kinds of data, for two different purposes:

- **MuSiQue (`musique/`) — the *retrieval* benchmark.** A multi-hop QA dataset with **gold supporting paragraphs**, so we can score **recall@K** (the fraction of gold chunks retrieved). Chosen because (a) it has the gold labels k-hop/PPR need to be measured against, and (b) it's what HippoRAG reports on, giving a comparable baseline. We use the first 200 dev examples (all 2-hop). `musique/eval.py` writes one versioned JSON per run to `eval_results/v{N}_{label}.json` with full config + per-question gold/retrieved chunkIds — the reproducible record behind PROCESS.md's version log.
- **`datasets/` (Cora, football, email) — *community-detection* ground truth.** Labeled graphs (paper topics / sports conferences / email departments) used to validate `leiden.py` against known communities via NMI. They have nothing to do with retrieval — they exist purely to prove the clustering algorithm is correct on graphs where the right answer is known. Karate-club and synthetic LFR graphs are generated in-test. (Why a separate doc owns these: [COMMUNITY_DETECTION.md](../docs/COMMUNITY_DETECTION.md).)

## Tests

Run each directly (`python <file>.py`). They print `PASS/FAIL` per assertion.

| Test | Validates | Why it matters |
|---|---|---|
| **`testPpr.py`** | PPR on the karate club: mass sums to 1; high-α ranks the seed first; mass concentrates in the seed's faction; top-5 ⊆ seed faction; switching the seed flips the dominant faction; **uniform seed reproduces `networkx.pagerank`**. | proves the PPR implementation is a correct Personalized PageRank that degenerates to classical PageRank. |
| **`testLoadGraph.py`** | Writes a tiny `:PprTest` fixture to Neo4j, then checks id↔index round-trips, node count, directed vs undirected non-zero counts, symmetry (`A == Aᵀ`), and that each row's non-zeros equal the node's true neighbours. Cleans up the fixture. | proves Cypher→CSR conversion is faithful (no dropped/duplicated/mis-indexed edges). |
| **`testWeightedPpr.py`** | On a weighted triangle: symmetric weights give equal scores; a 10× heavier edge shifts mass to that neighbour; the score ratio grows **monotonically** with the weight ratio; and PPR is **scale-invariant** (multiplying all weights by a constant changes nothing, because of row-normalisation). | proves edge weights behave as intended — and explains the v5 result that synonym-edge *magnitude* is irrelevant (PROCESS.md §5). |
| **`testLeiden.py`** / **`testCommunity.py`** | Community detection + persistence. | see [COMMUNITY_DETECTION.md](../docs/COMMUNITY_DETECTION.md). |

## Runners

`runRealPpr.py` (PPR on the real KG), `runSeed.py` (inspect seeds for a query), `runProbe.py` (eyeball retrieval on probe queries), `runRetrieve.py` (`RetrievalIndex` end-to-end), `runSynonyms.py` (write `SYNONYM` edges), `runCommunities.py` (Stage 4 — see companion doc).

## Key decisions (summary — full reasoning in PROCESS.md)

- **PPR over k-hop.** Measured on the *same* KG, PPR wins broad-K recall (+8.8 recall@10) and is 11.5× faster, while k-hop wins top-K precision. We target an LLM reader consuming 5–10 chunks, so PPR's profile wins (PROCESS.md §2.2, v0).
- **α = 0.5** (not the classical 0.15) — big top-1/top-2 gains; matches HippoRAG (v2).
- **Linear-normalised cosine seeds**, not one-hot (brittle) or softmax (extra hyperparameter) (§3.5).
- **Co-mention + triples + synonyms together** — co-mention gives density (recall safety net), triples add high-signal edges, synonyms bridge duplicate entities; triples *alone* regress (too sparse) (v4/v7/v7b).
- **Node specificity rejected** — redundant with a cosine seeder, double-counts and hurts (v3).
- **Concept/passage separation by query discipline** — one Neo4j graph, PPR sees only entity-entity edges; chunks reached via `MENTIONED_IN` projection.
- **`RetrievalIndex` loads once** — heavy state cached at construction so per-query cost is ~300 ms (whole 200-question eval < 2 min).
