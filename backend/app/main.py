from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import meta, export

app = FastAPI(title="BDC API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    """Simple healthcheck endpoint."""
    return {"status": "ok"}

app.include_router(meta.router, prefix="/meta", tags=["meta"]) 
app.include_router(export.router, prefix="/export", tags=["export"]) 
