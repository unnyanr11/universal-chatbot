"""Backend-only assertion helper. Call after authenticating your own website customer."""

import base64
import hashlib
import hmac
import json
import secrets
import time


def sign_identity(assistant_id: str, authenticated_customer_id: str, signing_secret: str) -> str:
    # Never accept an arbitrary customer ID supplied by a browser; derive it from your session.
    claims = {
        "assistant_id": assistant_id,
        "sub": str(authenticated_customer_id),
        "exp": int(time.time()) + 120,
        "nonce": secrets.token_urlsafe(24),
    }
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    signature = (
        base64.urlsafe_b64encode(
            hmac.new(signing_secret.encode(), payload.encode(), hashlib.sha256).digest()
        )
        .decode()
        .rstrip("=")
    )
    return payload + "." + signature
