"""IMAP4 client (stdlib imaplib) with UID-based operations."""

import imaplib
import re
import ssl
from .common import (
    FolderInfo,
    MessageMeta,
    decode_header_value,
    folder_role,
    internaldate_to_ts,
    meta_from_headers,
)

imaplib._MAXLINE = 10 * 1024 * 1024

_FETCH_CHUNK = 100
_HEADER_FIELDS = (
    "BODY.PEEK[HEADER.FIELDS (FROM TO CC BCC SUBJECT DATE MESSAGE-ID "
    "IN-REPLY-TO REFERENCES CONTENT-TYPE CONTENT-DISPOSITION)]"
)

_UID_RE = re.compile(rb"\bUID\s+(\d+)")
_SIZE_RE = re.compile(rb"\bRFC822\.SIZE\s+(\d+)")
_INTERNALDATE_RE = re.compile(rb'\bINTERNALDATE\s+"([^"]+)"')
_FLAGS_RE = re.compile(rb"\bFLAGS\s+\(([^)]*)\)")


class ImapError(Exception):
    pass


def _quote_folder(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_flags(raw) -> tuple:
    if not raw:
        return ()
    if isinstance(raw, bytes):
        raw = raw.decode("latin-1", errors="replace")
    return tuple(f for f in raw.split() if f)


def parse_fetch_response(items) -> dict:
    """imaplib fetch response -> {uid: MessageMeta} (headers parsed)."""
    result = {}
    if not items:
        return result
    i = 0
    while i < len(items):
        entry = items[i]
        if not isinstance(entry, tuple):
            i += 1
            continue
        meta_part, body = entry[0], entry[1] if len(entry) > 1 else b""
        if isinstance(meta_part, bytes):
            uid_m = _UID_RE.search(meta_part)
            uid = uid_m.group(1).decode() if uid_m else None
            size_m = _SIZE_RE.search(meta_part)
            size = int(size_m.group(1)) if size_m else 0
            date_m = _INTERNALDATE_RE.search(meta_part)
            date_ts = internaldate_to_ts(
                date_m.group(1).decode("latin-1")) if date_m else 0
            flags_m = _FLAGS_RE.search(meta_part)
            flags = _parse_flags(flags_m.group(1)) if flags_m else ()
        else:
            uid, size, date_ts, flags = None, 0, 0, ()
        # FLAGS may trail after the literal body
        if i + 1 < len(items) and isinstance(items[i + 1], (bytes, str)):
            trailing = items[i + 1]
            if isinstance(trailing, bytes):
                tm = _FLAGS_RE.search(trailing)
                if tm and not flags:
                    flags = _parse_flags(tm.group(1))
                i += 1
        if uid is None:
            i += 1
            continue
        headers = body if isinstance(body, bytes) else str(body).encode()
        meta = meta_from_headers(uid, headers, size=size, flags=flags)
        if date_ts:
            meta.date_ts = date_ts
        result[uid] = meta
        i += 1
    return result


def parse_list_response(lines) -> list:
    """imaplib list() lines -> [FolderInfo]."""
    folders = []
    for line in lines or []:
        if isinstance(line, bytes):
            line = line.decode("latin-1", errors="replace")
        m = re.match(r'^\((?P<flags>[^)]*)\)\s+'
                     r'(?P<delim>"[^"]*"|NIL)\s+(?P<rest>.*)$', line)
        if not m:
            continue
        flags = tuple(m.group("flags").split())
        delim = m.group("delim").strip('"')
        if delim.upper() == "NIL":
            delim = "/"
        rest = m.group("rest").strip()
        if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
            path = rest[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        elif rest.startswith("{"):
            continue  # literal path, rare; skip
        else:
            path = rest
        name = path.split(delim)[-1] if delim else path
        if path.upper() == "INBOX":
            name, path = "Inbox", "INBOX"
        folders.append(FolderInfo(path=path, name=name, flags=tuple(flags),
                                  delimiter=delim or "/"))
    return folders


class ImapClient:
    def __init__(self, account, timeout=30):
        self.account = account
        self.timeout = timeout
        self.con = None
        self.selected = None

    # ----------------------------------------------------------- lifecycle
    def connect(self):
        acc = self.account
        try:
            if acc.imap_ssl:
                ctx = ssl.create_default_context()
                self.con = imaplib.IMAP4_SSL(
                    acc.imap_host, acc.imap_port, ssl_context=ctx,
                    timeout=self.timeout)
            else:
                self.con = imaplib.IMAP4(
                    acc.imap_host, acc.imap_port, timeout=self.timeout)
        except Exception as exc:
            raise ImapError(f"Cannot reach {acc.imap_host}:{acc.imap_port} — {exc}") from exc
        try:
            typ, _ = self.con.login(acc.username or acc.email, acc.password)
        except Exception as exc:
            self.close()
            raise ImapError(f"Login failed — {exc}") from exc
        if typ != "OK":
            self.close()
            raise ImapError("Login failed")
        return self

    def close(self):
        try:
            if self.con:
                try:
                    self.con.logout()
                except Exception:
                    pass
        finally:
            self.con = None
            self.selected = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    def _require(self):
        if not self.con:
            raise ImapError("Not connected")

    # -------------------------------------------------------------- folders
    def list_folders(self) -> list:
        self._require()
        typ, data = self.con.list()
        if typ != "OK":
            raise ImapError("Cannot list folders")
        return parse_list_response(data)

    def select(self, folder: str):
        self._require()
        if self.selected == folder:
            return
        typ, data = self.con.select(_quote_folder(folder), readonly=False)
        if typ != "OK":
            # fallback unquoted (some servers dislike quotes on INBOX)
            typ, data = self.con.select(folder, readonly=False)
        if typ != "OK":
            raise ImapError(f"Cannot open folder {folder}")
        self.selected = folder

    def uidvalidity(self):
        self._require()
        # imaplib.response() returns (code, data) where code is the
        # response code itself ("UIDVALIDITY"), not a status.
        _code, data = self.con.response("UIDVALIDITY")
        if data and data[0]:
            try:
                return int(data[0])
            except (TypeError, ValueError):
                return 0
        return 0

    def create_folder(self, path: str):
        self._require()
        typ, _ = self.con.create(_quote_folder(path))
        if typ != "OK":
            raise ImapError(f"Cannot create folder {path}")

    def rename_folder(self, old: str, new: str):
        self._require()
        typ, _ = self.con.rename(_quote_folder(old), _quote_folder(new))
        if typ != "OK":
            raise ImapError(f"Cannot rename {old}")

    def delete_folder(self, path: str):
        self._require()
        typ, _ = self.con.delete(_quote_folder(path))
        if typ != "OK":
            raise ImapError(f"Cannot delete {path}")

    # ------------------------------------------------------------- messages
    def search_all(self) -> list:
        self._require()
        typ, data = self.con.uid("search", None, "ALL")
        if typ != "OK":
            raise ImapError("Search failed")
        raw = data[0] if data else b""
        if isinstance(raw, bytes):
            return [t.decode() for t in raw.split() if t]
        return []

    def fetch_summaries(self, uids=None) -> list:
        """Fetch headers+flags+sizes for uids (default: all)."""
        self._require()
        if uids is None:
            uids = self.search_all()
        metas = []
        for start in range(0, len(uids), _FETCH_CHUNK):
            chunk = uids[start:start + _FETCH_CHUNK]
            spec = f"(UID FLAGS RFC822.SIZE {_HEADER_FIELDS})"
            typ, data = self.con.uid("fetch", ",".join(chunk), spec)
            if typ != "OK":
                continue
            parsed = parse_fetch_response(data or [])
            metas.extend(parsed.values())
        return metas

    def fetch_full(self, uid: str) -> bytes:
        self._require()
        typ, data = self.con.uid("fetch", str(uid), "(BODY.PEEK[])")
        if typ != "OK" or not data:
            raise ImapError(f"Cannot download message {uid}")
        for item in data:
            if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
                return item[1]
        raise ImapError(f"Empty response for message {uid}")

    def set_seen(self, uid: str, seen: bool):
        self._require()
        flag = "\\Seen"
        op = "+FLAGS" if seen else "-FLAGS"
        typ, _ = self.con.uid("store", str(uid), op, f"({flag})")
        if typ != "OK":
            raise ImapError("Cannot update flags")

    def set_flagged(self, uid: str, flagged: bool):
        self._require()
        op = "+FLAGS" if flagged else "-FLAGS"
        typ, _ = self.con.uid("store", str(uid), op, "(\\Flagged)")
        if typ != "OK":
            raise ImapError("Cannot update flag")

    def copy(self, uids, target: str):
        self._require()
        typ, _ = self.con.uid("copy", ",".join(str(u) for u in uids),
                              _quote_folder(target))
        if typ != "OK":
            typ, _ = self.con.uid("copy", ",".join(str(u) for u in uids), target)
        if typ != "OK":
            raise ImapError(f"Cannot copy to {target}")

    def store_deleted(self, uids):
        self._require()
        typ, _ = self.con.uid("store", ",".join(str(u) for u in uids),
                              "+FLAGS", "(\\Deleted)")
        if typ != "OK":
            raise ImapError("Cannot mark deleted")

    def expunge(self):
        self._require()
        self.con.expunge()

    def move(self, uids, target: str):
        r"""COPY + mark \Deleted + EXPUNGE."""
        if not uids:
            return
        self.copy(uids, target)
        self.store_deleted(uids)
        self.expunge()

    def append(self, folder: str, data: bytes, flags="\\Seen"):
        self._require()
        typ, _ = self.con.append(_quote_folder(folder), flags, None, data)
        if typ != "OK":
            typ, _ = self.con.append(folder, flags, None, data)
        if typ != "OK":
            raise ImapError(f"Cannot append to {folder}")

    def noop(self):
        self._require()
        typ, _ = self.con.noop()
        return typ == "OK"
