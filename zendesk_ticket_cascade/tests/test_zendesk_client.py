import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zendesk_client import ZendeskClient


def _client():
    return ZendeskClient(subdomain="acme", email="agent@acme.com", api_token="tok", session=MagicMock())


def test_find_child_tickets_builds_query_with_both_fields():
    client = _client()
    client.session.get.return_value.json.return_value = {"results": [{"id": 1}], "next_page": None}

    results = client.find_child_tickets(
        parent_ticket_id=12000,
        parent_field_id="111",
        relationship_field_id="222",
        child_value="child_of_ticket_/_project",
    )

    assert results == [{"id": 1}]
    called_url, kwargs = client.session.get.call_args
    assert called_url[0] == "https://acme.zendesk.com/api/v2/search.json"
    assert kwargs["params"]["query"] == (
        'type:ticket custom_field_111:"12000" custom_field_222:"child_of_ticket_/_project"'
    )
    assert kwargs["auth"] == ("agent@acme.com/token", "tok")


def test_find_child_tickets_paginates():
    client = _client()
    page1 = {"results": [{"id": 1}], "next_page": "https://acme.zendesk.com/api/v2/search.json?page=2"}
    page2 = {"results": [{"id": 2}], "next_page": None}
    client.session.get.return_value.json.side_effect = [page1, page2]

    results = client.find_child_tickets(parent_ticket_id=12000, parent_field_id="111")

    assert results == [{"id": 1}, {"id": 2}]
    assert client.session.get.call_count == 2


def test_find_child_tickets_requires_parent_field_id():
    client = _client()
    try:
        client.find_child_tickets(parent_ticket_id=12000, parent_field_id=None)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_solve_ticket_with_note_sends_status_and_private_comment():
    client = _client()

    client.solve_ticket_with_note(42, "done")

    called_url, kwargs = client.session.put.call_args
    assert called_url[0] == "https://acme.zendesk.com/api/v2/tickets/42.json"
    assert kwargs["json"] == {"ticket": {"status": "solved", "comment": {"body": "done", "public": False}}}
