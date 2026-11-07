import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import lifespan
from routes.webhooks import router as webhooks_router

app = FastAPI(title="PakHook API", version="1.0.0", lifespan=lifespan)

origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(webhooks_router, prefix="/api")


@app.get("/health")
async def health():
    return {"ok": True}
