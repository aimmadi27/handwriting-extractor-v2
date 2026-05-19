# InkScan

An AI-powered web app that converts handwritten or filled documents — receipts, bank slips, assessments, letters, forms — into structured, editable digital records.

## How it works

```
Upload (PDF or image)
    ↓
Parser Agent      → identifies document type, extracts full content as typed sections
    ↓
Validator Agent   → checks accuracy, assigns confidence scores, flags issues
    ↓
Review UI         → side-by-side original image + editable digital document
    ↓
Export            → PDF  |  Word (.docx)  |  Excel (.xlsx)  |  JSON
```

The parser outputs structured **sections** — `key_value`, `table`, `qa_pair`, or `paragraph` — based on what it finds on the page. No pre-defined schemas required; it adapts to any document type.

---

## Features

- **Upload** — PDF, JPG, PNG, WEBP, or TIFF (up to 50 MB)
- **Batch upload** — drop multiple files at once; each extracts in parallel with live progress
- **Combine images** — merge multiple image files into one multi-page document
- **Async extraction** — ARQ task queue (Redis-backed) processes pages in parallel; SSE streams results live
- **Reconnect-safe** — cached results are re-emitted immediately if the browser reconnects
- **Document history** — all extractions saved to PostgreSQL; browse, rename, and re-open anytime
- **Editor** — inline editing of every extracted field, table row, and paragraph; add/delete rows
- **Confidence UI** — color-coded confidence bar per page; section-level badges flag low-confidence fields
- **Re-extract** — re-run extraction on any individual page without leaving the review screen
- **Auto-save** — edits are saved to the database 1 s after you stop typing
- **Export** — PDF, Word (.docx), Excel (.xlsx), or raw JSON from any document
- **Google OAuth** — PKCE flow, httpOnly refresh tokens, silent token refresh
- **Rate limiting** — per-user daily page quota + per-endpoint request limits

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11) |
| Task queue | ARQ + Redis |
| Database | PostgreSQL 16 + SQLAlchemy (async) + Alembic |
| Cache / pub-sub | Redis 7 |
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS |
| LLM | LiteLLM (Gemini, Claude, GPT-4o, Groq, Ollama, …) |
| Auth | Google OAuth 2.0 with PKCE + JWT (access + refresh tokens) |
| Exports | ReportLab (PDF) · python-docx (Word) · openpyxl (Excel) |
| Container | Docker Compose |

---

## Quick start (Docker)

```bash
git clone https://github.com/aimmadi27/handwriting-extractor-v2
cd handwriting-extractor-v2

# Create backend environment file
cp backend/.env.example backend/.env
# → fill in the values (see Configuration below)

docker compose up --build
```

Open **http://localhost** — the app is served by nginx on port 80.

> **First run:** Alembic runs `upgrade head` automatically on backend startup. No manual migration steps needed.

---

## Configuration

Edit `backend/.env`:

```env
# ── LLM ──────────────────────────────────────────────────────────────────────
LLM_MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=your_key_here

# ── Google OAuth ──────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET=generate_a_long_random_string_here

# ── App ───────────────────────────────────────────────────────────────────────
FRONTEND_URL=http://localhost
MAX_UPLOAD_MB=50
MAX_PAGES=50
MAX_PAGES_PER_DAY=100
```

### Supported LLM providers

Switch models by changing one line in `.env`:

| Provider | `LLM_MODEL` value | API key variable |
|---|---|---|
| Google Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Anthropic Claude | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Groq | `groq/llama-3.2-90b-vision-preview` | `GROQ_API_KEY` |
| NVIDIA NIM | `nvidia_nim/meta/llama-3.2-90b-vision-instruct` | `NVIDIA_NIM_API_KEY` |
| Ollama (local) | `ollama/llava` | _(none)_ |

---

## Local development (without Docker)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in values

# Start PostgreSQL and Redis locally first, then:
alembic upgrade head
uvicorn main:app --reload --port 8000

# In a separate terminal — start the ARQ worker:
arq worker.WorkerSettings
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

> The Vite dev server proxies `/api/*` to `http://localhost:8000`.

---

## Architecture

```
Browser
  │
  ├─ GET/POST /api/*  ─────────────────────────────► FastAPI (port 8000)
  │                                                       │
  │                                              ┌────────┴────────┐
  │                                           Router            Router
  │                                          /upload           /extract
  │                                              │                 │
  │  SSE ◄──────────────── Redis pub/sub ◄───── │    ARQ Worker ◄─┘
  │                                              │         │
  │                                           PostgreSQL   │
  │                                           (documents,  │
  │                                            pages)    LLM API
  │                                                   (Parser + Validator)
  │
  └─ Static assets ────────────────────────────► nginx (port 80)
```

**Extraction flow:**
1. `POST /api/upload` — converts PDF pages or images to PNG, stores in Redis (2-hour TTL), creates a `Document` row in PostgreSQL
2. `POST /api/extract` — sets a page counter in Redis, enqueues one ARQ job per page, then subscribes to a Redis pub/sub channel and streams events back as SSE
3. **Worker** — each job fetches the page image, runs Parser → Validator, publishes `progress` / `result` / `error` events, upserts the `Page` row in PostgreSQL, and decrements the counter (marking the document `done` when it hits zero)
4. **Reconnect** — if SSE drops, the cached Redis results are re-emitted instantly on reconnect; only uncached pages are re-enqueued

---

## Project structure

```
├── backend/
│   ├── main.py                  # FastAPI app, CORS, router registration
│   ├── worker.py                # ARQ worker — extract_page job + lifecycle hooks
│   ├── orchestrator.py          # Coordinates Parser + Validator agents
│   ├── llm_handler.py           # Universal LLM interface via LiteLLM
│   ├── storage.py               # Redis helpers (uploads, results, auth tokens, quotas)
│   ├── models.py                # SQLAlchemy ORM models (User, Document, Page)
│   ├── database.py              # Async engine + session factory
│   ├── dependencies.py          # JWT Bearer auth dependency
│   ├── limiter.py               # SlowAPI rate limiter
│   ├── logger.py                # Structured logging setup
│   ├── agents/
│   │   ├── parser.py            # Document classification + structured extraction
│   │   └── validator.py         # Confidence scoring + error correction
│   ├── routers/
│   │   ├── auth.py              # Google OAuth 2.0 with PKCE + refresh tokens
│   │   ├── upload.py            # Single-file upload + /combine multi-image endpoint
│   │   ├── extract.py           # SSE streaming endpoint (enqueues ARQ jobs)
│   │   ├── documents.py         # Document CRUD, page auto-save, rename, status
│   │   └── export.py            # PDF / Word / Excel / JSON export
│   ├── exporters/
│   │   ├── pdf_export.py        # ReportLab PDF generation
│   │   ├── word_export.py       # python-docx Word generation
│   │   └── excel_export.py      # openpyxl Excel generation
│   ├── migrations/
│   │   └── versions/            # Alembic migration scripts
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── HomePage.tsx         # Landing page + sign-in
│       │   ├── AppPage.tsx          # Upload → extract → review flow (single + batch)
│       │   ├── HistoryPage.tsx      # Paginated document list with inline rename
│       │   ├── DocumentPage.tsx     # Load saved document, edit, export
│       │   └── AuthCallback.tsx     # OAuth redirect handler
│       ├── components/
│       │   ├── SectionEditor.tsx    # Editable section renderer + confidence bar
│       │   ├── BatchQueue.tsx       # Batch upload progress list
│       │   ├── PagePicker.tsx       # Thumbnail page selector
│       │   ├── ProgressFeed.tsx     # Real-time SSE progress display
│       │   └── ExportBar.tsx        # Export format buttons
│       ├── api/
│       │   ├── client.ts            # Typed API client with auto token-refresh
│       │   └── types.ts             # Shared TypeScript types
│       └── hooks/
│           ├── useAuth.ts           # Auth state + logout
│           └── useDebounce.ts       # Debounced callback for auto-save
│
├── docker-compose.yml           # postgres + redis + backend + worker + frontend
└── README.md
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/auth/login` | Returns Google OAuth URL |
| `GET` | `/api/auth/callback` | OAuth redirect handler |
| `POST` | `/api/auth/refresh` | Silent access-token refresh |
| `POST` | `/api/auth/logout` | Revoke refresh token |
| `GET` | `/api/auth/me` | Current user info |
| `POST` | `/api/upload` | Upload a single PDF or image |
| `POST` | `/api/upload/combine` | Merge multiple images into one document |
| `DELETE` | `/api/upload/{id}` | Delete an upload from Redis |
| `POST` | `/api/extract` | Enqueue extraction jobs + SSE stream |
| `GET` | `/api/documents` | List user's documents (paginated) |
| `GET` | `/api/documents/{id}` | Get document + all extracted pages |
| `PATCH` | `/api/documents/{id}` | Rename document |
| `DELETE` | `/api/documents/{id}` | Delete document |
| `GET` | `/api/documents/{id}/status` | Lightweight extraction status check |
| `PATCH` | `/api/documents/{id}/pages/{n}` | Auto-save page edits |
| `POST` | `/api/export/{format}` | Export (`pdf`, `word`, `excel`, `json`) |
