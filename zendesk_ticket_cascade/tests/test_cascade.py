import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cascade
from cascade import cascade_solve


def _sign(secret, timestamp, body):
    message = timestamp.encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_cascade_solve_skips_already_solved_and_closed():
    client = MagicMock()
    client.find_child_tickets.return_value = [
        {"id": 1, "status": "open"},
        {"id": 2, "status": "solved"},
        {"id": 3, "status": "closed"},
        {"id": 4, "status": "pending"},
    ]

    solved = cascade_solve(client, parent_ticket_id=100)

    assert solved == [1, 4]
    assert client.solve_ticket_with_note.call_count == 2
    client.solve_ticket_with_note.assert_any_call(
        1, "Automatically solved because Parent Ticket #100 was solved."
    )


def test_cascade_solve_dry_run_touches_nothing():
    client = MagicMock()
    client.find_child_tickets.return_value = [{"id": 1, "status": "open"}]

    solved = cascade_solve(client, parent_ticket_id=100, dry_run=True)

    assert solved == [1]
    client.solve_ticket_with_note.assert_not_called()


def test_cascade_solve_no_children():
    client = MagicMock()
    client.find_child_tickets.return_value = []
    assert cascade_solve(client, parent_ticket_id=100) == []


def test_endpoint_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(cascade, "WEBHOOK_SIGNING_SECRET", "shh")
    test_client = cascade.app.test_client()

    resp = test_client.post("/zendesk/parent-solved", json={"ticket_id": 100})

    assert resp.status_code == 401


def test_endpoint_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(cascade, "WEBHOOK_SIGNING_SECRET", "shh")
    test_client = cascade.app.test_client()

    resp = test_client.post(
        "/zendesk/parent-solved",
        json={"ticket_id": 100},
        headers={
            "X-Zendesk-Webhook-Signature": "bad",
            "X-Zendesk-Webhook-Signature-Timestamp": "2026-01-01T00:00:00Z",
        },
    )

    assert resp.status_code == 401


def test_endpoint_solves_children_with_valid_signature(monkeypatch):
    secret = "shh"
    monkeypatch.setattr(cascade, "WEBHOOK_SIGNING_SECRET", secret)
    body = json.dumps({"ticket_id": 100}).encode("utf-8")
    timestamp = "2026-01-01T00:00:00Z"
    signature = _sign(secret, timestamp, body)

    fake_client = MagicMock()
    fake_client.find_child_tickets.return_value = [{"id": 1, "status": "open"}]

    with patch.object(cascade, "ZendeskClient", return_value=fake_client):
        test_client = cascade.app.test_client()
        resp = test_client.post(
            "/zendesk/parent-solved",
            data=body,
            content_type="application/json",
            headers={
                "X-Zendesk-Webhook-Signature": signature,
                "X-Zendesk-Webhook-Signature-Timestamp": timestamp,
            },
        )

    assert resp.status_code == 200
    assert resp.get_json() == {"parent_ticket_id": 100, "solved_children": [1]}
    fake_client.solve_ticket_with_note.assert_called_once_with(
        1, "Automatically solved because Parent Ticket #100 was solved."
    )


def test_endpoint_missing_ticket_id(monkeypatch):
    monkeypatch.setattr(cascade, "WEBHOOK_SIGNING_SECRET", None)
    test_client = cascade.app.test_client()

    resp = test_client.post("/zendesk/parent-solved", json={})

    assert resp.status_code == 400


def test_healthz():
    resp = cascade.app.test_client().get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
