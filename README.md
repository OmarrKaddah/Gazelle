# Gazelle — Graph-Grounded RAG for Banking Compliance

Gazelle is a hallucination-resistant Retrieval-Augmented Generation (RAG) chatbot for Arabic banking compliance documents, built for Central Bank of Egypt (CBE) regulatory material at ADIB. It answers compliance questions with chunk-level citations grounded in a hybrid vector + knowledge-graph retrieval pipeline. Every answer traces back to a specific source document, page, and chunk — the system refuses to answer rather than fabricate.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Quick Start](#2-quick-start)
3. [Prerequisites](#3-prerequisites)
4. [External Models and Datasets](#4-external-models-and-datasets)
5. [Installation](#5-installation)
6. [Environment Variables](#6-environment-variables)
7. [Database Setup](#7-database-setup)
8. [Ingestion Pipeline](#8-ingestion-pipeline)
9. [OCR Preprocessing (Handwriting Detection)](#9-ocr-preprocessing-handwriting-detection)
10. [Graph Construction — Two Routes](#10-graph-construction--two-routes)
11. [Classical NER Subsystem (CRF)](#11-classical-ner-subsystem-crf)
12. [Graph Traversal and PPR Retrieval](#12-graph-traversal-and-ppr-retrieval)
13. [Community Detection and Global Arm](#13-community-detection-and-global-arm)
14. [Query-Focused Summarization](#14-query-focused-summarization)
15. [Chat API](#15-chat-api)
16. [Frontend](#16-frontend)
17. [Access Control](#17-access-control)
18. [Context Memory](#18-context-memory)
19. [MuSiQue Benchmark Evaluation](#19-musique-benchmark-evaluation)
20. [Sensemaking Benchmark (AP News)](#20-sensemaking-benchmark-ap-news)
21. [Router Training](#21-router-training)
22. [Project Layout](#22-project-layout)
23. [Testing and Coverage](#23-testing-and-coverage)

---

## 1. Architecture Overview

```
Documents/ (Arabic PDFs / scanned images)
       |
       v
src/ocr.py          --> Doc_Out/*.md          (Qwen3-VL OCR, Arabic-aware)
       |
       v
src/parser.py       --> parsed/*.json         (structure extraction: sections, articles)
       |
       v
src/chunker.py  or  --> chunks/*.json         (token-bounded, section-aware chunks)
src/semantic_chunker.py
       |
       +---> src/embedding.py                 (BGE-M3 --> Neo4j vector index)
       |
       +---> src/glinerExtract.py             --> extractions/*_entities.json
       |          (GLiNER Arabic NER)             NER_STRATEGY=gliner (default)
       |     -- OR --
       +---> runners/runNerPipeline.py      --> extractions/<docName>_entities.json
       |          (CRF classical NER)             NER_STRATEGY=classical
       |                                         Route 1 (classical baseline)
       |     -- OR --
       |
       +---> src/graphExtract.py             --> extractions/*_graph.json
       |          (LLM entities + relationships) Route 2 (deployed)
       |
       +---> src/kgBuild.py   (Route 1)      --> Neo4j: Entity + COOCCURS_WITH
       |     src/graphBuild.py (Route 2)     --> Neo4j: Entity + RELATED{predicate,description}
       |
       +---> src/entityEmbedding.py          --> BGE-M3 embeddings on canonical entity names
       +---> graphTraversal/synonyms.py      --> SYNONYM edges (cosine deduplication)

RETRIEVAL (src/retriever.py)
   vector  --> Neo4j vector index (chunk_embedding)
   hybrid  --> vector + fulltext, RRF fused
   graph   --> entity seed lookup --> Personalized PageRank --> scored chunks

GLOBAL ARM (for sensemaking / corpus-wide queries)
   graphTraversal/leiden.py    --> Leiden community detection over entity graph
   src/community.py            --> persist hierarchy to Neo4j
   src/communitySummary.py     --> LLM report per community
   src/globalSearch.py         --> map-reduce over community summaries

QUERY ROUTING (src/router.py)
   local  --> specific fact/entity --> PPR retrieval
   global --> themes/trends/comparisons --> community map-reduce

CHAT API (src/chatApi.py, FastAPI)
   POST /api/chat   --> retrieve chunks --> stream LLM answer with [chunkId] citations
   GET  /api/graph  --> Neo4j entity/edge query for the graph explorer
   Auth: bearer token, SHA-256 hashed in PostgreSQL

FRONTEND (frontend/, React + Vite + Tailwind + Cytoscape.js)
   Chat UI with streaming, citation display, chat history
   Graph Explorer: Cytoscape.js force layout, entity search, hop expansion
```

---

## 2. Quick Start

**Get up and running in 5 minutes using a pre-built graph.**

### Step 1: Download Requirements

Clone the repository and install all dependencies:

```bash
git clone <repository-url>
cd Gazelle

# Install Python and frontend dependencies
make install install-frontend install-test

# Download Ollama models (required for chat and embeddings)
make setup-ollama

# This downloads:
# - qwen3-vl (OCR model)
# - bge-m3 (embedding model)
# - granite4.1 (chat model)
```

### Step 2: Start Services

**Neo4j and Ollama must be running.**

#### Option A: Using Docker (Recommended)

```bash
# Start Neo4j and Ollama with one command
make services-docker

# Services available at:
#   Neo4j:  http://localhost:7474 (user: neo4j, password: your_password)
#   Ollama: localhost:11434
```

#### Option B: Installed Locally

- Start **Neo4j** manually from https://neo4j.com/download/
- Start **Ollama** manually from https://ollama.com/download/

### Step 3: Setup Database and Configuration

```bash
# Initialize SQLite database and create default users
make quick-start

# This:
# - Creates ./gazelle.db (SQLite)
# - Initializes default seed users (omar, sara, ahmed, guest)
# - Copies .env.example to .env

# Edit .env with your API keys if needed
nano .env
```

### Step 4: Download Pre-built Graph

Instead of running the full OCR→Parse→Chunk→NER→KG pipeline, download a pre-built graph dump:
To test the global sense making feature download the ap_news.jsonl and set retrieval mode to auto and set llm summarizer or use direct chunks

```bash
mkdir -p dumps
# Download the graph dump
# 📥 Download from:
https://drive.google.com/drive/folders/14TZO9BMip4-8wX2tgVZ78EYoUlm5t7IU
#
# Place the file in: dumps/graph.jsonl
# (Create the dumps/ directory if it doesn't exist)


# Copy/move downloaded file to: dumps/graph.jsonl

# Restore the graph to Neo4j
make graph-restore DUMP=dumps/graph.jsonl

# This restores:
# - All entities and their embeddings
# - Knowledge graph relationships
# - Vector indexes
# - Fulltext indexes
```

### Step 5: Start the Application

```bash
# Terminal A: Start API server
make run-api
# API available at http://localhost:8000

# Terminal B: Start frontend dev server
make run-frontend
# Frontend available at http://localhost:5173

# Open http://localhost:5173 in your browser
# Login with default user: omar / admin123
```

### All make targets at a glance

Run `make help` for complete documentation. Key quick-start targets:

| Command                                     | Purpose                               |
| ------------------------------------------- | ------------------------------------- |
| `make install`                              | Install Python dependencies           |
| `make install-frontend`                     | Install Node.js frontend dependencies |
| `make install-test`                         | Install test dependencies             |
| `make setup-ollama`                         | Download required Ollama models       |
| `make services-docker`                      | Start Neo4j and Ollama via Docker     |
| `make quick-start`                          | Initialize database and .env          |
| `make graph-restore DUMP=dumps/graph.jsonl` | Restore pre-built graph               |
| `make run-api`                              | Start FastAPI server                  |
| `make run-frontend`                         | Start Vite dev server                 |
| `make services-stop`                        | Stop Docker services                  |

### Full Example Workflow

```bash
# Terminal 1: Start services
make services-docker

# Terminal 2: Setup everything
make install install-frontend install-test
make setup-ollama
make quick-start

# Download graph dump to dumps/graph.jsonl
# (See Step 4 above)

# Restore the graph
make graph-restore DUMP=dumps/graph.jsonl

# Edit .env if needed
nano .env

# Terminal 2 (new tab): Start API
make run-api
# API at http://localhost:8000

# Terminal 3: Start frontend
make run-frontend
# Frontend at http://localhost:5173

# Login with: omar / admin123
```

### Troubleshooting

- **"Neo4j connection failed"**: Ensure Neo4j is running
  - Check: http://localhost:7474 (should show Neo4j browser)
- **"Ollama models not found"**: Run `make setup-ollama` or pull manually:
  ```bash
  ollama pull qwen3-vl:8b-instruct-q4_K_M
  ollama pull bge-m3
  ollama pull granite4.1:8b
  ```
- **"Graph restore failed"**: Ensure `dumps/graph.jsonl` exists and has correct format
- **Port conflicts**: Change in `.env` if needed (NEO4J_URI, OLLAMA_URL, etc.)
- **Docker issues**: Run `make services-stop` then `make services-docker` to restart cleanly

---

## 3. Prerequisites

### System requirements

| Component | Minimum                   | Recommended       |
| --------- | ------------------------- | ----------------- |
| Python    | 3.10                      | 3.12              |
| Node.js   | 18                        | 20+               |
| RAM       | 16 GB                     | 32 GB+            |
| GPU VRAM  | 8 GB (GLiNER + small LLM) | 24 GB+ (70B LLMs) |
| Storage   | 20 GB                     | 50 GB+            |

### Required services

| Service    | Purpose                                             | Reference                   |
| ---------- | --------------------------------------------------- | --------------------------- |
| **Ollama** | OCR model, embedding model, local chat/extract LLMs | https://ollama.com/download |
| **Neo4j**  | Graph database + vector index + fulltext index      | https://neo4j.com/download/ |

**Database:** SQLite (built-in, no additional setup required)

Neo4j 5.x is required for the built-in vector index. Community Edition works; no paid plugins are required.

---

## 4. External Models and Datasets

### 3.1 Ollama models

Install Ollama, then pull the required models:

```bash
# OCR — vision-language model for Arabic PDFs (required)
ollama pull qwen3-vl:8b-instruct-q4_K_M

# Embedding — multilingual, handles Arabic + English (required)
ollama pull bge-m3

# Chat / local LLM (choose one)
ollama pull granite4.1:8b          # default, lighter
ollama pull llama3.1:8b            # alternative
ollama pull qwen2.5:72b-instruct-q4_K_M  # best quality, needs ~45 GB VRAM
```

### 3.2 HuggingFace models

These download automatically on first use via the `transformers` and `gliner` libraries. To pre-download:

**BGE-M3 embedding model** (~2.2 GB)

```bash
# Reference: https://huggingface.co/BAAI/bge-m3
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('BAAI/bge-m3')"
```

**GLiNER Arabic NER model** (~300 MB)

```bash
# Arabic-specific (recommended for Arabic-only documents)
# Reference: https://huggingface.co/NAMAA-Space/gliner_arabic-v2.1
python -c "from gliner import GLiNER; GLiNER.from_pretrained('NAMAA-Space/gliner_arabic-v2.1')"

# Multilingual alternative (mixed Arabic/English documents)
# Reference: https://huggingface.co/urchade/gliner_multi-v2.1
python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_multi-v2.1')"
```

**CAMeL Tools Arabic POS tagger** (required for Classical CRF NER only)

```bash
pip install camel-tools
# Download the CALIMA-MSA-r13 morphology database
camel_data -i morphology-db-msa-r13
# Reference: https://github.com/CAMeL-Lab/camel_tools
```

### 3.3 Datasets

#### MuSiQue — multi-hop QA benchmark (required for PPR evaluation)

Download from: https://github.com/stonybrooknlp/musique

Place the files at:

```
musique/data/musique_ans_v1.0_dev.jsonl
musique/data/musique_ans_v1.0_train.jsonl
```

#### WikiANN Arabic NER (optional — for CRF training augmentation)

WikiANN is downloaded automatically from HuggingFace by the converter script. Run from the `src/classical_NER/` directory:

```bash
cd src/classical_NER

# Install the datasets library if not already present
pip install datasets

# Convert the train split
python convertWikiann.py train wikiann_train
# Outputs:
#   ../../chunks/wikiann_train.json
#   annotations/wikiann_base.json
#   annotations/gold_wikiann_train.json

# Convert the test split
python convertWikiann.py test wikiann_test
# Outputs:
#   ../../chunks/wikiann_test.json
#   annotations/gold_wikiann_test.json
```

Reference: https://huggingface.co/datasets/unimelb-nlp/wikiann

#### ANERCorp Arabic NER (optional — for CRF training augmentation)

ANERCorp must be downloaded manually. Request the dataset from the original authors:

```
http://curtis.ml.cmu.edu/w/courses/index.php/ANERcorp
```

The dataset is a plain-text CoNLL-format file (one token + BIO tag per line, blank lines between sentences). Once you have `ANERCorp.txt`, run from the `src/classical_NER/` directory:

```bash
cd src/classical_NER

# Convert the training portion
python convertAnercorp.py /path/to/ANERCorp.txt anercorp
# Outputs:
#   ../../chunks/anercorp.json
#   annotations/anercorp_base.json
#   annotations/gold_anercorp.json

# Convert a held-out test portion (if you split the file manually)
python convertAnercorp.py /path/to/ANERCorp_test.txt anercorp_test
# Outputs:
#   annotations/gold_anercorp_test.json
```

#### AP News corpus (optional — for sensemaking evaluation only)

```bash
# Requires benchmark-qed in a separate venv (see Section 18)
.venv-qed/Scripts/benchmark-qed.exe data download AP_news sensemaking/data/ap_news
```

### 3.4 Generated model files (not included — generate with commands below)

| File                                         | Size   | How to generate                                        |
| -------------------------------------------- | ------ | ------------------------------------------------------ |
| `src/classical_NER/models/crf.pkl`           | ~5 MB  | `python src/classical_NER/trainCrf.py`                 |
| `src/classical_NER/models/crf_combined.pkl`  | ~5 MB  | Train with `includeWikiann=True, includeAnercorp=True` |
| `src/classical_NER/gazetteer/gazetteer.json` | <1 MB  | `python src/classical_NER/buildGazetteer.py`           |
| `src/classical_NER/training/train_data.json` | ~10 MB | `python src/classical_NER/featureExtract.py`           |

Pre-trained CRF variants already present in the repo (small enough to commit):

```
src/classical_NER/models/crf_bank.pkl       # trained on banking annotations only
src/classical_NER/models/crf_anercorp.pkl   # anercorp only
src/classical_NER/models/crf_wikiann.pkl    # wikiann only
```

---

## 5. Installation

### 4.1 Clone and set up Python environment

```bash
git clone <repo-url>
cd Gazelle

# Create and activate a virtual environment (Python 3.12 recommended)
python -m venv .venv
source .venv/bin/activate       # Linux / Mac
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### 4.2 Additional dependencies for the Classical NER subsystem

```bash
pip install sklearn-crfsuite seqeval camel-tools
camel_data -i morphology-db-msa-r13
```

### 4.3 Frontend

```bash
cd frontend
npm install
cd ..
```

---

## 6. Environment Variables

Create a `.env` file in the project root. All variables are read by `src/config.py` at startup.

```env
# ── Neo4j (required) ──────────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DB=neo4j

# ── PostgreSQL (required) ─────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/gazelle

# ── Ollama (local inference) ──────────────────────────────────────
OLLAMA_URL=http://localhost:11434/v1/chat/completions
OLLAMA_EMBED_URL=http://localhost:11434/api/embed
OLLAMA_VISION_MODEL=qwen3-vl:8b-instruct-q4_K_M
OLLAMA_EMBED_MODEL=bge-m3
OLLAMA_CHAT_MODEL=granite4.1:8b
OLLAMA_EXTRACT_MODEL=granite4.1:8b

# ── Groq (optional cloud chat fallback) ──────────────────────────
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.3-70b-versatile

# ── OpenRouter (required for Route 2 LLM graph extraction) ───────
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct

# ── Gemini (optional extraction backend) ─────────────────────────
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash

# ── Embedding model ───────────────────────────────────────────────
BGE_M3_PATH=BAAI/bge-m3

# ── Pipeline configuration ────────────────────────────────────────
GRAPH_ROUTE=2                    # 1=classical NER (gliner|crf|llm) + COOCCURS_WITH, 2=LLM full graph (default)
EXTRACT_DIR=extractions          # directory for all extraction JSONs (entities + graph)
CORPUS_NAME=cbe                  # tags Neo4j :Community nodes

# ── NER strategy ─────────────────────────────────────────────────
NER_STRATEGY=gliner              # gliner | llm | classical
GLINER_MODEL=NAMAA-Space/gliner_arabic-v2.1
GLINER_THRESHOLD=0.7

# ── Chunker type ─────────────────────────────────────────────────
CHUNKER_TYPE=semantic            # default | semantic

# ── Graph extraction workers ─────────────────────────────────────
GRAPH_EXTRACT_WORKERS=12
GRAPH_EXTRACT_BACKEND=openrouter # ollama | groq | openrouter | gemini

# ── Retrieval tuning ─────────────────────────────────────────────
LOCAL_COMENTION_EDGES=0          # 1 to walk COOCCURS_WITH in graph mode (Route 1)

# ── Community detection ──────────────────────────────────────────
COMMUNITY_RESOLUTION=1.0
SYNONYM_THRESHOLD=0.85

# ── OCR ──────────────────────────────────────────────────────────
OCR_PROVIDER=ollama
OCR_PARALLEL_PAGES=1
```

---

## 7. Database Setup

### 6.1 Neo4j

Start Neo4j (Community Edition or Enterprise, version 5.x). The pipeline automatically creates all constraints and indexes on first write — no manual schema setup is needed.

The graph schema created:

```
Nodes:
  (:Chunk  {chunkId, docName, text, sectionPath, pages, accessLevel})
  (:Entity {canonicalId, canonicalName, type, aliases, docName, description})
  (:Document {docName})
  (:Community {id, level, corpus, title, summary, rating})

Relationships:
  (Chunk)  -[:BELONGS_TO]->  (Document)
  (Entity) -[:MENTIONED_IN]-> (Chunk)
  (Entity) -[:COOCCURS_WITH {count}]->   (Entity)   -- Route 1
  (Entity) -[:RELATED {predicate, description, weight}]-> (Entity)  -- Route 2
  (Entity) -[:SYNONYM {cosine}]->   (Entity)
  (Entity) -[:IN_COMMUNITY {level}]-> (Community)
  (Community) -[:PARENT]-> (Community)

Indexes:
  Vector: chunk_embedding  (dim=1024, on Chunk nodes)
  Fulltext: chunk_text     (on Chunk.text)
```

### 6.2 SQLite

SQLite is the default database (airgapped build, no external dependencies). The database is automatically created and initialized with default users when you run:

```bash
make setup-db
```

This command creates `./gazelle.db` with the following tables:

- `users` — authenticated user accounts with role and clearance level
- `user_sessions` — session tokens and timestamps
- `chats` — conversation records
- `messages` — individual chat messages
- `chat_memory` — rolling chat summaries
- `user_memory` — persistent user preferences and notes
- `message_citations` — chunk citations for each message
- `audit_log` — activity audit trail

#### Default seed users

The database is initialized with these accounts (change passwords on first login):

| Username | Role               | Clearance    | Password      |
| -------- | ------------------ | ------------ | ------------- |
| `omar`   | Admin              | restricted   | admin123      |
| `sara`   | Senior Compliance  | confidential | compliance123 |
| `ahmed`  | Compliance Analyst | internal     | staff123      |
| `guest`  | External           | public       | guest         |

---

## 8. Ingestion Pipeline

Place source documents (PDFs, images) in the `Documents/` directory.

### 7.1 Full pipeline (all stages, skip-if-exists)

```bash
python runners/runPipeline.py
```

Runs: OCR → Parse → Chunk → NER/Extract → KG build → Embed → Entity embed → Synonyms, skipping any stage whose output already exists. Respects `GRAPH_ROUTE` and `NER_STRATEGY` — automatically selects the correct NER runner and, for Route 2, also runs community detection and summarization.

### 7.2 Individual stages

All runners must be executed from the **project root**. Each runner imports `_bootstrap.py` which adds `src/` to `sys.path` automatically.

```bash
# Stage 1 — OCR: PDFs/images --> Doc_Out/*.md
python runners/runOcr.py

# Stage 2 — Parse: Doc_Out/*.md --> parsed/*.json
python runners/runParser.py

# Stage 3 — Chunk: parsed/*.json --> chunks/*.json
python runners/runChunker.py

# Stage 4 — Embed chunks: chunks/*.json --> Neo4j vector index
python runners/runEmbed.py

# Stage 5a — Entity extraction, Route 1, NER_STRATEGY=gliner (default)
python runners/runGliner.py
# Output: extractions/<docName>_entities.json

# Stage 5b — Entity extraction, Route 1, NER_STRATEGY=classical (CRF pipeline)
python runners/runNerPipeline.py
# Output: extractions/<docName>_entities.json
# Runs: gazetteer → feature extraction → CRF train → inference

# Stage 5c — Entity extraction, Route 2 (LLM)
python runners/runGraphExtract.py
# Output: extractions/<docName>_graph.json

# Stage 6a — KG build, Route 1: Entity layer + COOCCURS_WITH
python runners/runKgBuild.py

# Stage 6b — KG build, Route 2: Entity + RELATED edges
python runners/runGraphBuild.py

# Stage 7 — Entity embeddings (BGE-M3 on canonical entity names)
python runners/runEntityEmbed.py
```

### 7.3 Batch processor (single file or directory)

```bash
# Process all files in Documents/
python runners/runAll.py Documents/

# Process a single file
python runners/runAll.py Documents/chapter_1.pdf

# Skip Neo4j write (run extraction only)
python runners/runAll.py Documents/ --skip-kg

# Skip embedding
python runners/runAll.py Documents/ --skip-embed
```

### 7.4 Output directories

| Directory      | Stage      | Contents                                                         |
| -------------- | ---------- | ---------------------------------------------------------------- |
| `Doc_Out/`     | OCR        | Markdown text per document                                       |
| `parsed/`      | Parser     | Structured JSON (sections, elements, page numbers)               |
| `chunks/`      | Chunker    | Token-bounded chunk arrays with `chunkId`                        |
| `extractions/` | All routes | Entity spans (`*_entities.json`), relation data (`*_graph.json`) |

---

## 9. OCR Preprocessing (Handwriting Detection)

**Optional preprocessing step** to improve OCR quality on documents with mixed handwritten and printed text.

### Overview

The preprocessing pipeline detects and removes handwritten regions from documents before OCR, which can improve Qwen3-VL's accuracy on printed text. This is particularly useful for:

- Scanned official documents with handwritten annotations
- Forms with handwritten entries mixed with printed fields
- Documents with margin notes or stamps

### Prerequisites

Download the required datasets for training the handwriting detector:

1. **Mendeley Handwriting Dataset** (primary dataset)
   - Download from: https://data.mendeley.com/datasets/2h76672znt/1
   - Extract to a directory on your system (e.g., `datasets/mendeley/`)

2. **RVL-CDIP Test Dataset** (validation dataset)
   - Download from: https://www.kaggle.com/datasets/pdavpoojan/the-rvlcdip-dataset-test
   - Extract to a directory on your system (e.g., `datasets/rvl_cdip/`)

### Setup and Training

1. **Install preprocessing dependencies** (if not already installed):

   ```bash
   pip install opencv-python scikit-learn  # (already in requirements.txt)
   ```

2. **Run the preprocessing notebook**:

   ```bash
   # Open the notebook and update dataset paths
   jupyter notebook preprocess_ocr.ipynb
   ```

3. **Configure dataset paths** in `preprocess_ocr.ipynb`:
   - Update `MENDELEY_PATH` to point to your Mendeley dataset directory
   - Update `RVLCDIP_PATH` to point to your RVL-CDIP dataset directory
   - Run all cells to train the handwriting detector

4. **Enable in the pipeline**:
   - Set `HANDWRITING_PREPROCESSING=true` in `.env`
   - Run the full pipeline — handwritten regions will be removed before OCR

### How it works

1. **Region Detection**: Analyzes document images to identify potential handwritten regions
2. **Filtering**: Removes or masks detected handwritten areas
3. **Reconstruction**: Preserves document structure while removing noise
4. **OCR**: Qwen3-VL processes the cleaned document, focusing on printed text

### Configuration

In `.env`:

```bash
# Enable/disable handwriting preprocessing
HANDWRITING_PREPROCESSING=true    # default: false

# Path to trained handwriting detector model (optional)
HANDWRITING_MODEL_PATH=./models/handwriting_detector.pkl
```

### Output

Preprocessed documents are saved to `Doc_Out/` with the same structure as regular OCR output:

- Raw OCR (before preprocessing): stored in pipeline logs if needed
- Cleaned OCR (after preprocessing): the primary output used for parsing

### Notes

- Preprocessing adds ~30-60 seconds per page depending on image size and GPU availability
- Disable preprocessing for documents that are purely printed or digital PDFs
- Re-run training if you add new handwriting samples to your datasets

---

## 10. Graph Construction — Two Routes

Select the route via the `GRAPH_ROUTE` env var (default: `2`). Both routes share the OCR → parse → chunk → embed pipeline.

### Route 1 — Classical (GLiNER or CRF baseline)

Extracts named entities and builds co-mention edges between entities that appear in the same chunk.

- **Builds:** `(:Entity)` nodes + `COOCCURS_WITH {count}` edges
- **Use when:** Fast local baseline, no API cost, no cloud dependency
- **Cannot feed:** Community summarization (no relationship descriptions)

The NER step is controlled by `NER_STRATEGY` (independent of `GRAPH_ROUTE`):

| `NER_STRATEGY`     | NER runner                  | Notes                                               |
| ------------------ | --------------------------- | --------------------------------------------------- |
| `gliner` (default) | `runners/runGliner.py`      | GLiNER Arabic model, single-pass                    |
| `classical`        | `runners/runNerPipeline.py` | CRF pipeline — gazetteer → features → train → infer |
| `llm`              | `src/llmNER.py`             | LLM-based NER, higher quality, API cost             |

```bash
export GRAPH_ROUTE=1

# Option A — GLiNER (default)
python runners/runGliner.py

# Option B — Classical CRF (set NER_STRATEGY=classical first)
export NER_STRATEGY=classical
python runners/runNerPipeline.py

python runners/runKgBuild.py
python runners/runEntityEmbed.py
```

Using `runPipeline.py` picks the correct NER runner automatically based on `NER_STRATEGY`.

### Route 2 — LLM (deployed, default)

A single LLM pass per chunk extracts entities, relationships, and natural-language descriptions of both. Produces a semantically richer graph that feeds both local PPR retrieval and the global community arm.

- **Builds:** `(:Entity {description})` + `RELATED {predicate, description, weight}` edges
- **Requires:** OpenRouter (or Groq/Ollama) API key
- **Cost:** Paid API calls — use `GRAPH_EXTRACT_WORKERS` to control parallelism

```bash
export GRAPH_ROUTE=2
python runners/runGraphExtract.py   # LLM extraction per chunk (checkpoint-resumable)
python runners/runGraphBuild.py     # write to Neo4j
python runners/runEntityEmbed.py    # embed entity names

# Add SYNONYM edges (identity bridges between near-duplicate entities)
python graphTraversal/runSynonyms.py           # uses SYNONYM_THRESHOLD from config
python graphTraversal/runSynonyms.py 0.85      # explicit threshold
```

---

## 11. Classical NER Subsystem (CRF)

A standalone Arabic NER pipeline using a CRF trained on gold-annotated CBE banking documents. This subsystem is in `src/classical_NER/`.

Set `NER_STRATEGY=classical` in `.env` (or the env var) to activate it in the main pipeline. `runners/runPipeline.py` will then call `runners/runNerPipeline.py` in place of `runGliner.py` for the entity extraction step.

### 9.1 Full CRF pipeline

```
chunks/*.json
    |
    v  Initial pre-annotation (GLiNER)
python runners/runGliner.py
    |
    v  Convert to Label Studio import format
python src/classical_NER/convertToLabelStudio.py
    --> annotations/ls_import.json
    |
    v  [Human annotation in Label Studio — accept/correct/add/delete spans]
    --> annotations/corrected.json
    |
    v  Build entity gazetteer from high-confidence annotations
python src/classical_NER/buildGazetteer.py
    --> src/classical_NER/gazetteer/gazetteer.json
    |
    v  Feature extraction (CAMeL Tools POS tagger + BIO alignment)
python src/classical_NER/featureExtract.py
    --> src/classical_NER/training/train_data.json
    |
    v  CRF training (80/20 split, L-BFGS, sklearn-crfsuite)
python src/classical_NER/trainCrf.py
    --> src/classical_NER/models/crf.pkl
    |
    v  Inference on new chunks
python src/classical_NER/runCrf.py
    --> extractions/<docName>_entities.json
```

### 9.2 CRF feature groups

Each Arabic token is represented by six feature groups:

| Group             | Features                                                                |
| ----------------- | ----------------------------------------------------------------------- |
| Surface + context | `word`, `w-1`, `w+1`, `is_first`                                        |
| POS tags          | `pos`, `p-2`, `p-1`, `p+1`, `p+2` (CALIMA-MSA-r13)                      |
| Morphological     | `has_def_art` (ال prefix), `has_prep_clitic`, `stem`                    |
| Script            | `is_arabic_num`, `is_western_num`, `contains_latin`, `is_clause_ref`    |
| Character n-grams | All bigrams and trigrams over token surface                             |
| Domain triggers   | `is_org_trigger`, `in_money_trigger`, `in_month`, `prev_is_org_trigger` |

### 9.3 Training with external datasets

To include WikiANN and/or ANERCorp in training, edit the `loadAnnotations` call in `featureExtract.py`:

```python
tasks = loadAnnotations(includeWikiann=True, includeAnercorp=True)
```

### 9.4 Entity types

11 types defined in `src/ontology.py`: `Person`, `BankingInstitution`, `RegulatoryBody`, `Law`, `Article`, `License`, `Document`, `FinancialInstrument`, `RegulatoryRequirement`, `MonetaryAmount`, `Date`.

### 9.5 Evaluate NER

```bash
python runners/runNerBenchmark.py
```

---

## 12. Graph Traversal and PPR Retrieval

The `graphTraversal/` subsystem implements **Personalized PageRank (PPR)** over the entity graph, following the HippoRAG architecture. It replaces fixed-depth k-hop traversal with a global random-walk algorithm.

### 10.1 How PPR retrieval works

1. **Embed** the query using BGE-M3
2. **Seed** — find the top-K most similar entity nodes by cosine similarity; these form the teleport (restart) distribution
3. **PPR walk** — run power iteration: `r_{t+1} = (1 - alpha) * M^T * r_t + alpha * seed`. Mass flows through `RELATED`, `COOCCURS_WITH`, and `SYNONYM` edges
4. **Project** — map entity PPR scores onto chunks via `MENTIONED_IN` edges; aggregate per chunk
5. **Return** top-K chunks ranked by accumulated mass

### 10.2 Standalone PPR commands

```bash
cd graphTraversal

# Run PPR retrieval for a test query
python runRetrieve.py

# Full PPR probe (times a batch of queries, reports recall)
python runProbe.py

# Inspect which entities get seeded for a query
python runSeed.py

# Generate synonym (SYNONYM) edges for entity alignment
python runSynonyms.py
python runSynonyms.py 0.85    # explicit threshold
```

### 10.3 Edge layers

| Edge type       | Enabled by                  | Notes                                      |
| --------------- | --------------------------- | ------------------------------------------ |
| `RELATED`       | `useRelated=True` (default) | LLM-extracted semantic relations — Route 2 |
| `COOCCURS_WITH` | `useCoMention=True`         | Co-mention within chunk — Route 1          |
| `SYNONYM`       | `includeSynonyms=True`      | Entity alignment bridges — both routes     |
| `TRIPLE`        | `useTriples=True`           | Bare OpenIE triples — deprecated           |

### 10.4 PPR hyperparameters (`src/config.py`)

| Parameter           | Default | Description                                                           |
| ------------------- | ------- | --------------------------------------------------------------------- |
| PPR `alpha`         | 0.5     | Teleport probability (restart rate)                                   |
| `SEED_K`            | 8       | Entity seeds per query                                                |
| `RRF_K`             | 60      | Reciprocal Rank Fusion constant                                       |
| `OVERFETCH`         | 4       | Fetch k \* OVERFETCH before access-control filter                     |
| `SYNONYM_THRESHOLD` | 0.85    | Cosine cutoff for SYNONYM edges                                       |
| `ENTITY_WEIGHT`     | 0.6     | Path score = entity*weight * entity*sim + (1-entity_weight) * rel_sim |

---

## 13. Community Detection and Global Arm

### 11.1 Leiden algorithm

`graphTraversal/leiden.py` implements Leiden community detection (Traag, Waltman & van Eck, 2019) from scratch. It runs three passes per level:

1. **Local move** — Louvain-style greedy modularity maximization
2. **Refinement** — splits communities into internally connected sub-communities (the step Louvain lacks; guarantees no disconnected communities)
3. **Aggregation** — collapse sub-communities to super-nodes, repeat on the smaller graph

Each level produces a coarser partition. `leidenHierarchy()` returns all levels finest-to-root. Level 0 (root) = fewest, broadest communities — the default answering level for the global arm.

### 11.2 Running community detection

**Prerequisite:** Route 2 graph must be built (entities with `RELATED` edges in Neo4j).

```bash
# Detect communities over the full corpus (all entities in the DB)
python graphTraversal/runCommunities.py

# Specific documents only (comma-separated docNames)
python graphTraversal/runCommunities.py chapter_1,chapter_2,chapter_3

# Custom Leiden resolution (higher = more, smaller communities)
python graphTraversal/runCommunities.py ALL 1.5

# Custom corpus name tag on the written :Community nodes
python graphTraversal/runCommunities.py ALL 1.0 my_corpus
```

### 11.3 Validate community detection

```bash
cd graphTraversal

# Unit tests for Leiden and persistence builders
python testLeiden.py
python testCommunity.py

# Validate on standard benchmark graphs (Cora, football, email)
python validateLeiden.py

# Plot community structure
python plotCommunities.py
```

---

## 14. Query-Focused Summarization

The global arm answers corpus-wide sensemaking questions using GraphRAG-style map-reduce over community summaries.

### 12.1 Generate community summary reports

Run after community detection has built the `(:Community)` skeleton:

```bash
# Generate LLM reports for all communities in the corpus
python runners/runCommunitySummary.py

# Explicit corpus and backend
python runners/runCommunitySummary.py cbe openrouter
```

Each community node gets: `title`, `summary`, `rating` (0–10), `rating_explanation`, and `findings[]` (each with `[Data: Entities (...); Relationships (...)]` inline citations).

### 12.2 How global answering works at query time

`src/globalSearch.py` runs:

1. **Map** — for each root-level (C0) community summary, call the LLM to extract relevant key points and a helpfulness score (0–100). Zero-score points are dropped.
2. **Reduce** — synthesize the top-40 scored points into a final prose answer, preserving all data citations.

### 12.3 Query routing

`src/router.py` classifies each query before retrieval:

| Classification | Trigger                                         | Handled by           |
| -------------- | ----------------------------------------------- | -------------------- |
| `local`        | Specific fact, entity, number, date             | PPR retrieval        |
| `global`       | Themes, trends, comparisons, "across documents" | Community map-reduce |

```bash
# Test the router standalone
python runners/runRouter.py
```

---

## 15. Chat API

### 13.1 Start the API server

```bash
python runners/runApi.py
# Starts on http://localhost:8000
```

### 13.2 API endpoints

| Method   | Endpoint                   | Description                              |
| -------- | -------------------------- | ---------------------------------------- |
| `POST`   | `/api/auth/login`          | Login — returns bearer token             |
| `POST`   | `/api/auth/logout`         | Invalidate session token                 |
| `POST`   | `/api/chat`                | Send a query, stream the LLM answer      |
| `GET`    | `/api/chats`               | List the authenticated user's chats      |
| `POST`   | `/api/chats`               | Create a new chat                        |
| `DELETE` | `/api/chats/{id}`          | Delete a chat                            |
| `GET`    | `/api/chats/{id}/messages` | Get all messages in a chat               |
| `GET`    | `/api/graph`               | Query Neo4j for the graph explorer       |
| `GET`    | `/api/memory/user`         | Get the user's persistent memory entries |
| `PUT`    | `/api/memory/user/{key}`   | Set a user memory entry                  |

### 13.3 Chat request body

```json
{
  "query": "ما هي متطلبات كفاية رأس المال؟",
  "chatId": "optional-uuid",
  "mode": "hybrid",
  "k": 5,
  "hops": 1,
  "provider": "ollama"
}
```

| Field      | Values                      | Description                          |
| ---------- | --------------------------- | ------------------------------------ |
| `mode`     | `vector`, `hybrid`, `graph` | Retrieval strategy                   |
| `k`        | integer                     | Number of chunks to retrieve         |
| `hops`     | integer                     | Traversal depth for k-hop graph mode |
| `provider` | `ollama`, `groq`            | LLM backend for answer generation    |

### 13.4 System prompt and grounding

The system prompt enforces: cite every claim with `[chunkId]`, refuse with a fixed sentence if context is insufficient, temperature always 0. The LLM physically cannot answer without retrieved chunks — hallucination resistance is structural, not relying on the model to self-police.

---

## 16. Frontend

### 14.1 Development server

```bash
cd frontend
npm run dev
# Open http://localhost:5173
# API requests are proxied to localhost:8000
```

### 14.2 Production build

```bash
cd frontend
npm run build
# Build output: frontend/dist/
# FastAPI serves these automatically when runApi.py starts
```

### 14.3 Tech stack

| Package           | Purpose                      |
| ----------------- | ---------------------------- |
| React 18          | UI framework                 |
| Vite 5            | Build tool + dev server      |
| Tailwind CSS 3    | Styling                      |
| Cytoscape.js 3    | Graph explorer visualization |
| cytoscape-fcose   | Force-directed graph layout  |
| react-cytoscapejs | React wrapper for Cytoscape  |

### 14.4 Features

- **Chat UI** — streaming responses with inline `[chunkId]` citation chips linked to source chunks
- **Chat history** — persistent across sessions (stored in PostgreSQL)
- **Graph Explorer** — interactive force-directed visualization of the entity graph; search entities by name, expand neighborhoods by hop count

---

## 17. Access Control

Documents are classified by sensitivity level in `src/docAccess.py`. Users carry a `clearance` field set at account creation. Retrieval is automatically filtered — users only receive chunks from documents at or below their clearance.

### Clearance levels (ascending)

```
public < internal < confidential < restricted
```

### Configuring document access

Edit `DOC_ACCESS` in `src/docAccess.py`:

```python
DOC_ACCESS = {
    'chapter_1': 'internal',
    'chapter_2': 'internal',
    'phase_1_document': 'confidential',
    'board_minutes': 'restricted',
}
```

Documents not listed default to `'internal'`. The `allowedDocs(userClearance)` function returns the list of documents a given user may access; this list is passed to every retrieval query.

---

## 18. Context Memory

The memory system has four layers that are assembled into the LLM prompt for each turn.

| Layer                                | Storage                  | Lifetime         | Token budget |
| ------------------------------------ | ------------------------ | ---------------- | ------------ |
| Retrieved context                    | Neo4j chunks             | Per turn         | 1500         |
| Chat memory (rolling summary)        | PostgreSQL `chat_memory` | Per chat session | 300          |
| User memory (persistent preferences) | PostgreSQL `user_memory` | Across all chats | 80           |
| Recent turn history                  | PostgreSQL `messages`    | Last N turns     | 600          |

### Chat memory

`src/memory/summarizer.py` updates the rolling summary after each assistant turn, but only when the debounce threshold is reached (6 new turns OR 1000 new tokens). The LLM is given the previous summary + new exchanges and produces an updated summary. PII (10+ digit sequences) is redacted before storage.

### User memory

`src/memory/promoter.py` scans each user message for patterns like `"always answer in Arabic"` or `"my role is compliance analyst"` and promotes matched facts to `user_memory`. These are injected at the top of every subsequent prompt.

---

## 19. MuSiQue Benchmark Evaluation

The `musique/` directory benchmarks the PPR retrieval upgrade against MuSiQue multi-hop QA (gold supporting paragraphs as ground truth).

### 17.1 Setup

```bash
# Place MuSiQue data (see Section 3.3), then:
cd musique
python loadChunks.py
# --> chunks/musique.json

python ../runners/runEmbed.py musique
# --> embeds musique chunks into Neo4j vector index
```

### 17.2 Build the MuSiQue entity graph (Route 2)

```bash
python ../runners/runGraphExtract.py musique
python ../runners/runGraphBuild.py musique
python ../runners/runEntityEmbed.py
python ../graphTraversal/runSynonyms.py musique 0.85
```

### 17.3 Run evaluation

```bash
cd musique
python eval.py
# Output: musique/eval_results/v<N>_<label>.json
```

Each run writes a versioned JSON with full config, per-question results, and recall@K (K = 1, 2, 5, 10).

### 17.4 Results summary

| Version         | Retriever                   | recall@5    | recall@10 |
| --------------- | --------------------------- | ----------- | --------- |
| v0 (baseline)   | k-hop (k=2)                 | 0.285       | 0.331     |
| v4 / v7b (best) | PPR, alpha=0.5, seedTopK=5  | **0.364**   | 0.419     |
| v8              | PPR + Route 2 RELATED edges | in progress | —         |

Full version log with design decisions in `docs/PROCESS.md`.

---

## 20. Sensemaking Benchmark (AP News)

End-to-end evaluation of the global arm against a vector-RAG baseline using Microsoft BenchmarkQED on the AP News corpus.

### 18.1 Set up the isolated BenchmarkQED environment

```bash
python -m venv .venv-qed
# Activate:
source .venv-qed/bin/activate      # Linux / Mac
# .venv-qed\Scripts\activate       # Windows

pip install benchmark-qed
# Reference: https://github.com/microsoft/benchmark-qed
```

### 18.2 Full pipeline

```bash
# 0. Download AP News corpus (LIMIT=50 in loadApNews.py for a quick slice)
.venv-qed/Scripts/benchmark-qed.exe data download AP_news sensemaking/data/ap_news

# 1. Build AP News chunks
python sensemaking/loadApNews.py

# 2. Route 2 graph extraction (PAID — OpenRouter)
python runners/runGraphExtract.py apnews
python runners/runGraphBuild.py apnews
python runners/runEmbed.py apnews
python runners/runEntityEmbed.py

# 3. Communities + summaries (PAID)
python graphTraversal/runSynonyms.py apnews 0.85
python graphTraversal/runCommunities.py apnews
python runners/runCommunitySummary.py apnews

# 4. Generate questions via AutoQ
.venv-qed/Scripts/benchmark-qed.exe autoq sensemaking/config/autoq <out> --generation-type data_global

# 5. Generate answers from both systems (global arm vs vector baseline)
python sensemaking/answerSystems.py <out>/questions.json apnews

# 6. Judge pairwise win-rates (PAID — requires OpenAI or OpenRouter key for judge)
.venv-qed/Scripts/benchmark-qed.exe autoe pairwise-scores \
    sensemaking/config/pairwise.json sensemaking/eval_results/pairwise.json
```

---

## 21. Router Training

The query router classifier is trained on a synthetic bilingual dataset (English + Arabic, local + global labels).

### 19.1 Generate training data

Requires: MuSiQue data in `musique/data/`, `Doc_Out/*.md` files from the CBE ingestion.

```bash
python router/genData.py
# Output: router/train.jsonl (~2600 rows), router/test.jsonl (~1450 rows)
```

### 19.2 Train the router

```bash
python router/train.py
```

### 19.3 Evaluate

```bash
python router/evalHoldout.py
```

The holdout file `router/holdout_real.jsonl` is a scaffold. Hand-author 80–100 real bilingual queries (mixing domains and languages) for a proper holdout evaluation.

---

## 22. Project Layout

```
Gazelle/
|-- src/                         Core importable modules
|   |-- ocr.py                   Arabic-aware OCR (Qwen3-VL via Ollama)
|   |-- ocrPreprocessing.py      Image preprocessing before OCR
|   |-- parser.py                Markdown --> structured JSON
|   |-- chunker.py               Token-bounded chunker
|   |-- semantic_chunker.py      Semantic boundary-aware chunker
|   |-- embedding.py             BGE-M3 chunk embedding --> Neo4j
|   |-- glinerExtract.py         GLiNER NER (Route 1)
|   |-- llmNER.py                LLM-based NER (alternative)
|   |-- graphExtract.py          LLM entity + relation extraction (Route 2)
|   |-- kgBuild.py               Route 1 KG writer (Entity + COOCCURS_WITH)
|   |-- graphBuild.py            Route 2 KG writer (Entity + RELATED)
|   |-- entityEmbedding.py       BGE-M3 on canonical entity names
|   |-- entityAlign.py           Cosine deduplication (SYNONYM edges)
|   |-- retriever.py             Vector / hybrid / graph retrieval
|   |-- chatApi.py               FastAPI app (chat, graph, auth, memory)
|   |-- auth.py                  Bearer token auth (SHA-256, PostgreSQL)
|   |-- docAccess.py             Per-document clearance levels
|   |-- ontology.py              Entity types + relationship schema
|   |-- config.py                All tuneable constants + env var loading
|   |-- router.py                Query router (local vs global)
|   |-- globalSearch.py          Global arm map-reduce over community reports
|   |-- communitySummary.py      LLM community report generation
|   |-- community.py             Persist Leiden hierarchy to Neo4j
|   |-- llmTriples.py            Multi-backend LLM call (Ollama/Groq/OpenRouter/Gemini)
|   |-- memory/
|   |   |-- assembler.py         Token-budgeted prompt assembly
|   |   |-- summarizer.py        Rolling chat summary updater
|   |   +-- promoter.py          Pattern-based user memory promotion
|   |-- db/
|   |   |-- models.py            SQLAlchemy ORM models
|   |   |-- session.py           Async session factory
|   |   +-- repositories/        DAO layer (auth, chat, memory, citation, audit)
|   +-- classical_NER/
|       |-- featureExtract.py    Arabic CRF feature engineering (CAMeL Tools)
|       |-- trainCrf.py          CRF training (sklearn-crfsuite, L-BFGS)
|       |-- runCrf.py            CRF inference on new chunks
|       |-- buildGazetteer.py    Build entity gazetteer from annotations
|       |-- convertToLabelStudio.py  Export GLiNER output for Label Studio
|       |-- evalNer.py           NER evaluation against gold annotations
|       |-- annotations/         Gold annotation files (Label Studio format)
|       |-- models/              Trained CRF model checkpoints (.pkl)
|       |-- training/            Feature-extracted BIO training sequences
|       +-- gazetteer/           Compiled entity lookup tables
|
|-- runners/                     Entry-point scripts
|   |-- _bootstrap.py            Adds src/ to sys.path, chdirs to repo root
|   |-- runApi.py                Start FastAPI server
|   |-- runOcr.py
|   |-- runParser.py
|   |-- runChunker.py
|   |-- runEmbed.py
|   |-- runGliner.py
|   |-- runNerPipeline.py            Full classical CRF NER pipeline (NER_STRATEGY=classical)
|   |-- runGraphExtract.py
|   |-- runGraphBuild.py
|   |-- runKgBuild.py
|   |-- runEntityEmbed.py
|   |-- runCommunitySummary.py
|   +-- runAll.py                Single-file or directory batch processor
|
|-- graphTraversal/              PPR retrieval and community detection
|   |-- _bootstrap.py
|   |-- ppr.py                   Personalized PageRank (power iteration, CSR)
|   |-- seeder.py                Query embedding --> entity seed vector
|   |-- retrieve.py              RetrievalIndex: loads graph state once per process
|   |-- loadGraph.py             Cypher edge rows --> sparse adjacency matrix
|   |-- synonyms.py              SYNONYM edge generation (entity alignment)
|   |-- leiden.py                From-scratch Leiden community detection
|   |-- khop.py                  K-hop retrieval (baseline comparison)
|   |-- runCommunities.py        entity graph --> Leiden --> Neo4j
|   |-- runSynonyms.py
|   |-- testLeiden.py
|   |-- testCommunity.py
|   +-- validateLeiden.py
|
|-- musique/                     MuSiQue multi-hop QA evaluation harness
|   |-- _bootstrap.py
|   |-- eval.py                  Recall@K evaluation, versioned JSON output
|   |-- loadChunks.py            Build chunk JSON from MuSiQue JSONL
|   |-- data/                    Place musique_ans_v1.0_*.jsonl here
|   +-- eval_results/            Versioned evaluation result JSONs
|
|-- sensemaking/                 Global arm evaluation (AP News + BenchmarkQED)
|-- router/                      Query router training data + classifier
|-- frontend/                    React + Vite frontend (chat UI + graph explorer)
|-- docs/                        Design documentation
|   |-- PROCESS.md               PPR retrieval design log + versioned eval results
|   |-- GLOBAL_PLAN.md           Global arm architecture plan
|   |-- COMMUNITY_DETECTION.md   Leiden design notes
|   +-- MEMORY_ARCHITECTURE.md   Memory system design
|-- Documents/                   Input PDFs (place your documents here)
|-- Doc_Out/                     OCR output Markdown
|-- parsed/                      Parser output JSON
|-- chunks/                      Chunker output JSON
|-- extractions/                 Entity and relation extraction outputs
|-- annotations/                 Gold annotation files (Label Studio format)
|-- requirements.txt
+-- .env                         Your environment variables (do not commit)
```

---

## 23. Testing and Coverage

### Running Tests

The project includes unit tests, module integration tests, and end-to-end integration tests.

#### Run all tests with coverage:

```bash
make test-all
```

This runs all tests (unit + module + integration) with coverage report and generates an HTML report.

#### Run specific test suites:

```bash
# Unit tests only
make test

# Unit tests with coverage report
make test-cov

# Module integration tests
make test-modules

# End-to-end integration tests
make test-integration

# Specific test file
make test-parser          # Parser tests
make test-chunker         # Chunker tests
make test-embedding       # Embedding tests
make test-semantic        # Semantic chunker tests
make test-gliner          # GLiNER NER tests
make test-llm-ner         # LLM NER tests
make test-config          # Config tests
```

### Viewing Coverage Reports

After running tests with coverage, an HTML report is generated at:

```
htmlcov/index.html
```

#### Open the report in your browser:

**Linux/Mac:**

```bash
# After running tests
open htmlcov/index.html
# Or use any web browser
```

**Windows:**

```bash
# After running tests
start htmlcov/index.html
# Or manually open htmlcov/index.html in your browser
```

#### Coverage report structure:

```
htmlcov/
├── index.html              Main coverage overview
├── status.json             Machine-readable coverage metrics
└── [module_name].html      Per-module coverage details
```

### Understanding Coverage Reports

The HTML report shows:

| Column         | Meaning                                   |
| -------------- | ----------------------------------------- |
| **Coverage**   | Percentage of lines executed during tests |
| **Statements** | Total lines of code                       |
| **Missed**     | Lines not executed (uncovered)            |
| **Branches**   | Conditional branches (if/else, loops)     |
| **Partial**    | Branches with partial coverage            |

### Key metrics to watch:

- **Overall coverage**: Goal is 80%+ for critical modules
- **Missed lines**: Click to see which lines aren't tested
- **Branch coverage**: Ensure both sides of conditionals are tested

### Example workflow:

```bash
# 1. Make code changes
# 2. Run tests with coverage
make test-all

# 3. View the report
open htmlcov/index.html

# 4. Identify uncovered code
# Look for red/pink lines in the HTML report

# 5. Write additional tests for uncovered lines
# 6. Re-run to verify improvement
make test-all
```

### CI/Coverage Integration

Coverage reports can be integrated with CI/CD pipelines:

- **GitHub Actions**: Use `coverage.py` with artifacts
- **GitLab CI**: Use `coverage` regex to extract metrics
- **Coverage badges**: Generate and embed in README

Example for GitHub:

```yaml
- name: Generate coverage report
  run: make test-all

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

### Troubleshooting

- **"No coverage data collected"**: Ensure `pytest` and `pytest-cov` are installed (`make install-test`)
- **"htmlcov directory not found"**: Run tests again with `--cov-report=html` flag
- **Coverage seems low**: Check if all test suites ran (`make test-all` runs all three: unit, module, integration)
- **Slow coverage generation**: Large projects can take time; use `make test` for faster unit-test-only coverage
