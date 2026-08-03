"""HTTP request handlers for Yak Shears."""

from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from pathlib import Path as SyncPath
from typing import Self
from urllib.parse import quote

from anyio import to_thread
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from yak_shears._log_utils import StageTimer, log
from yak_shears._templates import (
    SortBy,
    _render_template,
    render_error,
    render_new,
    render_search,
    render_settings,
    render_yak_edit,
    render_yaks,
)
from yak_shears._yak.categories import (
    PALETTE,
    assign_slots,
    load_slots,
    resolve_colors,
    save_slots,
    slot_css,
)
from yak_shears._yak.database import (
    get_backlinks,
    get_search_db_path,
    index_is_inside_vault,
    refresh_search_index,
    stray_vault_index,
)
from yak_shears._yak.filenames import apply_renames, plan_renames
from yak_shears._yak.media import (
    MediaError,
    build_doctor_report,
    process_upload,
    resolve_attachment,
)
from yak_shears._yak.request_utils import extract_yak_path, is_htmx_request
from yak_shears._yak.services import (
    YakPathError,
    create_yak,
    delete_yak,
    ensure_search_db_ready,
    ensure_search_index_updated,
    get_categories,
    get_yak_dir,
    index_yak_metadata,
    list_yak_paths,
    paginate_yaks,
    perform_search,
    prepare_yak_info,
    read_yak,
    read_yak_body,
    resolve_yak_path,
    save_yak,
)
from yak_shears.frontmatter import parse_frontmatter

_PALETTE_NAMES = {slot.name for slot in PALETTE}


@dataclass(frozen=True)
class YaksQueryParams:
    """Parameters for querying and paginating Djot yaks."""

    page: int
    sort_by: SortBy
    category: str | None
    page_size: int = 30

    @classmethod
    async def from_request(cls, request: Request, categories: set[str]) -> Self:
        """Parse and validate query parameters from HTTP request."""
        try:
            page = max(int(request.query_params.get("page", "1")), 1)
        except ValueError:
            page = 1

        try:
            sort_by = SortBy(request.query_params.get("sort_by", "").lower())
        except ValueError:
            sort_by = SortBy.CREATED_AT

        category = request.query_params.get("category") or None
        if category and category not in categories:
            log(f"Ignored invalid category: {category}")
            category = None

        return cls(page=page, sort_by=sort_by, category=category)


# -----------------------------------------------------------------------------
# Handlers


async def yaks_handler(request: Request) -> Response:
    """Handle requests to /yaks."""
    yak_dir = await get_yak_dir()
    all_paths = await list_yak_paths(yak_dir)
    categories = await get_categories(all_paths)

    query_params = await YaksQueryParams.from_request(request, categories)

    result = await paginate_yaks(
        paths=all_paths,
        page=query_params.page,
        page_size=query_params.page_size,
        sort_by=query_params.sort_by,
        category=query_params.category,
    )
    yaks = await prepare_yak_info(result.paths, yak_dir)
    yak_dir_label = f"./{yak_dir.name}"

    return render_yaks(
        yaks=yaks,
        current_page=query_params.page,
        total_pages=result.total_pages,
        total_yaks=result.total_count,
        yak_dir_label=yak_dir_label,
        sort_by=query_params.sort_by,
        current_category=query_params.category,
        categories=categories,
        category_colors=await resolve_colors(yak_dir, categories),
    )


async def new_yak_handler(request: Request) -> Response:
    """Handle requests to /new."""
    yak_dir = await get_yak_dir()
    if request.method != "POST":
        categories = await get_categories(await list_yak_paths(yak_dir))
        return render_new(categories=categories, category_colors=await resolve_colors(yak_dir, categories))

    form_data = await request.form()
    category = str(form_data.get("new_category", "")).strip() or str(form_data.get("category", "")).strip()

    if not category:
        return render_error("Category is required")

    try:
        yak_path = await create_yak(yak_dir, category)
    except YakPathError:
        return render_error("Invalid category name")
    relative_path = yak_path.relative_to(yak_dir).as_posix()
    return RedirectResponse(f"/edit?yak={relative_path}", status_code=HTTPStatus.SEE_OTHER)


async def settings_handler(request: Request) -> Response:
    """Handle requests to /settings, where categories are pinned to palette slots."""
    yak_dir = await get_yak_dir()
    categories = await get_categories(await list_yak_paths(yak_dir))

    saved = False
    if request.method == "POST":
        form_data = await request.form()
        stored = await load_slots(yak_dir)
        chosen = {
            category: str(form_data[category])
            for category in {*stored, *categories}
            if category in form_data and str(form_data[category]) in _PALETTE_NAMES
        }
        await save_slots(yak_dir, assign_slots(chosen, categories))
        saved = True

    slots = assign_slots(await load_slots(yak_dir), categories)
    owners: dict[str, list[str]] = {}
    for category, slot in sorted(slots.items()):
        owners.setdefault(slot, []).append(category)
    return render_settings(assignments=sorted(slots.items()), owners=owners, saved=saved)


async def edit_yak_handler(request: Request) -> Response:
    """Handle requests to /edit."""
    yak_dir = await get_yak_dir()
    yak_path_str = await extract_yak_path(request)

    if not yak_path_str:
        return render_error("No `yak` path specified")

    try:
        if request.method == "POST":
            form_data = await request.form()
            content = str(form_data.get("content", ""))
            await save_yak(yak_dir, yak_path_str, content)
            return HTMLResponse("")

        content, category = await read_yak(yak_dir, yak_path_str)
        frontmatter, _ = parse_frontmatter(content)
        backlinks = get_backlinks(yak_path_str)
        category_color = slot_css((await load_slots(yak_dir)).get(category, ""))

        return render_yak_edit(
            yak_path_str,
            content,
            category,
            category_color,
            frontmatter=frontmatter,
            backlinks=backlinks,
        )
    except (FileNotFoundError, YakPathError):
        return render_error(f"Yak not found: {yak_path_str}", status_code=HTTPStatus.NOT_FOUND)
    except Exception as exc:
        return render_error(f"An error occurred: {exc!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def search_handler(request: Request) -> Response:
    """Handle requests to /search."""
    query = request.query_params.get("query", "").strip()

    if not query:
        if is_htmx_request(request):
            return HTMLResponse('<div class="search-empty"><p>Start typing to search your yaks...</p></div>')
        return render_search([], query)

    timer = StageTimer()
    with timer.stage("db_ready"):
        await ensure_search_db_ready()

    yak_dir = await get_yak_dir()
    sync_yak_dir = SyncPath(yak_dir)

    with timer.stage("index"):
        ensure_search_index_updated(sync_yak_dir)

    try:
        results = perform_search(query, sync_yak_dir, timer)
    except Exception as exc:
        log(f"ERROR: Search database query failed: {exc}")
        return render_error("Search is temporarily unavailable", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    log(timer.format_line("SEARCH", query_len=len(query), results=len(results)))

    if is_htmx_request(request):
        return _render_template("search/search_results.html.jinja", results=results, query=query)

    return render_search(results, query)


async def delete_yak_handler(request: Request) -> Response:
    """Handle requests to delete a yak."""
    yak_dir = await get_yak_dir()
    yak_path_str = await extract_yak_path(request)

    if not yak_path_str:
        return render_error("No `yak` path specified")

    try:
        await delete_yak(yak_dir, yak_path_str)
        return Response("", status_code=HTTPStatus.OK, headers={"HX-Redirect": "/yaks"})
    except (FileNotFoundError, YakPathError):
        return render_error(f"Yak not found: {yak_path_str}", status_code=HTTPStatus.NOT_FOUND)
    except Exception as exc:
        return render_error(f"An error occurred: {exc!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def yak_preview_handler(request: Request) -> Response:
    """Handle requests for yak preview."""
    path = request.query_params.get("path", "")
    query = request.query_params.get("query", "")

    if not path:
        return JSONResponse({"error": "Path required"}, status_code=400)

    yak_dir = await get_yak_dir()
    try:
        yak_path = await resolve_yak_path(yak_dir, path)
    except YakPathError:
        return JSONResponse({"error": "File not found"}, status_code=404)

    if not await yak_path.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    try:
        body = await read_yak_body(yak_dir, path)
    except Exception as exc:
        log(f"ERROR: Failed to read file {yak_path}: {exc}")
        return JSONResponse({"error": "Failed to read file"}, status_code=500)

    edit_url = f"/edit?yak={quote(path)}&query={quote(query)}"
    return JSONResponse({"source": body, "query": query, "edit_url": edit_url})


_MEDIA_MAX_UPLOAD_BYTES = 300 * 1024 * 1024
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
_MEDIA_CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}


async def media_upload_handler(request: Request) -> Response:
    """Handle POST /media/upload: store one photo/video and return its embed snippet."""
    yak_dir = await get_yak_dir()
    form_data = await request.form()

    yak_path_str = str(form_data.get("yak", "")).strip()
    upload = form_data.get("file")
    if not yak_path_str or not isinstance(upload, UploadFile):
        return JSONResponse({"error": "Missing file or yak path"}, status_code=HTTPStatus.BAD_REQUEST)

    data = await upload.read()
    if len(data) > _MEDIA_MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "File too large"}, status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

    try:
        result = await process_upload(yak_dir, yak_path_str, upload.filename or "upload", data)
    except MediaError as exc:
        return JSONResponse({"error": str(exc)}, status_code=HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        log(f"ERROR: media upload failed: {exc}")
        return JSONResponse({"error": "Upload processing failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    return JSONResponse({
        "kind": result.kind.value,
        "url": result.url,
        "thumb": result.thumb_url,
        "snippet": result.snippet,
        "reused": result.reused,
    })


async def _serve_attachment(request: Request, *, thumb: bool) -> Response:
    yak_dir = await get_yak_dir()
    category = request.path_params["category"]
    filename = request.path_params["filename"]
    try:
        path = await resolve_attachment(yak_dir, category, filename, thumb=thumb)
    except MediaError:
        return Response("Not found", status_code=HTTPStatus.NOT_FOUND)
    if not await path.is_file():
        return Response("Not found", status_code=HTTPStatus.NOT_FOUND)

    media_type = "image/jpeg" if thumb else _MEDIA_CONTENT_TYPES.get(SyncPath(filename).suffix.lower())
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": _IMMUTABLE_CACHE})


async def media_file_handler(request: Request) -> Response:
    """Serve a full-resolution attachment (image or video with Range support)."""
    return await _serve_attachment(request, thumb=False)


async def thumb_file_handler(request: Request) -> Response:
    """Serve a downscaled thumbnail or video poster frame."""
    return await _serve_attachment(request, thumb=True)


async def doctor_handler(request: Request) -> Response:  # noqa: ARG001
    """Report broken media references, orphaned attachments, and naming drift."""
    yak_dir = await get_yak_dir()
    report = await build_doctor_report(yak_dir)
    filenames = plan_renames(SyncPath(yak_dir))
    stray = stray_vault_index()
    return _render_template(
        "doctor/index.html.jinja",
        missing=report.missing,
        orphans=report.orphans,
        referenced_count=report.referenced_count,
        file_count=report.file_count,
        filenames=filenames,
        index_path=str(get_search_db_path()),
        index_in_vault=index_is_inside_vault(),
        stray_index=str(stray) if stray else None,
        current_route="doctor",
    )


async def doctor_fix_filenames_handler(request: Request) -> Response:
    """Rename every migratable yak to the canonical timestamp form."""
    yak_dir = await get_yak_dir()
    sync_yak_dir = SyncPath(yak_dir)
    plan = plan_renames(sync_yak_dir)

    if not plan.needs_migration:
        return RedirectResponse("/doctor", status_code=HTTPStatus.SEE_OTHER)

    try:
        result = await to_thread.run_sync(apply_renames, sync_yak_dir, plan.renames)
    except (OSError, FileNotFoundError) as exc:
        log(f"ERROR: filename migration failed: {exc}")
        return render_error("Could not rename yaks", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    log(
        f"DOCTOR renamed={len(result.renamed)} relinked={len(result.relinked)} "
        f"blocked={len(plan.blocked)} unparseable={len(plan.unparseable)}"
    )

    # Paths changed underneath the index, so rebuild rather than waiting for the
    # staleness guard, which keys on mtime and would miss the renames entirely.
    # The schema is only created on the search path, which may never have run.
    await ensure_search_db_ready()
    for rename in result.renamed:
        index_yak_metadata(sync_yak_dir / rename.new_path, sync_yak_dir)
    await to_thread.run_sync(partial(refresh_search_index, sync_yak_dir, force=True))

    return RedirectResponse("/doctor", status_code=HTTPStatus.SEE_OTHER)


# Re-export for backwards compatibility with tests
get_search_db_path = __import__("yak_shears._yak.database", fromlist=["get_search_db_path"]).get_search_db_path
