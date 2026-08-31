"""Yak routes for the Yak Shears application."""

from starlette.routing import Route

from .bench_handlers import (
    habit_toggle_handler,
    habits_handler,
    list_toggle_handler,
    lists_handler,
    streams_handler,
)
from .benches import benches_handler
from .board import board_act_handler
from .handlers import (
    delete_yak_handler,
    doctor_fix_filenames_handler,
    doctor_handler,
    edit_yak_handler,
    link_candidates_handler,
    media_file_handler,
    media_upload_handler,
    new_yak_handler,
    search_handler,
    settings_handler,
    thumb_file_handler,
    yak_preview_handler,
    yaks_handler,
)

ROUTES = [
    Route("/yaks", endpoint=yaks_handler),
    Route("/benches", endpoint=benches_handler),
    Route("/habits", endpoint=habits_handler),
    Route("/habits/toggle", endpoint=habit_toggle_handler, methods=["POST"]),
    Route("/lists", endpoint=lists_handler),
    Route("/lists/toggle", endpoint=list_toggle_handler, methods=["POST"]),
    Route("/streams", endpoint=streams_handler),
    Route("/streams/act", endpoint=board_act_handler, methods=["POST"]),
    Route("/search", endpoint=search_handler),
    Route("/settings", endpoint=settings_handler, methods=["GET", "POST"]),
    Route("/new", endpoint=new_yak_handler, methods=["GET", "POST"]),
    Route("/edit", endpoint=edit_yak_handler, methods=["GET", "POST"]),
    Route("/delete", endpoint=delete_yak_handler, methods=["POST"]),
    Route("/doctor", endpoint=doctor_handler),
    Route("/doctor/fix-filenames", endpoint=doctor_fix_filenames_handler, methods=["POST"]),
    Route("/api/links", endpoint=link_candidates_handler),
    Route("/api/yak-preview", endpoint=yak_preview_handler),
    Route("/media/upload", endpoint=media_upload_handler, methods=["POST"]),
    Route("/media/{category}/{filename}", endpoint=media_file_handler),
    Route("/thumb/{category}/{filename}", endpoint=thumb_file_handler),
]
