"""Transactional email service (stdlib SMTP over SSL).

Small, robust, dependency-free email sending for MetaView. Sending is best
effort: if email is disabled or unconfigured, or if anything goes wrong at
send time, these functions log and return quietly. They NEVER raise to the
caller, so request handlers can fire an email without risking their own flow.
"""
import html
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


def _wrap_email(
    heading: str,
    body_html: str,
    button: dict | None = None,
    footer_extra_html: str | None = None,
) -> str:
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

    footer_extra = (
        f'<br><span style="margin-top:6px;display:inline-block;">{footer_extra_html}</span>'
        if footer_extra_html
        else ''
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
        'font-family:' + _FONT_STACK + ';">MetaView &middot; mymetaview.com'
        + footer_extra + '</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    from_name: str | None = None,
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

    sender_name = from_name or settings.SMTP_FROM_NAME or "MetaView"
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{sender_name} <{settings.SMTP_FROM}>"
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


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """Send a password reset link (fire-and-forget)."""
    body_html = (
        '<p style="margin:0 0 14px 0;">Someone asked to reset the password for '
        f'the MetaView account <strong>{to_email}</strong>.</p>'
        '<p style="margin:0 0 18px 0;">If that was you, use the button below. '
        'The link is valid for 30 minutes. If it was not you, you can safely '
        'ignore this email — your password stays unchanged.</p>'
    )
    html = _wrap_email(
        "Reset your password",
        body_html,
        button={"label": "Choose a new password", "url": reset_url},
    )
    send_email_async(to_email, "Reset your MetaView password", html)


def send_domain_verified_email(to_email: str, domain_name: str, dashboard_url: str) -> None:
    """Celebrate a verified domain and point at the next step (fire-and-forget)."""
    body_html = (
        f'<p style="margin:0 0 14px 0;"><strong>{domain_name}</strong> is verified. '
        'Previews you generate for it can now be served to social platforms.</p>'
        '<p style="margin:0 0 18px 0;">Next: generate previews for your most-shared '
        'pages and install the snippet so shared links use them.</p>'
    )
    html = _wrap_email(
        f"{domain_name} is verified",
        body_html,
        button={"label": "Generate previews", "url": dashboard_url},
    )
    send_email_async(to_email, f"{domain_name} is verified on MetaView", html)


def send_bulk_run_finished_email(
    to_email: str,
    domain_name: str,
    succeeded: int,
    failed: int,
    dashboard_url: str,
) -> None:
    """Tell the owner a bulk generation run finished (fire-and-forget)."""
    summary = f"{succeeded} preview{'s' if succeeded != 1 else ''} generated"
    if failed:
        summary += f", {failed} failed"
    body_html = (
        f'<p style="margin:0 0 14px 0;">Your bulk run for '
        f'<strong>{domain_name}</strong> just finished: {summary}.</p>'
        '<p style="margin:0 0 18px 0;">Review the results, tweak any card you '
        'want to improve, and they are live wherever your links are shared.</p>'
    )
    html = _wrap_email(
        "Bulk generation finished",
        body_html,
        button={"label": "Review previews", "url": dashboard_url},
    )
    send_email_async(to_email, f"Your previews for {domain_name} are ready", html)


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


def build_weekly_digest_email(
    user_email: str,
    domain_summaries: list[dict],
    unsubscribe_url: str,
    analytics_url: str,
) -> tuple[str, str, str]:
    """Build subject, HTML body, and plain-text body for the weekly performance digest.

    Per C1 & C7: shows impressions, clicks, CTR, and week-over-week changes per domain,
    plus top 3 previews by clicks, with a link to /app/analytics.
    """
    subject = "Your Weekly Performance Digest - MetaView"

    domain_blocks_html = []
    domain_blocks_text = []

    for d in domain_summaries:
        domain_name = d["domain_name"]
        escaped_domain_name = html.escape(domain_name)
        imp = d["impressions"]
        imp_delta = d.get("impressions_delta", 0)
        imp_pct = d.get("impressions_change_pct", 0.0)
        clk = d["clicks"]
        clk_delta = d.get("clicks_delta", 0)
        clk_pct = d.get("clicks_change_pct", 0.0)
        ctr = d["ctr"]
        ctr_delta = d.get("ctr_delta", 0.0)

        imp_delta_str = f"{'+' if imp_delta > 0 else ''}{imp_delta:,} ({'+' if imp_pct > 0 else ''}{imp_pct:.1f}%)"
        clk_delta_str = f"{'+' if clk_delta > 0 else ''}{clk_delta:,} ({'+' if clk_pct > 0 else ''}{clk_pct:.1f}%)"
        ctr_delta_str = f"{'+' if ctr_delta > 0 else ''}{ctr_delta:.2f}%"

        previews_html = ""
        previews_text = ""
        top_previews = d.get("top_previews") or []
        if top_previews:
            preview_items_html = []
            preview_items_text = []
            for i, p in enumerate(top_previews[:3], 1):
                p_title_raw = p.get("title") or p.get("url") or "Preview"
                p_url_raw = p.get("url") or ""
                p_clicks = p.get("clicks", 0)
                p_imp = p.get("impressions", 0)

                escaped_title = html.escape(str(p_title_raw))
                escaped_url = html.escape(str(p_url_raw))

                if escaped_url:
                    title_html = f'<a href="{escaped_url}" style="color:{_INK};text-decoration:underline;"><strong>{escaped_title}</strong></a>'
                else:
                    title_html = f'<strong>{escaped_title}</strong>'

                preview_items_html.append(
                    f'<li style="margin-bottom:6px;">{title_html}: '
                    f'{p_clicks:,} click{"s" if p_clicks != 1 else ""} '
                    f'({p_imp:,} impression{"s" if p_imp != 1 else ""})</li>'
                )
                preview_items_text.append(
                    f"  {i}. {p_title_raw}: {p_clicks} clicks ({p_imp} impressions)"
                )
            previews_html = (
                '<div style="margin-top:14px;">'
                f'<p style="font-weight:600;margin:0 0 6px 0;font-size:14px;color:{_INK};">Top previews by clicks:</p>'
                f'<ol style="margin:0;padding-left:20px;font-size:13px;color:{_INK};">'
                + "".join(preview_items_html) +
                '</ol></div>'
            )
            previews_text = "\nTop previews by clicks:\n" + "\n".join(preview_items_text) + "\n"

        domain_blocks_html.append(f"""
        <div style="background:#FFFFFF;border:1px solid {_BORDER};border-radius:8px;padding:16px 20px;margin-bottom:16px;">
            <h3 style="margin:0 0 12px 0;font-size:17px;font-weight:600;color:{_EVERGREEN};">{escaped_domain_name}</h3>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;line-height:22px;color:{_INK};">
                <tr>
                    <td style="padding:4px 0;"><strong>Impressions:</strong> {imp:,}</td>
                    <td style="padding:4px 0;color:{_MUTED};text-align:right;">{imp_delta_str} vs prev week</td>
                </tr>
                <tr>
                    <td style="padding:4px 0;"><strong>Clicks:</strong> {clk:,}</td>
                    <td style="padding:4px 0;color:{_MUTED};text-align:right;">{clk_delta_str} vs prev week</td>
                </tr>
                <tr>
                    <td style="padding:4px 0;"><strong>CTR:</strong> {ctr:.2f}%</td>
                    <td style="padding:4px 0;color:{_MUTED};text-align:right;">{ctr_delta_str} vs prev week</td>
                </tr>
            </table>
            {previews_html}
        </div>
        """)

        domain_blocks_text.append(f"""Domain: {domain_name}
- Impressions: {imp:,} ({imp_delta_str} vs prev week)
- Clicks: {clk:,} ({clk_delta_str} vs prev week)
- CTR: {ctr:.2f}% ({ctr_delta_str} vs prev week)
{previews_text}""".strip())

    body_html = f"""
    <p style="margin:0 0 16px 0;">Here is how your link previews performed over the last 7 days compared to the preceding week:</p>
    {"".join(domain_blocks_html)}
    """

    footer_extra = (
        f'<a href="{unsubscribe_url}" style="color:{_MUTED};text-decoration:underline;">'
        'Unsubscribe from weekly digests</a>'
    )

    html_email = _wrap_email(
        heading="Your Weekly Performance Digest",
        body_html=body_html,
        button={"label": "View analytics", "url": analytics_url},
        footer_extra_html=footer_extra,
    )

    divider = "\n" + "-" * 50 + "\n"
    formatted_domains_text = divider.join(domain_blocks_text)

    text_email = f"""MetaView - Weekly Performance Digest

Here is how your link previews performed over the last 7 days compared to the preceding week:

{formatted_domains_text}

View your full analytics dashboard:
{analytics_url}

To unsubscribe from weekly performance emails:
{unsubscribe_url}
""".strip()

    return subject, html_email, text_email


def send_weekly_digest_email(
    to_email: str,
    domain_summaries: list[dict],
    unsubscribe_url: str,
    analytics_url: str,
) -> bool:
    """Send a weekly performance digest email to an account.

    Sender name is explicitly 'MetaView' as required by C7.
    """
    subject, html_body, text_body = build_weekly_digest_email(
        user_email=to_email,
        domain_summaries=domain_summaries,
        unsubscribe_url=unsubscribe_url,
        analytics_url=analytics_url,
    )
    return send_email(
        to=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        from_name="MetaView",
    )

