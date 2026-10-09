"""Minimal in-process IMAP4 / POP3 / SMTP servers for end-to-end tests.

Each server binds an ephemeral port on 127.0.0.1, speaks just enough of the
protocol for the stdlib clients (imaplib / poplib / smtplib) used by
outlook.protocols, and records what the client did for assertions.
"""

import base64
import socket
import threading

CRLF = b"\r\n"


class _LineFile:
    """Buffered reader/writer over a socket with line + literal helpers."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def readline(self):
        while b"\r\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                line, self.buf = self.buf, b""
                return line
            self.buf += chunk
        line, self.buf = self.buf.split(b"\r\n", 1)
        return line + b"\r\n"

    def read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, data):
        self.sock.sendall(data)


class _Server:
    def __init__(self, handle_client):
        self._handle = handle_client
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._running = True
        self._clients = []
        self._accept = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept.start()

    @property
    def addr(self):
        return ("127.0.0.1", self.port)

    def _accept_loop(self):
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            self._clients.append(conn)
            threading.Thread(target=self._serve, args=(conn,),
                             daemon=True).start()

    def _serve(self, conn):
        try:
            self._handle(_LineFile(conn))
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass
        for conn in self._clients:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == ord('"') and s[-1] == ord('"'):
        return s[1:-1].decode("utf-8", "replace").replace('\\"', '"')
    return s.decode("utf-8", "replace")


# --------------------------------------------------------------------- IMAP
class FakeIMAP(_Server):
    """Plaintext IMAP4 server with in-memory mailboxes.

    mailboxes: {path: [ {"uid": int, "flags": set, "raw": bytes}, ... ]}
    """

    def __init__(self, mailboxes, username="alice", password="s3cret"):
        self.mailboxes = {p: [dict(m, flags=set(m.get("flags", ())))
                              for m in msgs]
                          for p, msgs in mailboxes.items()}
        self.username = username
        self.password = password
        self.next_uid = {p: max((m["uid"] for m in msgs), default=0) + 1
                         for p, msgs in self.mailboxes.items()}
        self.uidvalidity = {p: 1000 + i
                            for i, p in enumerate(self.mailboxes)}
        self.commands = []          # every tagged command received
        self.authenticated = None
        super().__init__(self._client)

    # ------------------------------------------------------------- plumbing
    def _find(self, path):
        if path.upper() == "INBOX" and "INBOX" in self.mailboxes:
            return "INBOX"
        for p in self.mailboxes:
            if p.lower() == path.lower():
                return p
        return None

    def _client(self, rf):
        rf.send(b"* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] FakeIMAP ready"
                + CRLF)
        selected = None
        while True:
            line = rf.readline()
            if not line:
                return
            line = line.rstrip(b"\r\n")
            if not line:
                continue
            try:
                tag, rest = line.split(b" ", 1)
            except ValueError:
                rf.send(b"* BAD Malformed command" + CRLF)
                continue
            parts = rest.split(b" ", 1)
            cmd = parts[0].upper()
            args = parts[1] if len(parts) > 1 else b""
            if cmd == b"UID":
                sub, _, subargs = args.partition(b" ")
                handler = getattr(self, "_cmd_uid_" +
                                  sub.decode().lower(), None)
                args = subargs
            else:
                handler = getattr(self, "_cmd_" + cmd.decode().lower(), None)
            if handler is None:
                rf.send(tag + b" BAD Unknown command" + CRLF)
                continue
            self.commands.append(
                (tag.decode(), (cmd.decode() + " " +
                 args[:80].decode("latin-1", "replace")).strip()))
            res = handler(rf, tag, args, selected)
            if res is not None:
                selected = res
            if cmd == b"LOGOUT":
                return

    # ------------------------------------------------------------ commands
    def _cmd_capability(self, rf, tag, args, selected):
        rf.send(b"* CAPABILITY IMAP4rev1 AUTH=PLAIN" + CRLF)
        rf.send(tag + b" OK CAPABILITY completed" + CRLF)

    def _cmd_noop(self, rf, tag, args, selected):
        rf.send(tag + b" OK NOOP completed" + CRLF)

    def _cmd_logout(self, rf, tag, args, selected):
        rf.send(b"* BYE FakeIMAP signing off" + CRLF)
        rf.send(tag + b" OK LOGOUT completed" + CRLF)
        return "logout"

    def _cmd_login(self, rf, tag, args, selected):
        user, _, pw = args.partition(b" ")
        if (_unquote(user) == self.username and
                _unquote(pw) == self.password):
            self.authenticated = _unquote(user)
            rf.send(tag + b" OK [CAPABILITY IMAP4rev1] LOGIN completed"
                    + CRLF)
        else:
            rf.send(tag + b" NO LOGIN failed" + CRLF)

    def _cmd_list(self, rf, tag, args, selected):
        ref, _, mbox = args.partition(b" ")
        pattern = _unquote(mbox)
        for path in self.mailboxes:
            if pattern in ("", "*") or pattern.lower() == path.lower():
                rf.send(b'* LIST (\\HasNoChildren) "/" "%s"' % path.encode()
                        + CRLF)
        rf.send(tag + b" OK LIST completed" + CRLF)

    def _cmd_select(self, rf, tag, args, selected):
        path = self._find(_unquote(args))
        if path is None:
            rf.send(tag + b" NO No such mailbox" + CRLF)
            return selected
        msgs = self.mailboxes[path]
        rf.send(b"* FLAGS (\\Seen \\Answered \\Flagged \\Deleted \\Draft)"
                + CRLF)
        rf.send(b"* %d EXISTS" % len(msgs) + CRLF)
        rf.send(b"* 0 RECENT" + CRLF)
        rf.send(b"* OK [UIDVALIDITY %d] UIDs valid"
                % self.uidvalidity[path] + CRLF)
        rf.send(b"* OK [UIDNEXT %d] Next UID" % self.next_uid[path] + CRLF)
        rf.send(tag + b" OK [READ-WRITE] SELECT completed" + CRLF)
        return path

    def _cmd_status(self, rf, tag, args, selected):
        path = self._find(_unquote(args.split(b" ")[0]))
        if path is None:
            rf.send(tag + b" NO No such mailbox" + CRLF)
            return selected
        n = len(self.mailboxes[path])
        rf.send(b'* STATUS "%s" (MESSAGES %d UIDVALIDITY %d)'
                % (path.encode(), n, self.uidvalidity[path]) + CRLF)
        rf.send(tag + b" OK STATUS completed" + CRLF)

    def _cmd_create(self, rf, tag, args, selected):
        path = _unquote(args)
        if path in self.mailboxes:
            rf.send(tag + b" NO Already exists" + CRLF)
            return selected
        self.mailboxes[path] = []
        self.next_uid[path] = 1
        self.uidvalidity[path] = 1000 + len(self.uidvalidity)
        rf.send(tag + b" OK CREATE completed" + CRLF)

    def _cmd_rename(self, rf, tag, args, selected):
        parts = args.split(b" ", 1)
        if len(parts) != 2:
            rf.send(tag + b" BAD RENAME needs 2 args" + CRLF)
            return selected
        old = self._find(_unquote(parts[0]))
        new = _unquote(parts[1])
        if old is None:
            rf.send(tag + b" NO No such mailbox" + CRLF)
            return selected
        self.mailboxes[new] = self.mailboxes.pop(old)
        self.next_uid[new] = self.next_uid.pop(old, 1)
        rf.send(tag + b" OK RENAME completed" + CRLF)

    def _cmd_delete(self, rf, tag, args, selected):
        path = self._find(_unquote(args))
        if path is None:
            rf.send(tag + b" NO No such mailbox" + CRLF)
            return selected
        if self.mailboxes[path]:
            rf.send(tag + b" NO Mailbox not empty" + CRLF)
            return selected
        del self.mailboxes[path]
        rf.send(tag + b" OK DELETE completed" + CRLF)

    def _cmd_close(self, rf, tag, args, selected):
        if selected:
            self.mailboxes[selected] = [
                m for m in self.mailboxes[selected]
                if "\\Deleted" not in m["flags"]]
        rf.send(tag + b" OK CLOSE completed" + CRLF)
        return ""                      # deselect

    def _cmd_expunge(self, rf, tag, args, selected):
        if selected:
            kept = []
            for i, m in enumerate(self.mailboxes[selected], start=1):
                if "\\Deleted" in m["flags"]:
                    rf.send(b"* %d EXPUNGE" % i + CRLF)
                else:
                    kept.append(m)
            self.mailboxes[selected] = kept
        rf.send(tag + b" OK EXPUNGE completed" + CRLF)

    def _cmd_append(self, rf, tag, args, selected):
        m = re_search_brace(args)
        if m is None:
            rf.send(tag + b" BAD APPEND literal required" + CRLF)
            return selected
        size = int(m.group(1))
        rf.send(b"+ Ready for literal data" + CRLF)
        literal = rf.read(size)
        rf.readline()                      # trailing CRLF after literal
        header = args[:m.start()].split(b" ")
        path = self._find(_unquote(header[0])) or _unquote(header[0])
        if path not in self.mailboxes:
            rf.send(tag + b" NO No such mailbox" + CRLF)
            return selected
        flags = set()
        if len(header) > 1 and header[1].startswith(b"("):
            flags = set(header[1].strip(b"()").decode().split())
        self.mailboxes[path].append({
            "uid": self.next_uid.get(path, 1),
            "flags": flags,
            "raw": literal,
        })
        self.next_uid[path] = self.next_uid.get(path, 1) + 1
        rf.send(tag + b" OK APPEND completed" + CRLF)

    # -------------------------------------------------------- UID commands
    def _cmd_uid_search(self, rf, tag, args, selected):
        if selected is None:
            rf.send(tag + b" NO No mailbox selected" + CRLF)
            return selected
        uids = " ".join(str(m["uid"]) for m in self.mailboxes[selected])
        rf.send(b"* SEARCH " + uids.encode() + CRLF)
        rf.send(tag + b" OK SEARCH completed" + CRLF)

    def _cmd_uid_fetch(self, rf, tag, args, selected):
        if selected is None:
            rf.send(tag + b" NO No mailbox selected" + CRLF)
            return selected
        spec_start = args.find(b"(")
        if spec_start < 0:
            rf.send(tag + b" BAD FETCH spec required" + CRLF)
            return selected
        uidlist = args[:spec_start].strip()
        spec = args[spec_start:]
        wanted = [u for u in uidlist.decode().split(",") if u]
        if wanted == ["*"]:
            wanted = [str(m["uid"]) for m in self.mailboxes[selected]]
        by_uid = {str(m["uid"]): m for m in self.mailboxes[selected]}
        upper = spec.upper()
        for uid in wanted:
            msg = by_uid.get(uid)
            if msg is None:
                continue
            seq = self.mailboxes[selected].index(msg) + 1
            meta = [b"UID %s" % uid.encode()]
            if b"FLAGS" in upper:
                meta.append(b"FLAGS (%s)" %
                            " ".join(sorted(msg["flags"])).encode())
            if b"RFC822.SIZE" in upper:
                meta.append(b"RFC822.SIZE %d" % len(msg["raw"]))
            literal = None
            if b"HEADER.FIELDS" in upper:
                literal = msg["raw"].split(b"\r\n\r\n", 1)[0]
                label = b"BODY[HEADER.FIELDS" + spec.upper().split(
                    b"HEADER.FIELDS", 1)[1].split(b"]", 1)[0] + b"]"
                meta.append(label)
            elif b"BODY.PEEK[]" in upper or b"BODY[]" in upper:
                literal = msg["raw"]
                meta.append(b"BODY[]")
            if literal is None:
                rf.send(b"* %d FETCH (%s)" % (seq, b" ".join(meta)) + CRLF)
                continue
            head = b"* %d FETCH (%s {%d}\r\n" % (seq, b" ".join(meta),
                                                 len(literal))
            rf.send(head + literal + b")\r\n")
        rf.send(tag + b" OK FETCH completed" + CRLF)

    def _cmd_uid_store(self, rf, tag, args, selected):
        if selected is None:
            rf.send(tag + b" NO No mailbox selected" + CRLF)
            return selected
        parts = args.split(b" ", 2)
        if len(parts) < 3:
            rf.send(tag + b" BAD STORE args" + CRLF)
            return selected
        uidlist, op, flagstr = parts
        flags = set(flagstr.strip(b"()").decode().split())
        by_uid = {str(m["uid"]): m for m in self.mailboxes[selected]}
        for uid in uidlist.decode().split(","):
            msg = by_uid.get(uid)
            if msg is None:
                continue
            if op in (b"+FLAGS", b"FLAGS"):
                msg["flags"] |= flags
            elif op == b"-FLAGS":
                msg["flags"] -= flags
        rf.send(tag + b" OK STORE completed" + CRLF)

    def _cmd_uid_copy(self, rf, tag, args, selected):
        if selected is None:
            rf.send(tag + b" NO No mailbox selected" + CRLF)
            return selected
        uidlist, _, target = args.rpartition(b" ")
        target = self._find(_unquote(target))
        if target is None:
            rf.send(tag + b" NO No such mailbox" + CRLF)
            return selected
        by_uid = {str(m["uid"]): m for m in self.mailboxes[selected]}
        for uid in uidlist.decode().split(","):
            src = by_uid.get(uid)
            if src is None:
                continue
            self.mailboxes[target].append({
                "uid": self.next_uid.get(target, 1),
                "flags": set(src["flags"]),
                "raw": src["raw"],
            })
            self.next_uid[target] = self.next_uid.get(target, 1) + 1
        rf.send(tag + b" OK COPY completed" + CRLF)


def re_search_brace(args):
    """Return match of trailing {N} in an APPEND command (or None)."""
    import re
    return re.search(rb"\{(\d+)\}$", args)


# --------------------------------------------------------------------- POP3
class FakePOP3(_Server):
    def __init__(self, messages, username="alice", password="s3cret"):
        self.messages = [dict(m) for m in messages]   # {"raw": bytes, "uidl": str}
        self.deleted = [False] * len(self.messages)
        self.username = username
        self.password = password
        self.authenticated = None
        self.commands = []
        super().__init__(self._client)

    @staticmethod
    def _dot_stuff(data):
        out = []
        for line in data.split(b"\r\n"):
            out.append(b"." + line if line.startswith(b".") else line)
        return b"\r\n".join(out)

    def _client(self, rf):
        rf.send(b"+OK FakePOP3 ready" + CRLF)
        user = None
        while True:
            line = rf.readline()
            if not line:
                return
            line = line.rstrip(b"\r\n")
            if not line:
                continue
            parts = line.split(b" ")
            cmd = parts[0].upper()
            self.commands.append(line.decode("latin-1", "replace"))
            if cmd == b"QUIT":
                rf.send(b"+OK Bye" + CRLF)
                return
            elif cmd == b"USER":
                user = line.split(b" ", 1)[1].decode()
                rf.send(b"+OK User ok" + CRLF)
            elif cmd == b"PASS":
                pw = line.split(b" ", 1)[1].decode()
                if user == self.username and pw == self.password:
                    self.authenticated = user
                    rf.send(b"+OK Logged in" + CRLF)
                else:
                    rf.send(b"-ERR Wrong password" + CRLF)
            elif cmd == b"STAT":
                live = [(i, m) for i, (m, d) in
                        enumerate(zip(self.messages, self.deleted)) if not d]
                size = sum(len(m["raw"]) for _i, m in live)
                rf.send(b"+OK %d %d" % (len(live), size) + CRLF)
            elif cmd == b"LIST":
                if len(parts) > 1:
                    idx = int(parts[1]) - 1
                    if 0 <= idx < len(self.messages) and not self.deleted[idx]:
                        rf.send(b"+OK %d %d" %
                                (idx + 1, len(self.messages[idx]["raw"]))
                                + CRLF)
                    else:
                        rf.send(b"-ERR No such message" + CRLF)
                else:
                    rf.send(b"+OK Listing" + CRLF)
                    for i, (m, d) in enumerate(
                            zip(self.messages, self.deleted)):
                        if not d:
                            rf.send(b"%d %d" % (i + 1, len(m["raw"]))
                                    + CRLF)
                    rf.send(b"." + CRLF)
            elif cmd == b"UIDL":
                if len(parts) > 1:
                    idx = int(parts[1]) - 1
                    if 0 <= idx < len(self.messages) and not self.deleted[idx]:
                        rf.send(b"+OK %d %s" %
                                (idx + 1,
                                 self.messages[idx]["uidl"].encode())
                                + CRLF)
                    else:
                        rf.send(b"-ERR No such message" + CRLF)
                else:
                    rf.send(b"+OK Uidl" + CRLF)
                    for i, (m, d) in enumerate(
                            zip(self.messages, self.deleted)):
                        if not d:
                            rf.send(b"%d %s" % (i + 1, m["uidl"].encode())
                                    + CRLF)
                    rf.send(b"." + CRLF)
            elif cmd in (b"RETR", b"TOP"):
                idx = int(parts[1]) - 1
                if not (0 <= idx < len(self.messages)) or self.deleted[idx]:
                    rf.send(b"-ERR No such message" + CRLF)
                    continue
                raw = self.messages[idx]["raw"]
                if cmd == b"TOP":
                    howmany = int(parts[2]) if len(parts) > 2 else 0
                    head, _, body = raw.partition(b"\r\n\r\n")
                    body_lines = body.split(b"\r\n")[:howmany]
                    payload = head + b"\r\n\r\n" + b"\r\n".join(body_lines)
                else:
                    payload = raw
                rf.send(b"+OK %d octets" % len(payload) + CRLF)
                rf.send(self._dot_stuff(payload) + CRLF + b"." + CRLF)
            elif cmd == b"DELE":
                idx = int(parts[1]) - 1
                if 0 <= idx < len(self.messages) and not self.deleted[idx]:
                    self.deleted[idx] = True
                    rf.send(b"+OK Deleted" + CRLF)
                else:
                    rf.send(b"-ERR No such message" + CRLF)
            elif cmd == b"NOOP":
                rf.send(b"+OK Ok" + CRLF)
            elif cmd == b"RSET":
                self.deleted = [False] * len(self.messages)
                rf.send(b"+OK Reset" + CRLF)
            else:
                rf.send(b"-ERR Unknown command" + CRLF)


# --------------------------------------------------------------------- SMTP
class FakeSMTP(_Server):
    def __init__(self, username="alice", password="s3cret"):
        self.username = username
        self.password = password
        self.messages = []          # raw DATA payloads (dot-unstuffed)
        self.envelopes = []         # (mail_from, [rcpt_to])
        self.authenticated = None
        self.commands = []
        super().__init__(self._client)

    def _client(self, rf):
        rf.send(b"220 fake ESMTP ready" + CRLF)
        mail_from = None
        rcpts = []
        while True:
            line = rf.readline()
            if not line:
                return
            line = line.rstrip(b"\r\n")
            if not line:
                continue
            verb, _, args = line.partition(b" ")
            verb = verb.upper()
            self.commands.append(line.decode("latin-1", "replace"))
            if verb == b"EHLO":
                rf.send(b"250-fake ESMTP" + CRLF)
                rf.send(b"250-8BITMIME" + CRLF)
                rf.send(b"250-AUTH PLAIN LOGIN" + CRLF)
                rf.send(b"250 SIZE 35882577" + CRLF)
            elif verb == b"HELO":
                rf.send(b"250 fake" + CRLF)
            elif verb == b"AUTH":
                mech = args.split(b" ", 1)
                if mech[0].upper() == b"PLAIN" and len(mech) == 2:
                    parts = base64.b64decode(mech[1]).split(b"\0")
                    u = parts[1] if len(parts) >= 3 else b""
                    pw = parts[2] if len(parts) >= 3 else b""
                    if (u.decode() == self.username and
                            pw.decode() == self.password):
                        self.authenticated = u.decode()
                        rf.send(b"235 2.7.0 Authentication successful" + CRLF)
                    else:
                        rf.send(b"535 5.7.8 Authentication failed" + CRLF)
                else:
                    rf.send(b"334 VXNlcm5hbWU6" + CRLF)   # "Username:"
                    u = base64.b64decode(
                        rf.readline().rstrip(b"\r\n") or b"")
                    rf.send(b"334 UGFzc3dvcmQ6" + CRLF)
                    pw = base64.b64decode(
                        rf.readline().rstrip(b"\r\n") or b"")
                    if (u.decode() == self.username and
                            pw.decode() == self.password):
                        self.authenticated = self.username
                        rf.send(b"235 2.7.0 Authentication successful"
                                + CRLF)
                    else:
                        rf.send(b"535 5.7.8 Authentication failed" + CRLF)
            elif verb == b"MAIL":
                mail_from = args.decode("latin-1", "replace")
                rcpts = []
                rf.send(b"250 2.1.0 Ok" + CRLF)
            elif verb == b"RCPT":
                rcpts.append(args.decode("latin-1", "replace"))
                rf.send(b"250 2.1.5 Ok" + CRLF)
            elif verb == b"DATA":
                rf.send(b"354 End data with <CR><LF>.<CR><LF>" + CRLF)
                payload = []
                while True:
                    l = rf.readline()
                    if not l:
                        break
                    l = l.rstrip(b"\r\n")
                    if l == b".":
                        break
                    payload.append(b"." + l[1:] if l.startswith(b"..")
                                   else l)
                self.messages.append(CRLF.join(payload))
                self.envelopes.append((mail_from, list(rcpts)))
                rf.send(b"250 2.0.0 Ok: queued" + CRLF)
            elif verb == b"RSET":
                mail_from, rcpts = None, []
                rf.send(b"250 2.0.0 Ok" + CRLF)
            elif verb == b"NOOP":
                rf.send(b"250 2.0.0 Ok" + CRLF)
            elif verb == b"QUIT":
                rf.send(b"221 2.0.0 Bye" + CRLF)
                return
            else:
                rf.send(b"502 5.5.2 Command not implemented" + CRLF)
