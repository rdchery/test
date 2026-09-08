"""Thin client for the Documo (mFax) REST API.

Endpoint paths and auth header shape are read from environment variables
so they can be corrected without touching code -- see README.md.
"""
import os

import requests

DOCUMO_API_BASE = os.environ.get("DOCUMO_API_BASE", "https://api.documo.com")
DOCUMO_API_KEY = os.environ.get("DOCUMO_API_KEY")
DOCUMO_AUTH_HEADER = os.environ.get("DOCUMO_AUTH_HEADER", "Authorization")
DOCUMO_AUTH_SCHEME = os.environ.get("DOCUMO_AUTH_SCHEME", "Basic")  # Documo's docs show "Authorization: Basic API_KEY"

# Confirmed working by live testing: GET /v1/fax/history (list, returns a
# "rows" array) and GET /v1/fax/{id}/download?format=pdf. Fax endpoints
# live under /v1/fax regardless of DOCUMO_API_BASE, so /v1 is baked into
# these paths rather than the base URL. MARK_READ_PATH is still an
# unconfirmed guess -- /v1/fax/history looks like an activity log with no
# read/unread field, so mark_fax_read() is treated as best-effort in sync.py.
LIST_PATH = os.environ.get("DOCUMO_LIST_PATH", "/v1/fax/history")
DOWNLOAD_PATH = os.environ.get("DOCUMO_DOWNLOAD_PATH", "/v1/fax/{fax_id}/download")
MARK_READ_PATH = os.environ.get("DOCUMO_MARK_READ_PATH", "/v1/fax/{fax_id}")


class DocumoClient:
    def __init__(self, api_key=None, base_url=None, session=None):
        self.api_key = api_key or DOCUMO_API_KEY
        if not self.api_key:
            raise ValueError("DOCUMO_API_KEY is not set")
        self.base_url = (base_url or DOCUMO_API_BASE).rstrip("/")
        self.session = session or requests.Session()

    def _headers(self):
        value = f"{DOCUMO_AUTH_SCHEME} {self.api_key}".strip()
        return {DOCUMO_AUTH_HEADER: value}

    def list_inbound_faxes(self, page=1, limit=50):
        # /v1/fax/history doesn't have a confirmed direction/status filter --
        # it returns fax activity generally (inbound and outbound mixed), so
        # filtering to inbound-only happens client-side in sync.py, and
        # "which ones are new" is tracked via the local state file rather
        # than any server-side unread flag.
        params = {"page": page, "limit": limit}
        resp = self.session.get(
            f"{self.base_url}{LIST_PATH}", headers=self._headers(), params=params, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def download_fax(self, fax_id):
        path = DOWNLOAD_PATH.format(fax_id=fax_id)
        resp = self.session.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params={"format": "pdf"},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.content

    def mark_fax_read(self, fax_id):
        path = MARK_READ_PATH.format(fax_id=fax_id)
        resp = self.session.patch(
            f"{self.base_url}{path}", headers=self._headers(), json={"status": "read"}, timeout=30
        )
        resp.raise_for_status()
        return resp.json()
