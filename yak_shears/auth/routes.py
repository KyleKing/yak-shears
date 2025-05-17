"""Authentication routes for the Yak Shears application."""

import base64

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from yak_shears.auth.storage import create_session, delete_session
from yak_shears.auth.webauthn import (
    generate_auth_options_for_user,
    generate_registration_options_for_user,
    get_user_from_session,
    verify_authentication,
    verify_registration,
)
from yak_shears.template import render_error, render_template
from webauthn import options_to_json


async def login_handler(request: Request) -> Response:
    """Handle login requests.

    Args:
        request: The incoming request

    Returns:
        Response: HTML page for login or a redirect
    """
    # Check if already logged in
    user = get_user_from_session(request)
    if user:
        return RedirectResponse(url="/home", status_code=303)

    # Handle form submission
    if request.method == "POST":
        form_data = await request.form()
        username = str(form_data.get("username", ""))

        # Generate WebAuthn options
        options, user = generate_auth_options_for_user(username)
        if not options or not user:
            return render_error(message="Invalid username", back_url="/auth/login")

        # Convert challenge to base64 for JSON
        challenge_b64 = base64.b64encode(options.challenge).decode()

        # Prepare options for the client
        client_options = {
            "challenge": challenge_b64,
            "timeout": options.timeout,
            "rpId": options.rp_id,
            "userVerification": options.user_verification,
            "allowCredentials": [
                {
                    "id": base64.b64encode(cred.id).decode(),
                    "type": cred.type,
                    "transports": getattr(cred, "transports", None),
                }
                for cred in options.allow_credentials or []
            ],
        }

        # Render login form with WebAuthn options
        return render_template("auth/login_webauthn.html.jinja", username=username, client_options=client_options)

    # Display login form
    return render_template("auth/login.html.jinja")


async def verify_login_handler(request: Request) -> Response:
    """Handle login verification.

    Args:
        request: The incoming request

    Returns:
        Response: JSON response with login result
    """
    try:
        # Parse the request data
        data = await request.json()
        username = data.get("username")
        credential_data = data.get("credential")

        if not username or not credential_data:
            return JSONResponse({"error": "Missing required fields"}, status_code=400)

        # Get the user
        from yak_shears.auth.storage import get_user_by_name

        user = get_user_by_name(username)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=400)

        # Verify the credential
        success, _ = verify_authentication(user, credential_data)
        if not success:
            return JSONResponse({"error": "Authentication failed"}, status_code=400)

        # Create a session
        session_id = create_session(user["id"])

        # Set the session cookie and return success
        response = JSONResponse({"success": True})
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=3600 * 24 * 7,  # 1 week
            path="/",
        )
        return response

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def register_handler(request: Request) -> Response:
    """Handle registration requests.

    Args:
        request: The incoming request

    Returns:
        Response: HTML page for registration or a redirect
    """
    # Check if already logged in
    user = get_user_from_session(request)
    if user:
        return RedirectResponse(url="/home", status_code=303)

    # Handle form submission
    if request.method == "POST":
        form_data = await request.form()
        username = str(form_data.get("username", ""))
        display_name = str(form_data.get("display_name", ""))

        if not username or not display_name:
            return render_error(message="Username and display name are required", back_url="/auth/register")

        # Check if username is already taken
        from yak_shears.auth.storage import get_user_by_name

        existing_user = get_user_by_name(username)
        if existing_user:
            return render_error(message="Username already taken", back_url="/auth/register")

        # Generate registration options
        options = generate_registration_options_for_user(username, display_name)

        # Convert challenge to base64 for JSON
        challenge_b64 = base64.b64encode(options.challenge).decode()

        # # Prepare options for the client
        # client_options = {
        #     "challenge": challenge_b64,
        #     "rp": {"name": options.rp_name, "id": options.rp_id},
        #     "user": {
        #         "id": base64.b64encode(options.user_id).decode(),
        #         "name": options.user_name,
        #         "displayName": options.user_display_name,
        #     },
        #     "pubKeyCredParams": [{"type": "public-key", "alg": alg} for alg in options.supported_pub_key_algs],
        #     "timeout": options.timeout,
        #     "attestation": options.attestation,
        #     "authenticatorSelection": {
        #         "authenticatorAttachment": options.authenticator_selection.authenticator_attachment,
        #         "requireResidentKey": options.authenticator_selection.require_resident_key,
        #         "residentKey": options.authenticator_selection.resident_key,
        #         "userVerification": options.authenticator_selection.user_verification,
        #     },
        # }

        # Render registration form with WebAuthn options
        return render_template(
            "auth/register_webauthn.html.jinja",
            username=username,
            display_name=display_name,
            client_options=options_to_json(options),# client_options,
        )

    # Display registration form
    return render_template("auth/register.html.jinja")


async def verify_register_handler(request: Request) -> Response:
    """Handle registration verification.

    Args:
        request: The incoming request

    Returns:
        Response: JSON response with registration result
    """
    try:
        # Parse the request data
        data = await request.json()
        username = data.get("username")
        display_name = data.get("display_name")
        credential_data = data.get("credential")
        challenge_b64 = data.get("challenge")

        if not username or not display_name or not credential_data or not challenge_b64:
            return JSONResponse({"error": "Missing required fields"}, status_code=400)

        # Convert challenge back to bytes
        challenge = base64.b64decode(challenge_b64)

        # Verify the credential
        success = verify_registration(credential_data, username, display_name, challenge)
        if not success:
            return JSONResponse({"error": "Registration failed"}, status_code=400)

        return JSONResponse({"success": True})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def logout_handler(request: Request) -> Response:
    """Handle logout requests.

    Args:
        request: The incoming request

    Returns:
        Response: Redirect to home page
    """
    # Get the session ID from the cookie
    session_id = request.cookies.get("session_id")
    if session_id:
        # Delete the session
        delete_session(session_id)

    # Redirect to home page and clear the cookie
    response = RedirectResponse(url="/home", status_code=303)
    response.delete_cookie(key="session_id", path="/")
    return response


async def status_handler(request: Request) -> Response:
    """Handle status requests.

    Args:
        request: The incoming request

    Returns:
        Response: JSON response with authentication status
    """
    # Get the user from the session
    user = get_user_from_session(request)
    if user:
        return JSONResponse(
            {
                "authenticated": True,
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "display_name": user["display_name"],
                },
            }
        )
    return JSONResponse({"authenticated": False})


# Define routes
auth_routes = [
    Route("/auth/login", endpoint=login_handler, methods=["GET", "POST"]),
    Route("/auth/verify_login", endpoint=verify_login_handler, methods=["POST"]),
    Route("/auth/register", endpoint=register_handler, methods=["GET", "POST"]),
    Route("/auth/verify_register", endpoint=verify_register_handler, methods=["POST"]),
    Route("/auth/logout", endpoint=logout_handler, methods=["GET"]),
    Route("/auth/status", endpoint=status_handler, methods=["GET"]),
]
