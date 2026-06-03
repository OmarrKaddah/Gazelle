import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j
NEO4J_URI = os.environ['NEO4J_URI']
NEO4J_USER = os.environ['NEO4J_USER']
NEO4J_PASSWORD = os.environ['NEO4J_PASSWORD']

# Ollama / llama-server endpoints
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

# Relation extraction
OLLAMA_EXTRACT_MODEL = os.environ.get('OLLAMA_EXTRACT_MODEL', 'granite4.1:8b')
PARALLEL_CHUNKS = int(os.environ.get('PARALLEL_CHUNKS', '4'))

# Chunking
CHUNKER_TYPE = os.environ.get('CHUNKER_TYPE', 'semantic').lower() # valid values: "default" (src/chunker.py) or "semantic" (src/semantic_chunker.py)

# Entity extraction (NER)
NER_STRATEGY = os.environ.get('NER_STRATEGY', 'gliner').lower() # valid values: "gliner" (src/glinerExtract.py) or "llm" (src/llmNER.py)

# Chat API
OLLAMA_CHAT_MODEL = os.environ.get('OLLAMA_CHAT_MODEL', 'llama3.1:8b')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# OpenRouter (for OpenIE triple extraction)
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', 'moonshotai/kimi-k2.6:free')

# Google AI Studio (Gemini)
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')

# Embedding
BGE_M3_PATH = os.environ.get('BGE_M3_PATH', 'BAAI/bge-m3')
OLLAMA_EMBED_URL = os.environ.get('OLLAMA_EMBED_URL', 'http://localhost:11434/api/embed')
OLLAMA_EMBED_MODEL = os.environ.get('OLLAMA_EMBED_MODEL', 'bge-m3')
EMBED_DIM = int(os.environ.get('EMBED_DIM', '1024'))
CHUNK_EMBED_BATCH = int(os.environ.get('CHUNK_EMBED_BATCH', '16'))
ENTITY_EMBED_BATCH = int(os.environ.get('ENTITY_EMBED_BATCH', '32'))

# GLiNER
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
