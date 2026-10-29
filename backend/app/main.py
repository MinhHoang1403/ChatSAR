"""Health endpoints tối thiểu cho nền tảng ChatSAR."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from app.auth import router as auth_router
from app.config import get_settings
from app.database import database_ready
from app.errors import AppError
from app.workspace import router as workspace_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    get_settings()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="ChatSAR", version="0.1.0", lifespan=lifespan)
    application.include_router(auth_router)
    application.include_router(workspace_router)

    @application.exception_handler(AppError)
    async def application_error(request: Request, error: AppError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {"code": error.code, "message": error.message},
                "request_id": request.state.request_id,
            },
            status_code=error.status,
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {"code": "INVALID_REQUEST", "message": "Dữ liệu gửi lên không hợp lệ."},
                "request_id": request.state.request_id,
            },
            status_code=422,
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Chưa thể xử lý yêu cầu. Vui lòng thử lại.",
                },
                "request_id": request.state.request_id,
            },
            status_code=503,
        )

    @application.middleware("http")
    async def request_identifier(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith(
            "/api/"
        ):
            if request.headers.get("Origin") != get_settings().app_origin:
                return JSONResponse(
                    {
                        "error": {
                            "code": "ORIGIN_REJECTED",
                            "message": "Nguồn yêu cầu không hợp lệ.",
                        },
                        "request_id": request.state.request_id,
                    },
                    status_code=403,
                )
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
