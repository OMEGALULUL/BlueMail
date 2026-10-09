"""UI regression tests (offscreen Qt)."""

import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["OT_NO_ANIM"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication, QPushButton  # noqa: E402


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        from outlook.ui import theme
        theme.apply_application_style(app)
    return app


class NewMessageTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()
        from outlook.config import Config
        from outlook.store import Store
        from outlook.ui.main_window import MainWindow

        self.tmp = tempfile.mkdtemp(prefix="ot-ui-")
        self.config = Config(self.tmp)
        self.store = Store(self.config.db_path)
        self.win = MainWindow(self.config, self.store, demo=False,
                              auto_sync=False)
        self.win.resize(1280, 800)
        self.win.show()
        for _ in range(6):
            self.app.processEvents()

    def tearDown(self):
        for w in list(self.win._compose_windows):
            w.close()
        self.win.close()
        for _ in range(4):
            self.app.processEvents()

    def _add_account(self):
        from outlook.config import Account
        acc = Account.new(
            name="T", email="t@example.com", protocol="imap",
            username="t", password="x",
            imap_host="127.0.0.1", imap_port=1, imap_ssl=False,
            smtp_host="127.0.0.1", smtp_port=1, smtp_security="none")
        self.config.add(acc)
        self.win._accounts_changed()
        return acc

    def test_new_message_survives_clicked_bool(self):
        """QAbstractButton.clicked passes (checked,) — must not crash."""
        self._add_account()
        self.win.new_message(False)     # what PyQt delivers for clicked
        for _ in range(6):
            self.app.processEvents()
        self.assertEqual(len(self.win._compose_windows), 1)
        cw = self.win._compose_windows[0]
        self.assertEqual(cw.account.email, "t@example.com")

    def test_new_message_via_ribbon_button(self):
        self._add_account()
        btn = None
        # locate the New Email ribbon button by its text
        from PyQt5.QtWidgets import QToolButton
        for tb in self.win.ribbon.findChildren(QToolButton):
            if tb.text() == "New Email":
                btn = tb
                break
        self.assertIsNotNone(btn, "New Email ribbon button not found")
        btn.click()
        for _ in range(6):
            self.app.processEvents()
        self.assertEqual(len(self.win._compose_windows), 1)

    def test_new_message_without_account_opens_nothing_bad(self):
        # no accounts configured: compose may open with account=None but
        # must not raise
        self.win.new_message(False)
        for _ in range(6):
            self.app.processEvents()
        self.assertLessEqual(len(self.win._compose_windows), 1)

    def test_welcome_page_shown_for_empty_config(self):
        self.assertEqual(self.win.stack.currentIndex(), 1)
        self.assertIsNotNone(getattr(self.win, "welcome_cta", None))

    def test_folder_tree_animated(self):
        self.assertTrue(self.win.folder_pane.isAnimated())


class RedesignTests(unittest.TestCase):
    """Row design, reading-pane header, quick actions, animations."""

    def setUp(self):
        self.app = _app()
        from outlook.config import Config
        from outlook.store import Store
        from outlook.ui.main_window import MainWindow

        self.tmp = tempfile.mkdtemp(prefix="ot-redesign-")
        self.config = Config(self.tmp)
        self.store = Store(self.config.db_path)
        self.win = MainWindow(self.config, self.store, demo=False,
                              auto_sync=False)
        self.win.resize(1280, 800)
        self.win.show()
        for _ in range(6):
            self.app.processEvents()
        self.row = {
            "uid": "42", "msgid": "<42@x>", "from_display": "Ada Lovelace",
            "from_addr": "ada@example.com", "to_addr": "me@example.com",
            "cc_addr": "", "subject": "Notes", "date_ts": 1759900000,
            "size": 1024, "is_read": False, "is_flagged": False,
            "has_attachment": False, "importance": "",
        }

    def tearDown(self):
        for w in list(self.win._compose_windows):
            w.close()
        self.win.close()
        for _ in range(4):
            self.app.processEvents()

    def test_message_list_row_design(self):
        from outlook.ui.message_list import COL_FROM, COL_IMPORTANCE
        from PyQt5.QtCore import Qt

        ml = self.win.message_list
        self.assertEqual(ml.verticalHeader().defaultSectionSize(), 34)
        self.assertEqual(ml.iconSize().width(), 20)
        ml.set_rows([self.row])
        model = ml._model
        avatar = model.data(model.index(0, COL_FROM), Qt.DecorationRole)
        self.assertIsNotNone(avatar, "avatar decoration missing")
        dot = model.data(model.index(0, COL_IMPORTANCE), Qt.DecorationRole)
        self.assertIsNotNone(dot, "unread dot decoration missing")
        # read message: no dot (and no flag/importance icons)
        self.row["is_read"] = True
        ml.set_rows([self.row])
        self.assertIsNone(
            model.data(model.index(0, COL_IMPORTANCE), Qt.DecorationRole))

    def test_reading_pane_header_and_actions(self):
        rp = self.win.reading_pane
        self.assertFalse(
            any(b.isEnabled() for b in rp._action_buttons),
            "actions must start disabled")
        rp.show_message(self.row, raw=None)
        self.assertIn("Ada Lovelace", rp.sender_name.text())
        self.assertTrue(rp.date_label.text())
        self.assertIsNotNone(rp.avatar.pixmap())
        self.assertFalse(rp.avatar.pixmap().isNull())
        self.assertEqual(len(rp._action_buttons), 5)
        self.assertTrue(all(b.isEnabled() for b in rp._action_buttons))
        # note: explicit show/hide state — the mail page itself may be
        # hidden behind the welcome page when no account exists yet
        self.assertFalse(rp.header_sep.isHidden())
        # to-row visible, cc-row hidden (cc empty)
        to_cap, to_val = rp._meta_labels["to"]
        cc_cap, _cc_val = rp._meta_labels["cc"]
        self.assertFalse(to_cap.isHidden())
        self.assertFalse(to_val.isHidden())
        self.assertTrue(cc_cap.isHidden())
        rp.clear()
        self.assertFalse(
            any(b.isEnabled() for b in rp._action_buttons),
            "actions must be disabled after clear()")

    def test_reading_action_buttons_emit_signals(self):
        rp = self.win.reading_pane
        rp.show_message(self.row, raw=None)
        got = []
        rp.action_requested.connect(got.append)
        rp._action_buttons[0].click()   # reply
        rp._action_buttons[4].click()   # delete
        self.assertEqual(got, ["reply", "delete"])

    def test_reading_action_noop_without_message(self):
        self.win._reading_action("reply")
        self.assertEqual(len(self.win._compose_windows), 0)

    def test_animations_disabled_in_tests(self):
        from outlook.ui import animations
        self.assertFalse(animations.enabled())
        self.assertIsNone(animations.fade_in(self.win))
        self.assertIsNone(animations.pulse(self.win.welcome_cta))

    def test_welcome_entrance_references(self):
        self.assertIsNotNone(self.win.welcome_band)
        self.assertIsNotNone(self.win.welcome_heading)
        self.assertIsNotNone(self.win.welcome_hint)
        self.assertIsNotNone(self.win.welcome_footer)
        self.assertIsNotNone(self.win.welcome_cta)

    def test_welcome_quick_signin_row(self):
        self.assertIsNotNone(self.win.welcome_provider_row)
        chips = self.win.welcome_provider_row.findChildren(QPushButton)
        labels = {b.text() for b in chips}
        for expected in ("Gmail", "Outlook / Hotmail", "Yahoo", "iCloud"):
            self.assertIn(expected, labels)

    def test_account_dialog_gmail_prefill(self):
        from outlook.config import Config
        from outlook.ui.account_dialog import AccountDialog
        cfg = Config(tempfile.mkdtemp())
        dlg = AccountDialog(cfg, provider="gmail")
        acc = next(iter(dlg._accounts.values()))
        self.assertEqual(acc.imap_host, "imap.gmail.com")
        self.assertEqual(acc.smtp_host, "smtp.gmail.com")
        self.assertEqual(dlg._current_provider(), "gmail")
        dlg.close()

    def test_account_dialog_email_autodetect(self):
        from outlook.config import Config
        from outlook.ui.account_dialog import AccountDialog
        cfg = Config(tempfile.mkdtemp())
        dlg = AccountDialog(cfg)
        self.assertEqual(dlg._current_provider(), "custom")
        dlg.email_edit.setText("me@yahoo.com")
        self.assertEqual(dlg._current_provider(), "yahoo")
        acc = next(iter(dlg._accounts.values()))
        self.assertEqual(acc.imap_host, "imap.mail.yahoo.com")
        self.assertEqual(acc.smtp_host, "smtp.mail.yahoo.com")
        dlg.close()


class AnimationsBehaviorTests(unittest.TestCase):
    """Animation helpers honour OT_NO_ANIM and restore state cleanly."""

    def setUp(self):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication([])
            from outlook.ui import theme
            theme.apply_application_style(self.app)

    def test_disabled_helpers_are_noops(self):
        from PyQt5.QtWidgets import QLabel, QVBoxLayout
        from outlook.ui import animations
        self.assertFalse(animations.enabled())
        w = QLabel("x")
        self.assertIsNone(animations.prime(w))
        self.assertIsNone(animations.fade_in(w))
        self.assertIsNone(animations.slide_in(w, QVBoxLayout()))
        self.assertIsNone(animations.pulse(w))
        animations.stagger([(w, 0, 50)])
        self.assertIsNone(w.graphicsEffect(), "stagger must not prime")

    def test_prime_and_fade_cycle(self):
        import time
        from PyQt5.QtCore import QAbstractAnimation
        from PyQt5.QtWidgets import QLabel
        from outlook.ui import animations
        w = QLabel("x")
        try:
            del os.environ["OT_NO_ANIM"]
            eff = animations.prime(w)
            self.assertIsNotNone(eff)
            self.assertEqual(eff.opacity(), 0.0)
            anim = animations.fade_in(w, 5)
            self.assertIsNotNone(anim)
            deadline = time.time() + 2
            while (anim.state() == QAbstractAnimation.Running
                    and time.time() < deadline):
                self.app.processEvents()
                time.sleep(0.002)
            self.assertAlmostEqual(eff.opacity(), 1.0, delta=0.02)
        finally:
            os.environ["OT_NO_ANIM"] = "1"

    def test_slide_in_restores_margins(self):
        import time
        from PyQt5.QtCore import QAbstractAnimation
        from PyQt5.QtWidgets import QVBoxLayout, QWidget
        from outlook.ui import animations
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(7, 9, 3, 5)
        try:
            del os.environ["OT_NO_ANIM"]
            anim = animations.slide_in(container, lay, distance=10, duration=5)
            self.assertIsNotNone(anim)
            deadline = time.time() + 2
            while (getattr(container, "_ot_anim", None) is not None
                    and container._ot_anim.state() == QAbstractAnimation.Running
                    and time.time() < deadline):
                self.app.processEvents()
                time.sleep(0.002)
            m = lay.contentsMargins()
            self.assertEqual((m.left(), m.top(), m.right(), m.bottom()),
                             (7, 9, 3, 5))
            animations.stop(container)
            self.assertIsNone(getattr(container, "_ot_anim", None))
        finally:
            os.environ["OT_NO_ANIM"] = "1"

    def test_stop_restores_layout_mid_slide(self):
        from PyQt5.QtWidgets import QVBoxLayout, QWidget
        from outlook.ui import animations
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        try:
            del os.environ["OT_NO_ANIM"]
            animations.slide_in(container, lay, distance=12, duration=8000)
            # let the first frame apply, then stop mid-flight
            self.app.processEvents()
            animations.stop(container)
            m = lay.contentsMargins()
            self.assertEqual((m.left(), m.top(), m.right(), m.bottom()),
                             (0, 0, 0, 0))
            self.assertIsNone(getattr(container, "_ot_anim", None))
        finally:
            os.environ["OT_NO_ANIM"] = "1"


class OpencodeDialogTests(unittest.TestCase):
    """Opencode assistant dialog: modes, power fields, download fallback."""

    def setUp(self):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication([])
            from outlook.ui import theme
            theme.apply_application_style(self.app)
        from outlook.ui.opencode_dialog import OpencodeDialog
        self.Dialog = OpencodeDialog

    @mock.patch("outlook.opencode.is_installed", return_value=True)
    def test_installed_shows_modes(self, _ok):
        from outlook.ui.opencode_dialog import OpencodeDialog
        dlg = OpencodeDialog()
        dlg.show()
        self.assertTrue(dlg.mode_buttons["quick"].isEnabled())
        self.assertTrue(dlg.mode_buttons["think"].isEnabled())
        self.assertTrue(dlg.mode_buttons["power"].isEnabled())
        self.assertFalse(dlg.download_btn.isVisible())
        dlg.close()

    @mock.patch("outlook.opencode.is_installed", return_value=False)
    def test_missing_shows_download(self, _ok):
        dlg = self.Dialog()
        dlg.show()
        self.assertFalse(dlg.mode_buttons["quick"].isEnabled())
        self.assertTrue(dlg.download_btn.isVisible())
        self.assertEqual(dlg.download_btn.text(), "Download opencode")
        dlg.close()

    @mock.patch("outlook.opencode.is_installed", return_value=True)
    def test_power_mode_reveals_inputs(self, _ok):
        dlg = self.Dialog()
        dlg.show()
        self.assertFalse(dlg.field_row.isVisible())
        dlg._pick("power")
        self.assertTrue(dlg.field_row.isVisible())
        self.assertEqual(dlg._mode, "power")
        dlg.close()


if __name__ == "__main__":
    unittest.main()
