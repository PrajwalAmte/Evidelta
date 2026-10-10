from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.change_detection import router as change_detection_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.extraction import router as extraction_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.issues import router as issues_router
from app.api.routes.llm import router as llm_router
from app.api.routes.probes import router as probes_router
from app.api.routes.replay import router as replay_router
from app.api.routes.sources import router as sources_router
from app.api.routes.status_page import router as status_page_router
from app.api.routes.synthesis import router as synthesis_router
from app.api.routes.ui import router as ui_router
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="External Change Intelligence for AI and Developer Platforms",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(ingestion_router, prefix=settings.api_prefix)
    app.include_router(probes_router, prefix=settings.api_prefix)
    app.include_router(sources_router, prefix=settings.api_prefix)
    app.include_router(extraction_router, prefix=settings.api_prefix)
    app.include_router(issues_router, prefix=settings.api_prefix)
    app.include_router(replay_router, prefix=settings.api_prefix)
    app.include_router(change_detection_router, prefix=settings.api_prefix)
    app.include_router(status_page_router, prefix=settings.api_prefix)
    app.include_router(synthesis_router, prefix=settings.api_prefix)
    app.include_router(evaluation_router, prefix=settings.api_prefix)
    app.include_router(llm_router, prefix=settings.api_prefix)
    app.include_router(ui_router, prefix=settings.api_prefix)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "status": "ok"}

    return app


app = create_app()
