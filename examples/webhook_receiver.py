"""Verification helper for your backend. Persist event IDs atomically before processing."""

import hashlib
import hmac
import json
import time


def verify_webhook(body: bytes, timestamp: str, signature: str, secret: str) -> dict:
    if len(body) > 65536 or abs(int(timestamp) - time.time()) > 300:
        raise ValueError("Expired or oversized webhook")
    expected = (
        "sha256="
        + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid signature")
    event = json.loads(body)
    if not isinstance(event.get("id"), str) or not isinstance(event.get("type"), str):
        raise ValueError("Malformed event")
    return event
