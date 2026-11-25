#!/usr/bin/env python3
"""php `sendmail_path` target: CAPTURE a kit's mail() instead of sending it.

DynaPD kits were de-weaponized to send credentials by email. PHP's mail() shells out to
sendmail_path; we point that at this script, which appends the full message (headers+body)
to the file named by QG_MAIL_LOG and exits 0 so the kit believes the mail was sent. Nothing
leaves the machine.
"""
import datetime
import os
import sys

log = os.environ.get("QG_MAIL_LOG", "qg_mail.log")
data = sys.stdin.buffer.read().decode("utf-8", "replace")
with open(log, "a", encoding="utf-8") as f:
    f.write(f"\n===== MAIL CAPTURED {datetime.datetime.now().isoformat()} argv={sys.argv[1:]} =====\n")
    f.write(data + "\n")
sys.exit(0)
