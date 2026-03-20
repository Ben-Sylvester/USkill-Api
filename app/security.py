"""
Security helpers.

Centralises input sanitisation so every router and service can call a
single function rather than rolling its own.

Rules applied to free-text fields (task, name, description):
  1. Strip ASCII control characters (0x00-0x1F except tab/newline)
  2. Reject strings that contain HTML tags when task_allow_html=False
  3. Enforce byte-length cap (prevents over-size payloads reaching DB)
  4. Normalise multiple consecutive whitespace to single space

None of this is a substitute for parameterised queries (SQLAlchemy handles
that) — this is defence-in-depth for the application layer.
"""

from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException, Request

from app.config import get_settings

settings = get_settings()

# Match HTML open/close tags and common injection patterns
_HTML_TAG_RE = re.compile(r"<[a-zA-Z/!][^>]*>")
# Strip C0 + C1 control characters except \t (0x09) and \n (0x0A)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B-\x1F\x7F\x80-\x9F]")
# Collapse repeated whitespace (but keep newlines for multi-line tasks)
_MULTI_SPACE_RE = re.compile(r"[^\S\n]+")


def sanitise_text(
    value: str,
    field_name: str = "field",
    max_bytes: int | None = None,
    allow_html: bool | None = None,
    request: Request | None = None,
) -> str:
    """
    Sanitise a free-text input string.

    Args:
        value:       The raw string from the request.
        field_name:  Used in error messages.
        max_bytes:   Override the global setting.
        allow_html:  Override the global setting.
        request:     If provided, the request_id is included in error details.

    Returns:
        The sanitised string.

    Raises:
        HTTPException(422) if validation fails.
    """
    rid = getattr(request.state, "request_id", None) if request else None
    cap = max_bytes if max_bytes is not None else settings.task_max_bytes
    html_ok = allow_html if allow_html is not None else settings.task_allow_html

    # 1. Strip control characters
    value = _CONTROL_CHAR_RE.sub("", value)

    # 2. Collapse redundant horizontal whitespace
    value = _MULTI_SPACE_RE.sub(" ", value).strip()

    # 3. Byte-length cap (UTF-8 can expand characters)
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) > cap:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INPUT_TOO_LARGE",
                "message": (
                    f"'{field_name}' exceeds the maximum of {cap} bytes "
                    f"(got {len(encoded)})."
                ),
                "field": field_name,
                "request_id": rid,
            },
        )

    # 4. HTML tag rejection
    if not html_ok and _HTML_TAG_RE.search(value):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INVALID_INPUT",
                "message": f"'{field_name}' must not contain HTML tags.",
                "field": field_name,
                "request_id": rid,
            },
        )

    return value


def sanitise_identifier(value: str, field_name: str = "id") -> str:
    """
    Validate a domain/resource identifier (lowercase, alphanumeric + underscores).
    No external call needed — just raises on invalid format.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", value):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INVALID_FORMAT",
                "message": (
                    f"'{field_name}' must be 3–64 chars, start with a letter, "
                    "and contain only lowercase letters, digits, and underscores."
                ),
                "field": field_name,
            },
        )
    return value
