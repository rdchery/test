"""Thin client for the Documo (mFax) REST API.

Endpoint paths and auth header shape are read from environment variables
so they can be corrected without touching code -- see README.md.
"""
import os

import requests

DOCUMO_API_BASE = os.environ.get("DOCUMO_API_BASE", "https://api.documo.com/v1")
DOCUMO_API_KEY = os.environ.get("DOCUMO_API_KEY")
DOCUMO_AUTH_HEADER = os.environ.get("DOCUMO_AUTH_HEADER", "Authorization")
DOCUMO_AUTH_SCHEME = os.environ.get("DOCUMO_AUTH_SCHEME", "")  # e.g. "Bearer", or "" for a raw key

LIST_PATH = os.environ.get("DOCUMO_LIST_PATH", "/fax")
DOWNLOAD_PATH = os.environ.get("DOCUMO_DOWNLOAD_PATH", "/fax/{fax_id}/download")
MARK_READ_PATH = os.environ.get("DOCUMO_MARK_READ_PATH", "/fax/{fax_id}")


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

    def list_inbound_faxes(self, status="new", page=1, limit=50):
        params = {"direction": "inbound", "status": status, "page": page, "limit": limit}
        resp = self.session.get(
            f"{self.base_url}{LIST_PATH}", headers=self._headers(), params=params, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def download_fax(self, fax_id):
        path = DOWNLOAD_PATH.format(fax_id=fax_id)
        resp = self.session.get(f"{self.base_url}{path}", headers=self._headers(), timeout=60)
        resp.raise_for_status()
        return resp.content

    def mark_fax_read(self, fax_id):
        path = MARK_READ_PATH.format(fax_id=fax_id)
        resp = self.session.patch(
            f"{self.base_url}{path}", headers=self._headers(), json={"status": "read"}, timeout=30
        )
        resp.raise_for_status()
        return resp.json()
