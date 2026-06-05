# TODO — remaining work before thesis hand-off

Pinned backlog. Nothing here is started yet — each item is discussed and agreed before execution.

---

## 1. Benchmark the new pipeline (MuSiQue + 2WikiMultihopQA)

Run the **Route 2** graph (OpenRouter LLM extraction → `RELATED` edges) through **PPR** retrieval and
collect recall@K. Add **2WikiMultihopQA** alongside the existing MuSiQue harness, since both are the
datasets HippoRAG reports on — gives us an apples-to-apples comparison point.

- Current best (old bare-`TRIPLE` graph): **recall@5 = 0.364** (v4/v7b).
- Goal: numbers for `RELATED + SYNONYM` (Route 2 default layers) on both datasets.

**Decisions:** MuSiQue subset = **200** (current `LIMIT`). **Fresh Neo4j instance** for the Route 2
graph (no wipe needed). 2Wiki = **after** MuSiQue lands (separate phase: download + loader + gold-unit
decision, since 2Wiki gold is sentence-level vs paragraph-level corpus).

**MuSiQue Route 2 runbook** (all from repo root; needs new Neo4j up, Ollama up, `OPENROUTER_API_KEY` set):
```
python musique/loadChunks.py              # chunks/musique.json (LIMIT=200)  [exists]
python runners/runEmbed.py musique        # chunk vector index
python runners/runGraphExtract.py musique # OpenRouter LLM extract -> extractions/musique_graph.json  (PAID)
python runners/runGraphBuild.py musique   # Entity + RELATED + MENTIONED_IN
python runners/runEntityEmbed.py          # entity embeddings (seeder needs e.embedding)
python graphTraversal/runSynonyms.py musique 0.85   # SYNONYM layer
# edit musique/eval.py CONFIG block -> PPR (relatedEdges=True, entityAlignment=True), bump VERSION
python musique/eval.py                     # -> musique/eval_results/v8_route2related.json
```
Only paid step is `runGraphExtract` (~600–900 `deepseek/deepseek-v4-flash` calls for 200 examples).

## 2. Test community detection

Validate the global-arm Leiden clustering on the actual KG (not just the `datasets/` toy graphs).
Need to settle **what "test" means here** — we had an idea and need to reconstruct it.

**Open questions:** what's the success criterion? modularity on the CBE graph? summary quality?
sensemaking eval? (this is the fuzzy one — discuss first.)

## 3. Remove redundant / confusing code — **VERY IMPORTANT**

Many files do the same or very similar things (retired typed lineage, old `run.py`/`runAll.py`,
duplicate runners). Audit and delete/consolidate so there's one obvious path.

**Constraint:** CLAUDE.md says the retired typed pipeline is "kept on disk as documented prior effort
(do not delete)".
**Decision:** do the deletion on a **new branch** — git history on `airgapped-sqlite` preserves the
retired code, the new branch gets the clean tree.

## 4. Humanize every file

Remove common AI tells (uniform spacing, over-commenting, telltale phrasing) and introduce natural
human irregularity that **does not change logic**.

**Decision:** parked — decide scope later, after cleanup + benchmarks.

## 5. Unified code-flow document (both routes)

One easy-to-read document tracing the full flow for Route 1 and Route 2, from documents → answer.

## 6. Ultra-detailed setup README (for the jury)

Step-by-step setup of every component (Ollama, Neo4j, SQLite, frontend, pipeline) so a juror can stand
the whole system up from scratch.

---

_Order is not fixed. Cleanup (3) should probably land before humanizing (4) and the flow doc (5) so we
don't document or hand-polish code that's about to be deleted._
