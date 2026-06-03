# src/entityEmbedding.py

Walks every canonical Entity node in Neo4j that lacks an embedding, generates one with BGE-M3, and writes it back. Also creates the cosine-similarity vector index if it's missing.

## Line-by-line

**Lines 1-3 — imports**

- `GraphDatabase` is the Neo4j driver entry point.
- `embedTexts` is the project's batched BGE-M3 helper from `src/embedding.py`.
- Config constants supply credentials, the embedding dimension, and the per-batch entity count.

**Lines 6-14 — `setupEntityIndex(tx)`**

Runs a Cypher statement that creates a vector index named `entity_embedding` on `(:Entity).embedding`. `IF NOT EXISTS` makes the call idempotent so this is safe to run on every embed pass. The `OPTIONS` map declares dimension and similarity function (`cosine`) — these must match `EMBED_DIM` and how `embedTexts` produces its vectors.

**Lines 17-23 — `loadPending(tx)`**

Selects every Entity whose `embedding` property is null and returns the canonicalId, canonicalName, and aliases for each. `[dict(r) for r in res]` converts Neo4j Record objects into plain dicts for downstream use.

**Lines 26-31 — `writeEmbedding(tx, canonicalId, embedding)`**

Single-row UPDATE: finds the Entity by canonicalId and sets its `embedding` property. Parameterized via `$id`/`$emb` rather than string interpolation — both for safety and because Neo4j only accepts vector params as named parameters.

**Lines 34-37 — `buildEmbedText(entity)`**

- Comment explains why aliases are concatenated: embedding the canonical name alone leaves alternate surface forms (abbreviations, transliterations) further away in vector space than they should be.
- Builds the candidate list `[name] + (aliases or [])` — the `or []` guard handles the case where `aliases` is null/None from Neo4j.
- `dict.fromkeys(p for p in parts if p)` deduplicates while preserving insertion order and filters out empty strings.
- `' / '.join(...)` produces the final embedding input, e.g. `"البنك المركزي المصري / Central Bank of Egypt / CBE"`.

**Lines 40-52 — `embedEntities()`**

Top-level orchestrator.

- Opens a Neo4j driver, then a session. The `with` blocks guarantee both are closed even if the loop crashes.
- `session.execute_write(setupEntityIndex)` runs the index DDL in a write transaction.
- `session.execute_read(loadPending)` runs the pending-entity query in a read transaction.
- `print(f"Embedding {len(entities)} entities", flush=True)` — progress line; `flush=True` forces the buffer out so the line appears immediately even when stdout is piped.
- The main loop slices the pending list into `ENTITY_EMBED_BATCH`-sized batches.
  - `texts = [buildEmbedText(e) for e in batch]` builds the embedding inputs.
  - `embs = embedTexts(texts)` calls BGE-M3 once per batch.
  - The inner `zip` loop writes each embedding back. Each `writeEmbedding` call is its own write transaction — not ideal for throughput but keeps each entity independently committed (a failure halfway through doesn't roll back the whole batch).
  - `min(i + ENTITY_EMBED_BATCH, len(entities))` clamps the progress count on the final partial batch.
