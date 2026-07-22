from fastapi import FastAPI

from src.ingestion.router import router as ingestion_router

app = FastAPI(title="repo-stats-herald")
app.include_router(ingestion_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
