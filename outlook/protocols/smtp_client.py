"""SMTP sending (stdlib smtplib)."""

import smtplib
import ssl
from email.message import Message


class SmtpError(Exception):
    pass


def send_message(account, message: Message):
    host = account.smtp_host
    port = account.smtp_port
    security = account.smtp_security
    if not host:
        raise SmtpError("No SMTP server configured")
    try:
        if security == "ssl":
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, port, timeout=30, context=ctx)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        if security == "starttls":
            ctx = ssl.create_default_context()
            server.starttls(context=ctx)
            server.ehlo()
        if account.username:
            server.login(account.username, account.password)
        server.send_message(message)
        server.quit()
    except SmtpError:
        raise
    except Exception as exc:
        raise SmtpError(f"Send failed via {host}:{port} — {exc}") from exc
