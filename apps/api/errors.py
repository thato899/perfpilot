"""The single error shape every endpoint returns.

api-contract.md documents exactly one envelope:

    { "error": { "code": "string", "message": "string", "detail": {} } }

FastAPI's defaults do not produce that — `HTTPException` yields
`{"detail": ...}` and a Pydantic validation failure yields a bare list — so
both are re-wrapped by the handlers registered in `install_error_handlers`.
Without that, the 422 the contract promises would be the one response shape
a client couldn't parse.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    """Raised by routers; rendered into the documented envelope.

    A dedicated exception rather than `HTTPException` so the `code` field is
    always set deliberately, instead of being derived from the status.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail or {}


def error_body(code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "detail": detail or {}}}


# --- The documented failure modes, as named constructors ------------------
# Named rather than raised inline so the status/code pairing in
# api-contract.md's error table is defined in exactly one place.


def unauthorized(message: str = "Missing or invalid authorization token.") -> APIError:
    return APIError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


def forbidden_target(base_url: str) -> APIError:
    return APIError(
        status.HTTP_403_FORBIDDEN,
        "target_not_allowed",
        "Target host is not on the configured allow-list.",
        {"base_url": base_url, "hint": "See ALLOWED_TARGET_HOSTS in .env.example."},
    )


def not_found(resource: str, resource_id: Any) -> APIError:
    return APIError(
        status.HTTP_404_NOT_FOUND,
        "not_found",
        f"{resource} not found.",
        {"id": str(resource_id)},
    )


def conflict(code: str, message: str, detail: dict[str, Any] | None = None) -> APIError:
    return APIError(status.HTTP_409_CONFLICT, code, message, detail)


def unprocessable(code: str, message: str, detail: dict[str, Any] | None = None) -> APIError:
    return APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, code, message, detail)


def safety_limit(code: str, message: str, detail: dict[str, Any] | None = None) -> APIError:
    """429 — a safety-ceiling rejection, not a rate limit.

    api-contract.md maps 429 to "Safety-limit rejection (e.g. requested VUs
    exceed MAX_VIRTUAL_USERS)". Reusing the status for request throttling
    later would make the two indistinguishable; the `code` field is what
    separates them.
    """
    return APIError(status.HTTP_429_TOO_MANY_REQUESTS, code, message, detail)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI defaults to 422 here, which matches the contract's "Body
        # fails schema validation". Only the envelope needs changing.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body(
                "validation_error",
                "Request body failed schema validation.",
                # str() on the errors: they can contain exception instances
                # under "ctx", which aren't JSON-serializable and would turn
                # a 422 into a 500 while rendering the response.
                {
                    "errors": [
                        {**e, "ctx": str(e["ctx"])} if "ctx" in e else e for e in exc.errors()
                    ]
                },
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Catches what the framework raises before a router runs — a 404 on
        # an unknown path, a 405 on the wrong method — so even those come
        # back in the documented envelope.
        codes = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(codes.get(exc.status_code, "error"), str(exc.detail)),
        )
