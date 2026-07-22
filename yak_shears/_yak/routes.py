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
    thumb_file_handler,
    yak_preview_handler,
    yaks_handler,
)

ROUTES = [
    Route("/yaks", endpoint=yaks_handler),
    Route("/search", endpoint=search_handler),
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
