"""Optional SMTP email delivery of the weekly report (STARTTLS, port 587)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import EmailConfig

logger = logging.getLogger(__name__)


def _markdown_to_html(markdown_text: str) -> str:
    """
    Lightweight Markdown → HTML conversion.
    Strategy: wrap content in <pre> for reliability.
    For richer HTML, integrate a library like 'markdown' (not in dependencies).
    See README for details on improving HTML output.
    """
    escaped = markdown_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!DOCTYPE html><html><body>"
        "<p style='font-family:monospace;font-size:13px;'>"
        "<pre style='white-space:pre-wrap;word-wrap:break-word;'>"
        f"{escaped}"
        "</pre></p></body></html>"
    )


def send_report_email(
    cfg: EmailConfig,
    subject_suffix: str,
    md_path: Path,
    dry_run: bool = False,
) -> bool:
    """
    Send the Markdown report as a multipart email (plain text + HTML).

    Returns True on success, False on failure (never raises — logs warning instead).
    """
    if not cfg.is_ready():
        logger.warning(
            "Email not sent: configuration is incomplete "
            "(check smtp_host, smtp_user, smtp_password, from_email, to_emails)."
        )
        return False

    if dry_run:
        logger.info("Dry-run: skipping email send to %s", cfg.to_emails)
        return True

    try:
        md_text = md_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Email not sent: cannot read report file %s — %s", md_path, exc)
        return False

    subject = f"{cfg.subject_prefix} {subject_suffix}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_email  # type: ignore[assignment]
    msg["To"] = ", ".join(cfg.to_emails)

    part_plain = MIMEText(md_text, "plain", "utf-8")
    part_html = MIMEText(_markdown_to_html(md_text), "html", "utf-8")
    msg.attach(part_plain)
    msg.attach(part_html)

    try:
        logger.info("Connecting to SMTP %s:%s (STARTTLS)…", cfg.smtp_host, cfg.smtp_port)
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:  # type: ignore[arg-type]
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg.smtp_user, cfg.smtp_password)  # type: ignore[arg-type]
            server.sendmail(cfg.from_email, cfg.to_emails, msg.as_string())  # type: ignore[arg-type]
        logger.info("Email sent to %s", cfg.to_emails)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Email send failed: %s", exc)
        return False
