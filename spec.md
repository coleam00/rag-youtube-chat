# RAG YouTube Chat — Product Specification

**Date:** 2026-03-28
**Version:** 1.0

---

## Product Overview

### What It Is
A premium, dark-mode AI chat application that allows users to have natural conversations grounded in YouTube video content from a creator's channel. Users ask questions in a conversational interface; the system retrieves relevant transcript passages from ingested videos and generates accurate, cited answers via an LLM.

### Who It's For
- Fans or followers of a YouTube creator who want to quickly search and explore the creator's back-catalog of content
- Developers and researchers who want to query video knowledge bases conversationally
- Content teams building AI-powered companion products alongside video libraries

### Core Value Proposition
Instead of scrubbing through hours of video to find a specific explanation or insight, users simply ask a question and receive a synthesized, sourced answer — with full conversation history and a chat experience that feels as polished as leading AI platforms.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18 + Vite + TypeScript + Tailwind CSS |
| **Frontend Runtime** | Bun (package manager & dev server runner) |
| **Backend** | Python + FastAPI (single process: API, RAG pipeline, LLM calls) |
| **Database** | SQLite via `aiosqlite` with repository pattern (Postgres-swappable) |
| **Embeddings** | OpenRouter Embeddings API — `openai/text-embedding-3-small` |
| **LLM** | OpenRouter Chat Completions — `anthropic/claude-sonnet-4.6` |
| **Document Processing** | Docling `HybridChunker` (native Python, no microservice) |
| **API Key** | `OPENROUTER_API_KEY` from `.env` in project root |
| **OpenRouter Base URL** | `https://openrouter.ai/api/v1` |
| **Python SDK** | `openai` Python SDK pointed at OpenRouter base URL |
| **Python Env** | `pip` + `python -m venv .venv` |
| **SQLite Path** | `app/backend/data/chat.db` |

---

## Design Language

### Theme & Mood
Dark mode exclusively. The visual identity should evoke **premium developer tooling** — think Linear, Vercel dashboard, Raycast. Clean, spacious, minimal chrome. Every pixel earns its place.

### Color Palette

| Role | Value | Usage |
|---|---|---|
| Background | `#0a0a0f` | Root app background (near-black blue-black) |
| Surface 1 | `#111827` | Sidebar, cards, panels |
| Surface 2 | `#1e293b` | Message backgrounds, input area, hover states |
| Border | `rgba(255,255,255,0.08)` or `#1e293b` | Dividers, card outlines |
| Accent Blue | `#3b82f6` | Primary buttons, active states, links, highlights |
| Accent Blue Dark | `#1d4ed8` | Button hover states |
| Accent Blue Glow | `rgba(59,130,246,0.3)` | Focus rings, subtle glows |
| Text Primary | `#f1f5f9` | All body copy, message content |
| Text Secondary | `#94a3b8` | Timestamps, labels, placeholders, muted info |
| Text Tertiary | `#475569` | Disabled states, very subtle hints |
| User Bubble | `#2563eb` | User message background |
| Assistant Bubble | `#1e293b` | Assistant message background |
| Success | `#10b981` | Ingestion success, status indicators |
| Danger | `#ef4444` | Delete actions, error states |

### Typography

- **Font Family:** `Inter`, falling back to the system font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`)
- **Base size:** 15px
- **Line height:** 1.7 for chat messages (generous, for readability); 1.4 for UI chrome
- **Heading weight:** 600 (semibold)
- **Body weight:** 400 (regular)
- **Code:** `JetBrains Mono`, `Fira Code`, or `monospace` system font at 13px

### Spacing System
- Base unit: 4px
- Standard gaps: 4, 8, 12, 16, 24, 32, 48px
- Generous padding inside message bubbles: 12px 16px
- Chat input textarea padding: 14px 16px

### Component Style Guidelines

**Buttons:**
- Primary: blue background (`#3b82f6`), white text, rounded-lg (8px), slight box-shadow with blue glow on hover
- Secondary: transparent with `#1e293b` border, text secondary color, same rounding
- Destructive: transparent with red accent on hover
- All buttons: no sharp corners, 2px focus ring in accent blue

**Input / Textarea:**
- Background: `#111827`
- Border: `rgba(255,255,255,0.1)` default; animated gradient or solid blue glow (`box-shadow: 0 0 0 2px #3b82f6`) on focus
- Rounded-xl (12px) for the main chat input
- Placeholder text in `#475569`

**Sidebar:**
- Width: 260px (collapsible on mobile via hamburger)
- Background: `#111827`
- Right border: `rgba(255,255,255,0.06)`
- Conversation items: subtle hover (`#1e293b`); active state gets a left blue border (3px) and slightly lighter background
- "New Chat" button: full-width, blue background, pinned to top

**Chat Bubbles:**
- User: right-aligned, max-width 70%, blue background, white text, rounded-2xl with bottom-right corner slightly less rounded
- Assistant: left-aligned, max-width 80%, dark surface background, white text, rounded-2xl
- Both have 4px of vertical spacing between consecutive messages from same sender

**Code Blocks (inside assistant messages):**
- Dark background (`#0d1117`)
- Syntax highlighting via `react-syntax-highlighter` with `oneDark` theme
- Language label in top-right corner, copy-to-clipboard button

**Skeleton Loaders:**
- Animated shimmer (gradient sweep) on `#1e293b` base shapes
- Used when loading conversation list, message history
- No spinners anywhere

**Typing Indicator:**
- Three dots with staggered pulse animation
- Shown in an assistant-style bubble on the left

---

## Project Structure

```
app/
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts          (proxies /api → localhost:8000)
│   ├── index.html
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx             (React Router setup)
│   │   ├── components/
│   │   │   ├── Sidebar.tsx     (conversation list, new chat button)
│   │   │   ├── ChatArea.tsx    (message list + scroll logic)
│   │   │   ├── ChatInput.tsx   (expanding textarea + send button)
│   │   │   ├── Message.tsx     (user/assistant bubble)
│   │   │   └── MarkdownRenderer.tsx  (react-markdown + syntax highlight)
│   │   ├── hooks/
│   │   │   ├── useConversations.ts
│   │   │   ├── useMessages.ts
│   │   │   └── useStreamingResponse.ts
│   │   ├── lib/
│   │   │   └── api.ts          (typed fetch wrappers)
│   │   └── styles/
│   │       └── globals.css
│   └── public/
├── backend/
│   ├── requirements.txt
│   ├── main.py                 (FastAPI app, lifespan startup)
│   ├── config.py               (env vars, loads from absolute .env path)
│   ├── db/
│   │   ├── schema.py           (table definitions, migrations)
│   │   ├── repository.py       (all DB queries — swappable pattern)
│   │   └── seed.py             (10 mock YouTube videos w/ transcripts)
│   ├── rag/
│   │   ├── chunker.py          (Docling HybridChunker wrapper)
│   │   ├── embeddings.py       (OpenRouter embeddings via openai SDK)
│   │   └── retriever.py        (cosine similarity search)
│   ├── llm/
│   │   └── openrouter.py       (streaming chat completions)
│   └── routes/
│       ├── conversations.py
│       ├── messages.py
│       └── ingest.py
├── .env                        (copied/referenced from root)
├── start.sh                    (Unix startup script)
└── start.bat                   (Windows startup script)
```

---

## Database Schema

### `videos`
| Column | Type | Notes |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| title | TEXT | Video title |
| description | TEXT | Short description |
| url | TEXT | YouTube URL (can be mock) |
| transcript | TEXT | Full transcript text |
| created_at | TIMESTAMP | |

### `chunks`
| Column | Type | Notes |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| video_id | TEXT | FK → videos.id |
| content | TEXT | Contextualized chunk text (with heading breadcrumbs) |
| embedding | TEXT | JSON array of floats |
| chunk_index | INTEGER | Order within video |
| start_seconds | REAL | Segment start time in seconds (from Supadata) |
| end_seconds | REAL | Segment end time in seconds (from Supadata) |
| snippet | TEXT | Original transcript text for citation display |

### `conversations`
| Column | Type | Notes |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| title | TEXT | Auto-generated from first user message |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | Updated on each new message |

### `messages`
| Column | Type | Notes |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| conversation_id | TEXT | FK → conversations.id |
| role | TEXT | `user` or `assistant` |
| content | TEXT | Message content |
| created_at | TIMESTAMP | |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/conversations` | List all conversations, sorted by `updated_at` DESC |
| POST | `/api/conversations` | Create a new empty conversation |
| GET | `/api/conversations/{id}` | Get conversation + all messages |
| DELETE | `/api/conversations/{id}` | Delete conversation and its messages |
| POST | `/api/conversations/{id}/messages` | Send a message; returns SSE stream |
| GET | `/api/videos` | List all ingested videos |
| POST | `/api/ingest` | Ingest new video content into the RAG pipeline |
| GET | `/api/health` | Health check (returns status + video count) |

---

## RAG Pipeline

### Ingestion Flow
1. Accept video title, description, URL, and transcript text
2. Build a `DoclingDocument` from the transcript using `DocItemLabel.TITLE`, `SECTION_HEADER`, and `PARAGRAPH` labels
3. Run `HybridChunker(max_tokens=512, merge_peers=True)` on the document
4. For each chunk, call `chunker.contextualize(chunk)` to get heading-enriched text
5. Call OpenRouter embeddings API (`openai/text-embedding-3-small`) on the contextualized text
6. Store the video record and all chunks (with embeddings as JSON) in SQLite
7. On first startup (empty DB), run the seed script automatically to ingest 10 mock videos

### Retrieval Flow
1. Embed the user's query via OpenRouter embeddings API
2. Load all chunk embeddings from SQLite
3. Compute cosine similarity between query embedding and all chunk embeddings in-process (NumPy or pure Python)
4. Return the top-5 chunks with their video metadata

### Generation Flow
1. Format retrieved chunks into a context block with video title citations
2. Construct system prompt instructing the model to answer from context and cite video sources
3. Stream chat completion from OpenRouter (`anthropic/claude-sonnet-4.6`) via `openai` SDK
4. Pipe SSE tokens back to the frontend using FastAPI `StreamingResponse`
5. After stream completes, persist the full assistant message to the database
6. If this is the first message in the conversation, auto-generate a short title from the user's message (via a quick non-streaming LLM call or simple truncation)

### System Prompt Template
```
You are a helpful assistant with access to transcripts from a YouTube creator's video library.
Answer the user's question based ONLY on the provided video context. If the answer isn't in the context, say so honestly.
Always cite which video(s) your answer draws from.

Context:
{retrieved_chunks_with_titles}
```

---

## Seed Data

Generate 10 mock YouTube videos covering AI and coding topics, as if from a technical creator's channel. Example topics:

1. "Building AI Agents from Scratch" — transcript covering agent loops, tool use, planning
2. "Understanding Retrieval-Augmented Generation" — transcript covering RAG architecture, chunking, embeddings
3. "Fine-tuning vs. Prompting: When to Use Each" — transcript on trade-offs
4. "Vector Databases Explained" — transcript on FAISS, Pinecone, pgvector
5. "How I Built a Coding Assistant in One Weekend" — personal project walkthrough
6. "The Future of LLM Tooling" — opinion piece on the ecosystem
7. "Prompt Engineering Best Practices" — tips and patterns
8. "Evaluating AI Outputs: Metrics That Matter" — evals, benchmarks, human feedback
9. "Local LLMs: A Practical Guide" — Ollama, quantization, hardware
10. "Building Production RAG Pipelines" — chunking strategies, re-ranking, hybrid search

Each video should have 3–5 paragraphs of realistic transcript text (300–600 words total).

---

## Feature List

### Sprint 1 — Foundation & Data Layer

**F1: Project Scaffolding**
- *User story:* As a developer, I want a single-command startup that boots both frontend and backend.
- *Description:* Create `app/` directory structure, `start.sh` / `start.bat` scripts, Python venv setup, Bun frontend setup, Vite proxy config for `/api`, environment variable loading from the absolute `.env` path.
- *Sprint:* 1

**F2: Database Schema & Repository Layer**
- *User story:* As a developer, I want a clean data access layer so the database can be swapped without touching business logic.
- *Description:* Define all four SQLite tables via `schema.py`. Implement `repository.py` with async methods for all CRUD operations (conversations, messages, videos, chunks). All DB access goes through the repository — no raw SQL in route handlers.
- *Sprint:* 1

**F3: Video Seed Data**
- *User story:* As a user opening the app for the first time, I want the system to already have video content I can query.
- *Description:* `seed.py` inserts 10 mock YouTube videos with transcripts on first startup. The FastAPI lifespan hook checks if the videos table is empty and runs seeding automatically. Log progress to stdout.
- *Sprint:* 1

**F4: Docling Chunking Integration**
- *User story:* As a developer, I want transcripts intelligently chunked for high-quality retrieval.
- *Description:* `chunker.py` wraps `HybridChunker`. Accepts a video dict, builds a `DoclingDocument`, runs the chunker, and returns a list of contextualized text strings ready for embedding.
- *Sprint:* 1

---

### Sprint 2 — RAG Pipeline

**F5: Embeddings Service**
- *User story:* As the system, I need to embed both document chunks and user queries for semantic search.
- *Description:* `embeddings.py` uses the `openai` SDK pointed at `https://openrouter.ai/api/v1` with `OPENROUTER_API_KEY`. Exposes `embed_text(text: str) -> list[float]` and `embed_batch(texts: list[str]) -> list[list[float]]`. Used at ingest time and at query time.
- *Sprint:* 2

**F6: Cosine Similarity Retriever**
- *User story:* As the system, I need to find the most relevant transcript chunks for any user query.
- *Description:* `retriever.py` loads all chunk embeddings from SQLite (via repository), computes cosine similarity against a query embedding, returns the top-K chunks with their video title and content. Pure Python/NumPy — no external vector DB required for MVP.
- *Sprint:* 2

**F7: Ingest API Endpoint**
- *User story:* As an admin, I want to ingest new YouTube video content via an API call.
- *Description:* `POST /api/ingest` accepts `{ title, description, url, transcript }`. Runs chunking → embedding → storage pipeline. Returns a summary of chunks created. Used internally by the seed script and externally for future content additions.
- *Sprint:* 2

**F8: Streaming LLM Generation**
- *User story:* As a user, I want to see the AI's response appear word-by-word as it's generated.
- *Description:* `openrouter.py` wraps the `openai` SDK for streaming chat completions against `anthropic/claude-sonnet-4.6`. Accepts a list of messages and a context string. Yields token strings as a generator. The route handler wraps this in a FastAPI `StreamingResponse` with `text/event-stream` content type and proper SSE formatting (`data: {token}\n\n`).
- *Sprint:* 2

---

### Sprint 3 — Conversation API & Core Chat

**F9: Conversation Management API**
- *User story:* As a user, I want my chat history persisted and organized into named conversations.
- *Description:* Implement all conversation CRUD endpoints: list (sorted by recency), create, get-with-messages, delete. Auto-generate conversation title from the first user message (truncate to ~50 chars or use a quick LLM call). Update `conversations.updated_at` on every new message.
- *Sprint:* 3

**F10: Message Send & RAG Response**
- *User story:* As a user, I want to send a message and receive a contextually grounded streaming reply.
- *Description:* `POST /api/conversations/{id}/messages` orchestrates the full RAG pipeline: save user message → embed query → retrieve top-5 chunks → build prompt → stream LLM response back as SSE → persist final assistant message. Handle conversation-not-found with 404.
- *Sprint:* 3

**F11: Videos List API**
- *User story:* As a user, I want to know which videos are in the knowledge base.
- *Description:* `GET /api/videos` returns all ingested videos with id, title, description, url, and created_at. Used by the frontend's source explorer.
- *Sprint:* 3

---

### Sprint 4 — Frontend Shell & Chat UI

**F12: App Shell & Routing**
- *User story:* As a user, I want a stable layout with sidebar and chat area that feels like a real AI product.
- *Description:* Set up React Router with routes for `/` (redirect to new chat) and `/c/:conversationId`. Implement the two-column layout: fixed sidebar (260px) + flex chat area. Dark background, all global CSS variables defined. Inter font loaded.
- *Sprint:* 4

**F13: Sidebar — Conversation List**
- *User story:* As a user, I want to see all my past conversations and quickly switch between them.
- *Description:* Sidebar fetches and displays all conversations sorted by recency. Each item shows: auto-generated title, relative timestamp ("2 hours ago"), and a truncated preview of the last message. Active conversation highlighted with blue left-border accent. Skeleton loaders while fetching. Delete button on hover (with confirmation). "New Chat" button pinned to top with blue background.
- *Sprint:* 4

**F14: Chat Area & Message Rendering**
- *User story:* As a user, I want to read conversations with clear visual distinction between my messages and AI responses.
- *Description:* Loads and displays all messages for the active conversation. User messages: right-aligned, blue bubble. Assistant messages: left-aligned, dark surface bubble with Markdown rendering (`react-markdown` + `react-syntax-highlighter` with `oneDark` theme for code blocks). Skeleton loaders while fetching message history. Auto-scroll to bottom on new messages; pause auto-scroll if user has scrolled up.
- *Sprint:* 4

**F15: Chat Input**
- *User story:* As a user, I want a comfortable, responsive way to type and send messages.
- *Description:* A `<textarea>` that auto-expands with content (up to ~6 lines) and shrinks after send. Blue animated glow on focus (`box-shadow`). Send button (blue, arrow icon) on the right; also submits on `Enter` (with `Shift+Enter` for newlines). Disabled and greyed-out while a response is streaming. Fixed to the bottom of the chat area with a subtle gradient fade above it.
- *Sprint:* 4

---

### Sprint 5 — Streaming, Polish & Delight

**F16: Real-Time Streaming in the UI**
- *User story:* As a user, I want to see the AI response stream in token-by-token, not appear all at once.
- *Description:* `useStreamingResponse` hook reads the SSE stream from the messages endpoint using the Fetch API's `ReadableStream`. Tokens are appended to a transient `streamingContent` state that renders in an assistant bubble. Typing indicator (three pulsing dots) shown immediately while waiting for the first token. On stream end, the message transitions from streaming to persisted state.
- *Sprint:* 5

**F17: Optimistic Message Updates**
- *User story:* As a user, I want my message to appear instantly when I send it, without a delay.
- *Description:* When the user submits a message, it's added to the message list immediately (optimistic update) with a temporary ID before the API call completes. If the API call fails, the optimistic message is removed and an error toast is shown.
- *Sprint:* 5

**F18: Source Citations Display**
- *User story:* As a user, I want to see which videos the AI's answer came from.
- *Description:* The assistant's message includes a collapsible "Sources" section at the bottom showing which video titles were cited. Parse source video titles from the LLM response or include them as metadata in the SSE stream's final event. Display as small blue-bordered chips/tags below the message content.
- *Sprint:* 5

**F19: Video Knowledge Base Explorer**
- *User story:* As a user, I want to browse what videos are available in the knowledge base.
- *Description:* A small "Sources" or "Library" panel accessible from the sidebar (icon button). Shows all ingested videos as cards with title, description, and a link. Helps users understand what they can ask about. Styled as a slide-over panel or modal.
- *Sprint:* 5

**F20: Empty States & Error Handling**
- *User story:* As a user, I want clear, friendly feedback when something goes wrong or when a view is empty.
- *Description:* Empty conversation state: centered illustration/icon with "Ask anything about the video library" prompt text and suggested starter questions. Empty sidebar: "No conversations yet" with a CTA to start one. API error states: inline error message with a retry button. Network error toast notification system (top-right corner, auto-dismiss after 4s).
- *Sprint:* 5

---

### Sprint 6 — Quality, Testing & DevEx

**F21: Health Check & Status Endpoint**
- *User story:* As a developer, I want to verify the backend is running and data is loaded.
- *Description:* `GET /api/health` returns `{ status: "ok", video_count: N, chunk_count: N, db_path: "..." }`. Used by the frontend to show a subtle status indicator and by the evaluator agent to confirm seeding worked.
- *Sprint:* 6

**F22: Conversation Title Auto-Generation**
- *User story:* As a user, I want my conversations to have meaningful names without having to name them myself.
- *Description:* After the first user message is sent, generate a short (≤6 word) conversation title. Use a fast non-streaming LLM call with a tight prompt ("Summarize this question in 5 words or fewer: {message}"), or fall back to truncating the first message. Update the sidebar title immediately when it resolves.
- *Sprint:* 6

**F23: Mobile-Responsive Sidebar**
- *User story:* As a mobile user, I want the sidebar to collapse so I can use the full screen for chat.
- *Description:* On viewports below 768px, the sidebar slides off-screen by default. A hamburger icon in the top bar opens it as an overlay. Tapping a conversation closes the sidebar. Smooth CSS transition (`transform: translateX`).
- *Sprint:* 6

**F24: Performance & Startup Optimization**
- *User story:* As a developer, I want the app to start fast and handle seed data gracefully.
- *Description:* Seed script runs in the FastAPI lifespan `startup` event only if the `videos` table is empty. Embedding generation during seeding is batched (send multiple texts per API call). The frontend uses `React.lazy` + `Suspense` for non-critical panels. Vite build produces optimized chunks.
- *Sprint:* 6

---

## Sprint Plan Summary

| Sprint | Theme | Key Deliverables |
|---|---|---|
| **Sprint 1** | Foundation & Data | Project scaffolding, DB schema + repo, seed data, Docling chunking |
| **Sprint 2** | RAG Pipeline | Embeddings service, cosine retriever, ingest endpoint, streaming LLM |
| **Sprint 3** | Conversation API | All conversation/message REST endpoints, full RAG orchestration |
| **Sprint 4** | Frontend Shell | App layout, sidebar, chat area, message rendering, chat input |
| **Sprint 5** | Streaming & Polish | SSE streaming UI, optimistic updates, source citations, video explorer, error states |
| **Sprint 6** | Quality & DevEx | Health check, title auto-gen, mobile responsive, perf optimization |

---

## Environment & Configuration

### Required Environment Variables
| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | API key for OpenRouter (embeddings + chat completions) |

### Absolute .env Path
The `.env` file is located at `C:/Users/colem/open-source/adversarial-dev/.env`.
`config.py` should load it with `python-dotenv` using the absolute path:
```python
load_dotenv("C:/Users/colem/open-source/adversarial-dev/.env")
```
Also copy or symlink it to `app/.env` for convenience.

### Key Configuration Constants
| Constant | Value |
|---|---|
| OpenRouter Base URL | `https://openrouter.ai/api/v1` |
| Embedding Model | `openai/text-embedding-3-small` |
| Chat Model | `anthropic/claude-sonnet-4.6` |
| HybridChunker max_tokens | 512 |
| Retrieval top-K | 5 |
| SQLite DB path | `app/backend/data/chat.db` |
| Backend port | 8000 |
| Frontend port | 5173 |

---

## Python Dependencies (`requirements.txt`)

```
fastapi
uvicorn[standard]
aiosqlite
httpx
python-dotenv
openai
docling-core[chunking]
numpy
```

## Frontend Dependencies (`package.json`)

```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18",
    "react-router-dom": "^6",
    "react-markdown": "^9",
    "react-syntax-highlighter": "^15",
    "remark-gfm": "^4",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "@types/react-syntax-highlighter": "^15"
  },
  "devDependencies": {
    "vite": "^5",
    "@vitejs/plugin-react": "^4",
    "typescript": "^5",
    "tailwindcss": "^3",
    "autoprefixer": "^10",
    "postcss": "^8"
  }
}
```

---

## Startup Scripts

### `start.sh` (Unix/Mac)
1. Check if `backend/.venv` exists; if not, create it with `python -m venv .venv`
2. Activate venv and run `pip install -r backend/requirements.txt`
3. Create `backend/data/` directory if it doesn't exist
4. Copy root `.env` to `app/.env` if not present
5. Start FastAPI: `uvicorn backend.main:app --reload --port 8000 &`
6. Check if `frontend/node_modules` exists; if not, run `bun install` in `frontend/`
7. Start Vite: `cd frontend && bun run dev`

### `start.bat` (Windows)
Same steps using Windows batch syntax, using `Scripts\activate` for venv.

---

## E2E Testability Notes

The app is designed to be fully testable via `agent-browser`:

- All interactive elements have clear semantic roles (buttons, textareas, links)
- The "New Chat" button is always visible and labeled
- Chat input textarea is a standard `<textarea>` element
- The send button is a `<button>` with a recognizable label/icon
- Conversation list items are `<li>` or `<button>` elements with the conversation title as visible text
- Streaming responses append text that is queryable with `agent-browser wait --text`
- The dark theme is applied via a root class or CSS variables verifiable via snapshot
- Port 5173 (frontend) and 8000 (backend) are the standard ports
- `GET /api/health` can be polled to confirm backend readiness before running browser tests

---

*End of Specification*
