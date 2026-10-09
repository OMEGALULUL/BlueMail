"""Well-known mail provider connection presets for quick sign-in."""

PROVIDERS = {
    "custom": {
        "label": "Custom / Other",
        "note": "Enter your server settings manually.",
    },
    "gmail": {
        "label": "Gmail",
        "note": "Google requires an App Password. Turn on 2-Step "
               "Verification, then create one at "
               "myaccount.google.com/apppasswords.",
        "imap_host": "imap.gmail.com", "imap_port": 993, "imap_ssl": True,
        "pop_host": "pop.gmail.com", "pop_port": 995, "pop_ssl": True,
        "smtp_host": "smtp.gmail.com", "smtp_port": 465,
        "smtp_security": "ssl",
    },
    "outlook": {
        "label": "Outlook / Hotmail",
        "note": "Works with outlook.com, hotmail.com, live.com and msn.com "
               "addresses.",
        "imap_host": "outlook.office365.com", "imap_port": 993,
        "imap_ssl": True,
        "pop_host": "outlook.office365.com", "pop_port": 995,
        "pop_ssl": True,
        "smtp_host": "smtp.office365.com", "smtp_port": 587,
        "smtp_security": "starttls",
    },
    "yahoo": {
        "label": "Yahoo Mail",
        "note": "Yahoo requires an App Password — generate one at "
               "myaccount.yahoo.com/security.",
        "imap_host": "imap.mail.yahoo.com", "imap_port": 993,
        "imap_ssl": True,
        "pop_host": "pop.mail.yahoo.com", "pop_port": 995, "pop_ssl": True,
        "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 465,
        "smtp_security": "ssl",
    },
    "icloud": {
        "label": "iCloud Mail",
        "note": "Create an App-Specific Password at account.apple.com. "
               "iCloud has no POP3 access.",
        "imap_host": "imap.mail.me.com", "imap_port": 993, "imap_ssl": True,
        "pop_host": "", "pop_port": 995, "pop_ssl": True,
        "smtp_host": "smtp.mail.me.com", "smtp_port": 465,
        "smtp_security": "ssl",
    },
    "aol": {
        "label": "AOL",
        "note": "AOL recommends an app password; standard SSL ports shown.",
        "imap_host": "imap.aol.com", "imap_port": 993, "imap_ssl": True,
        "pop_host": "pop.aol.com", "pop_port": 995, "pop_ssl": True,
        "smtp_host": "smtp.aol.com", "smtp_port": 465, "smtp_security": "ssl",
    },
}

#: domain suffix -> provider id (lowercased, no leading "@")
DOMAINS = {
    "gmail.com": "gmail", "googlemail.com": "gmail",
    "outlook.com": "outlook", "hotmail.com": "outlook",
    "live.com": "outlook", "msn.com": "outlook",
    "yahoo.com": "yahoo", "ymail.com": "yahoo", "rocketmail.com": "yahoo",
    "icloud.com": "icloud", "me.com": "icloud", "mac.com": "icloud",
    "aol.com": "aol",
}

#: order shown on the welcome quick-sign-in row and in the dialog combo
WELCOME_ROWS = [
    ("gmail", "Gmail"),
    ("outlook", "Outlook / Hotmail"),
    ("yahoo", "Yahoo"),
    ("icloud", "iCloud"),
    ("custom", "Other"),
]


def detect_provider(email):
    """Return the provider id a given email address belongs to."""
    if not email:
        return "custom"
    domain = email.split("@")[-1].strip().lower()
    return DOMAINS.get(domain, "custom")


def apply_provider(account, provider_id, protocol=None):
    """Fill an Account's server fields from a provider preset.

    Only connection settings are touched; identity fields (name, email,
    username, password) are left alone.
    """
    preset = PROVIDERS.get(provider_id or "custom", PROVIDERS["custom"])
    proto = (protocol or account.protocol or "imap").lower()
    if proto in ("imap", "pop3"):
        account.protocol = proto
    account.imap_host = preset.get("imap_host", "")
    account.imap_port = int(preset.get("imap_port", 993))
    account.imap_ssl = preset.get("imap_ssl", True)
    account.pop_host = preset.get("pop_host", "")
    account.pop_port = int(preset.get("pop_port", 995))
    account.pop_ssl = preset.get("pop_ssl", True)
    account.smtp_host = preset.get("smtp_host", "")
    account.smtp_port = int(preset.get("smtp_port", 587))
    account.smtp_security = preset.get("smtp_security", "starttls")