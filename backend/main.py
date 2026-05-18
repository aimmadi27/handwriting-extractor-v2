from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import auth, upload, extract, export

load_dotenv()

app = FastAPI(
    title="Handwriting Extractor API",
    description="Multi-agent pipeline for digitising any handwritten document.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # CRA dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,   prefix="/auth",   tags=["auth"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(extract.router, prefix="/extract", tags=["extract"])
app.include_router(export.router,  prefix="/export",  tags=["export"])


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
