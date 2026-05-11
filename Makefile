PYTHON ?= python
PIP ?= pip
ALEMBIC ?= alembic
NPM ?= npm

.PHONY: help install install-frontend migrate upgrade downgrade revision current history run-api run-frontend build-frontend py-compile eval clean

help:
	@echo Available targets:
	@echo   install          Install Python dependencies
	@echo   install-frontend Install frontend dependencies
	@echo   migrate          Create a new Alembic revision with autogenerate
	@echo   upgrade          Apply all database migrations
	@echo   downgrade        Roll back one migration
	@echo   current          Show current Alembic migration
	@echo   history          Show Alembic migration history
	@echo   run-api          Start the FastAPI server
	@echo   run-frontend     Start the Vite dev server
	@echo   build-frontend   Build the frontend for production
	@echo   py-compile       Quick Python syntax check for core backend files
	@echo   eval             Run the retrieval evaluation harness
	@echo   clean            Remove common build artifacts

install:
	$(PIP) install -r requirements.txt

install-frontend:
	cd frontend && $(NPM) install

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

eval:
	$(PYTHON) eval/runEval.py

clean:
	if exist frontend\dist rmdir /s /q frontend\dist
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist src\__pycache__ rmdir /s /q src\__pycache__
	if exist runners\__pycache__ rmdir /s /q runners\__pycache__
