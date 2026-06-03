# src/config.py

Central registry of all tunable constants for the project. Other modules import directly from here rather than re-reading the environment.

## Line-by-line

**Lines 1-4 — imports and dotenv load**

- `import os` exposes the OS environment dictionary so the file can look up `NEO4J_URI` and friends.
- `from dotenv import load_dotenv` brings in a helper that parses a local `.env` file and injects its key/value pairs into `os.environ`.
- `load_dotenv()` is called at import time. After this line, anything written in `.env` is reachable via `os.environ[...]`.

**Lines 6-9 — Neo4j connection**

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` are looked up with bracket access (`os.environ['…']`). Bracket access raises `KeyError` immediately if the key is missing — these three values are required, so failing fast at import is the correct behavior.

**Lines 11-13 — Local LLM HTTP endpoints**

- `OLLAMA_URL` points at Ollama's OpenAI-compatible chat endpoint running on the default port `11434`.
- `LLAMA_SERVER_URL` points at a llama.cpp `llama-server` instance on port `8080`. Used as the non-Ollama OCR provider.

**Lines 15-18 — OCR settings**

- `OCR_PROVIDER` selects which backend `src/ocr.py` calls. Either `"ollama"` or `"local"`.
- `OCR_PARALLEL_PAGES = 1` is the thread-pool size used when rendering and OCRing PDF pages. Kept at 1 to avoid GPU contention on a single-GPU host.
- `OLLAMA_VISION_MODEL` is the model tag Ollama serves for vision-language OCR — Qwen3-VL 8B in 4-bit quantization.

**Lines 20-22 — Relation extraction (LLM)**

- `OLLAMA_EXTRACT_MODEL` reads from env with a default of `granite4.1:8b`. `os.environ.get` returns `None` for missing keys; passing a second argument provides the default.
- `PARALLEL_CHUNKS = 4` is the per-batch parallelism cap when calling Ollama from `llmExtract.py`. The comment notes it must match the server-side `OLLAMA_NUM_PARALLEL` setting or extra requests queue up uselessly.

**Lines 24-28 — Chat API model selection**

- `OLLAMA_CHAT_MODEL` defaults to `llama3.1:8b` (the local fallback model used for answering chat questions).
- `GROQ_URL`, `GROQ_MODEL`, `GROQ_API_KEY` configure the optional Groq cloud backend. `GROQ_API_KEY` returns `None` if unset, which is the signal `chatApi.py` uses to decide whether Groq is even available.

**Lines 30-36 — Embedding configuration**

- `BGE_M3_PATH` points at the Hugging Face model identifier for BGE-M3. Defaults to the canonical `BAAI/bge-m3` repo.
- `OLLAMA_EMBED_URL` and `OLLAMA_EMBED_MODEL` configure Ollama's embedding endpoint. Embeddings are served separately from chat completions, so this URL is different from `OLLAMA_URL`.
- `EMBED_DIM = 1024` is BGE-M3's output dimensionality. Used when declaring Neo4j vector indexes.
- `CHUNK_EMBED_BATCH` and `ENTITY_EMBED_BATCH` are batch sizes for embedding chunks vs entities. Two values because chunks are much longer than entity names, so the GPU can fit fewer per batch.

**Lines 38-40 — GLiNER (Arabic NER)**

- `GLINER_MODEL` is a hard-coded absolute path to the Hugging Face cache snapshot of the NAMAA Arabic GLiNER model. Hard-coded so first-run downloads don't happen during ingestion.
- `GLINER_THRESHOLD = 0.5` filters out NER predictions below this confidence.

**Line 43 — Chunking**

- `CHUNK_TARGET_TOKENS = 600` is the soft cap `chunker.py` aims for when splitting OCR markdown into chunks.

**Lines 45-47 — Entity alignment**

- `SIM_THRESHOLD = 0.92` is the cosine-similarity cutoff for collapsing two entities into one canonical entity.
- `SKIP_SIM_TYPES = {'Date', 'MonetaryAmount'}` is a set of entity types where similarity-based merging is disabled — two different dates that look similar are usually genuinely different.

**Lines 49-57 — Retrieval tuning**

- `RRF_K = 60` is the constant in the Reciprocal Rank Fusion formula `1 / (k + rank)`.
- `OVERFETCH = 4` says: pull `k * 4` results from the vector index, then filter by document access control, then trim back to `k`. Compensates for losing rows to access filtering.
- `PATH_DEPTH = 3` is the max number of hops the graph search will traverse.
- `SEED_K = 8` is how many entity seeds are looked up from the query embedding before path traversal starts.
- `PATH_LIMIT = 300` caps total paths considered per query (keeps Cypher cost bounded).
- `REL_TYPE_TOP = 5` keeps only the top 5 relationship types by query similarity, suppressing weak matches.
- `REL_TYPE_FLOOR = 0.25` is an absolute cosine-sim floor for relationship types (anything below is dropped even if it makes top-5).
- `ENTITY_WEIGHT = 0.6` is the mixing coefficient for path scoring: 60% entity similarity, 40% relation similarity.
