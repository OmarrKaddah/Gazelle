import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# PROJECT SETUP — the one knob to set when running the project from scratch.
# Pick the graph-construction route; everything downstream derives from it.
#   '1' = Route 1: GLiNER NER + co-mention COOCCURS_WITH  (classical baseline,
#         deterministic, local-retrieval only, no descriptions)
#   '2' = Route 2: full-LLM entities + RELATED{predicate,description} edges
#         (deployed; required for the global/community arm)
# Override per-run with the GRAPH_ROUTE env var.
# ============================================================================
GRAPH_ROUTE = os.environ.get('GRAPH_ROUTE', '2')

# Clean-output knobs for a from-scratch run. ocr/parse/chunk keep their fixed
# folders (Doc_Out/, parsed/, chunks/) so they SKIP and don't re-run.
# EXTRACT_DIR is the only post-chunk *file* output; the rest of the pipeline
# writes to Neo4j, namespaced by CORPUS_NAME (the :Community {corpus} tag).
EXTRACT_DIR = os.environ.get('EXTRACT_DIR', 'extractions') # per-doc extraction JSON; all routes write here — GLiNER/CRF *_entities.json, LLM *_graph.json
CORPUS_NAME = os.environ.get('CORPUS_NAME', 'cbe')         # tags (:Community {corpus}); the scope key for community summaries
SYNONYM_THRESHOLD = float(os.environ.get('SYNONYM_THRESHOLD', '0.85'))  # cosine cutoff for SYNONYM identity-bridging edges
COMMUNITY_RESOLUTION = float(os.environ.get('COMMUNITY_RESOLUTION', '1.0'))  # Leiden resolution

# Neo4j
NEO4J_URI = os.environ['NEO4J_URI']
NEO4J_USER = os.environ['NEO4J_USER']
NEO4J_PASSWORD = os.environ['NEO4J_PASSWORD']
NEO4J_DB = os.environ.get('NEO4J_DB', 'neo4j')

# Ollama / llama-server endpoints
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/v1/chat/completions')
LLAMA_SERVER_URL = os.environ.get('LLAMA_SERVER_URL', 'http://localhost:8080/v1/chat/completions')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/v1/chat/completions')
LLAMA_SERVER_URL = os.environ.get('LLAMA_SERVER_URL', 'http://localhost:8080/v1/chat/completions')

# OCR
OCR_PROVIDER = os.environ.get('OCR_PROVIDER', 'ollama')
OCR_PARALLEL_PAGES = int(os.environ.get('OCR_PARALLEL_PAGES', '1'))
OLLAMA_VISION_MODEL = os.environ.get('OLLAMA_VISION_MODEL', 'qwen3-vl:8b-instruct-q4_K_M')

# Handwriting removal before OCR
HANDWRITING_PREPROCESSING = os.environ.get('HANDWRITING_PREPROCESSING', '0') == '1'
HANDWRITING_MODEL_PATH = os.environ.get('HANDWRITING_MODEL_PATH', 'models/handwriting_removal.joblib')
HANDWRITING_PATCH_SIZE = int(os.environ.get('HANDWRITING_PATCH_SIZE', '48'))
HANDWRITING_PATCH_STRIDE = int(os.environ.get('HANDWRITING_PATCH_STRIDE', '24'))
HANDWRITING_PATCHES_PER_IMAGE = int(os.environ.get('HANDWRITING_PATCHES_PER_IMAGE', '256'))
HANDWRITING_THRESHOLD = float(os.environ.get('HANDWRITING_THRESHOLD', '0.7'))
OCR_PROVIDER = os.environ.get('OCR_PROVIDER', 'ollama')
OCR_PARALLEL_PAGES = int(os.environ.get('OCR_PARALLEL_PAGES', '1'))
OLLAMA_VISION_MODEL = os.environ.get('OLLAMA_VISION_MODEL', 'qwen3-vl:8b-instruct-q4_K_M')

# Handwriting removal before OCR
HANDWRITING_PREPROCESSING = os.environ.get('HANDWRITING_PREPROCESSING', '0') == '1'
HANDWRITING_MODEL_PATH = os.environ.get('HANDWRITING_MODEL_PATH', 'models/handwriting_removal.joblib')
HANDWRITING_PATCH_SIZE = int(os.environ.get('HANDWRITING_PATCH_SIZE', '48'))
HANDWRITING_PATCH_STRIDE = int(os.environ.get('HANDWRITING_PATCH_STRIDE', '24'))
HANDWRITING_PATCHES_PER_IMAGE = int(os.environ.get('HANDWRITING_PATCHES_PER_IMAGE', '256'))
HANDWRITING_THRESHOLD = float(os.environ.get('HANDWRITING_THRESHOLD', '0.7'))

# Relation extraction
OLLAMA_EXTRACT_MODEL = os.environ.get('OLLAMA_EXTRACT_MODEL', 'llama3.1:8b')
PARALLEL_CHUNKS = int(os.environ.get('PARALLEL_CHUNKS', '4'))

# Chunking
CHUNKER_TYPE = os.environ.get('CHUNKER_TYPE', 'semantic').lower() # valid values: "default" (src/chunker.py) or "semantic" (src/semantic_chunker.py)

# Entity extraction (NER)
NER_STRATEGY = os.environ.get('NER_STRATEGY', 'gliner').lower() # valid values: "gliner" (src/glinerExtract.py), "llm" (src/llmNER.py), or "classical" (runners/runNerPipeline.py)

# Graph construction route — GRAPH_ROUTE is set in the PROJECT SETUP block at the top of this file.
GRAPH_EXTRACT_BACKEND = os.environ.get('GRAPH_EXTRACT_BACKEND', 'openrouter') # callLLM backend for Route 2 (ollama|groq|openrouter|gemini)
GRAPH_EXTRACT_WORKERS = int(os.environ.get('GRAPH_EXTRACT_WORKERS', '12')) # parallel chunk extraction requests in Route 2

# Chat API
CHAT_DOMAIN = os.environ.get('CHAT_DOMAIN', 'compliance') # system-prompt framing: "compliance" (CBE/ADIB) | "general" (open-domain benchmark data)
OLLAMA_CHAT_MODEL = os.environ.get('OLLAMA_CHAT_MODEL', 'llama3.1:8b')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# OpenRouter (for OpenIE triple extraction)
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', 'meta-llama/llama-3.3-70b-instruct')

# Google AI Studio (Gemini)
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')

# Embedding
BGE_M3_PATH = os.environ.get('BGE_M3_PATH', 'BAAI/bge-m3')
OLLAMA_EMBED_URL = os.environ.get('OLLAMA_EMBED_URL', 'http://localhost:11434/api/embed')
OLLAMA_EMBED_URL = os.environ.get('OLLAMA_EMBED_URL', 'http://localhost:11434/api/embed')
OLLAMA_EMBED_MODEL = os.environ.get('OLLAMA_EMBED_MODEL', 'bge-m3')
EMBED_DIM = int(os.environ.get('EMBED_DIM', '1024'))
CHUNK_EMBED_BATCH = int(os.environ.get('CHUNK_EMBED_BATCH', '16'))
ENTITY_EMBED_BATCH = int(os.environ.get('ENTITY_EMBED_BATCH', '32'))
EMBED_DIM = int(os.environ.get('EMBED_DIM', '1024'))
CHUNK_EMBED_BATCH = int(os.environ.get('CHUNK_EMBED_BATCH', '16'))
ENTITY_EMBED_BATCH = int(os.environ.get('ENTITY_EMBED_BATCH', '32'))

# GLiNER
GLINER_MODEL = 'C:/Users/omarl/.cache/huggingface/hub/models--NAMAA-Space--gliner_arabic-v2.1/snapshots/0403be7e18f0b6d27ddc9dd0e7f1ee6b674c17aa'
GLINER_MODEL_EN = 'urchade/gliner_multi-v2.1'
GLINER_THRESHOLD = 0.7
GLINER_MODEL = 'C:/Users/omarl/.cache/huggingface/hub/models--NAMAA-Space--gliner_arabic-v2.1/snapshots/0403be7e18f0b6d27ddc9dd0e7f1ee6b674c17aa'
GLINER_MODEL_EN = 'urchade/gliner_multi-v2.1'
GLINER_THRESHOLD = 0.7

# Chunking
CHUNK_TARGET_TOKENS = 600

# Entity alignment
SIM_THRESHOLD = 0.92
SKIP_SIM_TYPES = {'Date', 'MonetaryAmount'}

# Retrieval
RRF_K = 60
OVERFETCH = 4        # pull k*OVERFETCH from index, then filter by access control
PATH_DEPTH = 3
SEED_K = 8
PATH_LIMIT = 300
REL_TYPE_TOP = 5
REL_TYPE_FLOOR = 0.25
ENTITY_WEIGHT = 0.6  # path score = ENTITY_WEIGHT * entity_sim + (1-ENTITY_WEIGHT) * rel_sim
LOCAL_COMENTION_EDGES = os.environ.get('LOCAL_COMENTION_EDGES', '0') == '1'  # graph mode: walk COOCCURS_WITH (Route 1 graphs)
