"""FastAPI application wiring."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .config import Settings
from .config import settings as default_settings
from .dashboard import render_dashboard
from .devin_client import DevinClient
from .models import GitHubWebhookPayload
from .service import RemediationService
from .store import Store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("remediation")


def create_app(
    settings: Settings | None = None,
    *,
    store: Store | None = None,
    devin_client: DevinClient | None = None,
    enable_poller: bool = True,
) -> FastAPI:
    """Application factory.

    Dependencies can be injected (used by tests to supply a fake Devin client
    and an in-memory store). When omitted, real implementations are created
    from ``settings``.
    """
    cfg = settings or default_settings
    the_store = store or Store(cfg.database_path)
    the_client = devin_client or DevinClient(cfg.devin_api_key, cfg.devin_api_base)
    service = RemediationService(cfg, the_store, the_client)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        poller_task: asyncio.Task | None = None
        if enable_poller:
            poller_task = asyncio.create_task(_poll_loop(service, cfg.poll_interval_seconds))
        try:
            yield
        finally:
            if poller_task is not None:
                poller_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await poller_task
            await the_client.aclose()
            the_store.close()

    app = FastAPI(title="Devin Remediation Automation", version="1.0.0", lifespan=lifespan)
    app.state.settings = cfg
    app.state.store = the_store
    app.state.service = service

    def get_service() -> RemediationService:
        return app.state.service

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.post("/webhook/github")
    async def github_webhook(
        request: Request, svc: RemediationService = Depends(get_service)
    ) -> JSONResponse:
        payload_dict = await request.json()
        payload = GitHubWebhookPayload.model_validate(payload_dict)
        result = await svc.handle_webhook(payload)
        return JSONResponse(result)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(svc: RemediationService = Depends(get_service)) -> HTMLResponse:
        remediations = svc.store.list_all()
        html = render_dashboard(remediations, svc.settings.target_repo)
        return HTMLResponse(html)

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            {
                "service": "devin-remediation-automation",
                "endpoints": ["/healthz", "/webhook/github", "/dashboard"],
            }
        )

    return app


async def _poll_loop(service: RemediationService, interval: int) -> None:
    """Background loop that periodically refreshes active session statuses."""
    while True:
        try:
            await service.poll_active_sessions()
        except Exception:  # noqa: BLE001
            logger.exception("Error during background poll")
        await asyncio.sleep(interval)


# Module-level app for `uvicorn app.main:app`.
app = create_app()
