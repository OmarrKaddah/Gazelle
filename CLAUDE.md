# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

**Gazelle** — a graph-grounded, hallucination-resistant RAG system for banking and finance compliance/regulatory documents (currently: Central Bank of Egypt material for ADIB). Users interact via a chatbot UI that answers compliance questions with chunk-level citations, grounded in a knowledge graph + vector hybrid retrieval pipeline.

**Design constraint:** every stage must preserve provenance (source doc → page → chunk → entity → answer) so the chatbot can cite its sources verbatim. Hallucination resistance comes from strictly grounding answers in graph-traversed, cited evidence rather than free-form generation.

## Architecture

```
Documents/ (PDFs/images)
       │
       ▼
src/ocr.py          → Doc_Out/*.md         (Qwen3-VL OCR, Arabic)
       │
       ▼
src/parser.py       → parsed/*.json        (structure extraction)
       │
       ▼
src/chunker.py      → chunks/*.json        (token-bounded, section-aware)
       │
       ├──► src/embedding.py               (BGE-M3 via Ollama → Neo4j vector index)
       │
       ├──► src/glinerExtract.py           → extractions/*_entities.json
       │           (GLiNER Arabic NER)
       │
       └──► src/typedOntologyExtract.py   → extractions/*.json   (RETIRED typed lineage)
                   (Ollama LLM relation extraction, uses gliner output as entity list)
                            │
                            ▼
                   src/typedKgWriter.py     (writes Chunk/Entity/Relation nodes to Neo4j; RETIRED)
                            │
                   src/entityEmbedding.py   (BGE-M3 embeddings on canonical entities)
                            │
                   src/entityAlign.py       (cosine-sim deduplication of canonical entities)

RETRIEVAL (src/retriever.py)
   vector  → Neo4j vector index (chunk_embedding)
   hybrid  → vector + fulltext, RRF fused
   graph   → entity seed lookup → path traversal → scored chunks

CHAT API (src/chatApi.py, FastAPI)
   POST /api/chat   → retrieve chunks → stream LLM answer with [chunkId] citations
   GET  /api/graph  → Neo4j entity/edge query for the graph explorer
   Auth: bearer token, SHA-256 hashed in PostgreSQL user_sessions

FRONTEND (frontend/, React + Vite + Tailwind + Cytoscape.js)
   Chat UI with streaming, citation display, chat history
   Graph Explorer: Cytoscape.js force layout, entity search, hop expansion
```

## Services Required

| Service | Purpose | Default |
|---------|---------|---------|
| Ollama | OCR (`qwen3-vl:8b-instruct-q4_K_M`), embed (`bge-m3`), extract + chat (`granite4.1:8b`) | `localhost:11434` |
| Neo4j | Graph + vector + fulltext indexes | `NEO4J_URI` in `.env` |
| PostgreSQL | Users, sessions, chats, messages, memory, audit | `DATABASE_URL` in `.env` |

## Environment Variables (`.env`)

```
# Required
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
DATABASE_URL=postgresql+asyncpg://...

# Optional overrides (defaults in src/config.py)
GROQ_API_KEY=...
OLLAMA_EXTRACT_MODEL=granite4.1:8b
OLLAMA_CHAT_MODEL=granite4.1:8b
GROQ_MODEL=llama-3.3-70b-versatile
OLLAMA_EMBED_MODEL=bge-m3
BGE_M3_PATH=BAAI/bge-m3
```

## Running the System

**Database migrations** (must run once before first API start):
```bash
alembic upgrade head
```

**API server** (from repo root):
```bash
python runners/runApi.py
```

**Frontend dev** (proxies `/api` to `localhost:8000`):
```bash
cd frontend && npm run dev
```

**Frontend production build** (served by FastAPI as static files):
```bash
cd frontend && npm run build
```

**Full ingestion pipeline** (from repo root, processes all docs in `Documents/`):
```bash
python run.py
```

**Individual pipeline stages** (all must be run from repo root):
```bash
python runners/runOcr.py
python runners/runParser.py
python runners/runChunker.py
python runners/runEmbed.py
python runners/runGliner.py
python runners/runLlm.py
python runners/runKg.py
```

## Code Layout

```
src/             All importable modules (added to sys.path by runners/_bootstrap.py)
runners/         Entry-point scripts — each starts with `import _bootstrap`
run.py           Full pipeline orchestrator (skip-if-exists logic per stage)
alembic/         PostgreSQL migrations
frontend/        React + Vite app
graphTraversal/  PPR/HippoRAG retrieval-upgrade subsystem (own _bootstrap, imports src/)
musique/         MuSiQue benchmark: eval harness + versioned eval_results/
docs/            PROCESS.md (PPR design + eval log), GLOBAL_PLAN.md (global arm plan)
Documents/       Source PDFs
Doc_Out/         OCR output markdown
parsed/          Parser output JSON
chunks/          Chunked text JSON
extractions/     GLiNER entities (*_entities.json) + LLM relations (*.json)
```

**`runners/_bootstrap.py`** inserts `src/` into `sys.path` and `chdir`s to repo root. All `runners/` scripts must start with `import _bootstrap` and be run from any directory — they navigate to root themselves.

## Key Modules

- **`src/ontology.py`** — single source of truth for entity types (`ENTITIES`), relationship schema (`RELATIONSHIPS`), and bilingual relation descriptions for semantic scoring (`RELATIONSHIP_DESCRIPTIONS`). Both extraction stages and the retriever read from here.
- **`src/config.py`** — all tuneable constants (thresholds, model names, batch sizes, retrieval parameters).
- **`src/docAccess.py`** — per-document clearance levels (`DOC_ACCESS` dict). Users with `clearance` field can only retrieve docs at or below their level.
- **`src/retriever.py`** — three retrieval modes. Graph mode: embed query → seed entities → path traversal → score paths by entity+rel cosine sim → return top-k chunks with path metadata.
- **`src/chatApi.py`** — FastAPI app. The `SYSTEM_PROMPT` enforces strict grounding (cite every claim by `[chunkId]`, refuse if context is insufficient). Temperature is always 0.
- **`src/llmTriples.py`** — LLM-based OpenIE (subject, predicate, object) extraction per chunk, multi-backend (`BACKENDS` dict: Ollama, Groq, OpenRouter, Gemini). `callLLM(prompt, backend)` is the shared entry point reused by the router and global arm.
- **`src/kgBuild.py`** — entity-layer + edge writers for the PPR graph: co-mention (`COOCCURS_WITH`), `writeTripleEdges` (maps triple endpoints back to canonicalIds, drops unmatched orphans).
- **`src/router.py`** — Stage-1 query router for the GraphRAG arm: one LLM judgment classifying a query as `'global'` (corpus-wide sensemaking → community summaries) or `'local'` (specific fact → PPR retrieval). Gazelle's own design — no published classifier to copy.

## Graph Traversal Subsystem (`graphTraversal/`) — current branch work

This is a **separate, self-contained subsystem** for the retrieval upgrade, not part of the `src/` ingestion/chat pipeline. It replaces the old fixed-depth k-hop traversal in `src/retriever.py` (which stays untouched for the production chat path) with **Personalized PageRank over the entity graph**, following HippoRAG. Benchmarked against **MuSiQue** (gold supporting paragraphs → recall@K), not the CBE corpus.

- **Own bootstrap.** `graphTraversal/_bootstrap.py` (and `musique/_bootstrap.py`) mirror `runners/_bootstrap.py`: they add `src/` to `sys.path` and `chdir` to repo root. Every script in these dirs starts with `import _bootstrap`. `graphTraversal/` modules import freely from `src/` (e.g. `config`, `llmTriples`).
- **`ppr.py`** — Personalized PageRank (power iteration over a CSR adjacency, query-seeded teleport vector). **`seeder.py`** — query embedding → top-K entity seeds by cosine, linear-normalised to a seed mass vector. **`loadGraph.py`** — Cypher edge rows → sparse adjacency (symmetrised, `undirected=True`).
- **`retrieve.py`** — `RetrievalIndex` loads all heavy state once (entity embeddings, entity-entity adjacency, entity→chunk map) so per-query cost is ~300 ms. Edge layers are toggled by flags: `coMentionEdges`, `tripleEdges`, `entityAlignment` (synonym edges). PPR walks **only** entity-entity edges; `MENTIONED_IN` is used separately to project entity scores onto chunks.
- **`synonyms.py`** — entity alignment: `SYNONYM` edges between entities with high name-embedding cosine + same type + a token-subset filter to kill structural false positives.
- **`khop.py`** — the old k-hop algorithm reimplemented standalone, for the apples-to-apples v0 comparison on the same KG.
- **`leiden.py`** — from-scratch Leiden community detection (local move + refinement + aggregation). `leidenHierarchy(adj)` returns the partition at every level, finest→root; `leiden()` wraps the root level. Validated on `datasets/` (Cora, football, email). `clusterMetrics.py`, `validateLeiden.py`, `plots.py`, `cora.py` are its validation/figures tooling.
- **`src/community.py`** (Stage 4 of the global arm) — `writeCommunities(hierarchy, idxToId, corpus)` persists a Leiden hierarchy to Neo4j as `(:Community {id, level, corpus})` + `(:Entity)-[:IN_COMMUNITY {level}]->(:Community)` + `(:Community)-[:PARENT]->(:Community)`. `level` 0 = root; `PARENT` is assigned by plurality vote (levels don't always strictly nest). Run via `graphTraversal/runCommunities.py`; pure builders tested in `graphTraversal/testCommunity.py`. Skeleton only — summaries (Stage 3) are written onto these nodes later.
- **Eval harness** lives in `musique/eval.py`, writing one versioned JSON per run to `musique/eval_results/v{N}_{label}.json` (full config + per-question gold/retrieved chunkIds). PPR best so far: **recall@5 = 0.364** (v4/v7b); see `docs/PROCESS.md` §5 for the full version log.

**PPR graph schema** (Neo4j, `docName`-scoped, distinct from the CBE Arabic ontology): `(:Entity {canonicalId, canonicalName, type, aliases})` is the concept layer PPR walks; `(:Chunk)` is the passage layer; edges are `COOCCURS_WITH {count}`, `SYNONYM {cosine}`, `TRIPLE {count, predicates}` (entity-entity, walked by PPR) and `MENTIONED_IN` (entity→chunk, projection only).

## Graph construction — TWO routes (the canonical forward direction)

Graph building is consolidated to **two routes** (the earlier typed and bare-triple lineages are retired — see below). Both share the prep pipeline (ocr → parser → chunker → embedding → chunks + vector index) and both are retrieved by PPR; they diverge **only** at graph construction:

- **Route 1 — Classical:** GLiNER entities + co-mention `COOCCURS_WITH` edges (`glinerExtract.py` → `kgBuild.buildEntityLayer`). Cheap, deterministic **baseline**. Retrieval only — no descriptions, so it cannot feed community summaries.
- **Route 2 — LLM (deployed):** one LLM pass extracts entities **+ relationships + descriptions** (`graphExtract.py` → `graphBuild.py` → `(:Entity {description})-[:RELATED {weight, description}]->(:Entity)`). The only route that feeds the **global arm** (Leiden communities + summaries). Uses `llmTriples.callLLM` with the `openrouter` backend (configurable via `GRAPH_EXTRACT_BACKEND`). Route 2 == Stages 5+6 of `docs/GLOBAL_PLAN.md`. **Built.**

**End-to-end runner:** `runners/runPipeline.py` is the consolidated orchestrator — shared prep (ocr → parser → chunker → embed) then branches on `GRAPH_ROUTE` (`1` = Route 1 GLiNER+co-mention via `kgBuild.buildEntityLayer`; `2` = Route 2 via `graphExtract`+`graphBuild`). Strategy knobs all live in `config.py`: `CHUNKER_TYPE`, `NER_STRATEGY`, `GRAPH_ROUTE`, `GRAPH_EXTRACT_BACKEND`. (The older `run.py`/`runAll.py` remain but run the RETIRED typed lineage.)

**Retired but kept on disk as documented prior effort (do not delete):** the ontology-**typed** pipeline, renamed for clarity to `typedOntologyExtract.py` (was `llmExtract.py`) + `typedKgWriter.py` (was `kgWriter.py`), still wired into the old `run.py`/`runAll.py`/`runLlm.py`/`runKg.py`; the bare-**triples** intermediate (`llmTriples` bare prompt + `kgBuild.writeTripleEdges` + `runTripleEdges.py`, PPR v7).

## Design Docs (`docs/`) — read before extending the graph work

- **`docs/PROCESS.md`** — the thesis-grade record of the PPR/HippoRAG local-retrieval upgrade: algorithmic background, every design choice, and the complete versioned evaluation log (v0–v7b) with the measured k-hop-vs-PPR trade-off and the structural gap to HippoRAG. The authority for *why* the retrieval pipeline is shaped the way it is.
- **`docs/GLOBAL_PLAN.md`** — the forward plan for the **global arm**: GraphRAG-style query-focused summarization (router → map-reduce over C0 Leiden community summaries → cited answer). Lists the staged module breakdown (`router`, `globalSearch`, `communitySummary`, `community`, `graphBuild`, `graphExtract`, `sensemakingEval`) and the front-to-back build order. Some stages built (router, Leiden), most planned.

## Coding Conventions

- **Minimal** — no defensive slop. No try/except wrappers, no null guards unless a real failure mode demands it.
- **No inline imports** — all imports at the top of the file.
- **camelCase function names** — `parseDoc`, not `parse_doc`. Overrides Python snake_case norm.
- **One function = one thing** — single responsibility, small surface.
- **No unnecessary fallbacks** — if it fails, let it fail.

Apply to every edit. Match the new convention when touching old code.

## Domain-Specific Notes

**OCR prompt in `src/ocr.py` is carefully tuned** for Arabic legal/regulatory documents:
- Preserves Arabic-Indic numerals (٠١٢٣٤٥٦٧٨٩) — do not convert to Western digits
- Detects tables, outputs as markdown
- Handles multi-level signature blocks and RTL hierarchical structure

Casual edits to this prompt can degrade output quality — test against existing samples in `Doc_Out/` before changing.

**`ontology.py` is schema** — adding/removing entity or relationship types here affects GLiNER labels, LLM extraction prompts, KG writer validation, and retriever relation-type scoring all at once. Changes must be intentional.
