PYTHON ?= python
PIP ?= pip
ALEMBIC ?= alembic
NPM ?= npm

.PHONY: help install install-frontend install-test migrate upgrade downgrade revision current history run-api run-frontend build-frontend py-compile eval test test-parser test-chunker test-embedding test-semantic test-gliner test-llm-ner test-config test-classical-ner test-cov test-modules test-modules-parser test-modules-ner test-modules-embedding test-modules-classical-ner test-integration test-all clean

help:
	@echo Available targets:
	@echo   install          Install Python dependencies
	@echo   install-frontend Install frontend dependencies
	@echo   install-test     Install test dependencies
	@echo   migrate          Create a new Alembic revision with autogenerate
	@echo   upgrade          Apply all database migrations
	@echo   downgrade        Roll back one migration
	@echo   current          Show current Alembic migration
	@echo   history          Show Alembic migration history
	@echo   run-api          Start the FastAPI server
	@echo   run-frontend     Start the Vite dev server
	@echo   build-frontend   Build the frontend for production
	@echo   py-compile       Quick Python syntax check for core backend files
	@echo   test             Run all unit tests
	@echo   test-parser      Run parser unit tests only
	@echo   test-chunker     Run chunker unit tests only
	@echo   test-embedding   Run embedding unit tests only
	@echo   test-semantic    Run semantic chunker unit tests only
	@echo   test-gliner      Run GLiNER extraction unit tests only
	@echo   test-llm-ner     Run LLM NER unit tests only
	@echo   test-config      Run configuration unit tests only
	@echo   test-classical-ner Run classical NER unit tests only
	@echo   test-cov         Run tests with coverage report
	@echo   test-modules     Run all module integration tests
	@echo   test-modules-parser    Run parser-chunker integration tests only
	@echo   test-modules-ner       Run NER pipeline integration tests only
	@echo   test-modules-embedding Run embedding pipeline integration tests only
	@echo   test-modules-classical-ner Run classical NER pipeline module tests only
	@echo   test-integration Run all integration (end-to-end) tests
	@echo   test-all         Run all tests (unit + module + integration) with coverage
	@echo   eval             Run the retrieval evaluation harness
	@echo   clean            Remove common build artifacts

install:
	$(PIP) install -r requirements.txt

install-frontend:
	cd frontend && $(NPM) install

install-test:
	$(PIP) install -r tests/requirements-test.txt

migrate:
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

upgrade:
	$(ALEMBIC) upgrade head

downgrade:
	$(ALEMBIC) downgrade -1

current:
	$(ALEMBIC) current

history:
	$(ALEMBIC) history

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
