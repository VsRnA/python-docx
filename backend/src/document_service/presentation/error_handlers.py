import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


async def http_exception_handler(_: Request, error: StarletteHTTPException) -> JSONResponse:
    detail = error.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", "http_error"))
        message = str(detail.get("message", "Request failed"))
        details = {key: value for key, value in detail.items() if key not in {"code", "message"}}
    else:
        code = "http_error"
        message = str(detail)
        details = None
    return JSONResponse(status_code=error.status_code, content=_envelope(code, message, details))


async def validation_exception_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope("validation_error", "Request validation failed", error.errors()),
    )


async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled API exception path=%s method=%s",
        request.url.path,
        request.method,
        exc_info=error,
    )
    return JSONResponse(
        status_code=500,
        content=_envelope("internal_error", "Internal server error"),
    )
