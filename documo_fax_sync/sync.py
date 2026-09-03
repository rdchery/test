#!/usr/bin/env python3
"""Pull new inbound faxes from Documo and copy them to a network share.

Run once (e.g. from cron):     python sync.py
Run continuously:               python sync.py --interval 60
"""
import argparse
import logging
import os
import re
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from documo_client import DocumoClient
from share_writer import build_share_writer_from_env
from state import ProcessedFaxState

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("documo_fax_sync")

STATE_FILE = os.environ.get("STATE_FILE", "processed_faxes.json")
FILENAME_TEMPLATE = os.environ.get("FILENAME_TEMPLATE", "{received_at}_{from_number}_{fax_id}.pdf")


def _safe(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value)) if value else "unknown"


def build_filename(fax):
    return FILENAME_TEMPLATE.format(
        fax_id=_safe(fax.get("id") or fax.get("faxId")),
        from_number=_safe(fax.get("from") or fax.get("fromNumber")),
        received_at=_safe(fax.get("receivedAt") or fax.get("createdAt") or "unknown-date"),
    )


def sync_once(client, writer, state):
    result = client.list_inbound_faxes(status="new")
    faxes = result.get("faxes") or result.get("data") or []
    log.info("Found %d inbound fax(es)", len(faxes))

    for fax in faxes:
        fax_id = fax.get("id") or fax.get("faxId")
        if fax_id is None:
            log.warning("Skipping fax with no id: %r", fax)
            continue
        if state.is_processed(fax_id):
            continue

        try:
            content = client.download_fax(fax_id)
            filename = build_filename(fax)
            dest = writer.write(filename, content)
            log.info("Saved fax %s to %s", fax_id, dest)
            client.mark_fax_read(fax_id)
            state.mark_processed(fax_id)
        except Exception:
            log.exception("Failed to process fax %s", fax_id)


def main():
    parser = argparse.ArgumentParser(
        description="Pull inbound faxes from Documo and copy them to a network share."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Seconds between polls. 0 = run once and exit (default; suitable for cron).",
    )
    args = parser.parse_args()

    client = DocumoClient()
    writer = build_share_writer_from_env()
    state = ProcessedFaxState(STATE_FILE)

    if args.interval <= 0:
        sync_once(client, writer, state)
        return

    log.info("Starting poll loop every %ss", args.interval)
    while True:
        sync_once(client, writer, state)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
