"""WebAuthn-based authentication for Yak Shears."""

import base64
import json
import os
import secrets
from pathlib import Path
from typing import Any, TypedDict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRequestOptions,
    PublicKeyCredentialType,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

__all__ = [
    "AuthMiddleware",
    "CredentialEntry",
    "User",
    "add_credential_to_user",
    "auth_routes",
    "create_session",
    "create_user",
    "delete_session",
    "generate_auth_options_for_user",
    "get_user_by_id",
    "get_user_by_name",
    "get_user_from_session",
    "initialize",
    "update_credential_sign_count"
]


# Simple in-memory user storage - in a production app, use a database
class User(TypedDict):
    """User data structure."""

    id: str
    name: str
    display_name: str
    credentials: list[dict[str, Any]]
    current_challenge: str | None


class CredentialEntry(TypedDict):
    """Credential data structure."""

    id: str
    public_key: str
    sign_count: int
    transports: list[str] | None


# In-memory user storage - would be a database in production
_users: dict[str, User] = {}
_username_to_user_id: dict[str, str] = {}
_session_store: dict[str, str] = {}  # session_id -> user_id

# Path to save user data
_USER_DATA_PATH = Path("~/.yak-shears-users.json").expanduser()


def _generate_user_id() -> str:
    """Generate a random user ID."""
    return secrets.token_hex(16)


def _generate_session_id() -> str:
    """Generate a random session ID."""
    return secrets.token_hex(32)


def _save_users() -> None:
    """Save users to disk."""
    data = {
        "users": _users,
        "username_to_user_id": _username_to_user_id,
    }
    _USER_DATA_PATH.write_text(json.dumps(data, indent=2))


def _load_users() -> None:
    """Load users from disk."""
    global _users, _username_to_user_id

    if not _USER_DATA_PATH.exists():
        return

    try:
        data = json.loads(_USER_DATA_PATH.read_text())
        _users = data.get("users", {})
        _username_to_user_id = data.get("username_to_user_id", {})
    except (OSError, json.JSONDecodeError):
        # Start fresh if file is corrupt
        _users = {}
        _username_to_user_id = {}


def initialize() -> None:
    """Initialize the auth system."""
    _load_users()


def get_user_by_name(username: str) -> User | None:
    """Get a user by username."""
    user_id = _username_to_user_id.get(username)
    if not user_id:
        return None
    return _users.get(user_id)


def get_user_by_id(user_id: str) -> User | None:
    """Get a user by ID."""
    return _users.get(user_id)


def get_user_from_session(request: Request) -> User | None:
    """Get the user from the session cookie."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    user_id = _session_store.get(session_id)
    if not user_id:
        return None

    return get_user_by_id(user_id)


def create_user(username: str, display_name: str) -> User:
    """Create a new user."""
    user_id = _generate_user_id()
    user: User = {
        "id": user_id,
        "name": username,
        "display_name": display_name,
        "credentials": [],
        "current_challenge": None,
    }
    _users[user_id] = user
    _username_to_user_id[username] = user_id
    _save_users()
    return user


def add_credential_to_user(user_id: str, credential: CredentialEntry) -> None:
    """Add a credential to a user."""
    if user_id in _users:
        _users[user_id]["credentials"].append(credential)  # type: ignore
        _save_users()


def update_credential_sign_count(user_id: str, credential_id: str, sign_count: int) -> None:
    """Update the sign count for a credential."""
    if user_id not in _users:
        return

    for cred in _users[user_id]["credentials"]:  # type: ignore
        if cred["id"] == credential_id:
            cred["sign_count"] = sign_count
            break

    _save_users()


def create_session(user_id: str) -> str:
    """Create a new session for a user."""
    session_id = _generate_session_id()
    _session_store[session_id] = user_id
    return session_id


def delete_session(session_id: str) -> None:
    """Delete a session."""
    _session_store.pop(session_id, None)


def generate_auth_options_for_user(username: str) -> tuple[PublicKeyCredentialRequestOptions | None, User | None]:
    """Generate authentication options for a user."""
    user = get_user_by_name(username)
    if not user:
        return None, None

    allowed_credentials = []
    for credential in user["credentials"]:
        descriptor = PublicKeyCredentialDescriptor(
            id=base64.b64decode(credential["id"]),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )
        allowed_credentials.append(descriptor)

    challenge = secrets.token_bytes(32)
    user["current_challenge"] = base64.b64encode(challenge).decode("utf-8")
    _save_users()

    options = generate_authentication_options(
        rp_id=os.environ.get("WEBAUTHN_RP_ID", "localhost"),
        allow_credentials=allowed_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
        challenge=challenge,
    )

    return options, user


# WebAuthn handlers
async def register_begin_handler(request: Request) -> Response:
    """Begin WebAuthn registration process."""
    if request.method == "GET":
        return HTMLResponse(r"""
        <html>
        <head>
            <title>Register</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; }
                input { padding: 8px; width: 100%; max-width: 300px; }
                button { padding: 10px 15px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
                button:hover { background-color: #45a049; }
                .error { color: red; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h1>Register with Passkey</h1>
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="displayName">Display Name:</label>
                <input type="text" id="displayName" name="displayName" required>
            </div>
            <button onclick="startRegistration()">Register</button>
            <div id="error" class="error"></div>

            <script>
                async function startRegistration() {
                    const username = document.getElementById('username').value;
                    const displayName = document.getElementById('displayName').value;

                    if (!username || !displayName) {
                        document.getElementById('error').textContent = 'Username and display name are required';
                        return;
                    }

                    try {
                        // Request registration options from server
                        const optionsResponse = await fetch('/auth/register/options', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ username, displayName })
                        });

                        if (!optionsResponse.ok) {
                            throw new Error(`Server returned ${optionsResponse.status}`);
                        }

                        const options = await optionsResponse.json();

                        // Convert base64url strings to ArrayBuffer
                        options.challenge = base64URLToArrayBuffer(options.challenge);
                        options.user.id = base64URLToArrayBuffer(options.user.id);

                        if (options.excludeCredentials) {
                            for (let cred of options.excludeCredentials) {
                                cred.id = base64URLToArrayBuffer(cred.id);
                            }
                        }

                        // Create credential
                        const credential = await navigator.credentials.create({
                            publicKey: options
                        });

                        // Prepare credential data for server
                        const credentialData = {
                            id: credential.id,
                            rawId: arrayBufferToBase64URL(credential.rawId),
                            type: credential.type,
                            response: {
                                clientDataJSON: arrayBufferToBase64URL(credential.response.clientDataJSON),
                                attestationObject: arrayBufferToBase64URL(credential.response.attestationObject),
                            }
                        };

                        // Send credential to server
                        const verifyResponse = await fetch('/auth/register/verify', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                username,
                                credential: credentialData
                            })
                        });

                        if (!verifyResponse.ok) {
                            const error = await verifyResponse.json();
                            throw new Error(error.message || 'Registration failed');
                        }

                        const result = await verifyResponse.json();

                        if (result.success) {
                            window.location.href = '/home';
                        } else {
                            document.getElementById('error').textContent = result.message || 'Registration failed';
                        }
                    } catch (error) {
                        console.error('Registration error:', error);
                        document.getElementById('error').textContent = error.message || 'Registration failed';
                    }
                }

                // Helper functions for encoding/decoding
                function base64URLToArrayBuffer(base64URL) {
                    const base64 = base64URL.replace(/-/g, '+').replace(/_/g, '/');
                    const padLength = (4 - (base64.length % 4)) % 4;
                    const padded = base64 + '='.repeat(padLength);
                    const binary = atob(padded);
                    const buffer = new ArrayBuffer(binary.length);
                    const view = new Uint8Array(buffer);
                    for (let i = 0; i < binary.length; i++) {
                        view[i] = binary.charCodeAt(i);
                    }
                    return buffer;
                }

                function arrayBufferToBase64URL(buffer) {
                    const bytes = new Uint8Array(buffer);
                    let binary = '';
                    for (let i = 0; i < bytes.byteLength; i++) {
                        binary += String.fromCharCode(bytes[i]);
                    }
                    const base64 = btoa(binary);
                    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
                }
            </script>
        </body>
        </html>
        """)

    return HTMLResponse("<h1>Method not allowed</h1>", status_code=405)


async def register_options_handler(request: Request) -> Response:
    """Generate WebAuthn registration options."""
    try:
        data = await request.json()
        username = data.get("username")
        display_name = data.get("displayName")

        if not username or not display_name:
            return JSONResponse({"error": "Username and display name are required"}, status_code=400)

        # Check if user already exists
        if get_user_by_name(username):
            return JSONResponse({"error": "Username already exists"}, status_code=400)

        # Create user
        user = create_user(username, display_name)

        # Generate registration options
        challenge = secrets.token_bytes(32)
        user["current_challenge"] = base64.b64encode(challenge).decode("utf-8")
        _save_users()

        options = generate_registration_options(
            rp_id=os.environ.get("WEBAUTHN_RP_ID", "localhost"),
            rp_name="Yak Shears",
            user_id=base64.b64encode(user["id"].encode()),
            user_name=username,
            user_display_name=display_name,
            attestation="none",
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
            supported_pub_key_algs=[
                COSEAlgorithmIdentifier.ECDSA_SHA_256,
                COSEAlgorithmIdentifier.EDDSA,
                COSEAlgorithmIdentifier.RS256,
            ],
            challenge=challenge,
        )

        return JSONResponse(options.model_dump(exclude_none=True))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def register_verify_handler(request: Request) -> Response:
    """Verify WebAuthn registration."""
    try:
        data = await request.json()
        username = data.get("username")
        credential_data = data.get("credential")

        if not username or not credential_data:
            return JSONResponse({"error": "Missing username or credential"}, status_code=400)

        user = get_user_by_name(username)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        if not user["current_challenge"]:
            return JSONResponse({"error": "No active challenge for user"}, status_code=400)

        # Parse credential from request
        registration_credential = RegistrationCredential.model_validate({
            "id": credential_data["id"],
            "raw_id": credential_data["rawId"],
            "response": {
                "attestation_object": credential_data["response"]["attestationObject"],
                "client_data_json": credential_data["response"]["clientDataJSON"],
            },
            "type": credential_data["type"],
        })

        expected_challenge = base64.b64decode(user["current_challenge"])

        # Verify registration
        verification = verify_registration_response(
            credential=registration_credential,
            expected_challenge=expected_challenge,
            expected_origin=os.environ.get("WEBAUTHN_ORIGIN", "http://localhost:8080"),
            expected_rp_id=os.environ.get("WEBAUTHN_RP_ID", "localhost"),
            require_user_verification=False,
        )

        # Store credential
        credential_entry: CredentialEntry = {
            "id": base64.b64encode(verification.credential_id).decode(),
            "public_key": base64.b64encode(verification.credential_public_key).decode(),
            "sign_count": verification.sign_count,
            "transports": registration_credential.transports,
        }

        add_credential_to_user(user["id"], credential_entry)

        # Clear challenge
        user["current_challenge"] = None
        _save_users()

        # Create session
        session_id = create_session(user["id"])

        response = JSONResponse({"success": True, "message": "Registration successful"})
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=60 * 60 * 24 * 7,  # 1 week
            path="/",
        )

        return response
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def login_begin_handler(request: Request) -> Response:
    """Begin WebAuthn login process."""
    if request.method == "GET":
        return HTMLResponse(r"""
        <html>
        <head>
            <title>Login</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; }
                input { padding: 8px; width: 100%; max-width: 300px; }
                button { padding: 10px 15px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
                button:hover { background-color: #45a049; }
                .error { color: red; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h1>Login with Passkey</h1>
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <button onclick="startLogin()">Login</button>
            <div id="error" class="error"></div>
            <p><a href="/auth/register">Register a new account</a></p>

            <script>
                async function startLogin() {
                    const username = document.getElementById('username').value;

                    if (!username) {
                        document.getElementById('error').textContent = 'Username is required';
                        return;
                    }

                    try {
                        // Request authentication options from server
                        const optionsResponse = await fetch('/auth/login/options', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ username })
                        });

                        if (!optionsResponse.ok) {
                            const error = await optionsResponse.json();
                            throw new Error(error.error || `Server returned ${optionsResponse.status}`);
                        }

                        const options = await optionsResponse.json();

                        // Convert base64url strings to ArrayBuffer
                        options.challenge = base64URLToArrayBuffer(options.challenge);

                        if (options.allowCredentials) {
                            for (let cred of options.allowCredentials) {
                                cred.id = base64URLToArrayBuffer(cred.id);
                            }
                        }

                        // Get credential
                        const credential = await navigator.credentials.get({
                            publicKey: options
                        });

                        // Prepare credential data for server
                        const credentialData = {
                            id: credential.id,
                            rawId: arrayBufferToBase64URL(credential.rawId),
                            type: credential.type,
                            response: {
                                clientDataJSON: arrayBufferToBase64URL(credential.response.clientDataJSON),
                                authenticatorData: arrayBufferToBase64URL(credential.response.authenticatorData),
                                signature: arrayBufferToBase64URL(credential.response.signature),
                                userHandle: credential.response.userHandle ? arrayBufferToBase64URL(credential.response.userHandle) : null,
                            }
                        };

                        // Send credential to server
                        const verifyResponse = await fetch('/auth/login/verify', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                username,
                                credential: credentialData
                            })
                        });

                        if (!verifyResponse.ok) {
                            const error = await verifyResponse.json();
                            throw new Error(error.error || 'Login failed');
                        }

                        const result = await verifyResponse.json();

                        if (result.success) {
                            window.location.href = '/home';
                        } else {
                            document.getElementById('error').textContent = result.message || 'Login failed';
                        }
                    } catch (error) {
                        console.error('Login error:', error);
                        document.getElementById('error').textContent = error.message || 'Login failed';
                    }
                }

                // Helper functions for encoding/decoding
                function base64URLToArrayBuffer(base64URL) {
                    const base64 = base64URL.replace(/-/g, '+').replace(/_/g, '/');
                    const padLength = (4 - (base64.length % 4)) % 4;
                    const padded = base64 + '='.repeat(padLength);
                    const binary = atob(padded);
                    const buffer = new ArrayBuffer(binary.length);
                    const view = new Uint8Array(buffer);
                    for (let i = 0; i < binary.length; i++) {
                        view[i] = binary.charCodeAt(i);
                    }
                    return buffer;
                }

                function arrayBufferToBase64URL(buffer) {
                    const bytes = new Uint8Array(buffer);
                    let binary = '';
                    for (let i = 0; i < bytes.byteLength; i++) {
                        binary += String.fromCharCode(bytes[i]);
                    }
                    const base64 = btoa(binary);
                    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
                }
            </script>
        </body>
        </html>
        """)

    return HTMLResponse("<h1>Method not allowed</h1>", status_code=405)


async def login_options_handler(request: Request) -> Response:
    """Generate WebAuthn login options."""
    try:
        data = await request.json()
        username = data.get("username")

        if not username:
            return JSONResponse({"error": "Username is required"}, status_code=400)

        options, user = generate_auth_options_for_user(username)

        if not options or not user:
            return JSONResponse({"error": "User not found or has no registered credentials"}, status_code=404)

        return JSONResponse(options.model_dump(exclude_none=True))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def login_verify_handler(request: Request) -> Response:
    """Verify WebAuthn login."""
    try:
        data = await request.json()
        username = data.get("username")
        credential_data = data.get("credential")

        if not username or not credential_data:
            return JSONResponse({"error": "Missing username or credential"}, status_code=400)

        user = get_user_by_name(username)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        if not user["current_challenge"]:
            return JSONResponse({"error": "No active challenge for user"}, status_code=400)

        # Find the credential
        credential_id_b64 = credential_data["id"]
        stored_credential = None

        for cred in user["credentials"]:
            if cred["id"] == credential_data["rawId"]:
                stored_credential = cred
                break

        if not stored_credential:
            return JSONResponse({"error": "Credential not found"}, status_code=404)

        # Parse credential from request
        authentication_credential = AuthenticationCredential.model_validate({
            "id": credential_data["id"],
            "raw_id": credential_data["rawId"],
            "response": {
                "authenticator_data": credential_data["response"]["authenticatorData"],
                "client_data_json": credential_data["response"]["clientDataJSON"],
                "signature": credential_data["response"]["signature"],
                "user_handle": credential_data["response"].get("userHandle"),
            },
            "type": credential_data["type"],
        })

        expected_challenge = base64.b64decode(user["current_challenge"])

        # Verify authentication
        verification = verify_authentication_response(
            credential=authentication_credential,
            expected_challenge=expected_challenge,
            expected_origin=os.environ.get("WEBAUTHN_ORIGIN", "http://localhost:8080"),
            expected_rp_id=os.environ.get("WEBAUTHN_RP_ID", "localhost"),
            credential_public_key=base64.b64decode(stored_credential["public_key"]),
            credential_current_sign_count=stored_credential["sign_count"],
            require_user_verification=False,
        )

        # Update sign count
        update_credential_sign_count(user["id"], stored_credential["id"], verification.new_sign_count)

        # Clear challenge
        user["current_challenge"] = None
        _save_users()

        # Create session
        session_id = create_session(user["id"])

        response = JSONResponse({"success": True, "message": "Login successful"})
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=60 * 60 * 24 * 7,  # 1 week
            path="/",
        )

        return response
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def logout_handler(request: Request) -> Response:
    """Log out the current user."""
    session_id = request.cookies.get("session_id")

    if session_id:
        delete_session(session_id)

    response = RedirectResponse(url="/home", status_code=303)
    response.delete_cookie(key="session_id", path="/")

    return response


async def auth_status_handler(request: Request) -> Response:
    """Return the current authentication status."""
    user = get_user_from_session(request)

    if user:
        return JSONResponse({
            "authenticated": True,
            "username": user["name"],
            "displayName": user["display_name"],
        })

    return JSONResponse({"authenticated": False})


# Authentication middleware
class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for Starlette."""

    def __init__(self, app: Any, public_paths: list[str] = None) -> None:
        """Initialize the middleware.

        Args:
            app: The Starlette application
            public_paths: List of paths that don't require authentication
        """
        super().__init__(app)
        self.public_paths = public_paths or []

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request."""
        # Skip auth for public paths
        path = request.url.path

        if path in self.public_paths or path.startswith("/auth/"):
            return await call_next(request)

        # Check if user is authenticated
        user = get_user_from_session(request)

        if not user:
            return RedirectResponse(url="/auth/login", status_code=303)

        # User is authenticated, proceed
        return await call_next(request)


# Routes for authentication
auth_routes = [
    Route("/auth/register", endpoint=register_begin_handler, methods=["GET"]),
    Route("/auth/register/options", endpoint=register_options_handler, methods=["POST"]),
    Route("/auth/register/verify", endpoint=register_verify_handler, methods=["POST"]),
    Route("/auth/login", endpoint=login_begin_handler, methods=["GET"]),
    Route("/auth/login/options", endpoint=login_options_handler, methods=["POST"]),
    Route("/auth/login/verify", endpoint=login_verify_handler, methods=["POST"]),
    Route("/auth/logout", endpoint=logout_handler, methods=["GET"]),
    Route("/auth/status", endpoint=auth_status_handler, methods=["GET"]),
]
