"""End-to-end tests: real stdlib clients against in-process fake servers."""

import os
import sys
import unittest
from email.message import EmailMessage

_TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TESTS)
sys.path.insert(0, os.path.dirname(_TESTS))

from fakeservers import FakeIMAP, FakePOP3, FakeSMTP      # noqa: E402
from outlook.config import Account                         # noqa: E402
from outlook.protocols.imap_client import ImapClient, ImapError   # noqa: E402
from outlook.protocols.pop3_client import PopClient, PopError     # noqa: E402
from outlook.protocols.smtp_client import send_message, SmtpError  # noqa: E402


def raw_msg(msg_id, from_, to, subject, body,
            date="Mon, 05 Oct 2026 10:00:00 +0000"):
    return (
        f"From: {from_}\r\n"
        f"To: {to}\r\n"
        f"Subject: {subject}\r\n"
        f"Date: {date}\r\n"
        f"Message-ID: <{msg_id}>\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}\r\n"
    ).encode("utf-8")


INBOX_MSGS = [
    {"uid": 1, "flags": {"\\Seen"},
     "raw": raw_msg("m1@example.com", "Bob <bob@example.com>",
                    "alice@example.com", "Quarterly report attached",
                    "Numbers are inside. Regards, Bob")},
    {"uid": 2, "flags": set(),
     "raw": raw_msg("m2@example.com", "Carol <carol@example.com>",
                    "alice@example.com", "Lunch tomorrow?",
                    "Cafeteria at noon?")},
    {"uid": 3, "flags": set(),
     "raw": raw_msg("m3@example.com", "Dave <dave@example.com>",
                    "alice@example.com", "Desk assignment",
                    "You sit by the window now.")},
]
SENT_MSGS = [
    {"uid": 1, "flags": {"\\Seen"},
     "raw": raw_msg("s1@example.com", "alice@example.com",
                    "boss@example.com", "Re: Budget",
                    "Attached the numbers.")},
]
PROJECT_MSGS = [
    {"uid": 1, "flags": {"\\Seen"},
     "raw": raw_msg("p1@example.com", "Team <team@example.com>",
                    "alice@example.com", "Q3 kickoff notes",
                    "Meeting Monday.")},
]

POP_MESSAGES = [
    {"uidl": "uidl-001",
     "raw": raw_msg("u1@example.com", "Ann <ann@example.com>",
                    "alice@example.com", "First pop message",
                    "Hello from POP one.")},
    {"uidl": "uidl-002",
     "raw": raw_msg("u2@example.com", "Ben <ben@example.com>",
                    "alice@example.com", "Second pop message",
                    "Hello from POP two. The line below starts with a dot:"
                    "\r\n.normal text")},
]


def imap_account(port, password="s3cret"):
    return Account.new(
        name="Alice", email="alice@example.com", protocol="imap",
        username="alice", password=password,
        imap_host="127.0.0.1", imap_port=port, imap_ssl=False,
        smtp_host="127.0.0.1", smtp_port=port, smtp_security="none",
        sent_folder="Sent", trash_folder="Trash", junk_folder="Junk")


class ImapE2ETest(unittest.TestCase):
    def setUp(self):
        self.srv = FakeIMAP({
            "INBOX": INBOX_MSGS,
            "Sent": SENT_MSGS,
            "Trash": [],
            "Junk": [],
            "Projects/Q3": PROJECT_MSGS,
        })
        self.addCleanup(self.srv.stop)
        self.acc = imap_account(self.srv.port)

    def test_full_cycle(self):
        with ImapClient(self.acc) as cli:
            folders = {f.path for f in cli.list_folders()}
            self.assertEqual(
                folders, {"INBOX", "Sent", "Trash", "Junk", "Projects/Q3"})

            cli.select("INBOX")
            self.assertEqual(cli.uidvalidity(),
                             self.srv.uidvalidity["INBOX"])
            self.assertEqual(cli.search_all(), ["1", "2", "3"])

            metas = {m.uid: m for m in cli.fetch_summaries()}
            self.assertEqual(set(metas), {"1", "2", "3"})
            self.assertEqual(metas["1"].subject,
                             "Quarterly report attached")
            self.assertEqual(metas["1"].from_addr, "bob@example.com")
            self.assertEqual(metas["2"].subject, "Lunch tomorrow?")
            self.assertTrue(metas["1"].is_read)
            self.assertFalse(metas["2"].is_read)
            self.assertGreater(metas["1"].size, 0)
            self.assertGreater(metas["1"].date_ts, 0)

            self.assertEqual(cli.fetch_full("1"), INBOX_MSGS[0]["raw"])

            cli.set_seen("2", True)
            cli.set_flagged("2", True)
            flags = self._flags("INBOX", "2")
            self.assertIn("\\Seen", flags)
            self.assertIn("\\Flagged", flags)
            cli.set_seen("2", False)
            self.assertNotIn("\\Seen", self._flags("INBOX", "2"))

            cli.copy(["1"], "Sent")
            self.assertEqual(len(self.srv.mailboxes["Sent"]), 2)

            cli.move(["3"], "Trash")
            self.assertEqual(cli.search_all(), ["1", "2"])
            self.assertEqual(len(self.srv.mailboxes["Trash"]), 1)
            self.assertEqual(self.srv.mailboxes["Trash"][0]["uid"], 1)
            self.assertEqual(
                self.srv.mailboxes["Trash"][0]["raw"],
                INBOX_MSGS[2]["raw"])

            new = raw_msg("new@example.com", "alice@example.com",
                          "bob@example.com", "Sent from client",
                          "Body of appended message.")
            cli.append("Sent", new)
            self.assertEqual(self.srv.mailboxes["Sent"][-1]["raw"], new)

            cli.create_folder("Archive")
            self.assertIn("Archive", self.srv.mailboxes)
            cli.delete_folder("Archive")
            self.assertNotIn("Archive", self.srv.mailboxes)

            self.assertTrue(cli.noop())

        # after context exit the client logged out
        cmds = " ".join(c for _tag, c in self.srv.commands)
        self.assertIn("LOGIN", cmds)
        self.assertIn("LOGOUT", cmds)
        self.assertEqual(self.srv.authenticated, "alice")

    def test_select_unknown_folder_raises(self):
        cli = ImapClient(self.acc)
        self.addCleanup(cli.close)
        cli.connect()
        with self.assertRaises(ImapError):
            cli.select("No/Such/Folder")

    def test_wrong_password_raises(self):
        bad = imap_account(self.srv.port, password="wrong")
        with self.assertRaises(ImapError):
            ImapClient(bad).connect()

    def _flags(self, folder, uid):
        for m in self.srv.mailboxes[folder]:
            if str(m["uid"]) == uid:
                return m["flags"]
        self.fail(f"uid {uid} not in {folder}")


class Pop3E2ETest(unittest.TestCase):
    def setUp(self):
        self.srv = FakePOP3(POP_MESSAGES)
        self.addCleanup(self.srv.stop)
        self.acc = Account.new(
            name="Alice", email="alice@example.com", protocol="pop3",
            username="alice", password="s3cret",
            pop_host="127.0.0.1", pop_port=self.srv.port, pop_ssl=False,
            smtp_host="127.0.0.1", smtp_port=self.srv.port,
            smtp_security="none")

    def test_summaries_and_delete(self):
        with PopClient(self.acc) as cli:
            self.assertEqual(cli.uidl_list(),
                             [(1, "uidl-001"), (2, "uidl-002")])

            new, all_uidls = cli.fetch_summaries(existing=())
            self.assertEqual(len(new), 2)
            self.assertEqual(all_uidls, ["uidl-001", "uidl-002"])
            self.assertEqual(new[0].subject, "First pop message")
            self.assertEqual(new[0].from_addr, "ann@example.com")
            self.assertEqual(new[1].subject, "Second pop message")
            self.assertGreater(new[0].size, 0)

            # full message incl. a line starting with a dot
            raw = cli.fetch_full(2)
            self.assertIn(b"\r\n.normal text", raw)

            # only the new one is returned on a second sync
            newer, _ = cli.fetch_summaries(existing=("uidl-001",))
            self.assertEqual([m.uid for m in newer], ["uidl-002"])

            sizes = cli.list_sizes()
            self.assertEqual(sizes[1], len(POP_MESSAGES[0]["raw"]))

            cli.delete_uidl("uidl-001")
            # POP3 numbers don't shift after DELE within a session
            self.assertEqual(cli.uidl_list(), [(2, "uidl-002")])

        self.assertEqual(self.srv.authenticated, "alice")

    def test_wrong_password_raises(self):
        bad = Account.new(
            name="Alice", email="alice@example.com", protocol="pop3",
            username="alice", password="nope",
            pop_host="127.0.0.1", pop_port=self.srv.port, pop_ssl=False)
        with self.assertRaises(PopError):
            PopClient(bad).connect()


class SmtpE2ETest(unittest.TestCase):
    def setUp(self):
        self.srv = FakeSMTP()
        self.addCleanup(self.srv.stop)
        self.acc = Account.new(
            name="Alice", email="alice@example.com",
            username="alice", password="s3cret",
            smtp_host="127.0.0.1", smtp_port=self.srv.port,
            smtp_security="none")

    def test_send(self):
        msg = EmailMessage()
        msg["From"] = "alice@example.com"
        msg["To"] = "bob@example.com, carol@example.com"
        msg["Subject"] = "E2E greeting"
        msg.set_content("Hello Bob and Carol,\n\nit works.\n")

        send_message(self.acc, msg)

        self.assertEqual(self.srv.authenticated, "alice")
        self.assertEqual(len(self.srv.messages), 1)
        mail_from, rcpts = self.srv.envelopes[0]
        self.assertIn("alice@example.com", mail_from)
        self.assertEqual(len(rcpts), 2)
        payload = self.srv.messages[0]
        self.assertIn("Subject: E2E greeting", payload.decode())
        self.assertIn("it works.", payload.decode())

    def test_wrong_password_raises(self):
        bad = Account.new(
            name="Alice", email="alice@example.com",
            username="alice", password="nope",
            smtp_host="127.0.0.1", smtp_port=self.srv.port,
            smtp_security="none")
        msg = EmailMessage()
        msg["From"] = "alice@example.com"
        msg["To"] = "bob@example.com"
        msg["Subject"] = "x"
        msg.set_content("y")
        with self.assertRaises(SmtpError):
            send_message(bad, msg)


if __name__ == "__main__":
    unittest.main()
