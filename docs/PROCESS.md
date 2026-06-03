# Process Notes — PPR Graph Retrieval

This document records the reasoning, design choices, and empirical results of the graph-traversal-upgrade work on Gazelle. It is written as a reference for thesis writing — the *why* behind every decision, the algorithmic background, and a complete record of every evaluation version we ran.

Audience: future-me writing the thesis chapter. Tone: factual, not promotional. If a decision turned out to be wrong, the document says so.

---

## 1. The goal

Gazelle's long-term aim is a graph-grounded, hallucination-resistant RAG system for Central Bank of Egypt regulatory documents. The chatbot must answer compliance questions by retrieving and citing *specific chunks* of *specific documents*, with provenance preserved at every step.

The work documented here is the **retrieval upgrade**: replacing the original fixed-depth path-traversal in `src/retriever.py` with a Personalized PageRank (PPR) over an entity knowledge graph, broadly following the HippoRAG architecture. The CBE corpus is the deployment target; **MuSiQue** is the algorithmic benchmark we tune and evaluate against because (a) it has gold supporting paragraphs we can score recall against, (b) it is what HippoRAG reports on, giving a comparable baseline.

---

## 2. Background

### 2.1 Why standard RAG struggles with multi-hop questions

A typical RAG system embeds each passage independently and retrieves the top-k nearest to the query embedding. This works when the answer is *contained in a single passage* whose surface form is semantically close to the question. It fails when the answer requires *integrating information across passages*:

> *Question:* Who is the grandmother of Philippe, Duke of Orléans?

To answer this, the retriever needs (i) the passage identifying Philippe, Duke of Orléans, (ii) the passage giving his father (Louis XIII), (iii) the passage identifying Louis XIII's mother (Marie de' Medici). No single passage will be cosine-close to *all three* concepts simultaneously. Naive vector retrieval misses the chain.

The fix that HippoRAG proposes — and that we implement — is to build a knowledge graph over entities mentioned across the corpus, then use a graph-walking algorithm (PPR) at query time to traverse multi-hop chains.

### 2.2 The old k-hop traversal (what we replaced)

Before this branch, Gazelle's `src/retriever.py` already had a `graphSearch` mode based on a different graph-walking idea: **fixed-depth k-hop traversal**. The pipeline was:

1. Embed the query, find the K nearest entities by cosine (the seed set).
2. Starting from each seed, enumerate every path of length ≤ k (typically k=2 or 3) through the entity-relation graph.
3. Score each path by combining entity cosines and per-relation cosines (using a precomputed `RELATIONSHIP_DESCRIPTIONS` table in `src/ontology.py`).
4. For each path, fetch the chunks containing the path's terminal entity. Aggregate scores per chunk. Return top-k chunks.

This works for simple multi-hop questions when k is set high enough to reach the answer entity. It has well-known problems that motivated the upgrade:

- **Fixed depth is the wrong abstraction.** A question may need 2 hops or 5; the retriever has to commit to a number. Too small misses answers; too large explodes path count.
- **Exponential path enumeration.** At hop depth k, the number of paths is `O(d^k)` where `d` is the average entity degree. For dense graphs this becomes intractable at k≥3.
- **Local, not global, scoring.** A path is scored on its own merits without comparing to alternative paths. There's no notion of "this entity is centrally important across many paths."
- **No mass conservation.** Two paths to the same target entity each contribute separately; the retriever can't notice that *many* short paths converge on a particular entity, which is exactly the signal we want for multi-hop.

PPR addresses all four. The walker explores the entire graph at every step (no fixed depth), only `O(N)` storage is required regardless of effective hop count, scoring is global (every node's score depends on the whole graph), and mass conservation is automatic (probability sums to 1). The trade-off is that PPR doesn't give you the *path* — only the score per entity. For our purposes that's fine: we project scores onto chunks at the end.

**Note on the empirical comparison (see §5, v0).** We ran an apples-to-apples evaluation comparing k-hop and PPR on the *same* MuSiQue knowledge graph. The result is nuanced: PPR wins decisively on broad-K recall (recall@10 +8.8 points, hit@5 +10.1) and is 11.5× faster per query, but k-hop wins on top-K precision (recall@1 +3.3, recall@2 +3.5). The two algorithms target different operating points. For multi-hop QA where the LLM reader receives 5-10 chunks, PPR's profile is preferable; for low-latency K=1/K=2 deployments, k-hop is competitive at substantial latency cost. We chose PPR for the rest of this work because (a) our target downstream is an LLM reader consuming multiple chunks, (b) latency matters for the chat UI, and (c) PPR's coverage profile leaves more room for the algorithmic improvements that follow.

### 2.3 PageRank

PageRank was developed by **Larry Page and Sergey Brin at Stanford in 1996**, became the technical core of Google Search the following year, and is the canonical example of a graph-importance algorithm in computer science. The original problem was: given the web (billions of pages, hundreds of billions of hyperlinks), how do you rank pages by importance — not by what they say, but by *how the web treats them*?

Page and Brin's insight: a page's importance can be defined *recursively*. A page is important if many important pages link to it. This sounds circular but resolves to a well-defined eigenvector problem. They reframed it as a random walk: imagine a "random surfer" who keeps clicking links forever. The fraction of time the surfer spends on each page is that page's PageRank. The mathematics had been known since 1907 (Perron-Frobenius theorem for stochastic matrices), but applying it at web scale and recognising it as a search-ranking signal was the contribution.

The random-surfer model:

- With probability `1 - α`, the surfer moves to a uniformly-random *outneighbor* of the current page (clicks a random outgoing link).
- With probability `α` (typically ~0.15), the surfer **teleports** to a uniformly-random page anywhere in the graph (jumps to a bookmark, types in a URL).

After enough steps, the fraction of time spent at each node converges to a *stationary distribution*. Nodes with many incoming edges — especially from other high-ranked nodes — accumulate more probability mass. The teleport term guarantees convergence (no dead-end traps) and prevents the walker from getting stuck in sinks (pages with no outgoing links).

The iterative update rule:

```
p_{t+1} = (1 - α) · M^T · p_t + α · u
```

where `M` is the row-normalised adjacency matrix and `u` is the uniform distribution over all nodes. At convergence `p = p_{t+1} = p_t`, and that `p` is the PageRank vector.

**Mapping to our retrieval problem.** The translation from Google's web to our entity graph is direct:

| Google web | Our entity graph |
|---|---|
| Web pages (nodes) | Entities mentioned in the corpus |
| Hyperlinks (edges) | Co-mention / triple / synonym relations between entities |
| Page importance | Entity importance "to the query" |
| Random surfer | Random walker over the KG |

The walker doesn't care that the underlying graph is the web or a KG — it just needs an adjacency matrix. The trick that makes PageRank useful for retrieval (rather than just static importance ranking) is *personalising the teleport distribution* — that's the next subsection.

### 2.4 Personalized PageRank (PPR)

PPR replaces the uniform teleport distribution `u` with a *query-specific* seed distribution `s`:

```
p_{t+1} = (1 - α) · M^T · p_t + α · s
```

Each time the walker teleports, it lands somewhere proportional to `s`, not uniformly. The stationary distribution is now warped toward whatever `s` emphasises — nodes close to the seeds in the graph accumulate more mass.

For retrieval, this is exactly what we want: `s` encodes "what the query is about" (mass on a few seed entities), and PPR's stationary distribution gives a *personalized importance ranking* of all entities, biased toward query-relevant subgraphs.

Two roles `s` plays in one vector:

1. **Restart distribution.** Every teleport event injects fresh mass into seed entities.
2. **Initial distribution.** At step 0, the walker is placed according to `s` (faster convergence; the stationary distribution itself doesn't depend on the starting point).

`α` controls how *local* the walk stays. Small `α` → walker drifts far, ranking influenced by long graph paths. Large `α` → walker keeps teleporting back to seeds, ranking dominated by immediate neighbourhoods. HippoRAG reports `α = 0.5`.

### 2.5 The hippocampal memory indexing theory

HippoRAG's framing isn't decorative — the biological theory it draws from describes a *specific computational architecture* for memory retrieval, and that architecture closely matches what graph-based RAG needs to do. Worth understanding properly because (a) it motivates several design choices that look arbitrary otherwise (especially the *separation* between concept-level index and chunk-level evidence), and (b) the thesis story benefits from naming this connection cleanly.

The theory was proposed by **Teyler and Discenna in 1986** ("The hippocampal memory indexing theory," *Behavioral Neuroscience*) and refined in Teyler and Rudy (2007). It addresses a long-standing puzzle in neuroscience: where are memories actually *stored*?

**Background — the puzzle the theory solves.** Patients with hippocampal damage (the famous case study H.M. is the canonical example) can recall old memories perfectly but cannot form new ones. This suggests two things: first, memories *aren't stored in the hippocampus itself* (since old ones survive damage), and second, the hippocampus is doing *something* essential for memory formation and retrieval. The indexing theory's resolution: memories live in the **neocortex** (the outer wrinkled surface of the brain that handles sensory processing and concepts), but the **hippocampus** maintains a sparse *index* of pointers and associations that lets a partial cue trigger reactivation of a full memory pattern in the neocortex.

**Two computational objectives.** The theory holds the memory system serves two functions:

1. **Pattern separation.** When two experiences are similar but distinct, the hippocampus must encode them as *distinguishable* index entries — otherwise they'd collapse together and one would overwrite the other. Pattern separation happens at encoding time.
2. **Pattern completion.** When given a partial cue (e.g. a smell, a name, a fragment of a scene), the system must reactivate the *whole* original memory. This is the retrieval-time job, and it's exactly what RAG does computationally: from a query (partial cue) reconstruct the relevant passages (full memory).

**The three-stage flow.** The theory posits memory works through interaction between three regions:

- **Neocortex** — processes perceptual stimuli into higher-level features (objects, concepts, words) and is where the actual memory traces live. Vast storage, distributed representation.
- **Parahippocampal regions (PHR)** — a small set of structures that *route* signals between neocortex and hippocampus. They're the bridge layer: they take the rich neocortical representations and reduce them to something the hippocampus can index, and at retrieval time they go the other direction.
- **Hippocampus** — a small C-shaped structure that maintains the *index*. Crucially, the indexing happens in a sub-region called **CA3**, which has dense recurrent connections — meaning neurons in CA3 connect heavily to each other, allowing partial activation patterns to "complete" into full ones via the recurrent loops. This is the biological substrate for pattern completion.

**The retrieval pipeline, as the theory describes it:**

1. A partial cue (the query) enters via sensory cortex → routed through PHR.
2. PHR signals reach CA3 in the hippocampus.
3. CA3's recurrent connections activate the associated *index entries* — these are pointers to the relevant neocortical memory traces, plus *associations* between memory units that were co-encoded.
4. The reactivated indices are routed back through PHR to neocortex, where they trigger reactivation of the full memory traces.
5. The complete memory is now available for use.

**Why this matters computationally.** Several properties of this architecture are exactly what a knowledge-integration retrieval system wants:

- **Sparse index, distributed storage.** The hippocampus is small; the neocortex is vast. The index is cheap to query; the actual content can be huge. In RAG terms: the KG is small (~10s of thousands of entities), the corpus is large (~millions of tokens). Querying the index doesn't require touching the bulk content.
- **Updating without rewriting.** New experiences integrate by *adding to the index*, not by modifying the existing memory traces. The neocortex doesn't need to be rewritten when a new fact arrives. For RAG: when a new document is added, we extract its entities and edges, write them to the KG, and the existing chunks don't need to change.
- **Associative retrieval via graph structure.** CA3's recurrent connections aren't just storing pointers — they encode *associations* between memory units. Activating one pulls in linked others. For RAG: PPR walking the entity graph is the direct analogue of activation spreading through CA3's recurrent loops.
- **Pattern completion = multi-hop retrieval.** A partial cue activates an entry, which activates its associates, which activate theirs. Multi-step traversal *is* pattern completion. This is the deep reason graph traversal handles multi-hop questions better than passage-embedding lookup: passage embeddings give you single-point similarity, graph activation gives you associative reconstruction.

### 2.6 HippoRAG: the published method

HippoRAG (Jiménez Gutiérrez et al., NeurIPS 2024) is the concrete system that maps the theory above onto an LLM-based RAG pipeline. The mapping:

| Brain region | Function | HippoRAG analogue |
|---|---|---|
| **Neocortex** | Processes raw input into structured concepts; stores actual memory | LLM (GPT-3.5 / Llama-3.1). Extracts noun-phrase nodes and `(subject, predicate, object)` triples from each passage. The passage *text* is the stored memory. |
| **Parahippocampal regions** | Routes between concept space and index space; detects similarity | Retrieval encoder (Contriever / ColBERTv2). Adds *synonym edges* between near-identical concept nodes (cosine ≥ 0.8). |
| **Hippocampus (CA3)** | Sparse associative index; pattern completion via recurrent activation | Knowledge graph (nodes = concepts, edges = triples + synonyms) + **PPR** as the activation-spreading algorithm. |

**Offline indexing (memory encoding):** LLM is prompted per passage to extract (a) named entities and (b) `(subject, predicate, object)` triples. Subjects and objects are *noun phrases* — not restricted to any NER schema. Every unique noun phrase becomes a node in the KG. The retrieval encoder embeds all nodes and adds *synonym edges* between pairs with cosine ≥ 0.8. The resulting graph is the artificial hippocampal index.

**Online retrieval (pattern completion):** the LLM extracts named entities from the query. These map to KG nodes via embedding match — these are the *query nodes*, the partial cue. Query nodes seed the PPR vector. PPR walks the KG — the analogue of CA3's activation spreading. Final entity scores are projected onto passages via the entity-to-passage matrix; top-k passages are returned as the reconstructed memory.

**Why the framing isn't just rhetoric.** Several design choices follow naturally from the biological analogue but would look arbitrary without it:

- *Why two layers (concept index + passage layer) rather than one?* Because that's the architecture the theory specifies: small sparse index plus large distributed storage. The hippocampus doesn't *contain* memories; it indexes them. Engineering-wise, this lets the KG be small enough to traverse efficiently while the chunk store can be arbitrarily large.
- *Why PPR specifically, and not a different graph algorithm?* Because PPR's iterative mass-spreading mirrors CA3's recurrent activation. Each iteration is one round of "what does each node send to its neighbours," analogous to one timestep of neural activity. The convergent stationary distribution is the analogue of the stable activation pattern that emerges in CA3 during pattern completion.
- *Why synonymy edges separate from triple edges?* Because the parahippocampal regions specifically handle *similarity-based bridging* between concepts that aren't related by a direct triple but refer to the same thing. They're the "bridge" layer between neocortex (where "Adelphia Communications Corp" and "Adelphia" might be processed differently) and hippocampus (where they should activate the same index entry).
- *Why is the KG concept-level rather than passage-level?* Because the theory says the index points to memory units, and memory units in this context are concepts, not entire passages. Indexing whole passages would be like the hippocampus indexing whole afternoons — too coarse-grained for associative retrieval.

**Headline empirical numbers:** MuSiQue recall@5 = 0.519, 2WikiMultiHopQA recall@5 = 0.891, both reported on the OpenIE-based KG with Contriever or ColBERTv2 as the retrieval encoder. These are the numbers we compare against.

---

## 3. Our pipeline

Our implementation deliberately diverges from the paper in two structural ways. Both choices are explained below; both turn out to bound the headline number we can achieve.

### 3.1 Entity layer: GLiNER instead of LLM

We extract entities with **GLiNER** (a discriminative NER model) restricted to 10 English types: Person, Organization, Location, Work, Event, Date, Nationality, Occupation, Award, Language. Chosen because (i) the existing CBE Arabic pipeline already used GLiNER, keeping infrastructure consistent; (ii) GLiNER is fast, deterministic, and cheap relative to repeated LLM calls per passage; (iii) typed entities map cleanly to ontology slots used elsewhere in Gazelle (`src/ontology.py`).

Consequence: our entity set is a strict subset of HippoRAG's. Concepts like *"private FM radio station"*, *"the network"*, *"green facial makeup"* — noun phrases that HippoRAG's LLM treats as first-class nodes — are simply absent from our KG. This is the first structural divergence.

GLiNER threshold tuning is documented in the v1 row of §5: we settled on `0.7`, accepting that the model's score distribution is highly right-skewed (most outputs score >0.8 regardless), so the threshold dial doesn't separate noise from signal as cleanly as one might hope.

### 3.2 KG schema

Three node labels in Neo4j, all in one logical graph, but two logical *layers* enforced by query discipline rather than topology:

- `(:Document {docName})` — bookkeeping per corpus.
- `(:Chunk {chunkId, docName, text, sectionPath, pages, accessLevel})` — passage layer. Stores text for retrieval-time evidence.
- `(:Entity {canonicalId, canonicalName, type, aliases, docName})` — concept layer. PPR lives here.

Edges:

- `(:Chunk)-[:PART_OF]->(:Document)` — bookkeeping.
- `(:Entity)-[:MENTIONED_IN]->(:Chunk)` — projection layer. Used at retrieval time to map entity scores onto chunks. **PPR does not walk these.**
- `(:Entity)-[:COOCCURS_WITH {count}]->(:Entity)` — co-mention substrate (initial). Weight = number of chunks the pair shares.
- `(:Entity)-[:SYNONYM {cosine}]->(:Entity)` — entity alignment edges (added later, v4).
- `(:Entity)-[:TRIPLE {count, predicates}]->(:Entity)` — LLM-extracted relations (added later, v7).

The separation between the *concept layer* (Entity + entity-entity edges) and the *passage layer* (Chunk + MENTIONED_IN) is enforced **in the loader query**, not in the graph topology. The PPR adjacency loader pulls only entity-entity edges. The MENTIONED_IN edges are queried separately at projection time. This means the same Neo4j graph serves both layers, but PPR sees only the concept layer.

### 3.3 Co-mention edges: option C

We deferred LLM-based relation extraction during the initial build. Instead we connect entities by *co-mention*: any two entities mentioned in the same chunk get a `COOCCURS_WITH` edge weighted by chunk overlap count.

The Cypher that builds these edges:

```cypher
MATCH (e1:Entity {docName:$d})-[:MENTIONED_IN]->(c:Chunk)
      <-[:MENTIONED_IN]-(e2:Entity {docName:$d})
WHERE e1.canonicalId < e2.canonicalId
WITH e1, e2, count(DISTINCT c) AS weight
MERGE (e1)-[r:COOCCURS_WITH]->(e2) SET r.count = weight
```

The `<` filter keeps each pair once (one stored direction). The PPR loader symmetrises at load time (`undirected=True`), so the walker treats the graph as undirected.

Co-mention is noisier than typed-triple edges because every pair in a chunk gets an edge regardless of whether they're actually related. The trade-off was end-to-end velocity: we wanted to validate the full pipeline before adding the LLM-OpenIE step.

### 3.4 Embedding layer

`BGE-M3` via Ollama (`bge-m3:latest`). Used for two purposes:

1. **Entity embeddings.** Each `:Entity` node gets a vector built from `canonicalName / aliases` joined by `/`. Stored as `e.embedding` in Neo4j, also indexed by a Neo4j vector index.
2. **Query embeddings.** At retrieval time, the query is embedded with the same model.

The choice of BGE-M3 over the paper's Contriever/ColBERTv2 was infrastructural — Ollama already hosted BGE-M3 for the chunk embedding pipeline used in Gazelle's other retrieval modes, and adding another embedder would have meant another model in memory.

### 3.5 Seed selection

At query time, we cosine-rank all entity embeddings against the query embedding and take the top-K (K=5). The K similarities are linear-normalised to sum to 1 and become the seed mass vector.

Linear-normalise (`s = sims / sum(sims)`) was chosen over hard one-hot (brittle to misses) and softmax (introduces a temperature hyperparameter). This matches the published default. The paper additionally applies **node specificity** — multiplying each seed's mass by `1 / |chunks containing it|` to downweight common entities — which we tested and rejected (v3, below).

### 3.6 Chunk projection

After PPR converges, every entity has a score. We aggregate these into chunk scores via `MENTIONED_IN`:

```
chunkScore[c] = Σ over entities e mentioned in c: pprScore[e]
```

Top-K chunks are returned with text and the top 3 contributing entities, for debugging visibility.

---

## 4. Evaluation setup

### 4.1 Dataset

MuSiQue (Trivedi et al., 2022) dev set, first 200 examples — all are **2-hop questions** because the dataset is ordered by hop count and the first 200 happen to be all 2-hop. This means our results aren't directly comparable to HippoRAG's averaged-over-hop-counts numbers; we're benchmarking on the easier 2-hop subset where the paper does best. For an apples-to-apples comparison the paper's 2-hop slice would be the right reference, but the paper only reports averages.

Chunks are MuSiQue paragraphs *as-is*, deduplicated by content hash → ~3,075 unique chunks (mix of supporting paragraphs and distractors). Each chunk's `chunkId` is `musique-` + first 16 hex chars of SHA-1 over the paragraph text. This hashing function is the bridge between MuSiQue's `is_supporting` flags and our retrieved chunkIds.

### 4.2 Metrics

For each question with G gold supporting chunks:

- **Recall@K** = `|gold ∩ topK| / G`. Averaged across questions. This is HippoRAG's headline metric.
- **Hit@K** = `1 if any gold in topK else 0`. Averaged across questions. Looser sanity check.

Reported at K ∈ {1, 2, 5, 10}.

### 4.3 Output format & versioning

Each evaluation run writes to `musique/eval_results/{version}_{label}.json` with a top-level block:

```json
{
  "version": "v4",
  "label": "synonym",
  "notes": "...",
  "config": { "pprAlpha": 0.5, ... },
  "aggregate": { "recall@5": 0.364, ... },
  "byHop": { "2hop": {...} },
  "perQuestion": [...],
  "skipped": [...]
}
```

The `config` block captures every parameter that varies across versions, so any later comparison can be reconstructed mechanically. The `perQuestion` array preserves the gold + retrieved chunkId lists for every question, allowing detailed error analysis without re-running.

### 4.4 Caching for speed

`RetrievalIndex` (in `graphTraversal/retrieve.py`) loads all heavy state once at construction:

- Entity embeddings (~15k × 1024 float32 matrix from Neo4j).
- Entity-entity adjacency (CSR sparse matrix).
- Entity-to-chunks mapping (dict).

Per-query cost then drops to ~300 ms (one Ollama embed call, one matrix-vector cosine, one PPR run, one chunk-text fetch). For the 200-question eval, this brings end-to-end runtime from hours to under 2 minutes.

---

## 5. Versions

Every row records: motivation, the specific change, the headline result, and what we learned. Numbers are recall@5 on the 200-question 2-hop subset unless noted otherwise.

The paper's reference for context: **HippoRAG recall@5 = 0.519** (averaged over MuSiQue hop counts — likely higher on 2-hop alone).

### v0 — k-hop baseline (recall@5 = 0.364)

**Motivation.** Before claiming PPR is an improvement over the previous architecture (k-hop fixed-depth traversal, §2.2), measure both on the *same* knowledge graph. This isolates the algorithm choice from the data: same entities, same edges, different walker. The number tells us how much of any improvement is attributable to PPR specifically rather than to other pipeline differences.

**Implementation.** New module `graphTraversal/khop.py` (not a modification of `src/retriever.py`, which stays as-is for the production chat API path). Algorithm mirrors `retriever.graphSearch`:

1. Embed query → top-K=8 seed entities by cosine.
2. Enumerate paths from seeds up to depth=3, walking `COOCCURS_WITH | SYNONYM | TRIPLE` edges. Cap at 300 paths.
3. Score each path = mean(cosine(query, entity_emb) for entity in path).
4. For each entity in each path, all chunks containing it inherit the path score; max wins per chunk.
5. Return top-K chunks.

Why not call `retriever.graphSearch` directly: it filters paths by `RELATIONSHIP_DESCRIPTIONS` (CBE Arabic relation ontology) and projects chunks via `r.chunkIds` (a property only stored on typed CBE edges). Our MuSiQue edges have neither. The algorithmic *shape* is identical; the schema-specific glue (Cypher, projection) is what differs.

**Config.** Same KG as v7b — co-mention + synonym + triple edges all loaded; entities, embeddings unchanged.

| Metric | v0 (k-hop) | v7b (PPR best) | Δ (PPR − k-hop) |
|---|---|---|---|
| recall@1 | **0.217** | 0.184 | -3.3 |
| recall@2 | **0.290** | 0.255 | -3.5 |
| recall@5 | 0.364 | 0.364 | 0 |
| recall@10 | 0.399 | **0.487** | +8.8 |
| hit@1 | **0.434** | 0.369 | -6.5 |
| hit@5 | 0.525 | **0.626** | +10.1 |
| hit@10 | 0.535 | **0.662** | +12.7 |
| ms/query | ~3460 | ~300 | PPR is 11.5× faster |

**Observations.** Result is not the clean "PPR strictly wins" that simple readings of the literature would predict. The two algorithms expose a **measured precision–recall trade-off on the same KG**:

- **k-hop is more precise at the very top of the ranking** (+3.3 recall@1, +3.5 recall@2, +6.5 hit@1). Path enumeration along entity-cosine-good routes concentrates score on the seed's immediate neighbourhood, so the very top of the ranking is highly correlated with seed-relevance.
- **PPR is dramatically better at broader coverage** (+8.8 recall@10, +10.1 hit@5, +12.7 hit@10). Mass diffusion across the graph means more chunks accumulate non-trivial scores; the wider candidate set captures more supporting evidence.
- **PPR is 11.5× faster** per query (300 ms vs 3.5 s). k-hop's depth-3 path enumeration with 300-path cap is expensive even on our modest graph; PPR's sparse matrix iteration is cheap and constant-time per query after index load.

**The right thesis-framing** isn't "PPR strictly improves over k-hop" — that would be wrong given v0's recall@2 advantage. It's:

> *"On the same KG, k-hop and PPR target different operating points. k-hop favours top-K precision; PPR favours wider-K coverage. For multi-hop QA, where the reader requires multiple supporting paragraphs and 5-10 chunks are routinely passed to the downstream LLM, PPR's profile is preferable. For low-latency single-answer settings where K=1 or K=2 is the deployment target, k-hop is competitive at substantial latency cost."*

Note for the methodology chapter: §2.2 of this document originally asserted "PPR fixes [k-hop's four problems]" without measurement. After this experiment we know the picture is more nuanced — PPR fixes the *recall* and *latency* problems but doesn't strictly dominate on *top-K precision*. The thesis text in §2.2 has been updated to reflect the measured comparison.

### v1 — baseline (recall@5 = 0.359)

**Motivation.** Establish end-to-end functionality. Verify all pieces (NER, KG, embeddings, seeder, PPR, projection) work and produce a number.

**Config.** GLiNER threshold 0.7, co-mention edges only, linear-normalise top-5 seeds, PPR α=0.15, no synonyms, no node specificity. 14,815 entities; ~50k co-mention edges.

| Metric | Value |
|---|---|
| recall@1 | 0.114 |
| recall@2 | 0.189 |
| recall@5 | 0.359 |
| recall@10 | 0.472 |
| hit@5 | 0.601 |

**Observations.** The pipeline works. Co-mention substrate is dense (every entity-pair in a chunk gets an edge); PPR mass diffuses widely. Top-1 recall is low (11%) — for any given question, the single most-relevant chunk only lands top-1 about 1 in 9 times. Hit@5 of 0.60 shows that *some* supporting chunk lands in top-5 60% of the time, which is the baseline signal we'll be trying to lift across subsequent versions.

### v2 — α = 0.5 (recall@5 = 0.356)

**Motivation.** The paper uses `α = 0.5`. Our v1 used the original PageRank default 0.15. Higher α concentrates mass close to seeds, lower α lets the walker drift farther. For multi-hop retrieval, 0.5 should help find the seed-chunk reliably while still allowing some neighbourhood exploration.

**Change.** `pprAlpha: 0.15 → 0.5`. Single parameter, nothing else changed.

| Metric | v1 (α=0.15) | v2 (α=0.5) | Δ |
|---|---|---|---|
| recall@1 | 0.114 | **0.184** | **+7.1** |
| recall@2 | 0.189 | **0.247** | **+5.8** |
| recall@5 | 0.359 | 0.356 | -0.3 |
| recall@10 | 0.472 | 0.477 | +0.5 |
| hit@1 | 0.227 | **0.369** | **+14.2** |
| hit@2 | 0.348 | **0.464** | **+11.6** |
| hit@5 | 0.601 | 0.616 | +1.5 |

**Observations.** Massive shift at top-1/top-2 (recall@1 jumps 7 points; hit@1 jumps 14). recall@5 essentially unchanged. The pattern is consistent with the theoretical expectation: higher α keeps the walker close to seeds, dramatically improving the chance of finding the *first-hop* (seed-chunk) but offering no help for *second-hop* (bridge-chunk) retrieval. **α=0.5 is kept for all subsequent versions.**

### v3 — node specificity (recall@5 = 0.348)

**Motivation.** HippoRAG's ablation reports that node specificity contributes +3.7% to MuSiQue R@5. Each seed's mass is divided by the number of passages containing that entity (an IDF-like signal), then renormalised. The idea is to downweight generic high-frequency entities at the seed step.

**Change.** Add `applyNodeSpecificity` step in `RetrievalIndex.retrieve` between seed-vector build and PPR. All other config retained from v2.

| Metric | v2 | v3 | Δ |
|---|---|---|---|
| recall@1 | 0.184 | 0.174 | -1.0 |
| recall@2 | 0.247 | 0.225 | -2.3 |
| recall@5 | 0.356 | 0.348 | -0.8 |
| recall@10 | 0.477 | 0.460 | -1.7 |
| hit@5 | 0.616 | 0.596 | -2.0 |

**Observations.** Hurts across the board. Hypothesis for why:

HippoRAG's seeds come from **LLM-based NER** on the query, which extracts whatever named entity is mentioned — including high-frequency entities like "United States" — without semantic ranking. Node specificity is necessary to suppress these.

Our seeds come from **cosine ranking** over all entity embeddings. Cosine already prefers query-specific entities (a query about "Lago District" cosine-ranks "Lago District" above generic "United States" regardless of mention count). Stacking node specificity on top of cosine ranking **double-counts the specificity signal and over-corrects** — legitimately well-attested entities that *are* the answer get penalised.

This is a clean negative result worth documenting in the thesis: the paper's design choices are coupled. Node specificity only contributes when the seeder is mention-blind (LLM NER). With a cosine seeder it's redundant and harmful. **Reverted; not used in v4+.**

### v4 — entity alignment via synonym edges (recall@5 = 0.364) — *first new best*

**Motivation.** Probe diagnostics on the q1-q3 eyeball queries showed an entity-resolution failure. For the question *"What company succeeded the owner of Empire Sports Network?"*, the bridge entity "Adelphia Communications Corporation" was extracted by GLiNER, but the corpus also contains a separate `:Entity` node "Adelphia" (the LLM-extracted short form). The bridge edge to "Time Warner Cable" attaches to the *short-form duplicate* (which has near-zero PPR mass) instead of the *long-form duplicate* (which has the seed-derived mass). So PPR cannot propagate.

This is the published HippoRAG fix: add `SYNONYM` edges between entities whose name embeddings are similar AND share the same type. We add an optional second filter — **token-subset rule** — to suppress structurally-similar-but-distinct false positives (e.g. "1968 Democratic National Convention" vs "1968 Republican National Convention" cosine ≈ 0.95 but neither's tokens are a subset of the other's). Implementation in `graphTraversal/synonyms.py`.

**Threshold tuning.** Tried 0.80 (4,917 pairs), 0.85 (1,718), 0.90 (438). At 0.85 + subset filter the count drops to 604 pairs and the eyeballed precision is good — Adelphia ↔ Adelphia Communications Corporation is in the set, false-positive Conventions are not. Residual noise: "Nevada" ⊂ "Sierra Nevada" etc., which we accept as the cost of a non-LLM precision-checker.

**Change.** Add SYNONYM edge type to Neo4j. PPR loader now pulls `(:Entity)-[r:COOCCURS_WITH|SYNONYM]-(:Entity)` and treats both as graph edges (synonym edges get weight 1 by default).

| Metric | v2 (α=0.5 baseline) | v4 (+synonym) | Δ |
|---|---|---|---|
| recall@1 | 0.184 | 0.182 | -0.2 |
| recall@2 | 0.247 | 0.250 | +0.3 |
| recall@5 | 0.356 | **0.364** | **+0.8** |
| recall@10 | 0.477 | 0.480 | +0.3 |
| hit@5 | 0.616 | **0.626** | **+1.0** |

**Observations.** Small but real gain. This is consistent with HippoRAG's own ablation (paper attributes +1.7% R@5 to synonyms on average — we got +0.8 on 2-hop only).

### v5 — synonym edge weight = 10 (recall@5 = 0.359)

**Motivation.** Hypothesis: in v4, synonym edges have weight 1 while co-mention edges have weight = chunk-overlap count (often 1-20). Maybe the synonym contribution is too small relative to co-mention; PPR mass doesn't actually equilibrate between duplicates. Try forcing weight = 10 to push most mass through the synonym bridge.

**Change.** `synonymWeight: 1 → 10` in retrieval config.

| Metric | v4 | v5 | Δ |
|---|---|---|---|
| recall@1 | 0.182 | 0.182 | 0 |
| recall@2 | 0.250 | 0.250 | 0 |
| recall@5 | 0.364 | 0.359 | -0.5 |
| recall@10 | 0.480 | 0.475 | -0.5 |
| hit@5 | 0.626 | 0.616 | -1.0 |

**Observations.** Negative result. Weight magnitude doesn't matter: PPR row-normalises, so increasing one edge type's weight just shifts mass distribution within each node's neighbourhood, not the global topology. The synonym fix's gain isn't being held back by edge weight; it's bounded by *how many real duplicate pairs we caught* with the threshold + filter (604). To improve, we'd need to catch more duplicates (more permissive matching) or address a different bottleneck. **Reverted to weight=1 for v7+.**

### v6 — skipped

We considered "windowed co-mention" (only edge entities within N tokens of each other in the same chunk) but decided against it: the window size N would be another arbitrary hyperparameter, and the structural change is small compared to v7.

### v7 — replace co-mention with LLM triples (recall@5 = 0.331)

**Motivation.** Co-mention is the noisiest possible edge: every entity pair in a chunk gets an edge regardless of whether the text asserts a relation between them. HippoRAG's edges come from LLM OpenIE — only entity pairs that appear in an extracted `(subject, predicate, object)` triple become connected. Much sparser, much higher signal-per-edge. This is the structural fix.

**Implementation.**

1. **Extraction.** `src/llmTriples.py` calls llama3.1:8b via Ollama with the paper's Appendix-I prompt (slightly compressed). Per chunk: pass chunk text + GLiNER-extracted entity names, get back JSON `{"triples": [["subj","pred","obj"], ...]}`. Loose-mode prompt — LLM can introduce concepts beyond the GLiNER list. Batched at 5 chunks per call for throughput. Resume logic skips already-extracted chunks on restart. ~3,075 chunks × ~10 sec/chunk = ~7-8 hours total wall-clock on local GPU; backend ablation supported (Ollama, Groq, OpenRouter, Gemini) via `BACKENDS` dict.

2. **Edge writing.** `kgBuild.writeTripleEdges`: for each extracted triple, map subject and object surface strings to existing `:Entity` canonicalIds via `loadNameLookup` (exact match on lowercased canonicalName + aliases). Triples where either endpoint is unmatched are dropped. Aggregate by (subId, objId) pair, store edge weight = count, predicates = list of distinct predicate strings.

   Extraction result: **16,152 raw triples → 10,661 unmatched orphans dropped (66%) → 5,148 unique entity pairs**. Most LLM-extracted endpoints are concept-level noun phrases (`"private FM radio station"`, `"green facial makeup"`) that GLiNER never produced, so they have no canonicalId to map to.

3. **Loader.** `loadEntityGraph(useTriples=True)` pulls `[r:TRIPLE]` edges instead of co-mention edges. Synonyms still loaded.

| Metric | v4 | v7 | Δ |
|---|---|---|---|
| recall@1 | 0.182 | 0.167 | -1.5 |
| recall@2 | 0.250 | 0.235 | -1.5 |
| recall@5 | 0.364 | 0.331 | **-3.3** |
| recall@10 | 0.480 | 0.409 | **-7.1** |
| hit@5 | 0.626 | 0.480 | **-14.6** |
| hit@10 | 0.662 | 0.545 | -11.7 |

**Observations.** Significant regression. The 10× sparser graph (~5k edges vs ~50k) leaves too many entities isolated — PPR seeds landing on isolated entities can't walk anywhere. The triple edges that *do* exist are higher-signal than co-mention edges, but losing the safety net is a worse trade.

### v7b — co-mention AND triples (recall@5 = 0.364) — tied with v4

**Motivation.** Don't replace co-mention with triples; augment. Co-mention provides graph density (safety net for recall). Triples add high-signal relational edges on top.

**Change.** `loadEntityGraph` accepts independent `useCoMention` and `useTriples` flags. v7b sets both true.

| Metric | v4 | v7b | Δ |
|---|---|---|---|
| recall@1 | 0.182 | 0.184 | +0.2 |
| recall@2 | 0.250 | 0.255 | +0.5 |
| recall@5 | 0.364 | 0.364 | 0 |
| recall@10 | 0.480 | 0.487 | +0.7 |
| hit@5 | 0.626 | 0.626 | 0 |

**Observations.** Marginal — and revealing.

The reason for the near-tie has a clean explanation: **triple edges are largely redundant with co-mention edges.** Per-chunk extraction guarantees that if A and B appear in a triple together, they co-occurred in that chunk, so they already have a co-mention edge. Triples can only add *new connectivity* when one endpoint is an entity NOT in the co-mention graph — i.e. when the LLM extracted a concept that GLiNER missed. But concept endpoints get dropped at edge-write time because they don't match any canonicalId. **The triples we keep don't bridge anywhere new; the triples that would bridge somewhere new are the ones we drop.**

This realisation reframes the structural ceiling: our gains from triples are capped at whatever within-chunk relational re-weighting they provide. To unlock real connectivity gains, the dropped "orphan" endpoints would need to become first-class entity nodes (a v8 not yet implemented — see §6 and HANDOFF).

---

## 6. The structural gap to HippoRAG

After all versions, our best is **recall@5 = 0.364** (v4 and v7b tied). Paper baseline is 0.519. Gap = 16 points on average; likely larger if we could compare 2-hop-to-2-hop.

The gap is structural, not algorithmic:

| | HippoRAG | Ours | Ratio |
|---|---|---|---|
| Unique entity nodes | 91,729 | 14,815 | **6.2×** |
| Edges (triple-derived) | 107,448 | 5,148 | **20.9×** |
| Synonym edges | 191,636 (ColBERTv2) | 604 (BGE-M3) | **317×** |

Their graph has *six times* the nodes and *twenty times* the edges. PPR over the bigger, denser graph has correspondingly more bridges to find, and the synonymy layer connects formerly-isolated subgraphs at a scale we don't approach.

The deeper structural insight: HippoRAG's gain over plain co-mention isn't really from the triple format itself — it's from **promoting noun phrases to first-class nodes**. Each shared concept ("private FM radio station", "the network") becomes a Steiner point in the graph that links chunks talking about the same idea even when they don't share a named entity. PPR walks across chunks via concept nodes — the cross-chunk path-finding mechanism we don't have.

Two paths forward (deferred to HANDOFF):

- **v8 — concept entities.** Discard GLiNER as the canonical entity source; use LLM to extract both named entities *and* noun phrases per chunk. Every noun phrase becomes an `:Entity`. Expected nodes ~60-90k. Re-do embeddings, synonyms, triples. Closes most of the gap, probably lands at 0.45-0.50 R@5.

- **Pivot.** Document the current ceiling as our system's headline. Frame as a "concept-restricted variant" of HippoRAG with interpretability/control benefits. Move on to community detection (Leiden) and aggregation queries — the next chunk on the roadmap and a real contribution beyond replication.

---

## 7. Full version summary

| Version | Change | recall@1 | recall@2 | recall@5 | recall@10 | hit@5 | Notes |
|---|---|---|---|---|---|---|---|
| v0 | k-hop baseline (depth=3) | 0.217 | 0.290 | 0.364 | 0.399 | 0.525 | top-K precision; recall ceiling |
| v1 | baseline (α=0.15) | 0.114 | 0.189 | 0.359 | 0.472 | 0.601 | end-to-end works |
| v2 | α=0.5 | 0.184 | 0.247 | 0.356 | 0.477 | 0.616 | top-1/top-2 big gain |
| v3 | +node specificity | 0.174 | 0.225 | 0.348 | 0.460 | 0.596 | hurt; reverted |
| **v4** | +synonym edges (w=1) | 0.182 | 0.250 | **0.364** | 0.480 | **0.626** | new best |
| v5 | synonym weight=10 | 0.182 | 0.250 | 0.359 | 0.475 | 0.616 | weight irrelevant |
| v7 | triples only (no co-mention) | 0.167 | 0.235 | 0.331 | 0.409 | 0.480 | too sparse |
| **v7b** | co-mention + triples | 0.184 | 0.255 | **0.364** | 0.487 | 0.626 | tied with v4 |

Reference: **HippoRAG paper R@5 ≈ 0.519** (averaged across hop counts).

---

## 8. Files of record

Code:
- `graphTraversal/ppr.py` — Personalized PageRank implementation.
- `graphTraversal/seeder.py` — query → seed entities.
- `graphTraversal/retrieve.py` — `RetrievalIndex` class, edge loaders, projection.
- `graphTraversal/synonyms.py` — entity alignment via embedding cosine + token subset.
- `graphTraversal/loadGraph.py` — Cypher → sparse adjacency conversion.
- `src/kgBuild.py` — entity layer + co-mention + triple edge writers.
- `src/llmTriples.py` — LLM-based OpenIE extraction (multi-backend).
- `runners/runLlmTriples.py` — batch extraction with resume + parallel.

Eval artefacts:
- `musique/eval.py` — eval harness, versioned output.
- `musique/eval_results/v{N}_{label}.json` — one file per version, complete config + per-question results.

Reference papers:
- HippoRAG (Jiménez Gutiérrez et al., NeurIPS 2024) — local copy `2405.14831v3.pdf`.
- MuSiQue (Trivedi et al., 2022).
- Personalized PageRank (Haveliwala, 2002).
- Hippocampal memory indexing theory (Teyler & Discenna, 1986; Teyler & Rudy, 2007).

---

## 9. Final direction — two routes

After the versions above, the graph-construction effort is consolidated into **two maintained routes**, with the earlier attempts kept as a documented progression (this section is the thesis "trail of effort"):

- **Route 1 — Classical:** GLiNER entities + co-mention (`COOCCURS_WITH`) edges. This is the v1 substrate, retained as the cheap, deterministic **baseline** to beat. Retrieval-only.
- **Route 2 — LLM:** a single LLM pass extracts entities **and** relationships **and** descriptions, written as `(:Entity {description})-[:RELATED {predicate, description, weight}]->(:Entity)` (`graphExtract.py` → `graphBuild.py`). This is the deployed graph and the only one that feeds the global arm (community summaries consume the descriptions). It directly addresses the §6 structural gap — the LLM promotes concept noun-phrases to first-class entities, which GLiNER could not.

The intermediate experiments documented above are **retired but kept on disk** as the progression: the ontology-**typed** pipeline (`llmExtract.py` + `kgWriter.py`, the original CBE relation extractor) and the bare-**triples** route (`llmTriples` + `writeTripleEdges`, v7 — which §5/§7 showed regressed without descriptions). Route 2 supersedes both by adding descriptions; Route 1 survives as the baseline. Both routes run on the same chunks for a clean A/B comparison.
