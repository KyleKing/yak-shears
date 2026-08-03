"""Yak routes for the Yak Shears application."""

from starlette.routing import Route

from .handlers import (
    delete_yak_handler,
    doctor_fix_filenames_handler,
    doctor_handler,
    edit_yak_handler,
    media_file_handler,
    media_upload_handler,
    new_yak_handler,
    search_handler,
    settings_handler,
    thumb_file_handler,
    yak_preview_handler,
    yaks_handler,
)
from .lists import list_toggle_handler, lists_handler
from .streams import streams_handler

ROUTES = [
    Route("/yaks", endpoint=yaks_handler),
    Route("/lists", endpoint=lists_handler),
    Route("/lists/toggle", endpoint=list_toggle_handler, methods=["POST"]),
    Route("/streams", endpoint=streams_handler),
    Route("/search", endpoint=search_handler),
    Route("/settings", endpoint=settings_handler, methods=["GET", "POST"]),
    Route("/new", endpoint=new_yak_handler, methods=["GET", "POST"]),
    Route("/edit", endpoint=edit_yak_handler, methods=["GET", "POST"]),
    Route("/delete", endpoint=delete_yak_handler, methods=["POST"]),
    Route("/doctor", endpoint=doctor_handler),
    Route("/doctor/fix-filenames", endpoint=doctor_fix_filenames_handler, methods=["POST"]),
    Route("/api/yak-preview", endpoint=yak_preview_handler),
    Route("/media/upload", endpoint=media_upload_handler, methods=["POST"]),
    Route("/media/{category}/{filename}", endpoint=media_file_handler),
    Route("/thumb/{category}/{filename}", endpoint=thumb_file_handler),
]
