# Evaluation

How to evaluate each part of the system, and how to test whether graph traversal beats pure vector search.

## Three layers, three eval methods

### 1. Retrieval (vector vs hybrid vs graph)

**Standard IR metrics on a hand-curated gold set.** Bootstrapping:

```powershell
# 1. See what each mode currently retrieves for the seed queries
python eval/runEval.py
```

This dumps the chunkIds each mode returns. Open `eval/queries.json`, fill in
`relevantChunks` for each query — pick the chunkIds you'd want a human to see.
Run again:

```powershell
python eval/runEval.py
```

You get a table of **Recall@K**, **Precision@K**, **MRR** for vector / hybrid /
graph, plus a multi-hop-only subset (where graph should win).

The seeded queries in `queries.json` are split by intended type:
- `single-hop` — the answer lives in one chunk; vector should be sufficient.
- `multi-step` — answer is a procedure, often one chunk has the full list.
- `multi-hop` — requires connecting two entities through a relationship; **graph
  is the only mode that can reach evidence the vector embedding doesn't surface**.

If average MRR for graph >> vector on the multi-hop subset, the graph layer is
earning its keep. If it's the same or worse, it's not — and the next move is
either tightening entity extraction or revisiting how you traverse.

### 2. Entity / relationship extraction (GLiNER + LLM)

Already scaffolded. Use `runners/sampleChunks.py` to generate `gold/sample.json`,
then hand-annotate `expectedEntities` and `expectedRelationships`. A simple eval
script could compute per-type precision/recall against the annotations — let me
know if you want me to build it.

### 3. End-to-end RAG (retrieval + answer)

For LLM answer quality: **RAGAS** (`pip install ragas`) is the industry standard.
It computes:
- **faithfulness** — do answer claims come from retrieved context?
- **answer_relevancy** — does the answer address the question?
- **context_precision / recall** — is retrieved context actually useful?

A faithfulness check tailored to our citation format is doable in 50 lines:
parse `[chunkId]` markers from the LLM answer, verify each maps to a retrieved
chunk, flag claim sentences without any citation. Cheap and specific.

## Suggested gold-set workflow

1. Pick 20-30 questions a compliance officer would actually ask.
2. For each, retrieve in vector mode at `k=20`, eyeball the top results, mark
   the ones that genuinely contain the answer.
3. Add 5-10 questions that **require** combining facts from two chunks (multi-hop) —
   these are where the graph layer must prove itself.
4. Save into `eval/queries.json`, run `runEval.py`.
5. Iterate: bump `k`, change RRF weights, change graph hops, compare table-to-table.

## Reading the table

```
query     type         |        vector        |        hybrid        |        graph
                       |  R@K  P@K  MRR       |  R@K  P@K  MRR       |  R@K  P@K  MRR
q01       single-hop   |  1.00  0.40  1.000   |  1.00  0.40  1.000   |  1.00  0.20  0.500
```

- `R@K` = fraction of relevant chunks present in the top K.
- `P@K` = fraction of top K that are relevant.
- `MRR` = 1/rank of first relevant hit (1.0 means the very first result was relevant).

For graph mode, the seed chunks come from vector search but the neighbors come
from graph traversal — so on a multi-hop question, you'd expect graph's R@K to
exceed vector's even if its P@K is lower (graph trades precision for recall).
