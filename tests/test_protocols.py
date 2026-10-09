import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from outlook.protocols.common import (
    decode_header_value,
    format_size,
    folder_role,
    internaldate_to_ts,
    meta_from_headers,
    parse_address_field,
    first_address,
    parse_date_header,
)
from outlook.protocols.imap_client import parse_fetch_response, parse_list_response


class HeaderDecodingTest(unittest.TestCase):
    def test_encoded_words(self):
        raw = "=?UTF-8?B?SGVsbG8gV8O2cmxk?= <a@b.c>"
        self.assertEqual(decode_header_value(raw), "Hello Wörld <a@b.c>")

    def test_folded_header(self):
        raw = "a very long subject\n  that continues here"
        self.assertEqual(decode_header_value(raw), "a very long subject  that continues here")

    def test_address_field(self):
        val = "Bob <bob@x.com>, =?UTF-8?Q?Caf=C3=A9?= <c@x.com>"
        out = parse_address_field(val)
        self.assertIn("Bob <bob@x.com>", out)
        self.assertIn("Café <c@x.com>", out)

    def test_first_address(self):
        self.assertEqual(first_address("Jane Doe <jane@ex.com>"), "jane@ex.com")
        self.assertEqual(first_address(""), "")

    def test_date_header(self):
        ts = parse_date_header("Mon, 05 Aug 2024 10:30:00 +0000")
        self.assertGreater(ts, 1700000000)

    def test_internaldate(self):
        ts = internaldate_to_ts('05-Aug-2024 10:30:00 +0000')
        self.assertEqual(ts, 1722853800)
        self.assertEqual(internaldate_to_ts("garbage"), 0)

    def test_format_size(self):
        self.assertEqual(format_size(500), "500 B")
        self.assertEqual(format_size(2048), "2 KB")
        self.assertEqual(format_size(5 * 1024 * 1024), "5.0 MB")

    def test_folder_role(self):
        self.assertEqual(folder_role("INBOX", "INBOX"), "inbox")
        self.assertEqual(folder_role("Trash", "Trash"), "trash")
        self.assertEqual(folder_role("Junk E-mail", "Junk"), "junk")
        self.assertEqual(folder_role("Projects/Alpha", "Alpha"), "custom")


class MetaFromHeadersTest(unittest.TestCase):
    HEADERS = (
        b"From: Alice Example <alice@example.com>\r\n"
        b"To: Bob <bob@example.com>\r\n"
        b"Cc: carol@example.com\r\n"
        b"Subject: =?UTF-8?B?UHJvamVjdCB1cGRhdGU=?=\r\n"
        b"Date: Mon, 05 Aug 2024 10:30:00 +0000\r\n"
        b"Message-ID: <abc123@example.com>\r\n"
        b"Content-Type: multipart/mixed; boundary=XXX\r\n"
        b"\r\n"
    )

    def test_meta(self):
        meta = meta_from_headers("42", self.HEADERS, size=1234,
                                 flags=("\\Seen", "\\Flagged"))
        self.assertEqual(meta.uid, "42")
        self.assertEqual(meta.from_addr, "alice@example.com")
        self.assertEqual(meta.from_name, "Alice Example")
        self.assertEqual(meta.subject, "Project update")
        self.assertEqual(meta.msgid, "<abc123@example.com>")
        self.assertEqual(meta.size, 1234)
        self.assertTrue(meta.is_read)
        self.assertTrue(meta.is_flagged)
        self.assertGreater(meta.date_ts, 1700000000)
        self.assertEqual(meta.cc_addr, "carol@example.com")


class ImapParsingTest(unittest.TestCase):
    def test_fetch_response(self):
        header_bytes = (
            b"From: alice@example.com\r\nSubject: Hi\r\n"
            b"Date: Mon, 05 Aug 2024 10:30:00 +0000\r\n\r\n"
        )
        items = [
            (b'7 (UID 42 RFC822.SIZE 999 INTERNALDATE "05-Aug-2024 10:30:00 +0000" '
              b'BODY[HEADER.FIELDS (FROM)] {67}', header_bytes),
            b')',
        ]
        parsed = parse_fetch_response(items)
        self.assertIn("42", parsed)
        meta = parsed["42"]
        self.assertEqual(meta.size, 999)
        self.assertEqual(meta.subject, "Hi")
        self.assertEqual(meta.date_ts, 1722853800)

    def test_fetch_response_flags_trailing(self):
        header_bytes = b"From: a@b\r\nSubject: x\r\n\r\n"
        items = [
            (b'1 (UID 9 RFC822.SIZE 10 BODY[HEADER.FIELDS (FROM)] {24}',
             header_bytes),
            b' FLAGS (\\Seen))',
        ]
        parsed = parse_fetch_response(items)
        self.assertIn("9", parsed)
        self.assertTrue(parsed["9"].is_read)

    def test_list_response(self):
        lines = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Sent) "/" "Sent Items"',
            b'(\\HasNoChildren) "." "Trash"',
            b'(\\HasNoChildren) "/" "Projects/Alpha"',
        ]
        folders = parse_list_response(lines)
        paths = [f.path for f in folders]
        self.assertEqual(paths, ["INBOX", "Sent Items", "Trash", "Projects/Alpha"])
        self.assertEqual(folders[0].name, "Inbox")
        self.assertEqual(folders[2].delimiter, ".")


if __name__ == "__main__":
    unittest.main()
