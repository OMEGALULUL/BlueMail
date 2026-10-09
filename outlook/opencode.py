"""Integration with the opencode CLI for AI-assisted email replies.

Runs ``opencode run <prompt>`` headlessly in a non-interactive shell and
returns the generated text, so BlueMail can draft reply bodies on demand.

The three supported modes:

* ``quick``  — short, ready-to-send reply to the selected email
* ``think``  — a longer, well-considered response for copy & paste
* ``power``  — write what you want to say (and to whom) in your own words
"""

import re
import shutil
import subprocess

ANSI_ESC = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
META_LINE = re.compile(r"^>\s.*$", re.MULTILINE)
MAX_OUTPUT = 8000

DOWNLOAD_URL = "https://opencode.ai"


def opencode_path():
    """Absolute path to the opencode executable, or None if not found."""
    try:
        return shutil.which("opencode")
    except Exception:
        return None


def is_installed() -> bool:
    """Return True when the opencode CLI is available on PATH."""
    return opencode_path() is not None


def _context(message) -> str:
    if not message:
        return "Context: no email is selected — write the reply generically."
    sender = message.get("from_display") or message.get("from_addr") or "the sender"
    addr = message.get("from_addr") or ""
    subject = message.get("subject") or "(no subject)"
    lines = [f"Context — email from {sender}"]
    if addr:
        lines.append(f"Reply-to address: {addr}")
    lines.append(f"Subject: {subject}")
    return "\n".join(lines)


def build_prompt(mode, message=None, instruction="", target=""):
    """Build the prompt that will be handed to ``opencode run``."""
    ctx = _context(message)
    if mode == "quick":
        return (
            "You are a concise email assistant. Write a SHORT, friendly reply "
            "(2-4 sentences) to the email below. Match the tone of the sender.\n\n"
            f"{ctx}\n\n"
            'Reply with ONLY the email body text — no "Subject:", no greeting, '
            "no signature."
        )
    if mode == "think":
        return (
            "You are a thoughtful email assistant. Write a well-considered, "
            "human response to the email below. Acknowledge every point, ask "
            "one useful question if anything is ambiguous, and keep it "
            "polished but natural.\n\n"
            f"{ctx}\n\n"
            "Reply with ONLY the email body text — no signature."
        )
    if mode == "power":
        recipient = target.strip() if target else ""
        if not recipient and message:
            recipient = (message.get("from_addr") or "").strip()
        if not recipient:
            recipient = "the sender"
        if not instruction.strip():
            raise ValueError("instruction must not be empty")
        return (
            "You are a writing assistant. Compose an email for the recipient "
            "that expresses the following instruction naturally and briefly.\n\n"
            f"Recipient: {recipient}\n"
            f'What I want to say: "{instruction.strip()}"\n\n'
            "Reply with ONLY the email body text — no signature."
        )
    raise ValueError(f"unknown mode: {mode!r}")


def run(prompt, timeout=300):
    """Run ``opencode run`` with the given prompt and return its output.

    Raises RuntimeError when opencode is missing, fails, or returns nothing.
    """
    exe = opencode_path()
    if not exe:
        raise RuntimeError(
            "opencode is not installed — download it from " + DOWNLOAD_URL
        )
    proc = subprocess.run(
        [exe, "run", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = ANSI_ESC.sub("", proc.stdout or "")
    out = META_LINE.sub("", out).strip()
    if proc.returncode == 0 and out:
        return out[:MAX_OUTPUT]
    err = (proc.stderr or "").strip()
    raise RuntimeError(err or "opencode returned no output")