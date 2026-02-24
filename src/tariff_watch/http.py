"""Unified HTTP client with timeout, retry, and exponential backoff."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
BACKOFF_BASE = 2.0


class NetworkError(Exception):
    """Raised on unrecoverable HTTP / connectivity failures."""


class ParseError(Exception):
    """Raised when response content cannot be parsed."""


def _backoff(attempt: int) -> float:
    return BACKOFF_BASE ** attempt


def get(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    session: requests.Session | None = None,
) -> requests.Response:
    """GET with retry/backoff. Raises NetworkError on final failure."""
    client = session or requests.Session()
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            resp = client.get(url, timeout=timeout, headers=headers, params=params)
            resp.raise_for_status()
            return resp
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.warning("Timeout on attempt %d/%d: %s", attempt + 1, retries, url)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.warning("Connection error on attempt %d/%d: %s", attempt + 1, retries, url)
        except requests.exceptions.HTTPError as exc:
            last_exc = exc
            logger.warning(
                "HTTP %s on attempt %d/%d: %s",
                exc.response.status_code if exc.response is not None else "?",
                attempt + 1,
                retries,
                url,
            )

        if attempt < retries - 1:
            wait = _backoff(attempt)
            logger.debug("Backing off %.1fs before retry…", wait)
            time.sleep(wait)

    raise NetworkError(f"Failed to GET {url} after {retries} attempts: {last_exc}") from last_exc


def download_text(url: str, **kwargs: Any) -> str:
    """Download URL and return response body as text."""
    resp = get(url, **kwargs)
    try:
        return resp.text
    except Exception as exc:
        raise ParseError(f"Cannot decode response from {url}") from exc
