from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroError,
    KeitaroNotFound,
    KeitaroRejected,
    KeitaroUnavailable,
)
from app.log import request_id_var


class AppError(Exception):
    """An expected failure that maps to an HTTP error response."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class InvalidInputError(AppError):
    status_code = 422
    code = "validation_error"


class CreationFailed(AppError):
    """Keitaro accepted the campaign but not its streams."""

    status_code = 502
    code = "campaign_not_created"


def error_response(
    status_code: int, code: str, message: str, details: Any = None, headers: dict | None = None
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    error["request_id"] = request_id_var.get()
    return JSONResponse({"error": error}, status_code=status_code, headers=headers)


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        # loc is ("body", "geo", 0) or ("query", "limit"); the first part is not useful to a client
        field = ".".join(str(part) for part in err["loc"][1:])
        message = err["msg"].removeprefix("Value error, ")
        details.append({"field": field, "message": message})
    return error_response(422, "validation_error", "Проверьте введённые данные", details)


async def _keitaro_error(_: Request, exc: KeitaroError) -> JSONResponse:
    if isinstance(exc, KeitaroAuthError):
        return error_response(
            502, "keitaro_auth", "Keitaro не принял API-ключ, проверьте KEITARO_API_KEY"
        )
    if isinstance(exc, KeitaroUnavailable):
        return error_response(
            502, "keitaro_unavailable", "Keitaro сейчас недоступен, попробуйте ещё раз"
        )
    if isinstance(exc, KeitaroNotFound):
        return error_response(404, "keitaro_not_found", f"Не найдено в Keitaro: {exc.message}")
    if isinstance(exc, KeitaroRejected):
        return error_response(502, "keitaro_rejected", f"Keitaro отклонил запрос: {exc.message}")
    return error_response(502, "keitaro_error", exc.message)


async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(404, "not_found", "Не найдено")
    if exc.status_code == 405:
        return error_response(405, "method_not_allowed", "Метод не поддерживается")
    return error_response(exc.status_code, "http_error", str(exc.detail))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(KeitaroError, _keitaro_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
