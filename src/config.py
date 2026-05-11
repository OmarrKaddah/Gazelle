import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j
NEO4J_URI = os.environ['NEO4J_URI']
NEO4J_USER = os.environ['NEO4J_USER']
NEO4J_PASSWORD = os.environ['NEO4J_PASSWORD']

# Ollama / llama-server endpoints
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
LLAMA_SERVER_URL = "http://localhost:8080/v1/chat/completions"

# OCR
OCR_PROVIDER = "ollama"          # "ollama" or "local" (llama-server)
OCR_PARALLEL_PAGES = 1
OLLAMA_VISION_MODEL = "qwen3-vl:8b-instruct-q4_K_M"

# Relation extraction
OLLAMA_EXTRACT_MODEL = os.environ.get('OLLAMA_EXTRACT_MODEL', 'granite4.1:8b')
PARALLEL_CHUNKS = 4              # Match OLLAMA_NUM_PARALLEL on the Ollama server

# Chat API
OLLAMA_CHAT_MODEL = os.environ.get('OLLAMA_CHAT_MODEL', 'granite4.1:8b')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# Embedding
BGE_M3_PATH = os.environ.get('BGE_M3_PATH', 'BAAI/bge-m3')
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
OLLAMA_EMBED_MODEL = os.environ.get('OLLAMA_EMBED_MODEL', 'bge-m3')
EMBED_DIM = 1024
CHUNK_EMBED_BATCH = 16
ENTITY_EMBED_BATCH = 32

# GLiNER
GLINER_MODEL = 'NAMAA-Space/gliner_arabic-v2.1'
GLINER_THRESHOLD = 0.5

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
