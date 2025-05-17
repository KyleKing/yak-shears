"""Authentication routes for the Yak Shears application."""

import base64
import json

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from yak_shears.auth.storage import create_session, delete_session
from yak_shears.auth.webauthn import (
    generate_auth_options_for_user,
    generate_registration_options_for_user,
    get_user_from_session,
    verify_authentication,
    verify_registration,
)


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
        username = form_data.get("username", "")

        # Generate WebAuthn options
        options, user = generate_auth_options_for_user(username)
        if not options or not user:
            return HTMLResponse("Invalid username", status_code=400)

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

        # Create login form with WebAuthn options
        return HTMLResponse(
            f"""
            <html>
            <head>
                <title>Login</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .form-container {{ max-width: 400px; margin: 0 auto; padding: 20px;
                                     border: 1px solid #ccc; border-radius: 5px; }}
                    .form-field {{ margin-bottom: 15px; }}
                    label {{ display: block; margin-bottom: 5px; }}
                    input {{ width: 100%; padding: 8px; box-sizing: border-box; }}
                    button {{ padding: 10px 15px; background-color: #4CAF50; color: white;
                           border: none; border-radius: 4px; cursor: pointer; }}
                    button:hover {{ background-color: #45a049; }}
                    .error {{ color: red; margin-top: 10px; }}
                    .back-link {{ margin-top: 20px; display: block; }}
                </style>
            </head>
            <body>
                <div class="form-container">
                    <h2>Login</h2>
                    <div class="form-field">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" value="{username}" disabled>
                    </div>
                    <div class="form-field">
                        <button id="login-button">Login with WebAuthn</button>
                    </div>
                    <div id="error-message" class="error"></div>
                    <a href="/home" class="back-link">Back to Home</a>
                </div>

                <script>
                    // Store WebAuthn options
                    const webAuthnOptions = "{json.dumps(client_options)}";

                    document.getElementById('login-button').addEventListener('click', async () => {{
                        try {{
                            // Get options for WebAuthn
                            const publicKeyOptions = {{
                                challenge: base64ToArrayBuffer(webAuthnOptions.challenge),
                                timeout: webAuthnOptions.timeout,
                                rpId: webAuthnOptions.rpId,
                                userVerification: webAuthnOptions.userVerification,
                                allowCredentials: webAuthnOptions.allowCredentials.map(cred => ({{
                                    id: base64ToArrayBuffer(cred.id),
                                    type: cred.type,
                                    transports: cred.transports,
                                }})),
                            }};

                            // Request credential from authenticator
                            const credential = await navigator.credentials.get({{
                                publicKey: publicKeyOptions
                            }});

                            // Prepare credential for server
                            const credentialForServer = {{
                                id: arrayBufferToBase64(credential.rawId),
                                rawId: arrayBufferToBase64(credential.rawId),
                                type: credential.type,
                                response: {{
                                    authenticatorData: arrayBufferToBase64(credential.response.authenticatorData),
                                    clientDataJSON: arrayBufferToBase64(credential.response.clientDataJSON),
                                    signature: arrayBufferToBase64(credential.response.signature),
                                    userHandle: credential.response.userHandle ?
                                        arrayBufferToBase64(credential.response.userHandle) : null,
                                }},
                            }};

                            // Send credential to server for verification
                            const response = await fetch('/auth/verify_login', {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json',
                                }},
                                body: JSON.stringify({{
                                    username: '{username}',
                                    credential: credentialForServer,
                                }}),
                            }});

                            if (response.ok) {{
                                // Redirect to home page on success
                                window.location.href = '/home';
                            }} else {{
                                const data = await response.json();
                                document.getElementById('error-message').textContent =
                                    data.error || 'Authentication failed';
                            }}
                        }} catch (error) {{
                            console.error('WebAuthn error:', error);
                            document.getElementById('error-message').textContent =
                                'WebAuthn error: ' + error.message;
                        }}
                    }});

                    // Base64 utility functions
                    function base64ToArrayBuffer(base64) {{
                        const binaryString = atob(base64);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {{
                            bytes[i] = binaryString.charCodeAt(i);
                        }}
                        return bytes;
                    }}

                    function arrayBufferToBase64(buffer) {{
                        const bytes = new Uint8Array(buffer);
                        let binary = '';
                        for (let i = 0; i < bytes.byteLength; i++) {{
                            binary += String.fromCharCode(bytes[i]);
                        }}
                        return btoa(binary);
                    }}
                </script>
            </body>
            </html>
            """
        )

    # Display login form
    return HTMLResponse(
        """
        <html>
        <head>
            <title>Login</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .form-container { max-width: 400px; margin: 0 auto; padding: 20px;
                                 border: 1px solid #ccc; border-radius: 5px; }
                .form-field { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; }
                input { width: 100%; padding: 8px; box-sizing: border-box; }
                button { padding: 10px 15px; background-color: #4CAF50; color: white;
                       border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background-color: #45a049; }
                .back-link { margin-top: 20px; display: block; }
            </style>
        </head>
        <body>
            <div class="form-container">
                <h2>Login</h2>
                <form method="post">
                    <div class="form-field">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" required>
                    </div>
                    <div class="form-field">
                        <button type="submit">Continue</button>
                    </div>
                </form>
                <a href="/home" class="back-link">Back to Home</a>
            </div>
        </body>
        </html>
        """
    )


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
        username = form_data.get("username", "")
        display_name = form_data.get("display_name", "")

        if not username or not display_name:
            return HTMLResponse("Username and display name are required", status_code=400)

        # Check if username is already taken
        from yak_shears.auth.storage import get_user_by_name

        existing_user = get_user_by_name(username)
        if existing_user:
            return HTMLResponse("Username already taken", status_code=400)

        # Generate registration options
        options = generate_registration_options_for_user(username, display_name)

        # Convert challenge to base64 for JSON
        challenge_b64 = base64.b64encode(options.challenge).decode()

        # Prepare options for the client
        client_options = {
            "challenge": challenge_b64,
            "rp": {"name": options.rp_name, "id": options.rp_id},
            "user": {
                "id": base64.b64encode(options.user_id).decode(),
                "name": options.user_name,
                "displayName": options.user_display_name,
            },
            "pubKeyCredParams": [{"type": "public-key", "alg": alg} for alg in options.supported_pub_key_algs],
            "timeout": options.timeout,
            "attestation": options.attestation,
            "authenticatorSelection": {
                "authenticatorAttachment": options.authenticator_selection.authenticator_attachment,
                "requireResidentKey": options.authenticator_selection.require_resident_key,
                "residentKey": options.authenticator_selection.resident_key,
                "userVerification": options.authenticator_selection.user_verification,
            },
        }

        # Create registration form with WebAuthn options
        return HTMLResponse(
            f"""
            <html>
            <head>
                <title>Register</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .form-container {{ max-width: 400px; margin: 0 auto; padding: 20px;
                                     border: 1px solid #ccc; border-radius: 5px; }}
                    .form-field {{ margin-bottom: 15px; }}
                    label {{ display: block; margin-bottom: 5px; }}
                    input {{ width: 100%; padding: 8px; box-sizing: border-box; }}
                    button {{ padding: 10px 15px; background-color: #4CAF50; color: white;
                           border: none; border-radius: 4px; cursor: pointer; }}
                    button:hover {{ background-color: #45a049; }}
                    .error {{ color: red; margin-top: 10px; }}
                    .back-link {{ margin-top: 20px; display: block; }}
                </style>
            </head>
            <body>
                <div class="form-container">
                    <h2>Register</h2>
                    <div class="form-field">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" value="{username}" disabled>
                    </div>
                    <div class="form-field">
                        <label for="display_name">Display Name</label>
                        <input type="text" id="display_name" name="display_name"
                               value="{display_name}" disabled>
                    </div>
                    <div class="form-field">
                        <button id="register-button">Register with WebAuthn</button>
                    </div>
                    <div id="error-message" class="error"></div>
                    <a href="/home" class="back-link">Back to Home</a>
                </div>

                <script>
                    // Store WebAuthn options
                    const webAuthnOptions = "{json.dumps(client_options)}";

                    document.getElementById('register-button').addEventListener('click', async () => {{
                        try {{
                            // Get options for WebAuthn
                            const publicKeyOptions = {{
                                challenge: base64ToArrayBuffer(webAuthnOptions.challenge),
                                rp: webAuthnOptions.rp,
                                user: {{
                                    id: base64ToArrayBuffer(webAuthnOptions.user.id),
                                    name: webAuthnOptions.user.name,
                                    displayName: webAuthnOptions.user.displayName,
                                }},
                                pubKeyCredParams: webAuthnOptions.pubKeyCredParams,
                                timeout: webAuthnOptions.timeout,
                                attestation: webAuthnOptions.attestation,
                                authenticatorSelection: webAuthnOptions.authenticatorSelection,
                            }};

                            // Create credential with authenticator
                            const credential = await navigator.credentials.create({{
                                publicKey: publicKeyOptions
                            }});

                            // Prepare credential for server
                            const credentialForServer = {{
                                id: arrayBufferToBase64(credential.rawId),
                                rawId: arrayBufferToBase64(credential.rawId),
                                type: credential.type,
                                response: {{
                                    attestationObject: arrayBufferToBase64(
                                        credential.response.attestationObject),
                                    clientDataJSON: arrayBufferToBase64(
                                        credential.response.clientDataJSON),
                                }},
                                transports: credential.response.getTransports ?
                                    credential.response.getTransports() : null,
                            }};

                            // Send credential to server for verification
                            const response = await fetch('/auth/verify_register', {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json',
                                }},
                                body: JSON.stringify({{
                                    username: '{username}',
                                    display_name: '{display_name}',
                                    credential: credentialForServer,
                                    challenge: webAuthnOptions.challenge,
                                }}),
                            }});

                            if (response.ok) {{
                                // Redirect to login page on success
                                window.location.href = '/auth/login';
                            }} else {{
                                const data = await response.json();
                                document.getElementById('error-message').textContent =
                                    data.error || 'Registration failed';
                            }}
                        }} catch (error) {{
                            console.error('WebAuthn error:', error);
                            document.getElementById('error-message').textContent =
                                'WebAuthn error: ' + error.message;
                        }}
                    }});

                    // Base64 utility functions
                    function base64ToArrayBuffer(base64) {{
                        const binaryString = atob(base64);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {{
                            bytes[i] = binaryString.charCodeAt(i);
                        }}
                        return bytes;
                    }}

                    function arrayBufferToBase64(buffer) {{
                        const bytes = new Uint8Array(buffer);
                        let binary = '';
                        for (let i = 0; i < bytes.byteLength; i++) {{
                            binary += String.fromCharCode(bytes[i]);
                        }}
                        return btoa(binary);
                    }}
                </script>
            </body>
            </html>
            """
        )

    # Display registration form
    return HTMLResponse(
        """
        <html>
        <head>
            <title>Register</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .form-container { max-width: 400px; margin: 0 auto; padding: 20px;
                                 border: 1px solid #ccc; border-radius: 5px; }
                .form-field { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; }
                input { width: 100%; padding: 8px; box-sizing: border-box; }
                button { padding: 10px 15px; background-color: #4CAF50; color: white;
                       border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background-color: #45a049; }
                .back-link { margin-top: 20px; display: block; }
            </style>
        </head>
        <body>
            <div class="form-container">
                <h2>Register</h2>
                <form method="post">
                    <div class="form-field">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" required>
                    </div>
                    <div class="form-field">
                        <label for="display_name">Display Name</label>
                        <input type="text" id="display_name" name="display_name" required>
                    </div>
                    <div class="form-field">
                        <button type="submit">Continue</button>
                    </div>
                </form>
                <a href="/home" class="back-link">Back to Home</a>
            </div>
        </body>
        </html>
        """
    )


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
