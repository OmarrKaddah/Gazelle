# Gazelle — Bank Deployment Checklist

Follow these steps in order on the bank's server. Each step has a "check" so
you know it worked before moving on.

---

## 1. Install the required software

Install these (accept "Add to PATH" during each installer where offered):

- **Python 3.10+**  — https://www.python.org/downloads/  (tick "Add python.exe to PATH")
- **Node.js LTS**   — https://nodejs.org  (for building the web UI)
- **Git**           — https://git-scm.com
- **Ollama**        — https://ollama.com  (runs the AI models)
- **PostgreSQL 14+**— https://www.postgresql.org/download/  (remember the postgres password)
- **Neo4j 5+**      — https://neo4j.com/download/  (the knowledge graph)

Check: open a new terminal and run each — they should print a version:
`python --version`, `node --version`, `git --version`, `ollama --version`,
`psql --version`, and Neo4j should be running.

---

## 2. Get the code

```
git clone <YOUR-REPO-URL> Gazelle
cd Gazelle
git checkout feat/frontend-docs        # or main, once merged
```

---

## 3. Install Python dependencies

```
pip install -r requirements.txt
```

---

## 4. Create the `.env` file

Create a file named `.env` in the project root with this content (fill in your
real passwords/keys):

```
# Databases
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PG_PASSWORD@127.0.0.1:5432/gazelle
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=YOUR_NEO4J_PASSWORD

# Optional cloud LLM (leave blank if using only local Ollama)
GROQ_API_KEY=

# AI models (production-grade for Arabic banking docs)
OLLAMA_VISION_MODEL=qwen3-vl:30b-a3b-instruct
OLLAMA_TEXT_MODEL=qwen2.5:72b-instruct-q4_K_M
OLLAMA_EXTRACT_MODEL=qwen2.5:72b-instruct-q4_K_M
OLLAMA_CHAT_MODEL=qwen2.5:72b-instruct-q4_K_M
OLLAMA_EMBED_MODEL=bge-m3

# Pipeline settings
NER_STRATEGY=llm
CHUNKER_TYPE=semantic        # use "default" if the server has no internet
```

---

## 5. Make sure the services are running

- PostgreSQL service is started
- Neo4j is started
- Ollama is running: `ollama serve` (or it runs as a background service)

---

## 6. Set up the database (one time)

```
python runners/createDb.py        # creates the 'gazelle' database
python -m alembic upgrade head     # creates tables + seeds the demo users
```

Check: no errors. This also creates the login accounts.

---

## 7. Pull the AI models

```
python runners/pullModels.py
```

This reads the model names from your `.env` and downloads each one. It can take
a while (the models are large). Check: it ends with "Done. Pulled N model(s)."

---

## 8. Build the web UI

```
cd frontend
npm install
npm run build
cd ..
```

Check: a `frontend/dist` folder now exists. The backend serves the UI from it.

---

## 9. Start Gazelle

```
python runners/runApi.py
```

Open **http://localhost:8000** in the browser.

---

## 10. Use it

- Log in as the admin (default `omar` / `admin123`).
- You land on the **Admin Console**.
- Upload documents (PDF, Word, images, text) and click **Publish**.
- New documents/entities/relationships are added to the Neo4j graph
  incrementally — existing graph data is never deleted.
- Click **Chat with Gazelle** to ask questions about the published documents.

Check the graph in Neo4j Browser (http://localhost:7474):
```
MATCH (n) RETURN count(n);
MATCH p=(d:Document)<-[:PART_OF]-(:Chunk)<-[:MENTIONED_IN]-(:Entity) RETURN p LIMIT 100;
```

---

## Production / security notes

- **Change the default users and passwords** before real use (they are seeded
  by the migration for demo only).
- Put the app behind HTTPS and restrict access.
- **Air-gapped server (no internet):** set `CHUNKER_TYPE=default` so the chunker
  doesn't try to download a model from HuggingFace.
- **Hardware:** `qwen3-vl:30b` and `qwen2.5:72b` need a GPU or a large-RAM
  server. If the machine is smaller, use lighter tags (e.g.
  `qwen3-vl:8b-instruct-q4_K_M`, `qwen2.5:7b-instruct`) in `.env`.
- Only images and scanned PDFs use the vision model; digital PDFs, Word, and
  text are read directly with no OCR.
```
