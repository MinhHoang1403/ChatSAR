"""Health endpoints tối thiểu cho nền tảng ChatSAR."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.config import get_settings
from app.database import database_ready


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    get_settings()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="ChatSAR", version="0.1.0", lifespan=lifespan)

    @application.middleware("http")
    async def request_identifier(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.get("/live")
    def live(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "request_id": request.state.request_id})

    @application.get("/ready")
    def ready(request: Request) -> JSONResponse:
        available = database_ready()
        return JSONResponse(
            {
                "status": "ok" if available else "unavailable",
                "request_id": request.state.request_id,
            },
            status_code=200 if available else 503,
        )

    @application.get("/health")
    def health(request: Request) -> JSONResponse:
        available = database_ready()
        return JSONResponse(
            {
                "status": "ok" if available else "unavailable",
                "cloud_calls_allowed": get_settings().generation_allowed,
                "request_id": request.state.request_id,
            },
            status_code=200 if available else 503,
        )

    return application


app = create_app()
