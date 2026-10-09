"""Demo mailbox: a fake account with realistic messages for --demo mode."""

import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from .config import Account
from .protocols.common import MessageMeta, parse_address_field


def _build_raw(from_name, from_addr, to, subject, when, plain=None,
               html=None, cc="", attachments=None, in_reply_to=""):
    msg = EmailMessage()
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = formatdate(when)
    msg["Message-ID"] = make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    msg.set_content(plain or "")
    if html:
        msg.add_alternative(html, subtype="html")
    for name, data, mime in (attachments or []):
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype,
                           filename=name)
    return msg.as_bytes()


def _meta(uid, from_name, from_addr, to, subject, when, raw, cc="",
          unread=False, flagged=False, importance="", attachment=False):
    return MessageMeta(
        uid=uid,
        msgid=f"<{uid}@demo.local>",
        from_name=from_name,
        from_addr=from_addr,
        to_addr=parse_address_field(to),
        cc_addr=parse_address_field(cc),
        subject=subject,
        date_ts=int(when.timestamp()),
        size=len(raw),
        is_read=not unread,
        is_flagged=flagged,
        has_attachment=attachment,
        importance=importance,
    )


def _html_doc(inner):
    return (
        "<html><body style=\"font-family:Segoe UI,Arial,sans-serif;"
        "font-size:14px;color:#333;\">"
        f"{inner}</body></html>"
    )


def populate_demo(config, store, now=None):
    """Create a demo account and messages; returns the account."""
    now = now or datetime.now()
    acc = Account.new(
        name="Alex Morgan",
        email="alex.morgan@outlook-demo.com",
        protocol="imap",
        username="alex.morgan@outlook-demo.com",
        password="demo",
        imap_host="imap.outlook-demo.com",
        smtp_host="smtp.outlook-demo.com",
    )
    config._accounts.append(acc)

    inbox = [
        dict(
            from_name="Sara Chen", from_addr="sara.chen@northwind.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Q3 report — final numbers attached",
            plain=(
                "Hi Alex,\n\n"
                "The Q3 numbers are final. Revenue came in 4.2% above "
                "forecast and churn is down for the third month in a row.\n\n"
                "The full report is attached — please review the "
                "margin analysis on page 12 before Thursday's call.\n\n"
                "Thanks,\nSara\n"),
            unread=True, flagged=True, importance="high",
            attachments=[("Q3-financial-report.pdf",
                          b"%PDF-1.4\n% demo placeholder PDF payload\n" * 8,
                          "application/pdf")],
            hours=1.2,
        ),
        dict(
            from_name="Northwind IT", from_addr="it-helpdesk@northwind.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Scheduled maintenance: mail servers this Saturday",
            plain=("Hello,\n\n"
                   "Mail infrastructure maintenance is scheduled for "
                   "Saturday 02:00-04:00 UTC. Brief interruptions may "
                   "occur.\n\n-- Northwind IT"),
            unread=True, hours=4,
        ),
        dict(
            from_name="Marcus Webb", from_addr="marcus.webb@northwind.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            cc="team-leads@northwind.example",
            subject="Re: Kickoff agenda for Atlas rollout",
            plain=("Alex,\n\n"
                   "Agenda looks good. Could we add 10 minutes for the "
                   "migration risk review? I want ops to walk through the "
                   "cutover plan.\n\n"
                   "Marcus"),
            unread=True, hours=7,
        ),
        dict(
            from_name="Contoso Travel", from_addr="bookings@contoso-travel.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Your itinerary: JNB → CPT, 14 Oct (Confirmation "
                    "CT-8849123)",
            html=_html_doc(
                "<h2 style='color:#0f6cbd;'>Trip confirmed</h2>"
                "<p><b>Flight CT 214</b> — JNB 07:15 → CPT 09:20</p>"
                "<p>Seat 14C · Economy Plus · 1 checked bag</p>"
                "<table cellpadding='6' border='1' style='border-collapse:collapse;'>"
                "<tr><td><b>Outbound</b></td><td>Tue, 14 Oct 07:15</td></tr>"
                "<tr><td><b>Return</b></td><td>Thu, 16 Oct 18:45</td></tr>"
                "</table>"
                "<p style='color:#666;'>Manage your booking online.</p>"),
            hours=26,
        ),
        dict(
            from_name="Priya Nair", from_addr="priya.nair@northwind.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Design review notes + updated mockups",
            plain=("Hi Alex,\n\n"
                   "Notes from yesterday's review:\n\n"
                   "1. Reading pane default should be 'bottom'\n"
                   "2. Unread rows need stronger contrast\n"
                   "3. Ribbon groups: keep to 4 max\n\n"
                   "Updated mockups are in the shared drive.\n\n"
                   "Priya"),
            attachments=[("mockup-v3.png",
                          b"\x89PNG\r\n\x1a\n demo-image-bytes" * 4,
                          "image/png")],
            hours=29,
        ),
        dict(
            from_name="LinkedIn", from_addr="notifications@linkedin.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="You appeared in 12 searches this week",
            plain=("See who's looking for people like you.\n\n"
                   "- 12 searches\n"
                   "- 4 profile views\n"
                   "- 1 intro request"),
            hours=50,
        ),
        dict(
            from_name="Finance Dept", from_addr="expenses@northwind.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Expense report EXP-2291 approved",
            plain=("Your expense report EXP-2291 (R 4,280.00) has been "
                   "approved and will be paid in the next cycle.\n"),
            importance="high", hours=53,
        ),
        dict(
            from_name="GitHub", from_addr="noreply@github.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="[atlas-platform] CI failed on main (build #1842)",
            html=_html_doc(
                "<p><b>atlas-platform / build</b> failed on <code>main</code></p>"
                "<pre style='background:#f4f4f4;padding:10px;'>"
                "ERROR  test_sync.py::test_uid_validity — assert 0 != 0"
                "</pre>"
                "<p><a href='https://example.com/build/1842'>View build</a></p>"),
            unread=True, hours=56,
        ),
        dict(
            from_name="Dana Fischer", from_addr="dana.fischer@partner.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Lunch next week?",
            plain=("Hi Alex,\n\n"
                   "Are you free Tuesday or Wednesday for lunch? "
                   "I'd love to hear how the Atlas rollout is going.\n\n"
                   "Dana"),
            flagged=True, hours=74,
        ),
        dict(
            from_name="The Daily Byte", from_addr="editors@dailybyte.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Why desktop email clients are having a comeback",
            plain=("Plus: IMAP at 30, the quiet return of local-first "
                   "software, and this week's security advisories.\n"),
            hours=98,
        ),
        dict(
            from_name="HR Team", from_addr="people@northwind.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Reminder: submit timesheets by Friday 16:00",
            plain=("Hi all,\n\nFriendly reminder to submit your timesheets "
                   "before Friday at 16:00.\n\nThank you,\nPeople Team"),
            hours=122,
        ),
        dict(
            from_name="Cloud Notification", from_addr="billing@cloudmesh.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Your September invoice is ready (INV-9931)",
            plain=("Invoice INV-9931 for R 1,152.40 is available.\n"
                   "Payment is due 20 October.\n"),
            hours=150,
        ),
        dict(
            from_name="Sara Chen", from_addr="sara.chen@northwind.example",
            to="Alex Morgan <alex.morgan@outlook-demo.com>",
            subject="Re: Offsite planning — dates that work?",
            plain=("Works for me. Let's avoid the last week of the month.\n\n"
                   "Sara"),
            hours=170,
        ),
        dict(
            from_name="Security Team", from_addr="security@northwind.example",
            to="all-staff@northwind.example",
            subject="Phishing awareness: verify unexpected attachments",
            plain=("Colleagues,\n\n"
                   "We've seen a rise in targeted phishing. Remember: "
                   "unexpected attachments and shortened links should be "
                   "verified with the sender first.\n\n"
                   "Report suspicious mail to phishing@northwind.example\n"),
            unread=True, importance="high", hours=196,
        ),
    ]

    rows = []
    now_dt = datetime.now()

    def add(folder, meta, raw):
        rows.append((folder, meta, raw))

    # ------------------------------------------------------------- inbox
    for i, item in enumerate(inbox):
        when = now_dt - timedelta(hours=item.get("hours", 10))
        raw = _build_raw(
            item["from_name"], item["from_addr"], item["to"],
            item["subject"], when.timestamp(),
            plain=item.get("plain"), html=item.get("html"),
            cc=item.get("cc", ""), attachments=item.get("attachments"))
        meta = _meta(
            uid=str(1000 + i),
            from_name=item["from_name"], from_addr=item["from_addr"],
            to=item["to"], subject=item["subject"], when=when, raw=raw,
            cc=item.get("cc", ""), unread=item.get("unread", False),
            flagged=item.get("flagged", False),
            importance=item.get("importance", ""),
            attachment=bool(item.get("attachments")))
        add("INBOX", meta, raw)

    # -------------------------------------------------------------- sent
    sent_items = [
        ("Marcus Webb", "marcus.webb@northwind.example",
         "Kickoff agenda for Atlas rollout",
         "Marcus,\n\nAgenda attached. I've pencilled in Wednesday 10:00 "
         "for the kickoff. Add the migration risk review as agreed.\n\nAlex",
         8, False),
        ("Sara Chen", "sara.chen@northwind.example",
         "Re: Q3 report — final numbers attached",
         "Thanks Sara — reviewing now. I'll have comments before "
         "Thursday.\n\nAlex", 5, False),
        ("Priya Nair", "priya.nair@northwind.example",
         "Design review: confirmed attendees",
         "Confirmed — count me in. See you at 14:00.\n\nAlex", 30, False),
        ("Dana Fischer", "dana.fischer@partner.example",
         "Re: Lunch next week?",
         "Wednesday works. The bistro around the corner from your office?\n\nAlex",
         70, False),
    ]
    for i, (name, addr, subject, body, hours, _x) in enumerate(sent_items):
        when = now_dt - timedelta(hours=hours)
        raw = _build_raw("Alex Morgan", "alex.morgan@outlook-demo.com",
                         f"{name} <{addr}>", subject, when.timestamp(),
                         plain=body)
        meta = _meta(uid=f"s{2000 + i}", from_name="Alex Morgan",
                     from_addr="alex.morgan@outlook-demo.com",
                     to=f"{name} <{addr}>", subject=subject, when=when,
                     raw=raw)
        add("Sent", meta, raw)

    # ------------------------------------------------------------ drafts
    draft_items = [
        ("team-leads@northwind.example",
         "Atlas rollout — weekly status",
         "Team,\n\nQuick status: migration scripts are 80% done, "
         "cutover rehearsal is scheduled for...\n\n", 3),
        ("", "Ideas for the offsite",
         "- Local-first tooling session\n- Lightning talks\n- "
         "Vendor roadmap deep-dive\n\n", 22),
    ]
    for i, (to, subject, body, hours) in enumerate(draft_items):
        when = now_dt - timedelta(hours=hours)
        raw = _build_raw("Alex Morgan", "alex.morgan@outlook-demo.com",
                         to, subject, when.timestamp(), plain=body)
        meta = _meta(uid=f"d{3000 + i}", from_name="Alex Morgan",
                     from_addr="alex.morgan@outlook-demo.com",
                     to=to, subject=subject, when=when, raw=raw)
        add("Drafts", meta, raw)

    # ------------------------------------------------------------- trash
    for i, (name, addr, subject, hours) in enumerate([
        ("Promo Deals", "deals@megastore.example",
         "48 hours only — 70% off everything!", 20),
        ("Unknown", "no-reply@random.example",
         "RE: RE: RE: your package is held", 44),
    ]):
        when = now_dt - timedelta(hours=hours)
        raw = _build_raw(name, addr,
                         "Alex Morgan <alex.morgan@outlook-demo.com>",
                         subject, when.timestamp(), plain=" promotional ")
        meta = _meta(uid=f"t{4000 + i}", from_name=name, from_addr=addr,
                     to="alex.morgan@outlook-demo.com", subject=subject,
                     when=when, raw=raw)
        add("Trash", meta, raw)

    # -------------------------------------------------------------- junk
    when = now_dt - timedelta(hours=60)
    raw = _build_raw("Prize Center", "win@prizesc.example",
                     "alex.morgan@outlook-demo.com",
                     "You've WON a R5,000 gift card!",
                     when.timestamp(),
                     plain="Click here to claim your prize now!!!")
    meta = _meta(uid="j5000", from_name="Prize Center",
                 from_addr="win@prizesc.example",
                 to="alex.morgan@outlook-demo.com",
                 subject="You've WON a R5,000 gift card!", when=when,
                 raw=raw, unread=True)
    add("Junk", meta, raw)

    # ----------------------------------------------------- custom folder
    for i, (subject, body, hours) in enumerate([
        ("Q3 report — outline",
         "Outline for the Q3 deck:\n1. Revenue\n2. Costs\n3. "
         "Risks\n4. Outlook\n", 100),
        ("Margin analysis data",
         "Raw margins by product line for the quarter.\n", 96),
        ("Board pack — checklist", "- Financials\n- Ops metrics\n- "
         "People update\n", 90),
    ]):
        when = now_dt - timedelta(hours=hours)
        raw = _build_raw("Alex Morgan", "alex.morgan@outlook-demo.com",
                         "alex.morgan@outlook-demo.com", subject,
                         when.timestamp(), plain=body)
        meta = _meta(uid=f"p{6000 + i}", from_name="Alex Morgan",
                     from_addr="alex.morgan@outlook-demo.com",
                     to="alex.morgan@outlook-demo.com", subject=subject,
                     when=when, raw=raw)
        add("Projects/Q3 Report", meta, raw)

    # ------------------------------------------------------------- store
    folder_names = {
        "INBOX": ("Inbox", "inbox"),
        "Sent": ("Sent Items", "sent"),
        "Drafts": ("Drafts", "drafts"),
        "Trash": ("Deleted Items", "trash"),
        "Junk": ("Junk Email", "junk"),
        "Projects/Q3 Report": ("Q3 Report", "custom"),
    }
    for path, (name, role) in folder_names.items():
        store.upsert_folder(acc.id, path, name, role)
    by_folder = {}
    for folder, meta, raw in rows:
        by_folder.setdefault(folder, []).append((meta, raw))
    for folder, items in by_folder.items():
        store.apply_sync(acc.id, folder, [m for m, _r in items])
        for meta, raw in items:
            store.set_raw(acc.id, folder, meta.uid, raw)
    return acc
