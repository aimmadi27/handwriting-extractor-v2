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

- **Agents** — [LiteLLM](https://github.com/BerriAI/litellm) (supports Gemini, Claude, GPT-4o, Ollama, Groq, NVIDIA NIM, and 100+ more)
- **UI** — Streamlit
- **Exports** — ReportLab (PDF), python-docx (Word), openpyxl (Excel)
- **Auth** — Google OAuth 2.0 with PKCE

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```

Edit `.env` with your chosen LLM and API keys:

```env
# Pick any LiteLLM-compatible model
LLM_MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=your_key_here

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8501/
```

### 3. Run
```bash
streamlit run app.py
```

## Supported LLM providers

Switch models by changing one line in `.env`:

| Provider | Model string | Key needed |
|---|---|---|
| Google Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Anthropic Claude | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Groq | `groq/llama-3.2-90b-vision-preview` | `GROQ_API_KEY` |
| NVIDIA NIM | `nvidia_nim/meta/llama-3.2-90b-vision-instruct` | `NVIDIA_NIM_API_KEY` |
| Ollama (local) | `ollama/llava` | None |

## Project structure

```
├── app.py                  # Streamlit UI (Upload / Extract / Review / Export)
├── orchestrator.py         # Coordinates Parser + Validator agents
├── llm_handler.py          # Universal LLM interface via LiteLLM
├── renderer.py             # Section-type-aware editable Streamlit renderer
├── auth.py                 # Google OAuth 2.0 with PKCE
├── agents/
│   ├── parser.py           # Document classification + content extraction
│   └── validator.py        # Confidence scoring + error correction
├── exporters/
│   ├── pdf_export.py       # ReportLab PDF generation
│   ├── word_export.py      # python-docx Word generation
│   └── excel_export.py     # openpyxl Excel generation
├── requirements.txt
└── .env.example
```
