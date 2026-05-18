import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from limiter import limiter
from logger import setup_logging, set_request_id, reset_request_id, new_request_id
from routers import auth, upload, extract, export, documents

load_dotenv()
setup_logging()

app = FastAPI(
    title="InkScan API",
    description="AI-powered handwriting digitisation pipeline.",
    version="2.0.0",
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request-ID middleware ─────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or new_request_id()
    token = set_request_id(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        reset_request_id(token)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router,    prefix="/auth",    tags=["auth"])
app.include_router(upload.router,  prefix="/upload",  tags=["upload"])
app.include_router(extract.router, prefix="/extract", tags=["extract"])
app.include_router(export.router,     prefix="/export",    tags=["export"])
app.include_router(documents.router,  prefix="/documents", tags=["documents"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
