# Crisis Resource Intelligence Network — Runbook

Concise startup guide from a fresh terminal. This project runs locally as a **portfolio prototype** (simulated inventory data, draft AI briefings).

## Prerequisites

- Docker Desktop installed and running
- Python 3.11+ with project venv created (`pip install -r requirements.txt`)
- `.env` configured from `.env.example` (especially `DATABASE_URL` on port **5433**)
- For AI briefings only: [Ollama](https://ollama.com/) with `llama3.2` pulled

---

## Startup (fresh terminal)

### 1. Start Docker / PostgreSQL

```bash
docker compose up -d
```

### 2. Activate venv

**Windows (PowerShell):**

```powershell
.\venv\Scripts\activate
```

**macOS / Linux:**

```bash
source venv/bin/activate
```

### 3. Run health check

```bash
python -m scripts.health_check
```

Expected when all services are up:

```
[OK] Database connection
[OK] FastAPI backend
[OK] RAG context endpoint
[OK] AI briefing endpoint
```

> Run step 4 before expecting FastAPI/RAG/AI checks to pass. Database can pass after step 1 alone.

### 4. Start FastAPI

```bash
python -m uvicorn backend.main:app --reload --port 8001
```

Leave this terminal open. API docs: http://127.0.0.1:8001/docs

### 5. Start dashboard (second terminal)

Activate venv again, then:

```bash
streamlit run dashboard/app.py
```

Dashboard: http://localhost:8501

### 6. Optional — Ollama (AI-assisted briefings)

```bash
ollama list
ollama run llama3.2
```

AI briefings are optional. Template briefs and retrieved crisis context work without Ollama.

---

## First-time RAG setup (if health check fails on RAG)

Run once after PostgreSQL is up and Ollama has `nomic-embed-text`:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
python -m rag.build_corpus
python -m rag.chunk_documents
python -m database.create_rag_tables
python -m rag.embed_chunks
```

Then restart FastAPI and re-run `python -m scripts.health_check`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `[FAIL] Database connection` | Confirm **Docker Desktop is running**, then `docker compose up -d`. Verify `DATABASE_URL` in `.env` matches `docker-compose.yml` (port **5433**). |
| `[FAIL] FastAPI backend` | Start or restart FastAPI: `python -m uvicorn backend.main:app --reload --port 8001` |
| `[FAIL] RAG context endpoint` | Ensure RAG corpus/chunks/embeddings are built (see first-time RAG setup). Confirm `ZONE001` exists in the database. |
| `[WARN] AI briefing endpoint` | Start Ollama, confirm `llama3.2` is installed (`ollama list`), then retry. Dashboard still works without AI. |
| Dashboard shows backend warning | FastAPI not reachable on port **8001** — restart API and refresh the dashboard. |
| Port 8001 already in use | Stop the other process or use a different port (dashboard expects `8001` by default). |

**Do not run `docker compose down -v` unless you intentionally want to delete the database volume and reload all data.**

---

## Shutdown

```bash
# Stop FastAPI and Streamlit: Ctrl+C in each terminal

# Stop PostgreSQL container (keeps data):
docker compose down
```

---

## Quick reference

| Service | URL / command |
|---------|----------------|
| PostgreSQL | `localhost:5433` (via Docker) |
| FastAPI | http://127.0.0.1:8001 |
| Dashboard | http://localhost:8501 |
| Health check | `python -m scripts.health_check` |
