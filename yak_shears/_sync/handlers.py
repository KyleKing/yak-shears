"""HTTP handlers for the sync API a native client uses.

Leases travel as HTTP validators: a response carries `ETag: "<lease>"`, an update
or delete sends it back as `If-Match`, and a create sends `If-None-Match: *`. A
write without either is refused with 428 rather than treated as unconditional,
so a client bug cannot silently overwrite a note.

A mismatch answers 412 with what is on disk as the body and its lease as the
ETag, which is everything the client needs to show a diff, or to overwrite on
purpose by retrying with that ETag.
"""

from http import HTTPStatus

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from yak_shears._auth import storage
from yak_shears._auth.handlers import get_user_from_session, request_token
from yak_shears._auth.models import Password
from yak_shears._auth.rate_limit import login_limiter
from yak_shears._auth.tokens import API_TOKEN_TTL_SECONDS
from yak_shears._yak.services import (
    StaleYakError,
    YakPathError,
    delete_yak,
    get_yak_dir,
    read_yak,
    save_yak,
    yak_lease,
)

from .services import build_manifest, create_yak_with_content

MAX_YAK_BYTES = 5 * 1024 * 1024


def _error(message: str, status: HTTPStatus) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _etag(lease: str) -> dict[str, str]:
    return {"ETag": f'"{lease}"'}


def _parse_lease(header: str | None) -> str | None:
    """Read the single strong validator a conditional request carries.

    Returns:
        The lease, or None when the header is absent.
    """
    if header is None:
        return None
    return header.strip().removeprefix("W/").strip('"')


def _refusal(exc: StaleYakError | YakPathError | FileNotFoundError) -> Response:
    """Map a refused vault write to its status.

    Returns:
        412 with what is on disk and its lease, 400 for a bad path, or 404.
    """
    if isinstance(exc, StaleYakError):
        return PlainTextResponse(
            exc.current, status_code=HTTPStatus.PRECONDITION_FAILED, headers=_etag(yak_lease(exc.current))
        )
    if isinstance(exc, YakPathError):
        return _error(str(exc), HTTPStatus.BAD_REQUEST)
    return _error(str(exc), HTTPStatus.NOT_FOUND)


async def token_create_handler(request: Request) -> Response:
    """Handle POST /api/v1/token: trade an email and password for a bearer token.

    Shares the login form's rate limit, so the API is not a faster way to guess.

    Returns:
        201 with the token and its expiry, 401 on bad credentials, 429 when throttled.
    """
    try:
        body = await request.json()
    except ValueError:
        return _error("Expected a JSON body with email and password", HTTPStatus.BAD_REQUEST)
    if not isinstance(body, dict):
        return _error("Expected a JSON body with email and password", HTTPStatus.BAD_REQUEST)

    email = str(body.get("email") or "").strip()
    password = Password(str(body.get("password") or ""))
    if not email or not password:
        return _error("Email and password are required", HTTPStatus.BAD_REQUEST)

    client_ip = request.client.host if request.client else "unknown"
    limit_key = f"{client_ip}:{email}"
    if login_limiter.is_blocked(limit_key):
        return _error("Too many attempts. Try again in a few minutes.", HTTPStatus.TOO_MANY_REQUESTS)
    if not (user := await storage.authenticate_user(email, password)):
        login_limiter.register_failure(limit_key)
        return _error("Invalid email or password", HTTPStatus.UNAUTHORIZED)
    login_limiter.reset(limit_key)

    return JSONResponse(
        {"token": storage.create_api_token(user["id"]), "expires_in": API_TOKEN_TTL_SECONDS},
        status_code=HTTPStatus.CREATED,
    )


async def token_delete_handler(request: Request) -> Response:  # noqa: RUF029
    """Handle DELETE /api/v1/token: revoke the bearer token the request carries.

    Returns:
        204 once revoked, 401 when the request carries no valid token.
    """
    if not get_user_from_session(request) or not (token := request_token(request)):
        return _error("Authentication required", HTTPStatus.UNAUTHORIZED)
    storage.delete_session(token)
    return Response(status_code=HTTPStatus.NO_CONTENT)


async def manifest_handler(request: Request) -> Response:  # noqa: ARG001
    """Handle GET /api/v1/yaks: every yak's path, lease, and modification time.

    A client diffs this against the leases it last synced: a changed lease is a
    remote edit, a missing path a remote delete, and a new path a remote create.

    Returns:
        JSON object with a `yaks` list.
    """
    entries = await build_manifest(await get_yak_dir())
    return JSONResponse({"yaks": [{"path": e.path, "lease": e.lease, "modified": e.modified} for e in entries]})


async def yak_get_handler(request: Request) -> Response:
    """Handle GET /api/v1/yaks/{path}: one yak's text, with its lease as the ETag.

    Returns:
        The yak as text/plain, or 404.
    """
    try:
        content, _ = await read_yak(await get_yak_dir(), request.path_params["path"])
    except (FileNotFoundError, YakPathError) as exc:
        return _error(str(exc), HTTPStatus.NOT_FOUND)
    return PlainTextResponse(content, headers=_etag(yak_lease(content)))


async def yak_put_handler(request: Request) -> Response:
    """Handle PUT /api/v1/yaks/{path}: create or update a yak, conditionally.

    `If-None-Match: *` creates a new yak, whose name must be canonical.
    `If-Match: "<lease>"` replaces an existing one.

    Returns:
        201 or 200 with the new ETag; 412 with the current text on a conflict;
        404 when updating a yak that was deleted; 428 without a precondition.
    """
    relative_path = request.path_params["path"]
    body = await request.body()
    if len(body) > MAX_YAK_BYTES:
        return _error("Yak too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    try:
        content = body.decode("utf-8")
    except UnicodeDecodeError:
        return _error("Body must be UTF-8 text", HTTPStatus.BAD_REQUEST)

    yak_dir = await get_yak_dir()
    expected_lease = _parse_lease(request.headers.get("If-Match"))
    try:
        if request.headers.get("If-None-Match", "").strip() == "*":
            lease = await create_yak_with_content(yak_dir, relative_path, content)
            return Response(status_code=HTTPStatus.CREATED, headers=_etag(lease))
        if expected_lease is None:
            return _error("Send If-Match to update or If-None-Match: * to create", HTTPStatus.PRECONDITION_REQUIRED)
        lease = await save_yak(yak_dir, relative_path, content, expected_lease)
    except (StaleYakError, YakPathError, FileNotFoundError) as exc:
        return _refusal(exc)
    return Response(status_code=HTTPStatus.OK, headers=_etag(lease))


async def yak_delete_handler(request: Request) -> Response:
    """Handle DELETE /api/v1/yaks/{path}: remove a yak the client has seen.

    Returns:
        204 once deleted; 412 with the current text when it changed since;
        404 when already gone; 428 without If-Match.
    """
    expected_lease = _parse_lease(request.headers.get("If-Match"))
    if expected_lease is None:
        return _error("Send If-Match with the lease being deleted", HTTPStatus.PRECONDITION_REQUIRED)
    try:
        await delete_yak(await get_yak_dir(), request.path_params["path"], expected_lease)
    except (StaleYakError, YakPathError, FileNotFoundError) as exc:
        return _refusal(exc)
    return Response(status_code=HTTPStatus.NO_CONTENT)
