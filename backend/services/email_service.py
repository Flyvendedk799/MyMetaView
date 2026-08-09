"""Transactional email service (stdlib SMTP over SSL).

Small, robust, dependency-free email sending for MetaView. Sending is best
effort: if email is disabled or unconfigured, or if anything goes wrong at
send time, these functions log and return quietly. They NEVER raise to the
caller, so request handlers can fire an email without risking their own flow.
"""
import logging
import re
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brand palette (MetaView identity)
# ---------------------------------------------------------------------------
_EVERGREEN = "#0B3B2E"   # deep evergreen header
_EMBER = "#E8622C"       # ember accent (buttons)
_INK = "#1A2420"         # body text
_MUTED = "#6B7770"       # footer / secondary text
_PAGE_BG = "#F4F6F5"     # subtle page backdrop behind the card
_CARD_BG = "#FFFFFF"     # card background
_BORDER = "#E3E8E5"

_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, "
    "Arial, sans-serif"
)


def _html_to_text(html: str) -> str:
    """Best-effort plaintext fallback from an HTML body."""
    # Drop script/style blocks entirely, then strip tags.
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|h[1-6]|li)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace, preserving intentional newlines.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    return text.strip()


def _wrap_email(heading: str, body_html: str, button: dict | None = None) -> str:
    """Build the shared, mobile-friendly, inline-CSS email shell.

    ``button`` (optional) is a dict with ``label`` and ``url`` keys.
    """
    button_html = ""
    if button and button.get("url"):
        label = button.get("label", "Open")
        url = button["url"]
        button_html = (
            '<tr><td style="padding:8px 0 4px 0;">'
            f'<a href="{url}" '
            'style="display:inline-block;background-color:' + _EMBER + ';'
            'color:#FFFFFF;text-decoration:none;font-weight:600;font-size:15px;'
            'line-height:20px;padding:13px 26px;border-radius:8px;'
            'font-family:' + _FONT_STACK + ';">'
            f'{label}</a>'
            '</td></tr>'
        )

    return (
        '<!DOCTYPE html>'
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>{heading}</title></head>'
        f'<body style="margin:0;padding:0;background-color:{_PAGE_BG};'
        f'font-family:{_FONT_STACK};">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background-color:{_PAGE_BG};padding:24px 12px;">'
        '<tr><td align="center">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;width:100%;background-color:' + _CARD_BG + ';'
        'border:1px solid ' + _BORDER + ';border-radius:12px;overflow:hidden;">'
        # Header band
        '<tr><td style="background-color:' + _EVERGREEN + ';padding:22px 32px;">'
        '<span style="color:#FFFFFF;font-size:18px;font-weight:700;'
        'letter-spacing:0.2px;font-family:' + _FONT_STACK + ';">MetaView</span>'
        '</td></tr>'
        # Body
        '<tr><td style="padding:32px 32px 28px 32px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="font-size:22px;font-weight:700;color:' + _INK + ';'
        'padding-bottom:14px;font-family:' + _FONT_STACK + ';">' + heading + '</td></tr>'
        '<tr><td style="font-size:15px;line-height:24px;color:' + _INK + ';'
        'font-family:' + _FONT_STACK + ';">' + body_html + '</td></tr>'
        + button_html +
        '</table></td></tr>'
        # Footer
        '<tr><td style="padding:18px 32px 24px 32px;border-top:1px solid '
        + _BORDER + ';font-size:12px;color:' + _MUTED + ';'
        'font-family:' + _FONT_STACK + ';">MetaView &middot; mymetaview.com</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> bool:
    """Send a single transactional email. Returns True on success.

    Never raises. If email is disabled or SMTP is unconfigured, logs an info
    line and returns False without attempting a connection.
    """
    if not settings.EMAIL_ENABLED or not settings.SMTP_PASSWORD:
        logger.info(
            "Email disabled/unconfigured, skipping send to %s (subject=%r)",
            to, subject,
        )
        return False

    if text_body is None:
        text_body = _html_to_text(html_body)

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        try:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass
        logger.info("Email sent to %s (subject=%r)", to, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s (subject=%r): %s", to, subject, exc)
        return False


def send_email_async(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """Fire-and-forget wrapper around :func:`send_email`.

    Runs the send on a daemon thread so callers never block or fail on email.
    """
    def _run() -> None:
        try:
            send_email(to, subject, html_body, text_body)
        except Exception as exc:  # defensive: send_email already swallows
            logger.error("Async email thread failed for %s: %s", to, exc)

    try:
        threading.Thread(target=_run, daemon=True).start()
    except Exception as exc:
        logger.error("Could not start async email thread for %s: %s", to, exc)


def send_welcome_email(to_email: str, name: str | None = None) -> None:
    """Send an on-brand welcome email (fire-and-forget)."""
    greeting = f"Hi {name}," if name else "Welcome aboard,"
    body_html = (
        f'<p style="margin:0 0 14px 0;">{greeting}</p>'
        '<p style="margin:0 0 14px 0;">Thanks for joining MetaView. You are all '
        'set to turn any URL into a polished, share-ready preview card in seconds.</p>'
        '<p style="margin:0;">Paste a link, pick a style, and let MetaView do the '
        'design work. We are glad to have you.</p>'
    )
    html = _wrap_email("Welcome to MetaView", body_html)
    send_email_async(to_email, "Welcome to MetaView", html)


def send_org_invite_email(
    to_email: str,
    org_name: str,
    invite_url: str,
    inviter_email: str | None = None,
) -> None:
    """Send an organization invite email with a prominent join button."""
    who = f"{inviter_email} has invited" if inviter_email else "You have been invited"
    body_html = (
        f'<p style="margin:0 0 14px 0;">{who} you to join '
        f'<strong>{org_name}</strong> on MetaView.</p>'
        '<p style="margin:0 0 18px 0;">Click the button below to accept the '
        'invitation and start collaborating.</p>'
    )
    html = _wrap_email(
        "You have been invited",
        body_html,
        button={"label": f"Join {org_name}", "url": invite_url},
    )
    send_email_async(
        to_email,
        f"You've been invited to {org_name} on MetaView",
        html,
    )
