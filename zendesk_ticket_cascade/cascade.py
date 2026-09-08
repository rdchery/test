#!/usr/bin/env python3
"""Webhook receiver that cascades a parent ticket's Solved status onto its
children -- Step 3 of the parent/child ticket-linking plan (see README.md).

A Zendesk trigger fires this receiver via a "Notify active webhook" action
when a ticket's status changes to Solved. This process then finds that
ticket's children (via the lookup field created in Step 2) and solves each
one marked "Child of Project", leaving anything marked "Related Only" (or
without the lookup field set) untouched.

Run (dev):        python cascade.py
Run (production):  gunicorn cascade:app --bind 0.0.0.0:5000
"""
import base64
import hashlib
import hmac
import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from flask import Flask, jsonify, request

from zendesk_client import ZendeskClient

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("zendesk_ticket_cascade")

WEBHOOK_SIGNING_SECRET = os.environ.get("ZENDESK_WEBHOOK_SIGNING_SECRET")

app = Flask(__name__)


def verify_signature(req):
    """Verify the request came from Zendesk using the webhook's signing
    secret, per Zendesk's documented HMAC-SHA256 scheme:
    https://developer.zendesk.com/documentation/webhooks/verifying/

    With no signing secret configured this allows every request through
    (useful for local testing) -- set ZENDESK_WEBHOOK_SIGNING_SECRET before
    exposing this endpoint to the internet.
    """
    if not WEBHOOK_SIGNING_SECRET:
        log.warning("ZENDESK_WEBHOOK_SIGNING_SECRET not set -- skipping signature verification")
        return True

    signature = req.headers.get("X-Zendesk-Webhook-Signature")
    timestamp = req.headers.get("X-Zendesk-Webhook-Signature-Timestamp")
    if not signature or not timestamp:
        return False

    message = timestamp.encode("utf-8") + req.get_data()
    expected = base64.b64encode(
        hmac.new(WEBHOOK_SIGNING_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def cascade_solve(client, parent_ticket_id, dry_run=False):
    """Solve every Child-of-Project ticket linked to parent_ticket_id that
    isn't already solved/closed. Returns the list of ticket IDs that were
    (or, in dry_run, would be) solved.
    """
    children = client.find_child_tickets(parent_ticket_id)
    solved = []
    for child in children:
        child_id = child.get("id")
        if child.get("status") in ("solved", "closed"):
            continue
        note = f"Automatically solved because Parent Ticket #{parent_ticket_id} was solved."
        if dry_run:
            log.info("[DRY RUN] Would solve child ticket %s: %s", child_id, note)
        else:
            client.solve_ticket_with_note(child_id, note)
            log.info("Solved child ticket %s (parent %s)", child_id, parent_ticket_id)
        solved.append(child_id)
    return solved


@app.route("/zendesk/parent-solved", methods=["POST"])
def parent_solved():
    if not verify_signature(request):
        log.warning("Rejected webhook call with invalid/missing signature")
        return jsonify({"error": "invalid signature"}), 401

    payload = request.get_json(silent=True) or {}
    parent_ticket_id = payload.get("ticket_id") or payload.get("id")
    if not parent_ticket_id:
        return jsonify({"error": "missing ticket_id"}), 400

    client = ZendeskClient()
    solved = cascade_solve(client, parent_ticket_id)
    return jsonify({"parent_ticket_id": parent_ticket_id, "solved_children": solved})


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
