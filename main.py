#!/usr/bin/env python3
"""BlueMail — a local, free desktop mail client."""

import argparse
import os
import sys
import tempfile


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="bluemail",
        description="Local desktop mail client with an Outlook 2016 look "
                    "(IMAP/POP3/SMTP, no license required).")
    parser.add_argument("--demo", action="store_true",
                        help="start with a built-in demo mailbox")
    parser.add_argument("--offline", action="store_true",
                        help="start without auto-syncing accounts")
    parser.add_argument("--data-dir", default=None,
                        help="directory for config and mail cache")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.demo:
        base = args.data_dir or tempfile.mkdtemp(prefix="bluemail-demo-")
    else:
        base = args.data_dir or None

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("BlueMail")
    app.setOrganizationName("BlueMail")
    app.setApplicationVersion("0.2.0")

    from outlook.ui import theme
    theme.apply_application_style(app)

    from outlook.config import Config
    from outlook.store import Store
    from outlook.ui.main_window import MainWindow

    config = Config(base)
    store = Store(config.db_path)

    if args.demo:
        from outlook.demo import populate_demo
        populate_demo(config, store)

    window = MainWindow(config, store, demo=args.demo,
                        auto_sync=not args.offline)
    window.show()
    if args.demo:
        window.set_status("Demo mode — sample mailbox loaded")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
