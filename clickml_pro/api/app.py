"""
FastAPI application factory for ClickML-Pro.

Start with:  clickml serve
              uvicorn clickml_pro.api.app:create_app --factory --reload
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Path to the built React dashboard
_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "ui" / "dashboard" / "dist"


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="ClickML-Pro",
        description="Enterprise MLOps & Data Engineering platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ─────────────────────────────────────────────────────────
    from clickml_pro.api.routes.health import router as health_router
    from clickml_pro.api.routes.training import router as training_router
    from clickml_pro.api.routes.registry import router as registry_router
    from clickml_pro.api.routes.data import router as data_router
    from clickml_pro.api.routes.quantization import router as quant_router
    from clickml_pro.api.routes.governance import router as governance_router
    from clickml_pro.api.routes.notebook import router as notebook_router
    from clickml_pro.api.routes.airflow import router as airflow_router

    app.include_router(health_router)
    app.include_router(training_router, prefix="/api/v1/training", tags=["Training"])
    app.include_router(registry_router, prefix="/api/v1/registry", tags=["Registry"])
    app.include_router(data_router, prefix="/api/v1/data", tags=["Data"])
    app.include_router(quant_router, prefix="/api/v1/quantization", tags=["Quantization"])
    app.include_router(governance_router, prefix="/api/v1/governance", tags=["Governance"])
    app.include_router(notebook_router, prefix="/api/v1/notebook", tags=["Notebook"])
    app.include_router(airflow_router, prefix="/api/v1/airflow", tags=["Airflow ETL"])

    # ── Dashboard (built React SPA) ────────────────────────────────────
    if _DASHBOARD_DIR.is_dir():
        # Serve static assets (JS, CSS, images)
        assets_dir = _DASHBOARD_DIR / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="dashboard-assets")

        # Serve any other static files in dist root (favicon etc.)
        @app.get("/favicon.svg", include_in_schema=False)
        async def favicon():
            fav = _DASHBOARD_DIR / "favicon.svg"
            if fav.exists():
                return FileResponse(str(fav), media_type="image/svg+xml")

        # SPA catch-all: serve index.html for any non-API route
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_catch_all(request: Request, path: str):
            # Don't intercept API, docs, or health routes
            if path.startswith(("api/", "docs", "redoc", "openapi", "health", "ready")):
                return
            index = _DASHBOARD_DIR / "index.html"
            if index.exists():
                return FileResponse(str(index), media_type="text/html")
            return HTMLResponse("<h1>Dashboard not built</h1><p>Run: <code>cd clickml_pro/ui/dashboard && npm run build</code></p>", status_code=404)
    else:
        @app.get("/", include_in_schema=False)
        async def dashboard_not_built():
            return HTMLResponse(
                "<h1>ClickML Pro</h1>"
                "<p>Dashboard not built yet. Run:</p>"
                "<pre>cd clickml_pro/ui/dashboard &amp;&amp; npm install &amp;&amp; npm run build</pre>"
                "<p>API docs available at <a href='/docs'>/docs</a></p>",
            )

    logger.info("ClickML-Pro API ready")
    return app


# Module-level instance so uvicorn can resolve "clickml_pro.api.app:app"
app = create_app()
