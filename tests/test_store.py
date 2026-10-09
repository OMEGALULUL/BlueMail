import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from outlook.store import Store
from outlook.protocols.common import MessageMeta


def meta(uid, subject="Hello", date=1000, read=False, flagged=False, att=False):
    return MessageMeta(
        uid=str(uid), msgid=f"<m{uid}@x>", from_name="Alice",
        from_addr="alice@example.com", to_addr="bob@example.com",
        subject=subject, date_ts=date, size=2048, is_read=read,
        is_flagged=flagged, has_attachment=att,
    )


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(os.path.join(self.dir, "mail.db"))

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_folders_crud(self):
        self.store.upsert_folder("a1", "INBOX", "Inbox", role="inbox")
        self.store.upsert_folder("a1", "Work/Reports", "Reports", role="custom")
        folders = self.store.list_folders("a1")
        self.assertEqual(len(folders), 2)
        self.assertTrue(self.store.folder_path_exists("a1", "INBOX"))
        self.store.remove_folder("a1", "Work/Reports")
        self.assertEqual(len(self.store.list_folders("a1")), 1)

    def test_apply_sync_inserts_updates_and_prunes(self):
        self.store.apply_sync("a1", "INBOX", [meta(1), meta(2, "Second")])
        rows = self.store.list_messages("a1", "INBOX")
        self.assertEqual(len(rows), 2)
        # update subject of uid 1
        self.store.apply_sync("a1", "INBOX", [meta(1, "Changed")])
        rows = {r["uid"]: r for r in self.store.list_messages("a1", "INBOX")}
        self.assertEqual(rows["1"]["subject"], "Changed")
        self.assertEqual(len(rows), 2)
        # prune removed
        self.store.apply_sync("a1", "INBOX", [], removed_uids=["2"])
        self.assertEqual(len(self.store.list_messages("a1", "INBOX")), 1)

    def test_flags_and_counts(self):
        self.store.apply_sync("a1", "INBOX", [meta(1), meta(2), meta(3, read=True)])
        self.assertEqual(self.store.counts("a1", "INBOX"), {"INBOX": 2})
        self.store.set_flags("a1", "INBOX", ["1", "2"], is_read=True)
        self.assertEqual(self.store.counts("a1", "INBOX"), {"INBOX": 0})
        self.store.set_flags("a1", "INBOX", ["1"], is_flagged=True)
        row = self.store.get_message("a1", "INBOX", "1")
        self.assertEqual(row["is_flagged"], 1)

    def test_raw_cache(self):
        self.store.apply_sync("a1", "INBOX", [meta(1)])
        self.assertIsNone(self.store.get_raw("a1", "INBOX", "1"))
        raw = b"From: a\r\nSubject: x\r\n\r\nbody"
        self.store.set_raw("a1", "INBOX", "1", raw)
        self.assertEqual(self.store.get_raw("a1", "INBOX", "1"), raw)
        row = self.store.get_message("a1", "INBOX", "1")
        self.assertEqual(row["raw_size"], len(raw))

    def test_uid_set(self):
        self.store.apply_sync("a1", "INBOX", [meta(1), meta(5)])
        self.assertEqual(self.store.uid_set("a1", "INBOX"), {"1", "5"})

    def test_delete_messages(self):
        self.store.apply_sync("a1", "INBOX", [meta(1), meta(2)])
        self.store.delete_messages("a1", "INBOX", ["1"])
        self.assertEqual(len(self.store.list_messages("a1", "INBOX")), 1)


if __name__ == "__main__":
    unittest.main()
