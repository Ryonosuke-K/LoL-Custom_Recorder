import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone


def encode_state(code: str, secret: str) -> str:
    payload = {
        "code": code,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp(),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    token = {
        "p": base64.urlsafe_b64encode(payload_bytes).decode(),
        "s": sig,
    }
    return base64.urlsafe_b64encode(
        json.dumps(token, separators=(",", ":"), ensure_ascii=True).encode()
    ).decode()


def decode_state(token: str, secret: str) -> str:
    raw = base64.urlsafe_b64decode(token.encode())
    data = json.loads(raw.decode())
    payload_b64 = data["p"]
    sig = data["s"]

    payload_bytes = base64.urlsafe_b64decode(payload_b64.encode())
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid state signature")

    payload = json.loads(payload_bytes.decode())
    if datetime.now(timezone.utc).timestamp() > payload["exp"]:
        raise ValueError("State expired")

    return payload["code"]
