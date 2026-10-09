"""Unit tests for the opencode CLI integration and prompt builders."""

import os
import unittest
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["OT_NO_ANIM"] = "1"

from outlook import opencode  # noqa: E402

MESSAGE = {
    "uid": "1",
    "from_display": "Jane Doe",
    "from_addr": "jane@examples.com",
    "subject": "Status update",
    "to_addr": "me@example.com",
}


class AvailabilityTests(unittest.TestCase):
    @mock.patch("shutil.which", return_value="/usr/bin/opencode")
    def test_path_found(self, _w):
        self.assertEqual(opencode.opencode_path(), "/usr/bin/opencode")
        self.assertTrue(opencode.is_installed())

    @mock.patch("shutil.which", return_value=None)
    def test_path_missing(self, _w):
        self.assertIsNone(opencode.opencode_path())
        self.assertFalse(opencode.is_installed())


class PromptBuilderTests(unittest.TestCase):
    def test_quick_mentions_context(self):
        prompt = opencode.build_prompt("quick", MESSAGE)
        self.assertIn("jane@examples.com", prompt)
        self.assertIn("Status update", prompt)
        self.assertIn("2-4 sentences", prompt)

    def test_think_asks_for_gentle_question(self):
        prompt = opencode.build_prompt("think", MESSAGE)
        self.assertIn("Reply with ONLY the email body", prompt)

    def test_generic_when_no_message(self):
        prompt = opencode.build_prompt("quick", None)
        self.assertIn("no email is selected", prompt)

    def test_power_uses_instruction_and_recipient(self):
        prompt = opencode.build_prompt(
            "power", MESSAGE, instruction="confirm Thursday",
            target="bob@acme.com")
        self.assertIn("bob@acme.com", prompt)
        self.assertIn("confirm Thursday", prompt)

    def test_power_falls_back_to_sender(self):
        prompt = opencode.build_prompt(
            "power", MESSAGE, instruction="say hi")
        self.assertIn("jane@examples.com", prompt)

    def test_power_requires_instruction(self):
        with self.assertRaises(ValueError):
            opencode.build_prompt("power", MESSAGE, instruction="   ")

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            opencode.build_prompt("nope")


class RunTests(unittest.TestCase):
    def test_missing_binary_raises(self):
        with mock.patch.object(opencode, "opencode_path", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                opencode.run("hi")
            self.assertIn("download", str(ctx.exception).lower())

    def test_strips_ansi_and_meta_lines(self):
        proc = mock.Mock()
        proc.returncode = 0
        proc.stdout = "\x1b[0m\n> build \u00b7 big-pickle\n\x1b[0mHello there!\n"
        proc.stderr = ""
        with mock.patch.object(opencode, "opencode_path",
                               return_value="/bin/opencode"), \
             mock.patch("subprocess.run", return_value=proc) as sr:
            out = opencode.run("hi")
        self.assertEqual(out, "Hello there!")
        sr.assert_called_once()
        self.assertEqual(sr.call_args[0][0], ["/bin/opencode", "run", "hi"])

    def test_failure_raises_stderr(self):
        proc = mock.Mock()
        proc.returncode = 1
        proc.stdout = ""
        proc.stderr = "boom"
        with mock.patch.object(opencode, "opencode_path",
                               return_value="/bin/opencode"), \
             mock.patch("subprocess.run", return_value=proc):
            with self.assertRaises(RuntimeError) as ctx:
                opencode.run("hi")
        self.assertEqual(str(ctx.exception), "boom")

    def test_empty_output_raises(self):
        proc = mock.Mock()
        proc.returncode = 0
        proc.stdout = "> build"
        proc.stderr = ""
        with mock.patch.object(opencode, "opencode_path",
                               return_value="/bin/opencode"), \
             mock.patch("subprocess.run", return_value=proc):
            with self.assertRaises(RuntimeError):
                opencode.run("hi")


if __name__ == "__main__":
    unittest.main()