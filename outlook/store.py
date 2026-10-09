"""SQLite message/folder cache (thread-safe)."""

import json
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    account_id  TEXT NOT NULL,
    path        TEXT NOT NULL,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'custom',
    uidvalidity INTEGER NOT NULL DEFAULT 0,
    synced_at   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, path)
);

CREATE TABLE IF NOT EXISTS messages (
    account_id     TEXT NOT NULL,
    folder         TEXT NOT NULL,
    uid            TEXT NOT NULL,
    msgid          TEXT DEFAULT '',
    from_name      TEXT DEFAULT '',
    from_addr      TEXT DEFAULT '',
    to_addr        TEXT DEFAULT '',
    cc_addr        TEXT DEFAULT '',
    subject        TEXT DEFAULT '',
    date_ts        INTEGER NOT NULL DEFAULT 0,
    size           INTEGER NOT NULL DEFAULT 0,
    is_read        INTEGER NOT NULL DEFAULT 0,
    is_flagged     INTEGER NOT NULL DEFAULT 0,
    has_attachment INTEGER NOT NULL DEFAULT 0,
    importance     TEXT NOT NULL DEFAULT '',
    raw            BLOB,
    raw_size       INTEGER NOT NULL DEFAULT 0,
    updated_at     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, folder, uid)
);

CREATE INDEX IF NOT EXISTS idx_messages_folder
    ON messages (account_id, folder, date_ts DESC);
"""


class Store:
    def __init__(self, path: str):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            try:
                self._db.execute(
                    "ALTER TABLE messages ADD COLUMN importance "
                    "TEXT NOT NULL DEFAULT ''"
                )
            except sqlite3.OperationalError:
                pass
            self._db.commit()

    def close(self):
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------- folders
    def upsert_folder(self, account_id, path, name, role="custom", uidvalidity=0):
        with self._lock:
            self._db.execute(
                """INSERT INTO folders (account_id, path, name, role, uidvalidity, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(account_id, path) DO UPDATE SET
                     name=excluded.name, role=excluded.role,
                     uidvalidity=excluded.uidvalidity""",
                (account_id, path, name, role, uidvalidity, int(time.time())),
            )
            self._db.commit()

    def list_folders(self, account_id):
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM folders WHERE account_id=? ORDER BY role, name",
                (account_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def remove_folder(self, account_id, path):
        with self._lock:
            self._db.execute(
                "DELETE FROM folders WHERE account_id=? AND path=?",
                (account_id, path),
            )
            self._db.execute(
                "DELETE FROM messages WHERE account_id=? AND folder=?",
                (account_id, path),
            )
            self._db.commit()

    def folder_path_exists(self, account_id, path):
        with self._lock:
            cur = self._db.execute(
                "SELECT 1 FROM folders WHERE account_id=? AND path=?",
                (account_id, path),
            )
            return cur.fetchone() is not None

    def mark_folder_synced(self, account_id, path, uidvalidity=None):
        with self._lock:
            if uidvalidity is not None:
                self._db.execute(
                    "UPDATE folders SET synced_at=?, uidvalidity=? "
                    "WHERE account_id=? AND path=?",
                    (int(time.time()), uidvalidity, account_id, path),
                )
            else:
                self._db.execute(
                    "UPDATE folders SET synced_at=? WHERE account_id=? AND path=?",
                    (int(time.time()), account_id, path),
                )
            self._db.commit()

    # ------------------------------------------------------------ messages
    @staticmethod
    def _meta_row(account_id, folder, m):
        return (
            account_id,
            folder,
            str(m.uid),
            m.msgid or "",
            m.from_name or "",
            m.from_addr or "",
            m.to_addr or "",
            m.cc_addr or "",
            m.subject or "",
            int(m.date_ts or 0),
            int(m.size or 0),
            1 if m.is_read else 0,
            1 if m.is_flagged else 0,
            1 if m.has_attachment else 0,
            m.importance or "",
            int(time.time()),
        )

    def apply_sync(self, account_id, folder, metas, removed_uids=()):
        """Insert/update summaries and drop messages that vanished."""
        cols = (
            "account_id, folder, uid, msgid, from_name, from_addr, to_addr, "
            "cc_addr, subject, date_ts, size, is_read, is_flagged, "
            "has_attachment, importance, updated_at"
        )
        with self._lock:
            for m in metas:
                self._db.execute(
                    f"""INSERT INTO messages ({cols}) VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(account_id, folder, uid) DO UPDATE SET
                          msgid=excluded.msgid, from_name=excluded.from_name,
                          from_addr=excluded.from_addr, to_addr=excluded.to_addr,
                          cc_addr=excluded.cc_addr, subject=excluded.subject,
                          date_ts=excluded.date_ts, size=excluded.size,
                          is_read=excluded.is_read, is_flagged=excluded.is_flagged,
                          has_attachment=excluded.has_attachment,
                          importance=excluded.importance,
                          updated_at=excluded.updated_at""",
                    self._meta_row(account_id, folder, m),
                )
            if removed_uids:
                self._db.executemany(
                    "DELETE FROM messages WHERE account_id=? AND folder=? AND uid=?",
                    [(account_id, folder, str(u)) for u in removed_uids],
                )
            self._db.commit()

    def insert_message(self, account_id, folder, meta, raw: bytes = None):
        with self._lock:
            self.apply_sync(account_id, folder, [meta])
            if raw is not None:
                self._db.execute(
                    "UPDATE messages SET raw=?, raw_size=? "
                    "WHERE account_id=? AND folder=? AND uid=?",
                    (raw, len(raw), account_id, folder, str(meta.uid)),
                )
                self._db.commit()

    def list_messages(self, account_id, folder):
        with self._lock:
            cur = self._db.execute(
                """SELECT * FROM messages WHERE account_id=? AND folder=?
                   ORDER BY date_ts DESC, rowid DESC""",
                (account_id, folder),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_message(self, account_id, folder, uid):
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM messages WHERE account_id=? AND folder=? AND uid=?",
                (account_id, folder, str(uid)),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_raw(self, account_id, folder, uid):
        with self._lock:
            cur = self._db.execute(
                "SELECT raw FROM messages WHERE account_id=? AND folder=? AND uid=?",
                (account_id, folder, str(uid)),
            )
            row = cur.fetchone()
            return row["raw"] if row else None

    def set_raw(self, account_id, folder, uid, raw: bytes):
        with self._lock:
            self._db.execute(
                "UPDATE messages SET raw=?, raw_size=? "
                "WHERE account_id=? AND folder=? AND uid=?",
                (raw, len(raw), account_id, folder, str(uid)),
            )
            self._db.commit()

    def set_flags(self, account_id, folder, uids, is_read=None, is_flagged=None):
        sets, params = [], []
        if is_read is not None:
            sets.append("is_read=?")
            params.append(1 if is_read else 0)
        if is_flagged is not None:
            sets.append("is_flagged=?")
            params.append(1 if is_flagged else 0)
        if not sets:
            return
        with self._lock:
            self._db.executemany(
                f"UPDATE messages SET {', '.join(sets)} "
                "WHERE account_id=? AND folder=? AND uid=?",
                [tuple(params) + (account_id, folder, str(u)) for u in uids],
            )
            self._db.commit()

    def delete_messages(self, account_id, folder, uids):
        with self._lock:
            self._db.executemany(
                "DELETE FROM messages WHERE account_id=? AND folder=? AND uid=?",
                [(account_id, folder, str(u)) for u in uids],
            )
            self._db.commit()

    def move_messages(self, account_id, src_folder, dst_folder, uids):
        """Move rows (including cached raw) between folders with new uids."""
        uids = [str(u) for u in uids]
        with self._lock:
            for uid in uids:
                cur = self._db.execute(
                    "SELECT * FROM messages WHERE account_id=? AND folder=? AND uid=?",
                    (account_id, src_folder, uid),
                )
                row = cur.fetchone()
                if row is None:
                    continue
                new_uid = f"L{uid}" if dst_folder == src_folder else uid
                self._db.execute(
                    """INSERT OR REPLACE INTO messages
                       (account_id, folder, uid, msgid, from_name, from_addr,
                        to_addr, cc_addr, subject, date_ts, size, is_read,
                        is_flagged, has_attachment, importance, raw, raw_size,
                        updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                               ?)""",
                    (account_id, dst_folder, new_uid, row["msgid"],
                     row["from_name"], row["from_addr"], row["to_addr"],
                     row["cc_addr"], row["subject"], row["date_ts"], row["size"],
                     row["is_read"], row["is_flagged"], row["has_attachment"],
                     row["importance"], row["raw"], row["raw_size"],
                     int(time.time())),
                )
                self._db.execute(
                    "DELETE FROM messages WHERE account_id=? AND folder=? AND uid=?",
                    (account_id, src_folder, uid),
                )
            self._db.commit()

    def counts(self, account_id, folder=None):
        """{folder: unread_count} for an account (or a single folder)."""
        with self._lock:
            q = ("SELECT folder, COUNT(*) AS n FROM messages "
                 "WHERE account_id=? AND is_read=0")
            params = [account_id]
            if folder:
                q += " AND folder=?"
                params.append(folder)
            q += " GROUP BY folder"
            cur = self._db.execute(q, params)
            out = {r["folder"]: r["n"] for r in cur.fetchall()}
            if folder and folder not in out:
                out[folder] = 0
            return out

    def uid_set(self, account_id, folder):
        with self._lock:
            cur = self._db.execute(
                "SELECT uid FROM messages WHERE account_id=? AND folder=?",
                (account_id, folder),
            )
            return {r["uid"] for r in cur.fetchall()}

    def all_folder_paths(self, account_id):
        with self._lock:
            cur = self._db.execute(
                "SELECT path FROM folders WHERE account_id=?", (account_id,)
            )
            return [r["path"] for r in cur.fetchall()]

    # ---------------------------------------------------------------- misc
    def clear_account(self, account_id):
        with self._lock:
            self._db.execute("DELETE FROM folders WHERE account_id=?", (account_id,))
            self._db.execute("DELETE FROM messages WHERE account_id=?", (account_id,))
            self._db.commit()
