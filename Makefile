PYTHON ?= python
PIP ?= pip
NPM ?= npm

.PHONY: help quick-start setup-db setup-ollama setup-env run-ingestion setup-synonyms setup-communities run-system graph-dump graph-restore install install-frontend run-api run-frontend build-frontend py-compile eval test test-parser test-chunker test-embedding test-semantic test-gliner test-llm-ner test-config test-cov test-modules test-modules-parser test-modules-ner test-modules-embedding test-integration test-all services-docker services-stop docker-neo4j docker-ollama clean

help:
	@echo "Gazelle — Graph-Grounded RAG for Banking Compliance"
	@echo ""
	@echo "Quick Start targets (run in order):"
	@echo "  quick-start      Run full setup in one command (requires manual service setup)"
	@echo "  setup-env        Configure .env file from .env.example"
	@echo "  setup-db         Initialize SQLite database"
	@echo "  setup-ollama     Pull required Ollama models"
	@echo "  run-ingestion    Run full OCR→Parse→Chunk→NER→KG→Embed pipeline"
	@echo "  setup-synonyms   Add entity synonym (SYNONYM) edges"
	@echo "  setup-communities Detect communities and generate summaries (Route 2 only)"
	@echo "  run-system       Start API and frontend dev servers"
	@echo ""
	@echo "Services (Docker):"
	@echo "  services-docker  Start Neo4j and Ollama via Docker"
	@echo "  services-stop    Stop all Docker services"
	@echo "  docker-neo4j     Start Neo4j container only (http://localhost:7474)"
	@echo "  docker-ollama    Start Ollama container only (localhost:11434)"
	@echo ""
	@echo "Alternative graph pipeline (skip full ingestion):"
	@echo "  graph-dump       Dump current Neo4j graph to JSONL (backup)"
	@echo "  graph-restore    Restore graph from JSONL file (requires dump file)"
	@echo "  graph-restore    DUMP=dumps/myfile.jsonl  (specify dump file)"
	@echo ""
	@echo "Installation targets:"
	@echo "  install          Install Python dependencies"
	@echo "  install-frontend Install frontend dependencies"
	@echo "  install-test     Install test dependencies"
	@echo ""
	@echo "Server targets:"
	@echo "  run-api          Start the FastAPI server (http://localhost:8000)"
	@echo "  run-frontend     Start the Vite dev server (http://localhost:5173)"
	@echo "  build-frontend   Build the frontend for production"
	@echo ""
	@echo "Testing targets:"
	@echo "  py-compile       Quick Python syntax check for core backend files"
	@echo "  test             Run all unit tests"
	@echo "  test-parser      Run parser unit tests only"
	@echo "  test-chunker     Run chunker unit tests only"
	@echo "  test-embedding   Run embedding unit tests only"
	@echo "  test-semantic    Run semantic chunker unit tests only"
	@echo "  test-gliner      Run GLiNER extraction unit tests only"
	@echo "  test-llm-ner     Run LLM NER unit tests only"
	@echo "  test-config      Run configuration unit tests only"
	@echo "  test-cov         Run tests with coverage report"
	@echo "  test-modules     Run all module integration tests"
	@echo "  test-modules-parser    Run parser-chunker integration tests only"
	@echo "  test-modules-ner       Run NER pipeline integration tests only"
	@echo "  test-modules-embedding Run embedding pipeline integration tests only"
	@echo "  test-integration Run all integration (end-to-end) tests"
	@echo "  test-all         Run all tests (unit + module + integration) with coverage"
	@echo "  eval             Run the retrieval evaluation harness"
	@echo "  clean            Remove common build artifacts"
	@echo ""
	@echo "Prerequisites:"
	@echo "  • Python 3.10+ (3.12 recommended)"
	@echo "  • Node.js 18+ (20+ recommended)"
	@echo "  • Neo4j 5.x (Community Edition or Enterprise)"
	@echo "  • Ollama (for local models)"
	@echo "  • Docker (optional, for easy service startup with make services-docker)"
	@echo "  • .env file configured (copy from .env-example)"
	@echo ""

quick-start: install install-frontend setup-db
	@echo ""
	@echo "✓ Quick-start setup complete!"
	@echo ""
	@echo "Database created: ./gazelle.db (SQLite)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Start Neo4j and Ollama: make services-docker"
	@echo "  2. Update .env with your API keys (already configured for SQLite)"
	@echo "  3. Download Ollama models: make setup-ollama"
	@echo "  4. Place your documents in Documents/ directory"
	@echo "  5. Run the pipeline: make run-ingestion"
	@echo "  6. Start the app: make run-api (Terminal A) + make run-frontend (Terminal B)"
	@echo ""

setup-env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env from .env.example"; \
		echo "  Edit .env with your credentials and API keys"; \
	else \
		echo "✓ .env already exists (skipping copy)"; \
	fi

setup-db:
	@echo "Initializing SQLite database..."
	$(PYTHON) -c "import sys; sys.path.insert(0, 'src'); from db.session import initDb; import asyncio; asyncio.run(initDb())"
	@echo "✓ SQLite database initialized at ./gazelle.db"

setup-ollama:
	ollama pull qwen3-vl:8b-instruct-q4_K_M
	ollama pull bge-m3
	ollama pull granite4.1:8b
	@echo "✓ Ollama models downloaded"

run-ingestion:
	@echo "Running full ingestion pipeline (OCR → Parse → Chunk → NER → KG → Embed)..."
	$(PYTHON) runners/runPipeline.py

setup-synonyms:
	@echo "Adding entity synonym edges..."
	$(PYTHON) graphTraversal/runSynonyms.py
	@echo "✓ Synonym edges created"

setup-communities:
	@echo "Detecting communities and generating summaries..."
	$(PYTHON) graphTraversal/runCommunities.py
	$(PYTHON) runners/runCommunitySummary.py
	@echo "✓ Communities and summaries generated"

run-system:
	@echo "Starting API and frontend servers..."
	@echo "  API:      http://localhost:8000"
	@echo "  Frontend: http://localhost:5173"
	@echo ""
	@echo "In another terminal, run:"
	@echo "  make run-api"
	@echo "  make run-frontend"
	@echo ""
	$(PYTHON) runners/runApi.py

services-docker:
	@echo "Starting Neo4j and Ollama via Docker..."
	@echo ""
	@echo "Neo4j:  http://localhost:7474 (user: neo4j, password: your_password)"
	@echo "Ollama: localhost:11434"
	@echo ""
	@echo "Starting containers..."
	docker run -d -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/your_password --name gazelle-neo4j neo4j:5-community || echo "Neo4j container already running (gazelle-neo4j)"
	docker run -d -p 11434:11434 --gpus=all --name gazelle-ollama ollama/ollama || echo "Ollama container already running (gazelle-ollama)"
	@echo ""
	@echo "✓ Services started!"
	@echo "Database: SQLite at ./gazelle.db (no PostgreSQL needed)"
	@echo ""
	@echo "To stop all services, run: make services-stop"

services-stop:
	@echo "Stopping and removing Docker containers..."
	docker stop gazelle-neo4j gazelle-ollama 2>/dev/null || true
	docker rm gazelle-neo4j gazelle-ollama 2>/dev/null || true
	@echo "✓ All services stopped"

docker-neo4j:
	@echo "Starting Neo4j (http://localhost:7474)..."
	docker run -d -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/your_password --name gazelle-neo4j neo4j:5-community || echo "Neo4j already running"

docker-ollama:
	@echo "Starting Ollama (localhost:11434)..."
	docker run -d -p 11434:11434 --gpus=all --name gazelle-ollama ollama/ollama || echo "Ollama already running"

graph-dump:
	@echo "Dumping Neo4j graph to JSONL file..."
	$(PYTHON) runners/dumpGraph.py dumps/graph.jsonl
	@echo "✓ Graph dumped. To restore later, run:"
	@echo "  make graph-restore DUMP=dumps/graph.jsonl"

graph-restore:
	@if [ -z "$(DUMP)" ]; then \
		echo "Usage: make graph-restore DUMP=<dump_file.jsonl>"; \
		echo "Example: make graph-restore DUMP=dumps/graph.jsonl"; \
		exit 1; \
	fi
	@echo "Restoring Neo4j graph from $(DUMP)..."
	@echo "⚠ This will WIPE the current database and restore from the dump."
	@echo "Press Ctrl+C within 3 seconds to cancel..."
	$(PYTHON) -c "import time; time.sleep(3)"
	$(PYTHON) runners/restoreGraph.py $(DUMP)
	@echo "✓ Graph restored successfully"
	@echo ""
	@echo "Note: The restored graph includes all entities, relationships, and embeddings."
	@echo "You do NOT need to run the full ingestion pipeline again."

install:
	$(PIP) install -r requirements.txt

install-frontend:
	cd frontend && $(NPM) install

run-api:
	$(PYTHON) runners/runApi.py

run-frontend:
	cd frontend && $(NPM) run dev

build-frontend:
	cd frontend && $(NPM) run build

py-compile:
	$(PYTHON) -m py_compile src/chatApi.py src/auth.py src/db/models.py src/db/session.py src/db/repositories/authRepo.py src/db/repositories/chatRepo.py src/db/repositories/memoryRepo.py

test:
	$(PYTHON) -m pytest tests/unit-tests -v

test-parser:
	$(PYTHON) -m pytest tests/unit-tests/test_parser.py -v

test-chunker:
	$(PYTHON) -m pytest tests/unit-tests/test_chunker.py -v

test-embedding:
	$(PYTHON) -m pytest tests/unit-tests/test_embedding.py -v

test-semantic:
	$(PYTHON) -m pytest tests/unit-tests/test_semantic_chunker.py -v

test-gliner:
	$(PYTHON) -m pytest tests/unit-tests/test_glinerExtract.py -v

test-llm-ner:
	$(PYTHON) -m pytest tests/unit-tests/test_llmNER.py -v

test-config:
	$(PYTHON) -m pytest tests/unit-tests/test_config.py -v

test-classical-ner:
	$(PYTHON) -m pytest tests/unit-tests/test_classical_ner.py -v

test-cov:
	$(PYTHON) -m pytest tests/unit-tests --cov=src --cov-report=html --cov-report=term-missing

test-modules:
	$(PYTHON) -m pytest tests/module-tests -v

test-modules-parser:
	$(PYTHON) -m pytest tests/module-tests/test_parser_chunker_integration.py -v

test-modules-ner:
	$(PYTHON) -m pytest tests/module-tests/test_ner_pipeline_integration.py -v

test-modules-embedding:
	$(PYTHON) -m pytest tests/module-tests/test_embedding_pipeline_integration.py -v

test-modules-classical-ner:
	$(PYTHON) -m pytest tests/module-tests/test_classical_ner_pipeline.py -v

test-integration:
	$(PYTHON) -m pytest tests/integration-tests -v

test-all:
	$(PYTHON) -m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing -v

eval:
	$(PYTHON) eval/runEval.py

clean:
	if exist frontend\dist rmdir /s /q frontend\dist
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist src\__pycache__ rmdir /s /q src\__pycache__
	if exist runners\__pycache__ rmdir /s /q runners\__pycache__
