# RAG YouTube Chat

A dark-mode AI chat app that lets you have conversations grounded in YouTube video content. Ask questions about a creator's videos and get synthesized, cited answers pulled from transcript passages.

![Main chat interface](app/screenshots/screenshot-main.png)

## Architecture

```
┌─────────────────┐       /api proxy        ┌─────────────────────────┐
│    Frontend      │ ─────────────────────── │        Backend          │
│  React + Vite    │    localhost:5173 →      │       FastAPI           │
│  TypeScript      │        :8000            │                         │
│  Tailwind CSS    │                         │  Routes ── RAG Pipeline │
└─────────────────┘                         │    │        │           │
                                            │    │     Chunker        │
                                            │    │     (Docling)      │
                                            │    │        │           │
                                            │    DB    Embeddings     │
                                            │  (SQLite) (OpenRouter)  │
                                            │            │           │
                                            │         Retriever      │
                                            │       (NumPy cosine)   │
                                            │            │           │
                                            │          LLM           │
                                            │    (Claude via         │
                                            │     OpenRouter)        │
                                            └─────────────────────────┘
```

**Frontend:** React 18 + Vite + TypeScript + Tailwind CSS (Bun)
**Backend:** Python FastAPI, single process handling API + RAG + LLM
**Database:** SQLite via aiosqlite (Postgres-swappable via repository pattern)
**LLM:** Claude Sonnet via OpenRouter with SSE streaming
**Embeddings:** text-embedding-3-small via OpenRouter
**Chunking:** Docling HybridChunker
**Retrieval:** NumPy cosine similarity, top-5 chunks

## Quick Start

### Prerequisites

- Python 3.11+
- [Bun](https://bun.sh)
- An [OpenRouter](https://openrouter.ai) API key

### Setup

1. Clone the repo and create a `.env` file in the project root:

```
OPENROUTER_API_KEY=your-key-here
```

2. Start everything:

```bash
# Unix/Mac
cd app && ./start.sh

# Windows
cd app && start.bat
```

This will set up the Python venv, install dependencies, seed the database with 10 sample videos, and start both servers.

3. Open [http://localhost:5173](http://localhost:5173)

### Manual Start

If you prefer to run the servers separately:

1. Create a `.env` file in the project root:

```
OPENROUTER_API_KEY=your-key-here
```

2. Start the backend:

```bash
cd app
python -m venv backend/.venv
source backend/.venv/bin/activate  # or backend\.venv\Scripts\activate on Windows
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

On first run, the backend automatically creates the SQLite database and seeds it with 10 sample videos (this requires your `OPENROUTER_API_KEY` to generate embeddings and may take a moment).

3. Start the frontend (new terminal):

```bash
cd app/frontend
bun install
bun run dev
```

## How It Works

1. **Ingest** - Video transcripts are chunked with Docling's HybridChunker and embedded via OpenRouter
2. **Retrieve** - User queries are embedded and matched against chunks using cosine similarity
3. **Generate** - Top-5 chunks are passed as context to Claude, which streams a cited response back via SSE
