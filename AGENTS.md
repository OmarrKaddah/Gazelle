# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Goal

A **graph-grounded, hallucination-resistant RAG system** for banking and finance compliance/regulatory documents. The end product is a Codex-like chatbot UI that answers compliance questions with citations, grounded in a knowledge graph + vector hybrid retrieval pipeline.

The project is being built **part by part** — many pipeline stages are scaffolded but not yet implemented. Empty files (`chunker.py`, `kg_construction.py`) are placeholders for upcoming stages, not dead code.

## Full Pipeline (Target Architecture)

```
Word docs + scanned PDFs
        │
        ▼
   Ingestion / OCR        ← parser.py (partial: Arabic OCR via Qwen3-VL)
        │
        ▼
      Chunker             ← chunker.py (placeholder)
        │
        ▼
  KG Construction         ← kg_construction.py (placeholder), kg_builder.py (early scaffold)
   ├─ Entity extraction      arabic_ner.py (early scaffold)
   ├─ Relationship extraction
   └─ Further KG phases
        │
        ▼
       Neo4j
        │
        ▼
    Embeddings
        │
        ▼
   Hybrid Retrieval       (vector search + graph traversal)
        │
        ▼
    Chatbot UI
```

**Design constraint:** every stage must preserve provenance (source doc, page, chunk → entity → answer) so the chatbot can cite its sources. Hallucination resistance comes from grounding answers in graph-traversed, cited evidence rather than free-form generation over chunks.

## Current State (what's actually implemented)

- **`parser.py`** — OCR for Arabic banking PDFs/images via Qwen3-VL (Ollama or llama-server on `localhost:8080`). Outputs markdown to `Doc_Out/` and JSON metadata to `output/`. Parallel page processing via `ThreadPoolExecutor`, temperature=0.
- **`arabic_ner.py`** — Early entity extraction using GLiNER (`NAMAA-Space/gliner_arabic-v2.1`) for 5 Arabic entity types: شخص, منظمة, مكان, قانون, وثيقة.
- **`kg_builder.py`** — Early scaffold using `neo4j-graphrag`'s `SimpleKGPipeline` with `FixedSizeSplitter` (500/100). References an `extractor` module not yet in repo.
- **`chunker.py`, `kg_construction.py`** — empty placeholders for upcoming pipeline stages.

`Documents/` holds source docs (Central Bank of Egypt regulatory material). `Doc_Out/` and `output/` hold processed artifacts.

## Environment Setup

**Required services** (must be running for the relevant scripts):
- Vision model — Ollama (`ollama serve`, model `qwen3-vl:30b-a3b-instruct`) **or** llama-server on `localhost:8080` (for `parser.py`)
- Neo4j (for `kg_builder.py`)

**Environment variables (`.env`):**
- `GROQ_API_KEY` — Groq LLM API access

**Python environment:** Conda (`.vscode/settings.json`).

**Key dependencies** (no `requirements.txt` yet — inferred from imports):
- `pypdfium2` — PDF rasterization
- `requests` — HTTP to local vision model
- `gliner` — Arabic NER
- `neo4j-graphrag` — KG construction

## Running Individual Stages

Stages are standalone scripts, run manually:

```bash
python parser.py        # OCR
python arabic_ner.py    # NER
python kg_builder.py    # KG construction (needs Neo4j)
```

## Coding Conventions

Strict rules for all code in this project:

- **Minimal** — no defensive slop. No try/except wrappers, no input validation, no null guards unless a real failure mode demands it.
- **No inline imports** — all imports at the top of the file.
- **No underscores in function names** — camelCase (e.g. `parseDoc`, not `parse_doc`). Overrides the Python snake_case norm.
- **One function = one thing** — single responsibility, small surface.
- **Human readable above clever**.
- **No unnecessary fallbacks** — no "just in case" branches, no default-value safety nets. If it fails, let it fail.

Apply to every edit. Match the new convention when touching old code; don't preserve old patterns.

## Domain-Specific Notes

**OCR prompt in `parser.py` is carefully tuned** for Arabic legal/regulatory documents:
- Preserves Arabic-Indic numerals (٠١٢٣٤٥٦٧٨٩) — **do not** convert to Western digits
- Detects tables, outputs as markdown
- Handles multi-level signature blocks and RTL hierarchical structure

Casual edits to this prompt can degrade output quality on real banking docs — test against existing samples in `Doc_Out/` before changing.

**Citation/provenance is a first-class concern.** When extending any stage, keep the source-doc → page → chunk → entity/relationship lineage intact so downstream retrieval can cite sources verbatim.
