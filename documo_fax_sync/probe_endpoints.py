#!/usr/bin/env python3
"""One-off diagnostic: try several likely web addresses for listing faxes,
under both /v1 and no-prefix bases (Documo's API is inconsistent about
this), and report which one actually works.

Safe to run any time -- every request here is a read-only GET, nothing is
downloaded, saved, or changed in Documo. Uses DOCUMO_API_KEY,
DOCUMO_AUTH_HEADER, DOCUMO_AUTH_SCHEME from your .env file.

Run it with:
    .venv\\Scripts\\python probe_endpoints.py
"""
import os

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

API_KEY = os.environ.get("DOCUMO_API_KEY")
AUTH_HEADER = os.environ.get("DOCUMO_AUTH_HEADER", "Authorization")
AUTH_SCHEME = os.environ.get("DOCUMO_AUTH_SCHEME", "Basic")

BASES = ["https://api.documo.com", "https://api.documo.com/v1"]

FAX_PATHS = [
    "/fax",
    "/faxes",
    "/fax/inbox",
    "/faxes/inbox",
    "/inbox",
    "/messages",
    "/fax/messages",
    "/fax/list",
    "/fax/history",
    "/faxes/history",
]


def show(label, url, resp=None, exc=None):
    if exc is not None:
        print(f"[ERROR] {label}: {url}\n    -> {exc}\n")
        return
    preview = resp.text[:200].replace("\n", " ")
    print(f"[{resp.status_code}] {label}: {url}\n    -> {preview}\n")


def get(url, headers=None, params=None):
    try:
        return requests.get(url, headers=headers, params=params, timeout=15), None
    except requests.RequestException as exc:
        return None, exc


def main():
    if not API_KEY:
        print("ERROR: DOCUMO_API_KEY is not set in .env -- fill that in first.")
        return

    headers = {AUTH_HEADER: f"{AUTH_SCHEME} {API_KEY}".strip()}

    print("--- Sanity checks (is the server reachable? does the key work?) ---\n")

    resp, exc = get("https://api.documo.com/ping")
    show("ping (no auth)", "https://api.documo.com/ping", resp, exc)

    for base in BASES:
        url = f"{base}/me"
        resp, exc = get(url, headers=headers)
        show("my account info", url, resp, exc)

    print("--- Fax listing candidates ---\n")

    for base in BASES:
        for path in FAX_PATHS:
            url = f"{base}{path}"
            resp, exc = get(url, headers=headers, params={"direction": "inbound"})
            show("fax candidate", url, resp, exc)

    print(
        "Look for any status code that is NOT 404 -- especially on the 'my account "
        "info' lines (200 there confirms the key/auth works) and on the fax "
        "candidates (200 = found it, 401/403 = right address, needs a fix "
        "elsewhere). Paste this whole output back."
    )


if __name__ == "__main__":
    main()
