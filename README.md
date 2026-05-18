# Handwriting Extractor v2

An AI-powered web app that accepts any handwritten or filled document — receipts, bank slips, assessments, letters, forms — and converts it into a structured, editable digital version.

## How it works

```
PDF Upload
    ↓
Parser Agent     → identifies document type + extracts full content as typed sections
    ↓
Validator Agent  → checks accuracy, assigns confidence scores, flags issues
    ↓
Review UI        → side-by-side original image + editable digital document
    ↓
Export           → PDF  |  Word (.docx)  |  Excel (.xlsx)  |  JSON
```

The parser outputs structured **sections** — `key_value`, `table`, `qa_pair`, or `paragraph` — depending on what it finds on the page. This works for any document type without pre-defined schemas.

## Tech stack

- **Backend** — [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Frontend** — [React 19](https://react.dev/) + TypeScript + Vite + Tailwind CSS
- **Agents** — [LiteLLM](https://github.com/BerriAI/litellm) (supports Gemini, Claude, GPT-4o, Ollama, Groq, NVIDIA NIM, and 100+ more)
- **Exports** — ReportLab (PDF), python-docx (Word), openpyxl (Excel)
- **Auth** — Google OAuth 2.0 with PKCE + JWT

## Project structure

```
├── backend/
│   ├── main.py                 # FastAPI app + CORS + router registration
│   ├── orchestrator.py         # Coordinates Parser + Validator agents
│   ├── llm_handler.py          # Universal LLM interface via LiteLLM
│   ├── storage.py              # In-memory stores (upload, result, PKCE)
│   ├── dependencies.py         # JWT Bearer auth dependency
│   ├── agents/
│   │   ├── parser.py           # Document classification + content extraction
│   │   └── validator.py        # Confidence scoring + error correction
│   ├── routers/
│   │   ├── auth.py             # Google OAuth 2.0 with PKCE
│   │   ├── upload.py           # PDF upload + page-to-PNG conversion
│   │   ├── extract.py          # SSE streaming extraction endpoint
│   │   └── export.py           # PDF / Word / Excel / JSON export
│   ├── exporters/
│   │   ├── pdf_export.py       # ReportLab PDF generation
│   │   ├── word_export.py      # python-docx Word generation
│   │   └── excel_export.py     # openpyxl Excel generation
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── pages/
        │   ├── HomePage.tsx        # Landing + login
        │   ├── AppPage.tsx         # 3-step flow: upload → extract → review
        │   └── AuthCallback.tsx    # OAuth redirect handler
        ├── components/
        │   ├── SectionEditor.tsx   # Editable section renderer
        │   ├── PagePicker.tsx      # Thumbnail page selector
        │   ├── ProgressFeed.tsx    # Real-time SSE progress display
        │   └── ExportBar.tsx       # Export buttons
        ├── api/
        │   ├── client.ts           # Typed API client + SSE streaming
        │   └── types.ts            # Shared TypeScript types
        └── hooks/
            └── useAuth.ts          # JWT auth state
```

## Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env`:

```env
# Pick any LiteLLM-compatible model
LLM_MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=your_key_here

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# JWT signing secret
JWT_SECRET=your_random_secret_here

# React dev server
FRONTEND_URL=http://localhost:5173
```

```bash
uvicorn main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Supported LLM providers

Switch models by changing one line in `backend/.env`:

| Provider | Model string | Key needed |
|---|---|---|
| Google Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Anthropic Claude | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Groq | `groq/llama-3.2-90b-vision-preview` | `GROQ_API_KEY` |
| NVIDIA NIM | `nvidia_nim/meta/llama-3.2-90b-vision-instruct` | `NVIDIA_NIM_API_KEY` |
| Ollama (local) | `ollama/llava` | None |
