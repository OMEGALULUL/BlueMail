"""POP3 client (stdlib poplib) with UIDL tracking."""

import poplib
import ssl

from .common import MessageMeta, first_address, meta_from_headers, parse_date_header


class PopError(Exception):
    pass


def _ok(typ) -> bool:
    """poplib returns the full status line (as bytes); compare prefix."""
    if isinstance(typ, (bytes, bytearray)):
        return bytes(typ[:3]) == b"+OK"
    return str(typ)[:3] == "+OK"


class PopClient:
    def __init__(self, account, timeout=30):
        self.account = account
        self.timeout = timeout
        self.con = None
        self._num_by_uidl = {}

    def connect(self):
        acc = self.account
        try:
            if acc.pop_ssl:
                ctx = ssl.create_default_context()
                self.con = poplib.POP3_SSL(
                    acc.pop_host, acc.pop_port, timeout=self.timeout,
                    context=ctx)
            else:
                self.con = poplib.POP3(
                    acc.pop_host, acc.pop_port, timeout=self.timeout)
            self.con.user(acc.username or acc.email)
            self.con.pass_(acc.password)
        except Exception as exc:
            self.close()
            raise PopError(
                f"Cannot connect/login to {acc.pop_host}:{acc.pop_port} — {exc}"
            ) from exc
        return self

    def close(self):
        try:
            if self.con:
                try:
                    self.con.quit()
                except Exception:
                    pass
        finally:
            self.con = None
            self._num_by_uidl = {}

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    def _require(self):
        if not self.con:
            raise PopError("Not connected")

    def uidl_list(self) -> list:
        """[(num, uidl), ...] in server order."""
        self._require()
        typ, items, _ = self.con.uidl()
        if not _ok(typ):
            raise PopError("UIDL not supported")
        out = []
        for line in items:
            if isinstance(line, bytes):
                line = line.decode("latin-1", errors="replace")
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit():
                out.append((int(parts[0]), parts[1]))
        self._num_by_uidl = {uidl: num for num, uidl in out}
        return out

    def fetch_headers(self, num: int) -> bytes:
        self._require()
        try:
            typ, lines, _ = self.con.top(num, 0)
        except Exception:
            typ, lines = "+OK", []
        if not _ok(typ) or not lines:
            typ, lines, _ = self.con.retr(num)
            if not _ok(typ):
                raise PopError(f"Cannot fetch message {num}")
            # retr returns full body; cut at blank line
            raw = b"\r\n".join(lines)
            head, _, _ = raw.partition(b"\r\n\r\n")
            return head + b"\r\n\r\n"
        return b"\r\n".join(lines) + b"\r\n\r\n"

    def fetch_full(self, num: int) -> bytes:
        self._require()
        typ, lines, _ = self.con.retr(num)
        if not _ok(typ):
            raise PopError(f"Cannot download message {num}")
        return b"\r\n".join(lines)

    def delete(self, num: int):
        self._require()
        typ = self.con.dele(num)
        if not _ok(typ):
            raise PopError(f"Cannot delete message {num}")

    def delete_uidl(self, uidl: str):
        num = self._num_by_uidl.get(uidl)
        if num is None:
            raise PopError(f"Unknown message {uidl}")
        self.delete(num)

    def list_sizes(self) -> dict:
        self._require()
        typ, lines, _ = self.con.list()
        sizes = {}
        if _ok(typ):
            for i, line in enumerate(lines, start=1):
                if isinstance(line, bytes):
                    line = line.decode("latin-1", errors="replace")
                try:
                    sizes[i] = int(line.split()[-1])
                except (ValueError, IndexError):
                    continue
        return sizes

    def fetch_summaries(self, existing=()):
        """Return (new MessageMetas, all uidls currently on server)."""
        entries = self.uidl_list()
        sizes = self.list_sizes()
        existing = set(existing)
        new = []
        for num, uidl in entries:
            if uidl in existing:
                continue
            headers = self.fetch_headers(num)
            new.append(meta_from_headers(uidl, headers,
                                         size=sizes.get(num, 0)))
        return new, [uidl for _num, uidl in entries]

    def fetch_all_summaries(self) -> list:
        """TOP-based summaries keyed by UIDL; falls back to RETR."""
        metas = []
        for num, uidl in self.uidl_list():
            headers = self.fetch_headers(num)
            size = 0
            try:
                typ, lines, octets = self.con.list()
                if _ok(typ) and 1 <= num <= len(lines):
                    size = int(lines[num - 1].split()[-1])
            except Exception:
                pass
            meta = meta_from_headers(uidl, headers, size=size)
            metas.append(meta)
        return metas
