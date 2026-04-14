# RAG YouTube Chat API

Comprehensive reference documentation for all backend API endpoints.

## Base URL

```
http://localhost:8000/api
```

## Content Type

All request bodies must be JSON (`Content-Type: application/json`) unless otherwise noted.

---

## Endpoints

### Conversations

#### `GET /api/conversations`

List all conversations, sorted by `updated_at` descending.

**Response** `200 OK`

```json
[
  {
    "id": "conv_abc123",
    "title": "How does RAG work?",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T11:45:00Z",
    "preview": "RAG retrieves relevant chunks..."
  }
]
```

**Response fields**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Unique conversation ID |
| `title` | `string` | Conversation title (auto-generated from first user message, max 50 chars) |
| `created_at` | `string` | ISO 8601 timestamp |
| `updated_at` | `string` | ISO 8601 timestamp |
| `preview` | `string \| null` | Short preview of the last assistant message |

---

#### `POST /api/conversations`

Create a new empty conversation.

**Request body** (all fields optional — defaults shown)

```json
{
  "title": "New Conversation"
}
```

If the body is omitted entirely, the conversation is created with the default title `"New Conversation"`.

**Response** `201 Created`

```json
{
  "id": "conv_xyz789",
  "title": "New Conversation",
  "created_at": "2024-01-15T12:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z",
  "preview": null
}
```

---

#### `GET /api/conversations/{conv_id}`

Get a single conversation including all messages.

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conv_id` | `string` | The conversation ID |

**Response** `200 OK`

```json
{
  "id": "conv_abc123",
  "title": "How does RAG work?",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:45:00Z",
  "preview": "RAG retrieves relevant chunks...",
  "messages": [
    {
      "id": "msg_001",
      "conversation_id": "conv_abc123",
      "role": "user",
      "content": "How does RAG retrieval work?",
      "created_at": "2024-01-15T10:30:00Z",
      "sources": null
    },
    {
      "id": "msg_002",
      "conversation_id": "conv_abc123",
      "role": "assistant",
      "content": "RAG retrieves relevant chunks from the video corpus...",
      "created_at": "2024-01-15T10:30:05Z",
      "sources": ["Understanding RAG", "Vector Similarity Explained"]
    }
  ]
}
```

**Error responses**

| Status | Detail |
|--------|--------|
| `404` | `"Conversation not found"` |

---

#### `DELETE /api/conversations/{conv_id}`

Delete a conversation and all its associated messages.

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conv_id` | `string` | The conversation ID |

**Response** `204 No Content`

**Error responses**

| Status | Detail |
|--------|--------|
| `404` | `"Conversation not found"` |

---

### Messages

#### `POST /api/conversations/{conv_id}/messages`

Send a user message and stream the RAG-grounded assistant response.

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `conv_id` | `string` | The conversation ID |

**Request body**

```json
{
  "content": "What is the main topic of the video?"
}
```

**Validation**

- `content` must be a non-empty string (whitespace-only strings are rejected).

**Response** `200 OK` — `Content-Type: text/event-stream`

The response is a **Server-Sent Events (SSE)** stream. The client should read it as a stream of events.

**SSE Event format**

Each token from the LLM is sent as a separate SSE `data` event. Tokens are JSON-encoded to safely handle newlines and special characters:

```
data: "<json-encoded-token>"

```

When the stream is complete, a `[DONE]` signal is sent:

```
data: [DONE]

```

**Example SSE stream**

```
data: "RAG"
data: " retrieves"
data: " relevant"
data: " chunks"
data: " from"
data: " the"
data: " video"
data: " corpus"
data: "."
data: [DONE]

```

**Sources event** — Before the `[DONE]` signal, an `event: sources` line is emitted listing the video titles used as context:

```
event: sources
data: ["Understanding RAG", "Vector Similarity Explained"]

data: [DONE]

```

**SSE response headers**

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

**Error responses**

| Status | Detail |
|--------|--------|
| `404` | `"Conversation not found"` |

**Response fields** (for persisted assistant message)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Message ID |
| `conversation_id` | `string` | Parent conversation ID |
| `role` | `"user" \| "assistant"` | Message author |
| `content` | `string` | Message text |
| `created_at` | `string` | ISO 8601 timestamp |
| `sources` | `string[] \| null` | RAG source video titles (populated for assistant messages) |

---

### Videos

#### `GET /api/videos`

List all ingested videos.

**Response** `200 OK`

```json
[
  {
    "id": "vid_abc123",
    "title": "Understanding RAG",
    "description": "An introduction to retrieval-augmented generation",
    "url": "https://www.youtube.com/watch?v=...",
    "created_at": "2024-01-10T09:00:00Z"
  }
]
```

---

### Ingest

#### `POST /api/ingest`

Ingest a new video into the RAG pipeline. Accepts video metadata and transcript text, then runs the full **chunk → embed → store** pipeline.

**Request body**

```json
{
  "title": "Understanding RAG",
  "description": "An introduction to retrieval-augmented generation",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "transcript": "Welcome to this video on RAG..."
}
```

**Validation**

- `title` — non-empty string
- `description` — non-empty string
- `url` — valid URL
- `transcript` — non-empty string

**Response** `200 OK`

```json
{
  "video_id": "vid_abc123",
  "chunks_created": 12,
  "status": "ok"
}
```

**Response fields**

| Field | Type | Description |
|-------|------|-------------|
| `video_id` | `string` | ID of the newly created video record |
| `chunks_created` | `number` | Number of text chunks stored |
| `status` | `string` | `"ok"` on success, `"stored_no_chunks"` if chunker returned 0 chunks |

**Error responses**

| Status | Detail |
|--------|--------|
| `422` | Pydantic validation error (field missing, empty, or invalid URL) |
| `502` | `"Embeddings API request failed: <error>"` — the embeddings API is unavailable |
| `500` | `"Mismatch between chunk count and embedding count."` — internal error |

---

### Ingest Pipeline Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                        INGEST PIPELINE                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  POST /api/ingest                                                     │
│       │                                                               │
│       ▼                                                               │
│  ┌─────────────┐                                                     │
│  │   Validate  │ ── 422 ──► Reject bad input                         │
│  │   Request   │                                                     │
│  └──────┬──────┘                                                     │
│         │                                                             │
│         ▼                                                             │
│  ┌──────────────┐                                                    │
│  │  Create DB   │ ── 200 ──► Return { video_id, status }             │
│  │  Video Record│      └─ "stored_no_chunks" if no chunks            │
│  └──────┬───────┘                                                     │
│         │                                                             │
│         ▼                                                             │
│  ┌─────────────────────────────────────────┐                         │
│  │         Docling HybridChunker            │                         │
│  │  max_tokens=512, merge_peers=True       │                         │
│  │  → contextualize each chunk              │                         │
│  │  → returns list[str]                     │                         │
│  └──────┬───────────────────────────────────┘                         │
│         │                                                             │
│         ▼                                                             │
│  ┌─────────────────────────────────────────┐                         │
│  │   OpenRouter Embeddings API             │                         │
│  │   openai/text-embedding-3-small        │ ──► 502 Bad Gateway     │
│  │   Batched batched API call              │                         │
│  └──────┬───────────────────────────────────┘                         │
│         │                                                             │
│         ▼                                                             │
│  ┌─────────────────────────────────────────┐                         │
│  │   Store chunks in SQLite                │                         │
│  │   (content + embedding JSON)           │                         │
│  └──────┬───────────────────────────────────┘                         │
│         │                                                             │
│         ▼                                                             │
│  ┌─────────────────────────────────────────┐                         │
│  │   Return IngestResponse                 │                         │
│  │   { video_id, chunks_created, status }  │                         │
│  └─────────────────────────────────────────┘                         │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Health

#### `GET /api/health`

Health check endpoint. Returns database and pipeline status.

**Response** `200 OK`

```json
{
  "status": "ok",
  "video_count": 10,
  "chunk_count": 142,
  "db_path": "/path/to/database.db"
}
```

**Response fields**

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | Always `"ok"` if the server is responding |
| `video_count` | `number` | Total number of ingested videos |
| `chunk_count` | `number` | Total number of stored text chunks |
| `db_path` | `string` | Path to the SQLite database file |

---

## Error Response Format

All error responses follow FastAPI's standard format:

```json
{
  "detail": "Human-readable error message"
}
```

---

## Shared Types

### `Conversation`

```typescript
interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  preview?: string | null
}
```

### `Message`

```typescript
interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  sources?: string[] // RAG source video titles — only populated for freshly-streamed assistant messages
}
```

### `Video`

```typescript
interface Video {
  id: string
  title: string
  description: string
  url: string
  created_at: string
}
```

### `ConversationWithMessages`

```typescript
interface ConversationWithMessages extends Conversation {
  messages: Message[]
}
```

---

## RAG Pipeline Overview

The application uses a three-stage RAG (Retrieval-Augmented Generation) pipeline:

### Ingestion
1. Accept video metadata and transcript via `POST /api/ingest`
2. Chunk the transcript using Docling `HybridChunker` (512 tokens, peer merging)
3. Contextualize each chunk (inject heading/title context)
4. Generate embeddings via OpenRouter (`text-embedding-3-small`)
5. Store video record and chunks with embeddings in SQLite

### Retrieval
1. On a new user message, embed the query via OpenRouter
2. Load all chunk embeddings from SQLite
3. Compute cosine similarity between query and all chunks
4. Return the top-5 most relevant chunks with video metadata

### Generation
1. Format top-K chunks into a context block with video title citations
2. Build a system prompt instructing the model to answer from context and cite sources
3. Stream the response from OpenRouter (`claude-sonnet-4.6`) as SSE
4. Inject an `event: sources` line before `[DONE]` listing the source video titles
5. Persist the full assistant message to the database after the stream completes
6. Auto-generate conversation title from the first user message (if still the default)
