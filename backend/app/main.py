from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import meta, reports

app = FastAPI(title="BDC API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(meta.router, prefix="/meta", tags=["meta"]) 
app.include_router(reports.router, prefix="/reports", tags=["reports"])
