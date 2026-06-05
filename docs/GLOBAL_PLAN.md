# Plan — Global Query-Focused Summarization (GraphRAG arm)

This document plans the **global** half of Gazelle: answering corpus-wide sensemaking
questions ("what are the main themes / trends / risks?") via hierarchical community
summaries, following GraphRAG (Edge et al., 2024, *From Local to Global*).

It complements the existing **local** half (PPR / HippoRAG retrieval, see
`docs/PROCESS.md`), which answers specific fact questions by walking the entity
graph to specific chunks.

```
                 ┌── local query  → PPR over entity graph → chunks → answer   (built)
   query → router┤
                 └── global query → map-reduce over C0 community summaries → answer  (this plan)
```

## Locked decisions

- **Global answer = GraphRAG map-reduce, not retrieval.** Every community summary at
  the chosen level independently produces a partial answer + a 0–100 helpfulness
  score; the top-scored partials are reduced into the final answer. This is what
  makes the answer *global* (the whole corpus is considered, nothing is retrieved
  away).
- **Level = C0 (root).** The paper shows root-level summaries are ~as good as deeper
  levels at 9–43× fewer tokens. Deeper levels stay available via the hierarchy but
  C0 is the default answering level.
- **Provenance is mandatory.** Every summary carries source record IDs
  (`[Data: Entities (5,7); Relationships (23)]`) so answers cite back to evidence.
  This is Gazelle's hallucination-resistance requirement, not an optional extra.
- **Same Leiden we built and validated.** Graph-agnostic, no per-graph tuning.

## Conventions (apply to every module here)

camelCase functions · one function does one thing · no inline imports · no
defensive guards unless a real failure mode demands it (LLM JSON parse, HTTP
limits are the justified ones) · let it fail rather than paper over it.

---

## The pipeline, back to front

Designed back-to-front (from the answer the user sees down to extraction). Each
stage lists its decision, its module, and the one-thing functions in it.

### Stage 1 — Router: global vs local

**Decision.** Send the query to the global arm (this plan) or the local arm (PPR).
There is **no router in the GraphRAG paper or its core implementation** — they ship
local/global as separate methods the *caller* picks. So this is Gazelle's own
design. v1 = lightweight one-shot LLM classifier (self-contained, no dependency on
the index, so it can be built first); improve later. DRIFT-style blending (start
global, drill into local) is a possible future direction, not committed.

`src/router.py`
- `routeQuery(query, backend)` → `'global' | 'local'`. One LLM judgment.

### Stage 2 — Global search: summaries → answer (map-reduce)

**Decision (locked).** Map-reduce over all C0 summaries.

`src/globalSearch.py`
- `mapCommunity(query, summary, backend)` → `(partialAnswer, score)`. One LLM call;
  score 0 partials are dropped.
- `reduceAnswers(query, partials, backend)` → `globalAnswer`. Combine top-scored
  partials, preserving data references.
- `globalSearch(query, level=0, backend)` → orchestrates map over the level's
  community summaries, then reduce. Map calls are independent (parallelizable).

### Stage 3 — Community → summary report (with provenance, bottom-up)

**Decision.** Each community becomes a structured report (title, summary, rating,
findings) grounded in its entities/relationships with record-ID citations. Leaf
reports are built from elements; parent reports roll up child reports.

`src/communitySummary.py`
- `communityElements(communityId)` → entities + relationships (+ claims) of a
  community, ranked by combined node degree (prominence), packed to a token budget.
- `summarizeLeaf(elements, backend)` → report dict `{title, summary, rating, findings[]}`
  with `[Data: ...]` references.
- `summarizeParent(childReports, elements, backend)` → report, substituting child
  summaries for elements when over budget (the paper's roll-up rule).
- `summarizeHierarchy(hierarchy, backend)` → walks levels leaf→root, writing each
  community's report.

Storage: report fields on the `(:Community)` node (Stage 4).

### Stage 4 — KG → hierarchical communities  ✅ built

**Decision.** Expose Leiden's levels (we currently throw them away). Persist the
community tree.

`graphTraversal/leiden.py` ✅
- `leidenHierarchy(adj, resolution=1.0)` → list of membership arrays, finest→root.
  Each outer pass coarsens the partition, so the sequence *is* the hierarchy.
  `leiden()` is the flat convenience wrapper = last (root) level.

`src/community.py` ✅
- `writeCommunities(hierarchy, idxToId, corpus)` → `(:Community {id, level, corpus})`
  nodes, `(:Entity)-[:IN_COMMUNITY {level}]->(:Community)`, and
  `(:Community)-[:PARENT]->(:Community)` links between adjacent levels.
- **Scope = `corpus`, not `docName`.** The global arm is corpus-wide, so communities
  span all documents; the scope key on `:Community` is a corpus id. The **corpus-wide
  edge loader is built**: `loadEntityGraph(scope)` takes a single docName (back-compat),
  a list of docNames (one corpus over many docs), or `None` (whole DB); driven by
  `runCommunities.py <scope|ALL>`. Verified equivalent to the per-doc load on MuSiQue
  (`scopeClause` regression-tested in `testCommunity.py`).
- **`level` 0 = root** (coarsest). `leidenHierarchy` returns finest→root, so
  `writeCommunities` reverses on write to match the C0-answering convention above.
- **`PARENT` by plurality vote, not containment.** Consecutive Leiden levels do not
  always strictly nest (verified on email-Eu): a finer community's entities can split
  across two coarser ones, so each child is linked to the coarser community holding
  most of its members.
- Runner: `graphTraversal/runCommunities.py <scope> [resolution]`. Pure builders
  tested in `graphTraversal/testCommunity.py` (football hierarchy + plurality vote).

### Stage 5 — Extraction instances → KG

**Decision.** Aggregate per-chunk extractions into a graph: one node per unique
entity (descriptions aggregated), one edge per unique pair (**weight = number of
times the relationship was extracted**, descriptions aggregated).

`src/graphBuild.py`
- `mergeEntities(instances)` → `{name: {type, descriptions[], chunkIds[]}}`.
- `mergeRelationships(instances)` → `{(src,dst): {weight, descriptions[], chunkIds[]}}`.
- `writeGraph(entities, relationships, docName)` → Neo4j `(:Entity {canonicalId,
  name, type, description, docName})` and `(:Entity)-[:RELATED {weight, description}]->(:Entity)`.

> **Note (2026-06-03):** Stages 5+6 together ARE **Route 2** of the project's final
> two-route architecture (the deployed LLM graph). Route 1 (GLiNER + co-mention) is the
> retained baseline; the bare-triples route (v7) is retired. See `CLAUDE.md` → "Graph
> construction — TWO routes" and `docs/PROCESS.md` §9.

### Stage 6 — Chunks → entities & relationships **with descriptions**

**Decision.** This is the real change from the current pipeline. GraphRAG summaries
consume *descriptions*; GLiNER spans + triple predicates don't have them. So the
global arm extracts entities **and** relationships **and** their descriptions in one
LLM pass (paper Appendix E.1 prompt). Reuse the multi-backend pattern from
`src/llmTriples.py`.

`src/graphExtract.py`
- `EXTRACT_PROMPT` — the delimited-tuple prompt (entity name/type/description;
  relationship source/target/description/strength).
- `extractElements(chunkText, entityTypes, backend)` → raw delimited string.
- `parseElements(raw)` → `{entities: [(name,type,desc)], relationships: [(src,dst,desc,strength)]}`.

`runners/runGraphExtract.py` — batch over a docName's chunks, resume-safe (same
pattern as `runLlmTriples.py`).

### Stage 0 — Evaluation (no gold → LLM-as-judge)

**Decision.** Global sensemaking has no gold answers. Use the paper's protocol:
generate global questions, then head-to-head LLM judging vs the local/vector
baseline on comprehensiveness, diversity, empowerment (+ directness as control).

`src/sensemakingEval.py`
- `generateQuestions(corpusDescription, K, N, M, backend)` → `K*N*M` global
  questions (paper Algorithm 1: personas → tasks → questions).
- `judge(question, answerA, answerB, criterion, backend)` → `winner ∈ {1,2,0}` + reason.
- `compareSystems(questions, systemA, systemB, backend)` → win-rate table over criteria.

---

## Storage summary (Neo4j, docName-scoped, consistent with existing graph)

- `(:Entity {canonicalId, name, type, description, docName})`
- `(:Entity)-[:RELATED {weight, description}]->(:Entity)` — the global-arm graph.
- `(:Community {id, level, corpus, title, summary, rating, findings})` — `level` 0 = root;
  `title/summary/rating/findings` written later by Stage 3 onto the Stage-4 skeleton.
- `(:Entity)-[:IN_COMMUNITY {level}]->(:Community)`
- `(:Community)-[:PARENT]->(:Community)` — child (finer) → parent (coarser).

Note: this `[:RELATED]` graph is separate from the PPR arm's
`COOCCURS_WITH/TRIPLE/SYNONYM` edges. Same entities can carry both; the loaders stay
independent (one logical graph, layer chosen by query discipline — as already done
for PPR).

## Build order

Design was back-to-front; **build front-to-back** (you can't answer without the
index), with two exceptions pulled forward because they're isolated and cheap:

1. ~~**Stage 4 — `leidenHierarchy`** + `writeCommunities`. Isolated, unblocks
   everything community-level. Test on football/Cora hierarchies.~~ ✅ **done**
   (skeleton only — communities are written, not yet summarised).
2. **Stage 6 — `graphExtract`** on a *small slice first* (5–10 chunks), eyeball
   description quality before scaling. This is the cost/quality crux.
3. **Stage 5 — `graphBuild`** → write the `[:RELATED]` graph.
4. **Stage 3 — `communitySummary`** (leaf, then roll-up).
5. **Stage 2 — `globalSearch`** (map-reduce C0). First end-to-end global answer.
6. **Stage 1 — `router`**.
7. **Stage 0 — `sensemakingEval`** → the thesis numbers (vs local/vector RAG).

Validate each stage on a small corpus slice before scaling, per the project's
iterative habit (propose → run → evaluate).

## Open decisions (deferred, not blocking)

- **Demo/eval corpus.** CBE (domain target, qualitative) vs the paper's news/podcast
  (replication, comparable). Decide before Stage 0.
- **Description compression.** GraphRAG LLM-summarizes aggregated entity descriptions
  at build time; we can defer this (concatenate first) and add it if context blows up.
- **Claims/covariates.** Optional GraphRAG element; skip in v1, add if summaries need
  more factual grounding.
