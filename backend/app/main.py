from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api.v1 import api_router as api_v1_router

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AgroCast API — система климатического анализа и поддержки решений",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Подключаем роуты v1
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
