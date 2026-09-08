# Zendesk Parent/Child Ticket Cascade

Automates the one piece of the parent/child/related ticket structure that
Zendesk's Linked Ticket app doesn't do on its own: when a parent (core
project) ticket is marked **Solved**, this service finds its **Child of
Project** tickets and solves them too, with an internal note explaining why.
Tickets marked **Related Only** (or **Standalone**) are never touched.

```
Parent ticket -> Solved
        |
        v
   Zendesk trigger
        |
        v
   webhook POST to this service (/zendesk/parent-solved)
        |
        v
Search: custom_field_<parent> == parent id
        AND custom_field_<relationship> == child_of_project
        |
        v
For each match not already solved/closed:
  PUT /tickets/{id}  status=solved
  + private comment: "Automatically solved because Parent Ticket #<id> was solved."
```

Deliberately cascades on **Solved**, not **Closed** -- that leaves the
normal window to reopen a child before tickets close for good, and Related
Only tickets are excluded by construction (the search query only ever
matches the child relationship value).

## Setup status

- **Step 1 -- Install the Linked Ticket app.** Already done.
- **Step 2 -- Custom fields.** Still to do in Admin Center (see below);
  this service needs the two fields' numeric IDs once they exist.
- **Step 3 -- Cascading closure.** This service. Deploy it, then wire a
  Zendesk trigger + webhook to call it (see below).

## Step 2: create the two custom ticket fields

In **Admin Center -> Objects and rules -> Tickets -> Fields**:

1. **Ticket Relationship** (dropdown), options/tags:
   - `core_project`
   - `child_of_project`
   - `related_only`
   - `standalone`
2. **Parent Ticket** (lookup field, relationship: ticket -> ticket).

After creating them, open each field and copy its numeric ID from the URL
(or call `GET /api/v2/ticket_fields.json`) into `.env` as
`ZENDESK_PARENT_FIELD_ID` / `ZENDESK_RELATIONSHIP_FIELD_ID`. If you name the
dropdown option something other than `child_of_project`, set
`ZENDESK_CHILD_RELATIONSHIP_VALUE` to match its stored value (the tag, not
the display label).

## Step 3: deploy this service and wire the trigger

```bash
cd zendesk_ticket_cascade
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: Zendesk subdomain/email/API token, the two field IDs from Step 2
```

Run it:

```bash
python cascade.py                       # dev server on :5000
gunicorn cascade:app --bind 0.0.0.0:5000 # production
```

The service must be reachable by Zendesk over HTTPS (a reverse proxy /
load balancer that terminates TLS in front of it, or a tunnel like ngrok
for testing).

Then in Zendesk:

1. **Admin Center -> Apps and integrations -> Webhooks -> Create webhook.**
   - Endpoint URL: `https://<your-host>/zendesk/parent-solved`
   - Method: `POST`, format: `JSON`
   - Request body: `{"ticket_id": "{{ticket.id}}"}`
   - Copy the generated **Signing Secret** into `.env` as
     `ZENDESK_WEBHOOK_SIGNING_SECRET` -- the service verifies every request
     against it (Zendesk's documented HMAC-SHA256 scheme) and rejects
     anything that doesn't match, so don't skip this in production.
2. **Admin Center -> Objects and rules -> Business rules -> Triggers ->
   Create trigger.**
   - Conditions: `Ticket: Status` changed to `Solved`, AND
     `Ticket Relationship` is `Core Project` (so only a parent ticket's own
     solve fires the cascade, not a child solving itself).
   - Action: `Notify active webhook` -> the webhook created above.

## Tests

```bash
pytest
```

Tests cover the search query construction, pagination, the solve/skip
logic (already-solved and already-closed children are left alone), dry
run, and the webhook endpoint's signature verification -- all mocked, no
live Zendesk account or network access needed.

## Verifying against your account

This was built from Zendesk's publicly documented REST API (ticket
update, search, and webhook signing) rather than live testing, since a
Zendesk account wasn't available in this environment. Before relying on
it:

- Confirm the search query actually returns your child tickets: run
  `python -c "from zendesk_client import ZendeskClient; print(ZendeskClient().find_child_tickets(12000))"`
  against a real parent ticket ID once `.env` is filled in.
- Confirm the webhook signature check passes with a real Zendesk-sent
  request (send a test from the webhook's settings page) before requiring
  it in the trigger.
