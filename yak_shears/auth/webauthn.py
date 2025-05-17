"""WebAuthn authentication functionality."""

import base64
import secrets
from typing import Any

from starlette.requests import Request
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

from yak_shears.auth.models import CredentialEntry, User
from yak_shears.auth.storage import (
    get_user_by_id,
    get_user_by_name,
    get_user_id_from_session,
    update_credential_sign_count,
)

# Constants for the RP (Relying Party)
_RP_ID = "localhost"
_RP_NAME = "Yak Shears"
_RP_EXPECTED_ORIGIN = "http://localhost:8000"


def generate_auth_options_for_user(username: str) -> tuple[PublicKeyCredentialRequestOptions | None, User | None]:
    """Generate authentication options for a user.

    Args:
        username: The username to generate authentication options for

    Returns:
        Tuple[PublicKeyCredentialRequestOptions | None, User | None]: A tuple containing the authentication options
            and the user if found
    """
    user = get_user_by_name(username)
    if not user:
        return None, None

    # Get credential IDs for the user
    allowed_credentials = []
    for cred in user["credentials"]:
        cred_id = cred["id"]
        # Convert base64 string to bytes
        cred_id_bytes = base64.b64decode(cred_id)
        allowed_credentials.append(
            PublicKeyCredentialDescriptor(
                id=cred_id_bytes,
                type=PublicKeyCredentialType.PUBLIC_KEY,
            )
        )

    # Generate a challenge
    challenge = secrets.token_bytes(32)

    # Create authentication options
    options = generate_authentication_options(
        rp_id=_RP_ID,
        challenge=challenge,
        allow_credentials=allowed_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # Store the challenge for later verification
    user["current_challenge"] = base64.b64encode(challenge).decode()

    return options, user


def verify_authentication(user: User, credential_data: dict[str, Any]) -> tuple[bool, CredentialEntry | None]:
    """Verify authentication response.

    Args:
        user: The user to verify
        credential_data: The credential data to verify

    Returns:
        Tuple[bool, CredentialEntry | None]: A tuple containing a boolean indicating if the verification was successful
            and the credential if found
    """
    if not user["current_challenge"]:
        return False, None

    # Find the credential
    credential = None
    for cred in user["credentials"]:
        cred_id = cred["id"]
        if cred_id == credential_data.get("id"):
            credential = cred
            break

    if not credential:
        return False, None

    # Convert the credential data to the expected format
    auth_cred = AuthenticationCredential(
        id=base64.b64decode(credential_data["id"]),
        raw_id=base64.b64decode(credential_data["rawId"]),
        response={
            "authenticatorData": base64.b64decode(credential_data["response"]["authenticatorData"]),
            "clientDataJSON": base64.b64decode(credential_data["response"]["clientDataJSON"]),
            "signature": base64.b64decode(credential_data["response"]["signature"]),
            "userHandle": (
                base64.b64decode(credential_data["response"]["userHandle"])
                if credential_data["response"].get("userHandle")
                else None
            ),
        },
        type=credential_data["type"],
    )

    # Get the expected challenge
    expected_challenge = base64.b64decode(user["current_challenge"])

    # Get the public key
    public_key = base64.b64decode(credential["public_key"])

    try:
        # Verify the authentication response
        verification = verify_authentication_response(
            credential=auth_cred,
            expected_challenge=expected_challenge,
            expected_rp_id=_RP_ID,
            expected_origin=_RP_EXPECTED_ORIGIN,
            credential_public_key=public_key,
            credential_current_sign_count=credential["sign_count"],
            require_user_verification=True,
        )

        # Update the sign count
        if verification.new_sign_count is not None:
            update_credential_sign_count(user["id"], credential_data["id"], verification.new_sign_count)

        # Clear the challenge
        user["current_challenge"] = None

        return True, credential
    except Exception:
        return False, None


def generate_registration_options_for_user(username: str, display_name: str) -> PublicKeyCredentialRequestOptions:
    """Generate registration options for a new user.

    Args:
        username: The username for the new user
        display_name: The display name for the new user

    Returns:
        PublicKeyCredentialRequestOptions: The registration options
    """
    # Generate a user ID for the registration
    user_id = secrets.token_bytes(16)

    # Generate a challenge
    challenge = secrets.token_bytes(32)

    # Create registration options
    options = generate_registration_options(
        rp_id=_RP_ID,
        rp_name=_RP_NAME,
        user_id=user_id,
        user_name=username,
        user_display_name=display_name,
        attestation="direct",
        challenge=challenge,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.EDDSA,
            COSEAlgorithmIdentifier.RS256,
        ],
    )

    return options


def verify_registration(credential_data: dict[str, Any], username: str, display_name: str, challenge: bytes) -> bool:
    """Verify registration response.

    Args:
        credential_data: The credential data to verify
        username: The username of the user
        display_name: The display name of the user
        challenge: The challenge to verify

    Returns:
        bool: True if the verification was successful, False otherwise
    """
    # Convert the credential data to the expected format
    reg_cred = RegistrationCredential(
        id=base64.b64decode(credential_data["id"]),
        raw_id=base64.b64decode(credential_data["rawId"]),
        response={
            "attestationObject": base64.b64decode(credential_data["response"]["attestationObject"]),
            "clientDataJSON": base64.b64decode(credential_data["response"]["clientDataJSON"]),
        },
        type=credential_data["type"],
    )

    try:
        # Verify the registration response
        verification = verify_registration_response(
            credential=reg_cred,
            expected_challenge=challenge,
            expected_rp_id=_RP_ID,
            expected_origin=_RP_EXPECTED_ORIGIN,
            require_user_verification=True,
        )

        # Create the credential
        credential: CredentialEntry = {
            "id": credential_data["id"],
            "public_key": base64.b64encode(verification.credential_public_key).decode(),
            "sign_count": verification.sign_count,
            "transports": credential_data.get("transports"),
        }

        # Create or update the user
        from yak_shears.auth.storage import add_credential_to_user, create_user

        user = get_user_by_name(username)
        if not user:
            user = create_user(username, display_name)

        # Add the credential to the user
        add_credential_to_user(user["id"], credential)

        return True
    except Exception as e:
        print(f"Error verifying registration: {e}")
        return False


def get_user_from_session(request: Request) -> User | None:
    """Get the user from a session.

    Args:
        request: The request containing the session cookie

    Returns:
        User | None: The user if found, None otherwise
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    user_id = get_user_id_from_session(session_id)
    if not user_id:
        return None

    return get_user_by_id(user_id)
