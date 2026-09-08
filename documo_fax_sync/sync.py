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
    # Field names confirmed from Documo's "Fax Inbound" webhook payload
    # (messageId / faxNumber / createdAt); id/from/receivedAt kept as
    # fallbacks in case the list endpoint's shape differs slightly.
    return FILENAME_TEMPLATE.format(
        fax_id=_safe(fax.get("messageId") or fax.get("id") or fax.get("faxId")),
        from_number=_safe(fax.get("faxNumber") or fax.get("from") or fax.get("fromNumber")),
        received_at=_safe(
            fax.get("createdAt") or fax.get("receivedAt") or "unknown-date"
        ),
    )


def _is_inbound(fax):
    # /v1/fax/history marks direction via "classificationLabel" (confirmed
    # live); older assumption was "direction". Treat unknown/missing as
    # inbound rather than silently dropping faxes, only exclude a fax
    # that's explicitly marked outbound.
    value = fax.get("classificationLabel") or fax.get("direction")
    return value != "outbound"


def sync_once(client, writer, state, dry_run=False, mark_as_read=True):
    result = client.list_inbound_faxes()
    all_faxes = result.get("rows") or result.get("faxes") or result.get("data") or []
    faxes = [f for f in all_faxes if _is_inbound(f)]
    log.info("Found %d inbound fax(es) (%d total returned)", len(faxes), len(all_faxes))

    for fax in faxes:
        fax_id = fax.get("messageId") or fax.get("id") or fax.get("faxId")
        if fax_id is None:
            log.warning("Skipping fax with no id: %r", fax)
            continue
        if state.is_processed(fax_id):
            continue

        if dry_run:
            log.info("[DRY RUN] Would save fax %s as %s (nothing written, nothing marked read)",
                      fax_id, build_filename(fax))
            continue

        try:
            content = client.download_fax(fax_id)
            filename = build_filename(fax)
            dest = writer.write(filename, content)
            log.info("Saved fax %s to %s", fax_id, dest)
        except Exception:
            log.exception("Failed to process fax %s", fax_id)
            continue

        # Saved successfully -- record that now, so a re-run never re-saves
        # this fax even if the still-unconfirmed mark-as-read call below
        # fails. Documo's own read/unread flag for this endpoint is
        # unconfirmed; treat marking it as best-effort, not required.
        state.mark_processed(fax_id)
        if mark_as_read:
            try:
                client.mark_fax_read(fax_id)
            except Exception:
                log.warning("Saved fax %s but could not mark it read in Documo", fax_id, exc_info=True)


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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Connect to Documo and list new faxes only. Downloads nothing, writes nothing, "
        "marks nothing as read. Doesn't even need SHARE_DIR/SMB settings. Safe first test "
        "of the API key.",
    )
    args = parser.parse_args()

    mark_as_read = os.environ.get("MARK_AS_READ", "true").strip().lower() not in ("false", "0", "no")

    client = DocumoClient()
    writer = None if args.dry_run else build_share_writer_from_env()
    state = ProcessedFaxState(STATE_FILE)

    if args.interval <= 0:
        sync_once(client, writer, state, dry_run=args.dry_run, mark_as_read=mark_as_read)
        return

    log.info("Starting poll loop every %ss", args.interval)
    while True:
        sync_once(client, writer, state, dry_run=args.dry_run, mark_as_read=mark_as_read)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
