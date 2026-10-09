"""Unit tests for the provider presets used by quick sign-in."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["OT_NO_ANIM"] = "1"

from outlook.config import Account
from outlook import providers


class DetectProviderTests(unittest.TestCase):
    def test_known_domains(self):
        cases = {
            "alex@gmail.com": "gmail",
            "x@googlemail.com": "gmail",
            "bob@outlook.com": "outlook",
            "bob@hotmail.com": "outlook",
            "bob@live.com": "outlook",
            "bob@msn.com": "outlook",
            "bob@yahoo.com": "yahoo",
            "bob@rocketmail.com": "yahoo",
            "bob@icloud.com": "icloud",
            "bob@me.com": "icloud",
            "a@mac.com": "icloud",
            "bob@aol.com": "aol",
        }
        for email, expected in cases.items():
            self.assertEqual(providers.detect_provider(email), expected, email)

    def test_unknown_and_empty(self):
        self.assertEqual(providers.detect_provider("host@skybre.co.za"),
                         "custom")
        self.assertEqual(providers.detect_provider(""), "custom")
        self.assertEqual(providers.detect_provider(None), "custom")

    def test_case_insensitive(self):
        self.assertEqual(providers.detect_provider("A@GMAIL.COM"), "gmail")


class ApplyProviderTests(unittest.TestCase):
    def test_gmail_preset_fills_servers(self):
        acc = Account.new(name="Alex", email="a@gmail.com", protocol="imap")
        providers.apply_provider(acc, "gmail")
        self.assertEqual(acc.imap_host, "imap.gmail.com")
        self.assertEqual(acc.imap_port, 993)
        self.assertTrue(acc.imap_ssl)
        self.assertEqual(acc.smtp_host, "smtp.gmail.com")
        self.assertEqual(acc.smtp_port, 465)
        self.assertEqual(acc.smtp_security, "ssl")
        self.assertEqual(acc.name, "Alex", "identity fields untouched")

    def test_outlook_starttls(self):
        acc = Account.new(name="", email="x@hotmail.com")
        providers.apply_provider(acc, "outlook")
        self.assertEqual(acc.smtp_host, "smtp.office365.com")
        self.assertEqual(acc.smtp_security, "starttls")
        self.assertEqual(acc.imap_host, "outlook.office365.com")

    def test_protocol_respected(self):
        acc = Account.new(name="", email="x@gmail.com")
        providers.apply_provider(acc, "gmail", protocol="pop3")
        self.assertEqual(acc.protocol, "pop3")
        self.assertEqual(acc.pop_host, "pop.gmail.com")
        self.assertEqual(acc.imap_host, "imap.gmail.com")

    def test_icloud_has_no_pop(self):
        acc = Account.new(name="", email="x@icloud.com")
        providers.apply_provider(acc, "icloud", protocol="pop3")
        self.assertEqual(acc.pop_host, "")

    def test_unknown_provider_falls_back_custom(self):
        acc = Account.new(name="", email="x@y.z")
        providers.apply_provider(acc, "nope")
        self.assertEqual(acc.imap_host, "")
        self.assertEqual(acc.smtp_host, "")


if __name__ == "__main__":
    unittest.main()