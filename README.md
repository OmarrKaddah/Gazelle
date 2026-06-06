# Gazelle — ADIB Compliance RAG

A graph-grounded, hallucination-resistant RAG system for Arabic banking and finance compliance documents. Ingests scanned regulatory PDFs and Word documents, extracts a knowledge graph plus vector embeddings, serves a streaming chat UI with citations, role-based access control, PostgreSQL-backed chat persistence, and a graph explorer.

---

## Pipeline at a glance

```
Documents (.pdf, .docx, image)
    │
    ▼
ocr.py            ─► Doc_Out/{doc}.md            human-readable markdown
                  ─► output/{doc}.json           per-page sidecar
    │
    ▼
parser.py         ─► parsed/{doc}.json           structured ParsedElement[]
    │                                            (heading | paragraph | table | list)
    ▼
chunker.py        ─► chunks/{doc}.json           token-budgeted chunks (BGE-M3 tokenizer)
    │                                            with sectionPath, pages, accessLevel
    │
    ├── glinerExtract.py  ─► extractions/{doc}_entities.json   raw GLiNER spans
    │
    └── llmExtract.py     ─► extractions/{doc}.json            canonical entities
                                                                + LLM-extracted relationships
    │
    ▼
kgWriter.py       ─► Neo4j: (:Document)-(:Chunk)-(:Entity)-{predicate}-(:Entity)
    │
    ▼
embedding.py      ─► Neo4j: Chunk.embedding (BGE-M3 dense, 1024-dim)
                    + chunk_text fulltext index for hybrid search
    │
    ▼
retriever.py      ─► three modes (vector | hybrid | graph), filtered by user clearance
    │
    ▼
chatApi.py        ─► FastAPI: /api/login, /api/chat (SSE streaming), /api/graph, /api/info
    │
    ▼
frontend/         ─► React + Tailwind: chat with citations, graph explorer, RBAC login
```


---

## Memory Architecture

Gazelle separates conversational memory into two clearly-scoped layers so
follow-up questions work, user preferences carry across chats, and every
remembered fact is auditable.

### The problem this fixes

The original system wrote to `chat_memory` and `user_memory` on every turn
but **never read from them during inference**. Every chat call was
stateless, so multi-turn questions like *"and what about article 5?"*
could not resolve against prior turns. The "summary" field was rewritten
on every turn with just the latest exchange, and the "extracted entities"
field actually held chunk citation IDs under a misleading name.

### What changed

- `message_citations` — new table. Every assistant answer now stores its
  cited chunks with rank and similarity score, indexed per message.
- `chat_memory` — extended with `summaryTokens` and
  `lastSummarizedMessageId`. The summary is now an LLM-written rolling
  recap of older turns, produced by a debounced background task. The
  watermark column makes the summariser incremental, not quadratic.
- `user_memory` — extended with `category`
  (`preference | instruction | profile | domain`), `source`
  (`explicit | promoted | inferred`), and `evidenceChatId`. Long-term
  preferences are now consumed on every chat turn and carry a full
  provenance trail.
- `src/memory/` — new module with three responsibilities:
  - `assembler.py` packs the LLM prompt with strict per-layer token
    budgets in a canonical order.
  - `summarizer.py` updates the chat summary asynchronously, only when
    enough new turns or tokens have accumulated, with PII redaction in
    the prompt.
  - `promoter.py` lifts stable user statements (e.g. *"always answer in
    Arabic"*) into `user_memory` from a small regex allowlist, with a
    PII gate that refuses any text containing 10+ digit runs.
- `src/chatApi.py` — the chat endpoint now loads user memory, chat
  summary, and the last 4 messages, passes them to the assembler, and
  writes citations synchronously while scheduling the summariser and
  promoter as background tasks.

### Setup

The migration applies automatically on the next startup:

```bash
alembic upgrade head
```

This adds the new table and columns and is fully reversible via
`alembic downgrade -1`.

### Verifying the fix

```bash
python test_memory.py
```

The script runs 23 checks against your live PostgreSQL covering: the
promoter regex allowlist, the PII gate, the explicit-wins guarantee,
top-k user memory filtering, recent-message ordering, prompt assembly
order and structure, citation roundtrip, cascade-delete behaviour, and
chat-memory watermark persistence. All 23 are expected to pass.

For deeper background see `docs/MEMORY_ARCHITECTURE.md` (the design) and
`docs/DESIGN_RATIONALE.md` (why this design, and what alternatives were
considered and rejected).

### Files ignored on this branch

To keep the repository clean, the following are excluded via
`.gitignore`:

- Pipeline-derived data: `Doc_Out/`, `output/`, `parsed/`, `chunks/`,
  `extractions/`
- Source corpus: `Documents/` (potentially confidential)
- Local PostgreSQL data directory: `.pgdata/`
- Editor / agent session caches: `.claude/`
- Build outputs: `frontend/dist/`, `node_modules/`
- Local developer helpers: `RUN.bat`, `INSPECT.bat`, `MIGRATE.bat`,
  `bootstrap.py`, `inspect_memory.py`, PowerShell convenience scripts


<<<<<<< HEAD
=======
---

## Admin Document Publishing

A role-gated admin interface for uploading new source documents and ingesting
them into the **live** knowledge graph **incrementally** — new documents,
entities, and relationships are added without deleting or rebuilding the
existing graph.

### Frontend (Admin console)

- Users with the `Admin` role are redirected to a dedicated **Admin Console**
  on login; everyone else lands on the normal chat app. Role logic is
  centralized in `frontend/src/lib/roles.js` and enforced by
  `frontend/src/components/RequireRole.jsx`.
- `frontend/src/components/AdminPage.jsx` — drag-and-drop upload UI, selected
  file list, and a **Publish** button wired to the real backend with per-file
  success/error reporting. A **Chat with Gazelle** button switches to the chat
  UI; the sidebar gains an **Admin Console** item to return.
- `frontend/src/api/admin.js` — multipart upload to the publish endpoint.
- Modified: `App.jsx` (top-level area routing + admin login redirect),
  `Sidebar.jsx` (admin-only nav item), `Icons.jsx` (upload / file icons).

### Backend (publish endpoint + incremental ingestion)

- `POST /api/admin/documents/publish` (`src/chatApi.py`) — multipart upload,
  protected by the new `requireAdmin` dependency in `src/auth.py`
  (**server-side** role enforcement, not just the UI). Saves files to
  `Documents/`, runs ingestion off the event loop, and writes an audit log.
- `src/ingest.py` — the incremental orchestrator. Runs the existing pipeline
  stages per uploaded document and writes to Neo4j with the **MERGE-based**
  writer (`kgWriter.writeDoc`) — **no `clearDb`**, so existing graph data is
  preserved. Existing entity nodes are reused; relationships and aliases are
  de-duplicated. The global entity-embed and `deduplicate()` passes run once at
  the end so new entities link into the existing graph.
- `src/docConvert.py` — no-OCR readers: digital PDFs are read via their text
  layer (`pypdf`), Word via paragraph/table extraction. Only images and scanned
  PDFs (no text layer) fall back to the OCR vision model. Every path produces
  the same `output/{doc}.json` sidecar the parser consumes.

### Supported upload types

| Type            | Ingestion path              | Needs vision model? |
| --------------- | --------------------------- | ------------------- |
| Digital PDF     | text layer via `pypdf`      | no                  |
| Scanned PDF     | OCR fallback                | yes                 |
| Word (`.docx`)  | paragraph / table extract   | no                  |
| Images (`.png`, `.jpg`, …) | OCR              | yes                 |
| Text (`.md`, `.txt`)       | passthrough      | no                  |

### Deployment helpers

- `runners/createDb.py` — creates the PostgreSQL `gazelle` database from
  `DATABASE_URL` (no `psql` required).
- `runners/pullModels.py` — pulls every Ollama model the pipeline uses, read
  from `.env` so it stays in sync with the app.
- `docs/BANK_SETUP.md` — full server deployment checklist.

### Relevant `.env` settings

```
OLLAMA_VISION_MODEL   # OCR of scanned PDFs / images (e.g. qwen3-vl:8b-instruct-q4_K_M)
OLLAMA_EXTRACT_MODEL  # relationship extraction (defaults to OLLAMA_TEXT_MODEL)
OLLAMA_TIMEOUT        # per-request timeout in seconds for local models (default 600)
NER_STRATEGY          # llm | gliner | hybrid
CHUNKER_TYPE          # default (no model) | semantic (downloads BGE-M3 from HF)
```


---

>>>>>>> main
## Tech stack

- **OCR**: Qwen3-VL via Ollama (or llama-server)
- **Word**: docling
- **Tokenizer**: BGE-M3 (chunk sizing)
- **NER**: GLiNER `NAMAA-Space/gliner_arabic-v2.1` by default, with optional LLM-only or hybrid modes via `.env`
- **Relation extraction**: any LLM via Ollama (default `qwen2.5:72b-instruct-q4_K_M`) or Groq Cloud
- **Graph DB**: Neo4j (vector + fulltext indexes on Chunk; relationship graph on Entity)
- **Embeddings**: BGE-M3 dense (1024-dim, fp16) — stored on Chunk nodes
- **API**: FastAPI + uvicorn, SSE streaming
- **Persistence**: PostgreSQL + async SQLAlchemy + Alembic for users, chats, messages, chat memory, and user memory
- **Frontend**: Vite + React + Tailwind, cytoscape.js for graph viz
- **Auth**: PostgreSQL-backed seeded users with bcrypt passwords and bearer token sessions

---

## Repository layout

```
Graph/
├── src/                ← module code (importable Python)
├── src/db/             ← async SQLAlchemy models, sessions, and repositories
├── runners/            ← scripts (one per pipeline stage + benchmark runner)
├── alembic/            ← database migration environment and versions
├── eval/               ← retrieval evaluation harness
├── frontend/           ← React + Vite SPA
├── streamlit/          ← read-only internal dashboard (Streamlit)
├── Documents/          ← source PDFs, images, docx
├── Doc_Out/            ← OCR markdown output
├── output/             ← OCR per-page JSON sidecars
├── parsed/             ← structured ParsedElement lists
├── chunks/             ← token-budgeted chunks
├── extractions/        ← entities + relationships (GLiNER or LLM + LLM)
├── gold/               ← gold-set annotations (manual)
├── .env                ← Neo4j creds, PostgreSQL URL, Groq API key, BGE-M3 path, NER/LLM strategy
├── .env-example        ← sanitized example config
├── .env-example        ← template for local development
├── Modelfile           ← Ollama Modelfile (vision model)
├── requirements.txt
├── CLAUDE.md           ← coding conventions for Claude Code
└── README.md           ← you are here
```

---

## Files

### Pipeline modules (`src/`)

#### `src/ocr.py` — Stage 1: OCR

Renders PDF pages with `pypdfium2`, sends each page image to Qwen3-VL (Ollama or llama-server) with a carefully tuned Arabic prompt. Preserves Arabic-Indic numerals, detects tables as markdown, handles signature blocks. `process_pdf()` runs pages in parallel via `ThreadPoolExecutor`. `runOcrAndDump()` is the convenience entry point used by the runner — writes both `Doc_Out/{stem}.md` and `output/{stem}.json` (per-page sidecar that the parser later uses to recover page numbers).

#### `src/parser.py` — Stage 2: Structuring

Converts OCR markdown OR a Word document into a unified `ParsedElement` list. Two paths:

- **Markdown** (from OCR): reads `output/{doc}.json`, splits each page into blocks, classifies (`heading | table | paragraph | list`).
- **Word docx**: uses docling's `DocumentConverter`, walks `SectionHeaderItem` / `TableItem` / `ListItem` / `TextItem` natively for richer structure.

Maintains a heading stack so every element inherits a `sectionPath` like `["Chapter 3", "Article 5"]`. Tables stay atomic. Provenance fields: `docName`, `sectionPath`, `page`, `elementType`, `text`, `elementId`, `accessLevel`. Output: `parsed/{doc}.json`.

#### `src/chunker.py` — Stage 3: Chunking

Section-aware packing with overlap. Walks elements in order, groups consecutive elements with the same `sectionPath`, packs them until adding the next element would exceed the token budget (default 600, measured by BGE-M3 tokenizer). When flushing, the last element of the previous chunk carries into the next as **overlap** (preserves meaning across split sections). Tables are atomic — never split, always their own chunk. Heading-only elements are skipped (their text already lives in `sectionPath`). The leaf section heading is **prepended to chunk text** for embedding context. Output: `chunks/{doc}.json`.

#### `src/glinerExtract.py` — Stage 4a: NER

Loads the Arabic GLiNER model `NAMAA-Space/gliner_arabic-v2.1` once at module import. Pulls labels from `ontology.ENTITIES.keys()` (single source of truth). For each chunk, runs `model.predict_entities()` with threshold 0.5; emits one entity record per detected span with `chunkId`, char offsets, type, and confidence score. Output: `extractions/{doc}_entities.json` (raw spans, no deduplication).

#### `src/llmExtract.py` — Stage 4b: Relationship extraction

Two-step:

1. **`canonicalizeEntities()`** — deterministic. Groups GLiNER spans by `(text, type)`, generates kebab-case canonical IDs (`{slugified-text}-{type-lower}`), preserves chunkId provenance. No LLM call here.
2. **`extractRelationships()`** — LLM call. For each chunk, sends a focused prompt: ontology relationship spec + direction rules + the canonical entities present in this chunk + the chunk text. The LLM returns only relationships, not entities. Strict JSON output via `response_format: {type: "json_object"}`.

Parallelized via `ThreadPoolExecutor` (`PARALLEL_CHUNKS = 4`; needs `OLLAMA_NUM_PARALLEL=4` on the Ollama server). Output: `extractions/{doc}.json` (per-chunk entity list + relationships).

`OLLAMA_URL`, `OLLAMA_TEXT_MODEL`, and `OLLAMA_NUM_PARALLEL` are configurable through `.env`.

#### `src/kgWriter.py` — Stage 5: Knowledge graph

Idempotent MERGE writes into Neo4j. Schema:

```
(:Document {docName})
(:Chunk {chunkId, docName, sectionPath, pages, text, accessLevel}) -[:PART_OF]-> (:Document)
(:Entity {canonicalId, canonicalName, type, aliases})              -[:MENTIONED_IN]-> (:Chunk)
(:Entity) -[<PREDICATE> {chunkIds}]-> (:Entity)        # ISSUED_BY, GOVERNS, AMENDS, …
```

`mergeChunk` MERGEs on chunkId (creates relationship to Document). `mergeEntityWithMention` MERGEs entity, dedupes aliases via Cypher `REDUCE`, and creates the MENTIONED_IN edge in the same transaction. `mergeRelationship` interpolates the predicate as the edge type (safe — predicate is filtered against the ontology), dedupes chunkIds. **`buildTypeMap` + `isValidRelationship`** validate that subject/object types match the schema (e.g., `BankingInstitution APPLIES_TO RegulatoryBody` is rejected at write time).

Unique constraints created on `Document.docName`, `Chunk.chunkId`, `Entity.canonicalId`.

#### `src/embedding.py` — Stage 6: Vector embeddings

Loads `BGEM3FlagModel` once (path from `BGE_M3_PATH` env var, defaults to HF id). Encodes chunk text in batches of 16 with fp16. Creates a 1024-dim vector index `chunk_embedding` on `Chunk.embedding` and a Lucene fulltext index `chunk_text` on `Chunk.text` for hybrid search. `embedQuery()` is also exposed — used by the retriever to embed user questions at request time.

#### `src/retriever.py` — Stage 7: Retrieval (3 modes)

All modes pre-filter chunks by `node.docName IN $allowed` before scoring. The allowed list comes from the user's clearance via `docAccess.allowedDocs(clearance)` — chunks the user can't see never reach the LLM.

- **`vectorSearch(query, k, allowed)`** — pure semantic. Embeds the query, calls `db.index.vector.queryNodes` with overfetch (4×K) so RBAC filtering doesn't undershoot, then takes top K.
- **`hybridSearch(query, k, allowed)`** — RRF fusion of vector + Neo4j fulltext (Lucene BM25). Score = Σ 1/(60 + rank) across both rankings. Standard reciprocal rank fusion.
- **`graphSearch(query, k, hops, allowed)`** — vector-finds K seed chunks, traverses `(:Entity)-[*1..hops]-(:Entity)` from entities mentioned in those seeds (excluding `MENTIONED_IN` edges), pulls back chunks where the expanded entities are mentioned. Neighbors ranked by entity overlap count.

Top-level `retrieve(query, mode, k, hops, clearance)` dispatches.

#### `src/chatApi.py` — FastAPI server

Endpoints:

- `POST /api/login` — username/password against PostgreSQL users → returns bearer token
- `POST /api/logout` — invalidates token in PostgreSQL session storage
- `GET /api/me` — returns current user
- `GET /api/info` — providers (Ollama / Groq) with availability + access levels
- `POST /api/retrieve` — runs retriever, returns chunks (gated by clearance)
- `POST /api/chat` — runs retriever **then** streams LLM tokens via Server-Sent Events. First event is `{type:"citations", citations:[...]}`, subsequent are `{type:"token", text:"..."}`, final is `{type:"done"}`. The backend also persists the user message, assistant message, and per-chat memory in PostgreSQL.
- `GET /api/chats` — list the authenticated user's chats
- `POST /api/chats` — create a new chat for the authenticated user
- `GET /api/chats/{chatId}` — load a chat and its messages
- `PATCH /api/chats/{chatId}` — rename a chat
- `DELETE /api/chats/{chatId}` — delete a chat
- `GET /api/chats/{chatId}/memory` / `PUT /api/chats/{chatId}/memory` — manage chat memory
- `GET /api/memory/user` / `PUT /api/memory/user/{memoryKey}` — manage long-term per-user memory
- `GET /api/graph` — returns Cytoscape-shaped JSON for the graph explorer; supports `?search=`, `?type=`, `?seed=`, `?hops=` query params.

Provider routing: `PROVIDERS` dict supports both `ollama` (no auth) and `groq` (Bearer key from `GROQ_API_KEY`). Per-request `provider` field selects.

LLM grounding is enforced via a **system message** (`SYSTEM_PROMPT`) with strict rules: cite every claim by chunkId, refuse with an exact bilingual sentence when context is insufficient, no general-knowledge fallback.

If `frontend/dist/` exists, it's mounted at `/` for production serving.

### Configuration & domain (`src/`)

#### `src/ontology.py` — Entity & relationship vocabulary (v0)

11 entity types (`Person`, `BankingInstitution`, `RegulatoryBody`, `Law`, `Article`, `License`, `Document`, `FinancialInstrument`, `RegulatoryRequirement`, `MonetaryAmount`, `Date`) and 9 relationship types with `(allowedSubjectTypes, allowedObjectTypes)` tuples. **Single source of truth** — GLiNER labels, LLM prompt, and KG validation all import from here. Edit this file to iterate the ontology.

#### `src/docAccess.py` — Access-level taxonomy

Defines `LEVELS = ['public', 'internal', 'confidential', 'restricted']` (rank-ordered). `DOC_ACCESS` maps `docName → level` (defaults to `internal` if not listed). `allowedDocs(clearance)` returns the list of docs visible at a given clearance level. Mock data marks `gazma2` confidential and `table_ar` restricted for testing.

#### `src/auth.py` — Authentication

Async authentication backed by PostgreSQL. The seed users (`omar` / `sara` / `ahmed` / `guest`) are inserted by the initial Alembic migration with bcrypt password hashes. `user_sessions` stores bearer token hashes, so auth survives server restarts. `getCurrentUser()` is a FastAPI `Depends(...)` that reads `Authorization: Bearer <token>` and returns the current user object — applied to every protected endpoint.

### Runners (`runners/`)

Each runner is a thin script that imports `_bootstrap` (adds `src/` to `sys.path` and chdirs to project root), then sets a `docName` or other input variable at the top, then calls the relevant module function.

| Runner            | Input                                  | Output                                         |
| ----------------- | -------------------------------------- | ---------------------------------------------- |
| `runOcr.py`       | `imagePath = "Documents/x.pdf"`        | `Doc_Out/x.md`, `output/x.json`                |
| `runParser.py`    | `source = "Doc_Out/x.md"` (or `.docx`) | `parsed/x.json`                                |
| `runChunker.py`   | `docName = "x"`                        | `chunks/x.json`                                |
| `runGliner.py`    | `docName = "x"`                        | `extractions/x_entities.json`                  |
| `runLlm.py`       | `docName = "x"`                        | `extractions/x.json`                           |
| `runKg.py`        | `docName = "x"`                        | Neo4j writes                                   |
| `runEmbed.py`     | `docName = "x"`                        | `Chunk.embedding` populated in Neo4j           |
| `runRetrieve.py`  | CLI args: `query mode k hops`          | prints retrieved chunks (clearance=restricted) |
| `runApi.py`       | —                                      | starts uvicorn `:8000` with reload             |
| `sampleChunks.py` | —                                      | seeds `gold/sample.json` for hand-annotation   |

#### `runners/_bootstrap.py`

Three lines: prepends `src/` to `sys.path`, chdirs to project root. Imported (not called) at the top of every runner so all the in-tree imports and relative paths just work.

### Frontend (`frontend/`)

Vite + React + Tailwind SPA, ADIB navy + gold + cream theme.

| File                               | Purpose                                                                                                                                                                                                                                                                                                                            |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `package.json`                     | Deps: react, vite, tailwind, cytoscape, cytoscape-fcose, react-cytoscapejs                                                                                                                                                                                                                                                         |
| `vite.config.js`                   | Dev server on `:5173`, proxies `/api` → `:8000`                                                                                                                                                                                                                                                                                    |
| `tailwind.config.js`               | Custom palette: `brand` (navy), `gold`, `cream`, `ink` + keyframes                                                                                                                                                                                                                                                                 |
| `postcss.config.js`                | Tailwind + autoprefixer                                                                                                                                                                                                                                                                                                            |
| `index.html`                       | Inter + Fraunces + JetBrains Mono fonts via Google Fonts                                                                                                                                                                                                                                                                           |
| `src/main.jsx`                     | React entry point                                                                                                                                                                                                                                                                                                                  |
| `src/index.css`                    | Tailwind import + scrollbar styling, streaming caret animation, citation-flash highlight                                                                                                                                                                                                                                           |
| `src/App.jsx`                      | Top-level: gates on auth → renders `Login` or `Sidebar` + main content. View routing (chat / graph). ⌘N keyboard shortcut for new chat.                                                                                                                                                                                            |
| `src/components/Login.jsx`         | Login screen with mock-user shortcut buttons (autofill).                                                                                                                                                                                                                                                                           |
| `src/components/Sidebar.jsx`       | Collapsible sidebar (260px / 56px). New-chat button, Tools nav (Chat / Graph Explorer), Recent chats list (hover-delete), user footer with role + clearance badge + sign-out menu.                                                                                                                                                 |
| `src/components/ChatView.jsx`      | TopBar showing model, Welcome screen with suggestions, message list with inline `[chunkId]` citations rendered as clickable superscript pills (jump + flash the source card), Composer with mode pills + settings popover (k, hops, provider toggle Ollama/Groq), SSE streaming with token-by-token render and gold pulsing caret. |
| `src/components/GraphExplorer.jsx` | Cytoscape canvas with `fcose` layout. Search bar + refresh button up top, color-coded entity-type legend (collapsible), click-to-select with all-other-faded effect, slide-in inspector panel with "Expand neighbors" button. Custom Cytoscape stylesheet for ADIB palette.                                                        |
| `src/components/Icons.jsx`         | All SVG icons including the gazelle-silhouette logo mark (gold on navy).                                                                                                                                                                                                                                                           |
| `src/hooks/useChats.js`            | Per-user conversation history loaded from `/api/chats` and `/api/chats/{chatId}`.                                                                                                                                                                                                                                                  |
| `src/hooks/useAuth.js`             | Token + user persisted to `localStorage`. `authHeaders()` helper used by every protected fetch. Verifies token on mount.                                                                                                                                                                                                           |

### Eval (`eval/`)

#### `eval/queries.json`

Hand-curated gold queries with `id`, `query`, `type` (`single-hop` / `multi-hop` / `multi-step`), `relevantChunks` (chunkIds you'd want surfaced), and `expectedAnswer`. Seeded with 5 starter queries for ADIB compliance topics; you fill in `relevantChunks` after eyeballing what the retriever returns.

#### `eval/runEval.py`

Runs all three retrieval modes against every annotated query. Computes `Recall@K`, `Precision@K`, `MRR` per query per mode, plus averages. Prints a side-by-side table with a multi-hop subset broken out separately (where graph mode should outperform vector). Saves `eval/results.json`. Run from project root: `python eval\runEval.py`.

#### `eval/README.md`

Explains methodology for evaluating each layer (retrieval / extraction / end-to-end), the three IR metrics and how to read them, suggested workflow for building the gold set, and pointers to RAGAS for end-to-end RAG eval.

### Data directories

- **`Documents/`** — source PDFs, Word docs, scanned images. Input to OCR.
- **`Doc_Out/`** — OCR-extracted markdown, one file per source. Human-readable.
- **`output/`** — OCR per-page JSON sidecars `[{page, markdown}]`. Used by parser to recover page numbers.
- **`parsed/`** — `ParsedElement[]` per doc. Structured normalized form, the parser's output.
- **`chunks/`** — token-budgeted chunks per doc. The unit of retrieval.
- **`extractions/`** — `{doc}_entities.json` (raw GLiNER spans) and `{doc}.json` (canonical entities + LLM relationships).
- **`gold/`** — manual annotations (entity & relationship gold set, optional retrieval gold).

### Top-level config files

- **`.env`** — `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `DATABASE_URL`, `GROQ_API_KEY` (optional), `GROQ_MODEL`, `OLLAMA_TEXT_MODEL`, `BGE_M3_PATH`.
- **`.env-example`** — starter template for local setup.
- **`alembic/`** — async SQLAlchemy/Alembic migrations.
- **`requirements.txt`** — Python deps.
- **`.env-example`** — sanitized example config for NER, Ollama, Neo4j, embeddings, and pipeline flags.
- **`Modelfile`** — Ollama Modelfile for the vision model used by OCR.
- **`CLAUDE.md`** — coding conventions for Claude Code (camelCase functions, no defensive code, etc.).

---

## Running end-to-end

### Prerequisites

```powershell
# Python (in your conda env)
pip install -r requirements.txt

# Or use the Makefile shortcut
make install

# Copy the example env and fill in your secrets
copy .env-example .env

# PostgreSQL must be running locally or reachable by DATABASE_URL
# Example: postgresql+asyncpg://postgres:postgres@localhost:5432/gazelle

# Run the initial database migration and seed users
alembic upgrade head

# Or use the Makefile shortcut
make upgrade

# Frontend
cd frontend
npm install
cd ..

# Or use the Makefile shortcut
make install-frontend

# Local services
ollama serve                               # in its own terminal
# Neo4j running on bolt://localhost:7687

# .env populated with at least:
#   NEO4J_URI=bolt://localhost:7687
#   NEO4J_USER=neo4j
#   NEO4J_PASSWORD=...
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/gazelle
#   BGE_M3_PATH=C:/Users/.../bge-m3/snapshots/<hash>
```

### Database and migration commands

Use these while developing the PostgreSQL layer:

```powershell
# Apply all migrations
alembic upgrade head

# Makefile shortcut
make upgrade

# Roll back one migration
alembic downgrade -1

# Makefile shortcut
make downgrade

# Create a new migration after model changes
alembic revision --autogenerate -m "describe the change"

# Makefile shortcut
make migrate MSG="describe the change"

# Inspect current migration state
alembic current

# Makefile shortcut
make current

# Show migration history
alembic history

# Makefile shortcut
make history
```

The initial migration seeds the four login users, so there is no separate seed command to run.

### Per-document ingestion (run once per source doc)

```powershell
# Edit the imagePath in runners/runOcr.py to point at the PDF, then:
python runners\runOcr.py        # OCR
python runners\runParser.py     # structure
python runners\runChunker.py    # chunk
python runners\runGliner.py     # NER
python runners\runLlm.py        # relations
python runners\runKg.py         # write to Neo4j
python runners\runEmbed.py      # embeddings + indexes
```

### Makefile shortcuts

```powershell
# Install Python deps
make install

# Install frontend deps
make install-frontend

# Run the API
make run-api

# Run the frontend dev server
make run-frontend

# Build the frontend
make build-frontend

# Quick backend syntax check
make py-compile

# Run the evaluation harness
make eval

# Clean common build artifacts
make clean

# Optional: compare gliner / llm / hybrid NER strategies on the same chunk file
python runners\runNerBenchmark.py chapter_3 --output ner_benchmark.json
```

### Serve

```powershell
# Terminal A
python runners\runApi.py        # FastAPI :8000

# Terminal B
cd frontend
npm run dev                     # Vite :5173 with /api proxy
```

You can also run the same services with the Makefile:

```powershell
# Terminal A
make run-api

# Terminal B
make run-frontend
```

Open http://localhost:5173 → log in (any mock user) → start chatting.

### Streamlit dashboard

The repo also includes a separate read-only internal dashboard in `streamlit/` that reuses the same FastAPI backend.

```powershell
pip install -r requirements.txt
streamlit run streamlit\app.py
```

Set `GAZELLE_API_URL` if the API is not running on `http://localhost:8000`.

### Evaluate

```powershell
# After ingesting a doc and populating eval/queries.json with relevantChunks
python eval\runEval.py

# Or
make eval
```

---

## Pipeline order summary (what depends on what)

```
runOcr      ─►  Doc_Out/, output/
runParser   ─►  parsed/                         (needs output/ sidecar)
runChunker  ─►  chunks/                         (needs parsed/)
runGliner   ─►  extractions/_entities.json     (needs chunks/, uses GLiNER or hybrid path)
runNerBenchmark ─► timing/results for gliner | llm | hybrid
runLlm      ─►  extractions/.json              (needs chunks/ AND extractions/_entities.json)
runKg       ─►  Neo4j                          (needs chunks/ AND extractions/.json)
runEmbed    ─►  Neo4j Chunk.embedding          (needs Neo4j chunks already written by runKg)
runApi      ─►  serves frontend                (needs Neo4j + ollama running)
```

If any stage is skipped, downstream stages fail silently or with empty results — re-run from the earliest missing step.

### Useful development commands

```powershell
# Backend syntax check after edits
python -m py_compile src\chatApi.py src\auth.py src\db\models.py src\db\session.py

# Run the API server
python runners\runApi.py

# Build the frontend for production validation
cd frontend
npm run build

# Start the frontend dev server
npm run dev

# Run the evaluation harness
python eval\runEval.py
```

---

## Key design constraints

- **Hallucination resistance**: every LLM-generated claim is forced to cite a `[chunkId]`; no-context queries refuse with an exact bilingual sentence. Implemented via a strict system prompt.
- **Provenance**: every chunk, entity, and relationship carries `chunkIds` back to source. Citations in the chat are clickable and scroll to the verbatim chunk text.
- **Access control at retrieval**: chunks the user can't see never reach the LLM. Filtered in Cypher (`WHERE node.docName IN $allowed`), not just hidden in the UI.
- **Chat persistence**: each authenticated user has isolated chats, messages, and memory in PostgreSQL. The frontend does not own persistence.
- **Schema-validated extraction**: entities are typed against the ontology; relationships are dropped if subject/object types don't match the schema.
- **Single source of truth**: ontology lives in one Python file, imported by GLiNER, LLM, and KG validation alike.
- **Configurable NER strategy**: choose `gliner`, `llm`, or `hybrid` from `.env` to match the hardware and document mix.
