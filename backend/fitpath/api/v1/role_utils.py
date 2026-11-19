"""Validaciones pequeñas compartidas por las APIs internas por rol."""

import hmac
import unicodedata
from datetime import datetime, timezone

from flask import request

from ...auth.authorization import current_identity


def csrf_is_valid():
    identity = current_identity()
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = identity["csrf_token"] if identity else ""
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def positive_integer(value, field="id"):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(field)
    return value


def bounded_integer(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(field)
    return value


def clean_text(value, field, *, maximum=255, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(field)
    result = unicodedata.normalize("NFC", value).strip()
    if optional and not result:
        return None
    if not result or len(result) > maximum:
        raise ValueError(field)
    if any(unicodedata.category(character).startswith("C") for character in result):
        raise ValueError(field)
    return result


def require_json_fields(payload, allowed, required=()):
    if not isinstance(payload, dict) or set(payload) - set(allowed):
        raise ValueError("request")
    if any(field not in payload for field in required):
        raise ValueError("request")
    return payload
