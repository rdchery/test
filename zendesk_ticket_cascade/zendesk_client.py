"""Thin client for the Zendesk Support REST API (ticket search + update).

Auth uses Zendesk's documented email/token Basic auth:
https://developer.zendesk.com/api-reference/introduction/security-and-auth/
    Authorization: Basic base64("{email}/token:{api_token}")

The "Parent Ticket" lookup field and "Ticket Relationship" dropdown field
are account-specific -- they only exist once you've created them per Step 2
of the ticket-linking plan (see README.md), so their numeric IDs are read
from environment variables rather than hardcoded.
"""
import os

import requests

ZENDESK_SUBDOMAIN = os.environ.get("ZENDESK_SUBDOMAIN")
ZENDESK_EMAIL = os.environ.get("ZENDESK_EMAIL")
ZENDESK_API_TOKEN = os.environ.get("ZENDESK_API_TOKEN")

# Numeric field IDs from Admin Center -> Objects and rules -> Tickets ->
# Fields, or GET /api/v2/ticket_fields.json -- see README.md Step 2.
PARENT_FIELD_ID = os.environ.get("ZENDESK_PARENT_FIELD_ID")
RELATIONSHIP_FIELD_ID = os.environ.get("ZENDESK_RELATIONSHIP_FIELD_ID")
# Default matches the tag actually configured on the Ticket Relationship
# field's "Child of Ticket / Project" option -- see README.md Step 2.
CHILD_RELATIONSHIP_VALUE = os.environ.get(
    "ZENDESK_CHILD_RELATIONSHIP_VALUE", "child_of_ticket_/_project"
)


class ZendeskClient:
    def __init__(self, subdomain=None, email=None, api_token=None, session=None):
        self.subdomain = subdomain or ZENDESK_SUBDOMAIN
        self.email = email or ZENDESK_EMAIL
        self.api_token = api_token or ZENDESK_API_TOKEN
        if not (self.subdomain and self.email and self.api_token):
            raise ValueError("ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_API_TOKEN must all be set")
        self.base_url = f"https://{self.subdomain}.zendesk.com/api/v2"
        self.session = session or requests.Session()

    def _auth(self):
        return (f"{self.email}/token", self.api_token)

    def find_child_tickets(self, parent_ticket_id, parent_field_id=None, relationship_field_id=None,
                            child_value=None):
        """Tickets whose lookup field points at parent_ticket_id and whose
        relationship field marks them as a child.

        Uses Zendesk's Search API with the documented custom_field_{id}:value
        query syntax:
        https://developer.zendesk.com/api-reference/ticketing/ticket-management/search/
        """
        parent_field_id = parent_field_id or PARENT_FIELD_ID
        relationship_field_id = relationship_field_id or RELATIONSHIP_FIELD_ID
        child_value = child_value or CHILD_RELATIONSHIP_VALUE
        if not parent_field_id:
            raise ValueError("ZENDESK_PARENT_FIELD_ID is not set")

        # Values are quoted so punctuation in a tag (e.g. the "/" in
        # "child_of_ticket_/_project") can't be misread as query syntax.
        query = f'type:ticket custom_field_{parent_field_id}:"{parent_ticket_id}"'
        if relationship_field_id:
            query += f' custom_field_{relationship_field_id}:"{child_value}"'

        results = []
        url = f"{self.base_url}/search.json"
        params = {"query": query}
        while url:
            resp = self.session.get(url, auth=self._auth(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
            url = data.get("next_page")
            params = None  # next_page is already a full URL with query params baked in
        return results

    def solve_ticket_with_note(self, ticket_id, note):
        """Set status to solved and add a private (internal) comment in one call.
        https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/#update-ticket
        """
        resp = self.session.put(
            f"{self.base_url}/tickets/{ticket_id}.json",
            auth=self._auth(),
            json={"ticket": {"status": "solved", "comment": {"body": note, "public": False}}},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
