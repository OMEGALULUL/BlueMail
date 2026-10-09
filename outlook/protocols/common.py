"""Shared helpers for parsing mail data."""

import calendar
import email.utils
import re
import time
from dataclasses import dataclass, field
from email.header import decode_header
from email.utils import parseaddr, getaddresses

INTERNALDATE_RE = re.compile(
    r'^(?P<day>\d{1,2})-(?P<mon>[A-Za-z]{3})-(?P<year>\d{4}) '
    r'(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}) (?P<tz>[+-]\d{4})$'
)
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

ATTACH_CTYPES = (
    "application/pdf", "application/zip", "application/msword",
    "application/vnd.openxmlformats", "application/vnd.ms-excel",
    "application/octet-stream", "image/", "video/", "audio/",
    "application/rtf", "application/x-zip",
)


@dataclass
class MessageMeta:
    uid: str = ""
    msgid: str = ""
    from_name: str = ""
    from_addr: str = ""
    to_addr: str = ""
    cc_addr: str = ""
    subject: str = ""
    date_ts: int = 0
    size: int = 0
    is_read: bool = False
    is_flagged: bool = False
    has_attachment: bool = False
    importance: str = ""

    @property
    def from_display(self):
        if self.from_name and self.from_addr:
            if self.from_name == self.from_addr:
                return self.from_addr
            return self.from_name
        return self.from_addr or self.from_name or ""


@dataclass
class FolderInfo:
    path: str
    name: str
    flags: tuple = ()
    delimiter: str = "/"


def decode_header_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="replace")
        except Exception:
            value = str(value)
    try:
        parts = decode_header(value)
    except Exception:
        return str(value)
    out = []
    for data, charset in parts:
        if isinstance(data, bytes):
            for cs in (charset, "utf-8", "latin-1"):
                if not cs:
                    continue
                try:
                    out.append(data.decode(cs, errors="replace"))
                    break
                except (LookupError, UnicodeDecodeError):
                    continue
            else:
                out.append(data.decode("utf-8", errors="replace"))
        else:
            out.append(data)
    text = "".join(out)
    text = re.sub(r"\r?\n", "", text)
    return text.strip()


def parse_address_field(value) -> str:
    """Normalize an address header to 'Name <addr>, ...' display form."""
    if not value:
        return ""
    if isinstance(value, bytes):
        value = decode_header_value(value)
    decoded = decode_header_value(value)
    addrs = getaddresses([decoded])
    out = []
    for name, addr in addrs:
        name = decode_header_value(name).strip()
        addr = addr.strip()
        if not addr and not name:
            continue
        if name and addr:
            out.append(f"{name} <{addr}>")
        else:
            out.append(addr or name)
    return ", ".join(out)


def first_address(value) -> str:
    """First bare email address in a header."""
    if not value:
        return ""
    if isinstance(value, bytes):
        value = decode_header_value(value)
    addrs = getaddresses([decode_header_value(value)])
    for _name, addr in addrs:
        if addr:
            return addr.strip()
    return ""


def internaldate_to_ts(text: str) -> int:
    m = INTERNALDATE_RE.match(text.strip()) if text else None
    if not m:
        return 0
    try:
        mon = _MONTHS[m.group("mon").capitalize()]
        tz = m.group("tz")
        sign = 1 if tz[0] == "+" else -1
        off = sign * (int(tz[1:3]) * 3600 + int(tz[3:5]) * 60)
        naive = (int(m.group("year")), mon, int(m.group("day")),
                 int(m.group("h")), int(m.group("m")), int(m.group("s")))
        return int(calendar.timegm(naive + (0, 0, -1)) - off)
    except (ValueError, OverflowError):
        return 0


def parse_date_header(value) -> int:
    if not value:
        return 0
    if isinstance(value, bytes):
        value = decode_header_value(value)
    try:
        dt = email.utils.parsedate_to_datetime(decode_header_value(value))
        if dt is None:
            return 0
        return int(dt.timestamp())
    except Exception:
        return 0


def format_size(n) -> str:
    n = int(n or 0)
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 ** 3):.1f} GB"


def part_has_attachment(part) -> bool:
    try:
        filename = part.get_filename()
    except Exception:
        filename = None
    if filename:
        return True
    if part.get_content_disposition() == "attachment":
        return True
    return False


def message_has_attachment(msg) -> bool:
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part_has_attachment(part):
                    return True
            return (msg.get_content_subtype() or "").lower() == "mixed"
        ctype = (msg.get_content_type() or "").lower()
        return any(ctype.startswith(p) for p in ATTACH_CTYPES)
    except Exception:
        return False


def parse_importance(msg) -> str:
    try:
        xp = decode_header_value(msg.get("X-Priority", ""))
        imp = decode_header_value(msg.get("Importance", "")).lower()
        pri = decode_header_value(msg.get("Priority", "")).lower()
    except Exception:
        return ""
    if "high" in imp or "urgent" in pri:
        return "high"
    if "low" in imp or "non-urgent" in pri:
        return "low"
    digits = re.match(r"\s*(\d)", xp)
    if digits:
        n = digits.group(1)
        if n in "12":
            return "high"
        if n in "45":
            return "low"
    return ""


def meta_from_headers(uid, headers: bytes, size: int = 0, flags=()) -> MessageMeta:
    """Build a MessageMeta from a raw RFC822 header block."""
    import email
    from email import message_from_bytes

    try:
        msg = message_from_bytes(headers or b"")
    except Exception:
        msg = email.message.Message()

    flag_set = {f.decode() if isinstance(f, bytes) else f for f in flags}
    from_raw = msg.get("From", "")
    to_raw = msg.get("To", "")
    cc_raw = msg.get("Cc", "")
    meta = MessageMeta(
        uid=str(uid),
        msgid=decode_header_value(msg.get("Message-ID", "")),
        from_name=decode_header_value(parseaddr(decode_header_value(from_raw))[0]),
        from_addr=first_address(from_raw),
        to_addr=parse_address_field(to_raw),
        cc_addr=parse_address_field(cc_raw),
        subject=decode_header_value(msg.get("Subject", "")),
        date_ts=parse_date_header(msg.get("Date", "")),
        size=size,
        is_read="\\Seen" in flag_set,
        is_flagged="\\Flagged" in flag_set,
        has_attachment=message_has_attachment(msg),
        importance=parse_importance(msg),
    )
    return meta


def folder_role(path: str, name: str) -> str:
    p = (path or name or "").lower()
    base = p.split("/")[-1].strip('"')
    if base == "inbox":
        return "inbox"
    if "junk" in base or "spam" in base or "bulk" in base:
        return "junk"
    if "trash" in base or "deleted" in base or base == "bin":
        return "trash"
    if "draft" in base:
        return "drafts"
    if "sent" in base or base == "outbox" or "send" in base:
        return "sent"
    if "archive" in base:
        return "archive"
    return "custom"


ROLE_ORDER = ["inbox", "drafts", "sent", "junk", "trash", "archive", "custom"]
ROLE_LABELS = {
    "inbox": "Inbox",
    "drafts": "Drafts",
    "sent": "Sent Items",
    "junk": "Junk Email",
    "trash": "Deleted Items",
    "archive": "Archive",
    "custom": "Folder",
}
