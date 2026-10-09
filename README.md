# BlueMail

A free, local desktop mail client with an Outlook 2016 look and
Thunderbird-like functionality. No license, no telemetry, no cloud —
everything stays on your machine.

## Features

- **Outlook 2016 UI** — blue File tab, ribbon, folder pane, message list,
  reading pane (bottom or right), status bar.
- **Quick sign-in** — one-click presets for Gmail, Outlook/Hotmail, Yahoo,
  iCloud and AOL (servers auto-filled from your email address).
- **Protocols** — IMAP (UID-based sync, UIDVALIDITY handling, folder
  create/rename/move), POP3 (local virtual folders, TOP/UIDL), SMTP with
  STARTTLS/SSL.
- **Mail actions** — send, reply, reply-all, forward, delete, junk, mark
  read/unread, importance, drafts (auto-saved locally), move between folders.
- **Reading pane** — sanitized HTML rendering, inline `cid:` images from
  the local cache; **remote images are never fetched**.
- **Search** — instant filter over the current folder (Ctrl+F).
- **Accounts** — multiple accounts; stored in `~/.config/bluemail/`
  with `0600` permissions.

## Requirements

- Python 3.12
- PyQt5 (Qt 5.15) — already installed on this system
- Standard library only otherwise (`imaplib`, `poplib`, `smtplib`,
  `email`, `sqlite3`)

No `pip install` needed.

## Quick start (from Git)

```sh
git clone https://github.com/<you>/BlueMail.git
cd BlueMail

# Linux — one command sets everything up:
./bluemail            # creates .venv, installs PyQt5, then launches the app
./bluemail build      # builds the Linux app packages into dist/
./bluemail install    # installs the built .deb system-wide
```

`./bluemail` is self-contained: it checks for Python 3, creates a virtual
environment on first run, and installs only the PyQt5 runtime dependency.
If you prefer to manage dependencies yourself:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Installers

| Platform | Artifact | Where it comes from |
|---|---|---|
| Linux | `BlueMail-x86_64.AppImage`, `bluemail_0.2.0_x86_64.deb`, `BlueMail-linux-x86_64.tar.gz` | `./bluemail build` (local) or CI → `bluemail-linux` |
| Windows | `BlueMail-Setup-0.2.0.exe` — full installation wizard | CI → `bluemail-windows`, or local: `packaging/windows/BlueMail.iss` (Inno Setup) |
| macOS | `BlueMail-0.2.0.pkg` — opens the macOS *Install BlueMail* wizard, plus `BlueMail.dmg` | CI → `bluemail-macos`, or local: `packaging/macos/build_pkg.sh` |

Every artifact bundles Python, PyQt5 and Qt — no dependencies to install on
the target machine. The Windows and macOS installers (plus the Linux set) are
also built automatically on every `v*` tag via the GitHub Actions workflow
`.github/workflows/build.yml`; download them from the Actions run or a
release. macOS packages are unsigned, so first-time users must right-click →
Open (Gatekeeper).

## Building release packages

```sh
# Linux packages (AppImage / .deb / tar.gz)
./bluemail build

# or directly:
./build.sh
```

Build tools: `pyinstaller`, `patchelf`, `desktop-file-utils`,
`squashfs-tools` (apt), plus `appimagetool` (downloaded automatically
if absent). Output: the AppImage, .deb and tarball in `dist/`.

### Windows (local)

```bat
python -m pip install PyQt5 pyinstaller
python -m PyInstaller --noconfirm --windowed --name BlueMail --paths . main.py
ISCC.exe packaging\windows\BlueMail.iss   :: produces dist\BlueMail-Setup-0.2.0.exe
```

### macOS (local, must run on a Mac)

```sh
bash packaging/macos/build_pkg.sh          # produces BlueMail-0.2.0.pkg + BlueMail.dmg
```

Requires Xcode command-line tools (`pkgbuild`, `hdiutil`).

## Usage

```sh
# demo mailbox (sample data in a temp dir; real config untouched)
python3 main.py --demo

# real use, without auto-sync
python3 main.py --offline

# real use
python3 main.py

# custom data directory
python3 main.py --data-dir /path/to/data
```

## Data locations

| Path | Contents |
|---|---|
| `~/.config/bluemail/accounts.json` | account credentials/settings (0600) |
| `~/.config/bluemail/settings.json` | window/UI preferences |
| `~/.config/bluemail/mail.db` | SQLite cache (folders, messages, raw) |

`BLUEMAIL_HOME` overrides the base directory. First run migrates any
existing `~/.config/outlook-mail/` data into the new location.

## Architecture

```
main.py                 CLI entry
outlook/
  config.py             Config + Account dataclass (JSON, 0600)
  providers.py          Gmail/Outlook/Yahoo/iCloud/AOL presets
  store.py              SQLite mail store
  workers.py            thread-pool workers bridged to Qt signals
  demo.py               built-in demo mailbox
  protocols/
    imap_client.py      IMAP4/IMAP4_SSL wrapper (UID-based)
    pop3_client.py      POP3 wrapper (TOP/UIDL)
    smtp_client.py      SMTP wrapper
    common.py           header parsing, dates, importance, folder roles
  ui/
    main_window.py      ribbon wiring, sync/send orchestration
    theme.py            full Outlook 2016 QSS
    animations.py       staggered entrances, fade/slide/pulse helpers
    avatars.py          generated contact avatars
    icons.py            28 icons painted with QPainter (no QtSvg)
    ribbon.py  folder_pane.py  message_list.py
    reading_pane.py  compose.py  account_dialog.py
tests/
  test_store.py         unit tests for the mail store
  test_protocols.py     unit tests for protocol parsing helpers
  test_ui.py            UI widget/behavior tests (offscreen)
  test_e2e.py           end-to-end: real imaplib/poplib/smtplib clients
                        against in-process fake servers (fakeservers.py)
  fakeservers.py        minimal IMAP4/POP3/SMTP servers for e2e tests
  screenshot.py         offscreen screenshot generator
```

Protocol I/O runs in a `ThreadPoolExecutor`; results are marshalled to the
UI thread via `QObject` signals.

## Tests

```sh
python3 -m unittest discover -s tests
```

40 tests: store + parsing units, UI behavior, plus end-to-end cycles
(IMAP login/list/select/fetch/flags/copy/move/append, POP3 UIDL/TOP/RETR/DELE,
SMTP AUTH PLAIN + send) against local fake servers — no network required.

## Screenshots (headless)

```sh
QT_QPA_PLATFORM=offscreen python3 tests/screenshot.py
```

Writes `home.png`, `home-right-pane.png`, and `compose.png` to a temp dir.