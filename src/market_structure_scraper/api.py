from fastapi import FastAPI, HTTPException

from . import __version__
from .config import Settings
from .models import Capabilities, CollectionRequest, CollectionResponse
from .service import CollectorService, capabilities

settings = Settings()
service = CollectorService(settings)
app = FastAPI(
    title="Market Structure Scraper",
    version=__version__,
    description="Nasdaq symbol-directory and FINRA short-volume research evidence.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/capabilities", response_model=Capabilities)
async def get_capabilities() -> Capabilities:
    return capabilities(settings)


@app.post("/v1/collect", response_model=CollectionResponse)
async def collect(request: CollectionRequest) -> CollectionResponse:
    try:
        return await service.collect(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

