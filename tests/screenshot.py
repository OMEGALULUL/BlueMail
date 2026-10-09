"""Render offscreen screenshots of the UI for visual verification."""

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt5.QtWidgets import QApplication  # noqa: E402

from outlook.ui import theme  # noqa: E402


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(
        prefix="outlook-shots-")
    os.makedirs(out_dir, exist_ok=True)
    app = QApplication(sys.argv)
    theme.apply_application_style(app)

    from outlook.config import Config
    from outlook.store import Store
    from outlook.demo import populate_demo
    from outlook.ui.main_window import MainWindow
    from outlook.ui.compose import ComposeWindow

    config = Config(tempfile.mkdtemp(prefix="outlook-shot-cfg-"))
    store = Store(config.db_path)
    account = populate_demo(config, store)

    win = MainWindow(config, store, demo=True, auto_sync=False)
    win.resize(1280, 800)
    win.show()
    app.processEvents()

    # select first inbox message
    if win.message_list.model().rowCount() > 0:
        win.message_list.selectRow(0)
    app.processEvents()
    app.processEvents()

    path1 = os.path.join(out_dir, "home.png")
    win.grab().save(path1)

    # reading pane on the right
    win.set_reading_pane("right")
    app.processEvents()
    path2 = os.path.join(out_dir, "home-right-pane.png")
    win.grab().save(path2)
    win.set_reading_pane("bottom")
    app.processEvents()

    # compose window
    win.new_message()
    app.processEvents()
    compose = win._compose_windows[-1]
    compose.to_edit.setText("sara.chen@northwind.example")
    compose.subject_edit.setText("Re: Q3 report — final numbers attached")
    compose.body.setPlainText("Hi Sara,\n\nLooks great — see my comments\n\nAlex")
    app.processEvents()
    compose_path = os.path.join(out_dir, "compose.png")
    compose.grab().save(compose_path)
    compose.close()
    app.processEvents()

    print("screenshots written to", out_dir)
    for name in sorted(os.listdir(out_dir)):
        print(" -", name)


if __name__ == "__main__":
    main()
