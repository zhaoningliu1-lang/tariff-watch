"""Configuration loader with ENV:VAR_NAME resolution."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


def _resolve(value: Any) -> Any:
    """Recursively resolve ENV:VAR_NAME references."""
    if isinstance(value, str) and value.startswith("ENV:"):
        var = value[4:]
        resolved = os.environ.get(var)
        if resolved is None:
            logger.debug("Environment variable %s not set (value stays None)", var)
        return resolved
    if isinstance(value, dict):
        return {k: _resolve(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v) for v in value]
    return value


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    from_email: str | None = None
    to_emails: list[str] = field(default_factory=list)
    subject_prefix: str = "[Tariff Watch]"

    def is_ready(self) -> bool:
        return bool(
            self.enabled
            and self.smtp_host
            and self.smtp_user
            and self.smtp_password
            and self.from_email
            and self.to_emails
        )


@dataclass
class StorageConfig:
    snapshots_dir: str = "snapshots"
    reports_dir: str = "reports"
    retain_weeks: int = 12


@dataclass
class SourcesConfig:
    usitc_hts_export_url: str = ""


@dataclass
class RuntimeConfig:
    timezone: str = "America/Los_Angeles"
    log_level: str = "INFO"


@dataclass
class AppConfig:
    mode: str = "tracked_only"
    tracked_hts: list[str] = field(default_factory=list)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    notify_email: EmailConfig = field(default_factory=EmailConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw: dict = yaml.safe_load(fh) or {}

    raw = _resolve(raw)

    cfg = AppConfig()
    cfg.mode = raw.get("mode", "tracked_only")
    cfg.tracked_hts = [str(h) for h in raw.get("tracked_hts", [])]

    src = raw.get("sources", {})
    cfg.sources = SourcesConfig(
        usitc_hts_export_url=src.get("usitc_hts_export_url", ""),
    )

    sto = raw.get("storage", {})
    cfg.storage = StorageConfig(
        snapshots_dir=sto.get("snapshots_dir", "snapshots"),
        reports_dir=sto.get("reports_dir", "reports"),
        retain_weeks=int(sto.get("retain_weeks", 12)),
    )

    em = raw.get("notify_email", {})
    cfg.notify_email = EmailConfig(
        enabled=bool(em.get("enabled", False)),
        smtp_host=em.get("smtp_host"),
        smtp_port=int(em.get("smtp_port", 587)),
        smtp_user=em.get("smtp_user"),
        smtp_password=em.get("smtp_password"),
        from_email=em.get("from_email"),
        to_emails=list(em.get("to_emails", [])),
        subject_prefix=em.get("subject_prefix", "[Tariff Watch]"),
    )

    rt = raw.get("runtime", {})
    cfg.runtime = RuntimeConfig(
        timezone=rt.get("timezone", "America/Los_Angeles"),
        log_level=rt.get("log_level", "INFO"),
    )

    logging.basicConfig(level=getattr(logging, cfg.runtime.log_level.upper(), logging.INFO))
    return cfg
