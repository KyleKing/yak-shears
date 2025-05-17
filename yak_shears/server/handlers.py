"""Request handlers for the Yak Shears server."""

import json
from datetime import UTC, datetime
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from yak_shears import auth


async def home_handler(request: Request) -> HTMLResponse:
    """Handle requests to /home.

    Args:
        request: The incoming request

    Returns:
        HTMLResponse with navigation index
    """
    user = auth.get_user_from_session(request)
    auth_status = ""

    if user:
        auth_status = f"""
        <div style="margin-bottom: 20px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
            <p>Logged in as: <strong>{user["display_name"]}</strong></p>
            <a href="/auth/logout" style="color: #d9534f;">Logout</a>
        </div>
        """
    else:
        auth_status = """
        <div style="margin-bottom: 20px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
            <p>Not logged in</p>
            <a href="/auth/login" style="margin-right: 10px;">Login</a>
            <a href="/auth/register">Register</a>
        </div>
        """

    return HTMLResponse(f"""
    <html>
    <head>
        <title>Yak Shears Server</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            ul {{ padding-left: 20px; }}
            li {{ margin-bottom: 10px; }}
            a {{ color: #337ab7; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h1>Yak Shears Server</h1>
        {auth_status}
        <ul>
            <li><a href="/files">Browse Files</a></li>
            <li><a href="/echo">Echo Endpoint</a></li>
            <li><a href="/time">Current Time</a></li>
        </ul>
    </body>
    </html>
    """)


async def echo_handler(request: Request) -> HTMLResponse:
    """Handle both GET and POST requests to /echo.

    Args:
        request: The incoming request

    Returns:
        HTMLResponse with echoed data
    """
    # Build HTML response
    response = "<h1>Echo</h1>"

    # Add URL parameters to response if they exist
    query_params = dict(request.query_params)
    if query_params:
        response += "<h2>URL Parameters</h2>"
        response += "<ul>"
        for key, value in query_params.items():
            response += f"<li><strong>{key}</strong>: {value}</li>"
        response += "</ul>"

    # Add JSON data for POST requests
    if request.method == "POST":
        try:
            json_data = await request.json()
            response += "<h2>JSON Payload</h2>"
            response += f"<pre>{json.dumps(json_data, indent=2)}</pre>"
        except json.JSONDecodeError:
            # Handle case where body is not valid JSON
            body = await request.body()
            if body:
                response += "<h2>Raw POST Data</h2>"
                response += f"<pre>{body.decode('utf-8')}</pre>"

    return HTMLResponse(response)


async def time_handler(request: Request) -> HTMLResponse:  # noqa: ARG001,RUF029
    """Handle requests to /time.

    Args:
        request: The incoming request

    Returns:
        HTMLResponse with current time
    """
    now = datetime.now(tz=UTC)
    return HTMLResponse(f"<h1>Current Time</h1><p>{now.strftime('%Y-%m-%d %H:%M:%S')}</p>")


def get_djot_files(directory_path: str, page: int = 1, page_size: int = 50) -> tuple[list[Path], int, int]:
    """Get a paginated list of Djot files from the specified directory.

    Args:
        directory_path: Path to the directory to list files from
        page: Current page number (1-indexed)
        page_size: Number of files per page

    Returns:
        Tuple containing (list of file paths, total number of files, total pages)
    """
    pth = Path(directory_path).expanduser()
    if not pth.exists() or not pth.is_dir():
        return [], 0, 0

    # TODO: Also need to include the parent directory folder
    all_files = sorted([f for f in pth.rglob("*.dj") if f.is_file()], key=lambda x: x.name.lower())
    total_files = len(all_files)
    total_pages = (total_files + page_size - 1) // page_size

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_files)

    return all_files[start_idx:end_idx], total_files, total_pages


def generate_file_table_html(
    files: list[Path],
    current_page: int,
    total_pages: int,
    total_files: int,
    directory_path: str,
) -> str:
    """Generate HTML for displaying files in a table with pagination.

    Args:
        files: List of file paths to display
        current_page: Current page number
        total_pages: Total number of pages
        total_files: Total number of files
        directory_path: Path to the directory being listed

    Returns:
        HTML string for the file table and pagination
    """
    html = f"""
    <html>
    <head>
        <title>Files in {directory_path}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
            tr:hover {{ background-color: #f5f5f5; }}
            .pagination {{ display: flex; margin-top: 20px; }}
            .pagination a {{ color: black; padding: 8px 16px; text-decoration: none; }}
            .pagination a.active {{ background-color: #4CAF50; color: white; }}
            .pagination a:hover:not(.active) {{ background-color: #ddd; }}
            .file-info {{ display: flex; justify-content: space-between; }}
            .status-bar {{ margin-top: 10px; }}
        </style>
    </head>
    <body>
        <h1>Files in {directory_path}</h1>
        <p class="status-bar">Showing {len(files)} of {total_files} files (Page {current_page} of {total_pages})</p>
        <table>
            <tr>
                <th>Filename</th>
                <th>Size</th>
                <th>Last Modified</th>
            </tr>
    """

    # Add file rows
    for file_path in files:
        file_stats = file_path.stat()
        size_kb = file_stats.st_size / 1024
        last_modified = datetime.fromtimestamp(file_stats.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

        html += f"""
            <tr>
                <td><a href="/edit?file={file_path!s}">{file_path.name}</a></td>
                <td>{size_kb:.2f} KB</td>
                <td>{last_modified}</td>
            </tr>
        """

    html += """
        </table>
    """

    # Add pagination
    if total_pages > 1:
        html += '<div class="pagination">'

        # Previous page
        if current_page > 1:
            html += f'<a href="/files?page={current_page - 1}">&laquo; Previous</a>'

        # Page numbers
        for page_num in range(max(1, current_page - 2), min(total_pages + 1, current_page + 3)):
            active_class = "active" if page_num == current_page else ""
            html += f'<a class="{active_class}" href="/files?page={page_num}">{page_num}</a>'

        # Next page
        if current_page < total_pages:
            html += f'<a href="/files?page={current_page + 1}">Next &raquo;</a>'

        html += "</div>"

    html += """
    </body>
    </html>
    """

    return html


async def files_handler(request: Request) -> Response:  # noqa: RUF029
    """Handle requests to /files.

    Args:
        request: The incoming request

    Returns:
        Response with paginated file listing
    """
    directory_path = "~/Sync/yak-shears"

    # Get page from query parameters, default to 1
    try:
        page = int(request.query_params.get("page", "1"))
        page = max(page, 1)
    except ValueError:
        page = 1

    # Get files with pagination
    files, total_files, total_pages = get_djot_files(directory_path, page)

    # Generate HTML
    html_content = generate_file_table_html(files, page, total_pages, total_files, directory_path)

    return HTMLResponse(html_content)


async def edit_file_handler(request: Request) -> Response:
    """Handle requests to /edit.

    Args:
        request: The incoming request

    Returns:
        Response with file editor or redirect
    """
    file_path_str = request.query_params.get("file")

    if not file_path_str:
        return HTMLResponse("<h1>Error</h1><p>No file specified</p>", status_code=400)

    try:
        file_path = Path(file_path_str)
        if not file_path.exists() or not file_path.is_file():
            return HTMLResponse(f"<h1>Error</h1><p>File not found: {file_path}</p>", status_code=404)

        # If the request includes content, save the changes
        if request.method == "POST":
            form_data = await request.form()
            content = str(form_data.get("content", ""))
            file_path.write_text(content)
            return RedirectResponse(url=f"/edit?file={file_path_str}", status_code=303)

        # Generate HTML editor
        content = file_path.read_text()
        html = f"""
        <html>
        <head>
            <title>Editing {file_path.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                textarea {{ width: 100%; height: 70vh; font-family: monospace; padding: 10px; }}
                .header {{ display: flex; justify-content: space-between; align-items: center; }}
                .actions {{ margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Editing {file_path.name}</h1>
                <a href="/files">Back to Files</a>
            </div>
            <form method="post">
                <textarea name="content">{content}</textarea>
                <div class="actions">
                    <button type="submit">Save Changes</button>
                </div>
            </form>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<h1>Error</h1><p>An error occurred: {e!s}</p>", status_code=500)


async def root_handler(request: Request) -> Response:  # noqa: ARG001
    """Redirect root to home page.

    Args:
        request: The incoming request

    Returns:
        Redirect to home page
    """
    return RedirectResponse(url="/home")
