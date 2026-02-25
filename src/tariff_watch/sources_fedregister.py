"""Fetch tariff-related notices from the Federal Register public API."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from .http import NetworkError, ParseError, get as http_get

logger = logging.getLogger(__name__)

# Federal Register open API — no auth required.
_FR_API = "https://www.federalregister.gov/api/v1/documents.json"

# Agencies whose notices are most relevant for tariff monitoring.
_TARIFF_AGENCIES = [
    "united-states-trade-representative",   # USTR — Section 301
    "commerce-department",                   # Commerce — Section 232, AD/CVD
    "customs-border-protection",             # CBP
    "international-trade-commission",        # USITC
]


def fetch_notices(
    since: date | None = None,
    agencies: list[str] | None = None,
    per_page: int = 20,
) -> list[dict[str, Any]]:
    """
    Fetch recent Federal Register notices relevant to tariff changes.

    Args:
        since:    Earliest publication date (default: 30 days ago).
        agencies: Agency slugs to filter by (default: :data:`_TARIFF_AGENCIES`).
        per_page: Max results to fetch per agency (capped at 20 by the API).

    Returns:
        List of notice dicts with keys:
        ``document_number``, ``published_date``, ``title``,
        ``url``, ``agency``, ``abstract``.
    """
    if since is None:
        since = date.today() - timedelta(days=30)
    if agencies is None:
        agencies = _TARIFF_AGENCIES

    results: list[dict[str, Any]] = []

    for agency in agencies:
        params = {
            "conditions[agencies][]": agency,
            "conditions[publication_date][gte]": since.isoformat(),
            "conditions[type][]": ["NOTICE", "RULE", "PRORULE"],
            "fields[]": [
                "document_number",
                "publication_date",
                "title",
                "html_url",
                "agencies",
                "abstract",
            ],
            "per_page": per_page,
            "order": "newest",
        }
        try:
            resp = http_get(_FR_API, params=params, timeout=15)
            data = resp.json()
        except NetworkError as exc:
            logger.warning("Federal Register fetch failed for agency %s: %s", agency, exc)
            continue
        except Exception as exc:
            raise ParseError(f"Federal Register response parse error: {exc}") from exc

        for doc in data.get("results", []):
            agency_names = ", ".join(
                a.get("name", "") for a in doc.get("agencies", [])
            ) or agency
            results.append({
                "document_number": doc.get("document_number", ""),
                "published_date": doc.get("publication_date", ""),
                "title": doc.get("title", ""),
                "url": doc.get("html_url", ""),
                "agency": agency_names,
                "abstract": (doc.get("abstract") or "")[:1000],
            })

        logger.info(
            "Federal Register: %d notice(s) from agency '%s' since %s",
            len(data.get("results", [])),
            agency,
            since,
        )

    # Deduplicate by document_number (an agency may appear in multiple conditions)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in results:
        if r["document_number"] not in seen:
            seen.add(r["document_number"])
            unique.append(r)

    logger.info("Federal Register total: %d unique notice(s) fetched", len(unique))
    return unique
