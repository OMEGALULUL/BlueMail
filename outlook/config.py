"""Application configuration: accounts and UI settings."""

import json
import os
import shutil
import stat
import uuid
from dataclasses import asdict, dataclass, field, fields

DEFAULT_BASE_DIR = os.environ.get(
    "BLUEMAIL_HOME",
    os.path.join(os.path.expanduser("~"), ".config", "bluemail"),
)

#: legacy pre-rebrand data dir, migrated on first run
LEGACY_BASE_DIR = os.path.join(
    os.path.expanduser("~"), ".config", "outlook-mail"
)

PROTOCOLS = ("imap", "pop3")
SMTP_SECURITY = ("starttls", "ssl", "none")


@dataclass
class Account:
    id: str
    name: str
    email: str
    protocol: str = "imap"
    username: str = ""
    password: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    pop_host: str = ""
    pop_port: int = 995
    pop_ssl: bool = True
    sent_folder: str = ""
    drafts_folder: str = ""
    trash_folder: str = ""
    junk_folder: str = ""
    enabled: bool = True

    @staticmethod
    def new(**kwargs) -> "Account":
        return Account(id=uuid.uuid4().hex, **kwargs)

    @property
    def inbound_host(self) -> str:
        return self.imap_host if self.protocol == "imap" else self.pop_host

    @property
    def inbound_port(self) -> int:
        return self.imap_port if self.protocol == "imap" else self.pop_port


class Config:
    """Loads/saves accounts.json and settings.json under the base dir."""

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR
        if base_dir is None:
            self._migrate_legacy()
        os.makedirs(self.base_dir, mode=0o700, exist_ok=True)
        self.accounts_path = os.path.join(self.base_dir, "accounts.json")
        self.settings_path = os.path.join(self.base_dir, "settings.json")
        self.db_path = os.path.join(self.base_dir, "mail.db")
        self._accounts = []
        self.settings = {}
        self._load()

    # ---------------------------------------------------------------- load
    @staticmethod
    def _migrate_legacy():
        """Copy accounts/settings/db from the old outlook-mail config dir."""
        if os.path.exists(DEFAULT_BASE_DIR):
            return
        for name in ("accounts.json", "settings.json", "mail.db"):
            src = os.path.join(LEGACY_BASE_DIR, name)
            if not os.path.exists(src):
                continue
            try:
                os.makedirs(DEFAULT_BASE_DIR, mode=0o700, exist_ok=True)
                shutil.copy2(src, os.path.join(DEFAULT_BASE_DIR, name))
            except OSError:
                pass

    def _load(self):
        self._accounts = []
        if os.path.exists(self.accounts_path):
            try:
                with open(self.accounts_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                data = []
            known = {f.name for f in fields(Account)}
            for item in data:
                try:
                    self._accounts.append(
                        Account(**{k: v for k, v in item.items() if k in known})
                    )
                except TypeError:
                    continue
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as fh:
                    self.settings = json.load(fh)
            except (OSError, ValueError):
                self.settings = {}

    def save(self):
        self._write_json(
            self.accounts_path, [asdict(a) for a in self._accounts]
        )
        self._write_json(self.settings_path, self.settings)

    @staticmethod
    def _write_json(path, obj):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, path)

    # -------------------------------------------------------------- accounts
    @property
    def accounts(self):
        return list(self._accounts)

    def get(self, account_id):
        for a in self._accounts:
            if a.id == account_id:
                return a
        return None

    def add(self, account: Account):
        self._accounts.append(account)
        self.save()

    def update(self, account: Account):
        for i, a in enumerate(self._accounts):
            if a.id == account.id:
                self._accounts[i] = account
                break
        self.save()

    def remove(self, account_id: str):
        self._accounts = [a for a in self._accounts if a.id != account_id]
        self.save()

    # -------------------------------------------------------------- settings
    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.save()
