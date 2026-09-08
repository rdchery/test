#!/usr/bin/env python3
"""One-off diagnostic: try several likely web addresses for listing faxes
and report which one actually works, instead of guessing from the docs.

Safe to run any time -- every request here is a read-only GET, nothing is
downloaded, saved, or changed in Documo. Uses the same DOCUMO_API_KEY,
DOCUMO_API_BASE, DOCUMO_AUTH_HEADER, DOCUMO_AUTH_SCHEME from your .env file.

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
BASE = os.environ.get("DOCUMO_API_BASE", "https://api.documo.com").rstrip("/")
AUTH_HEADER = os.environ.get("DOCUMO_AUTH_HEADER", "Authorization")
AUTH_SCHEME = os.environ.get("DOCUMO_AUTH_SCHEME", "Basic")

CANDIDATE_PATHS = [
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


def main():
    if not API_KEY:
        print("ERROR: DOCUMO_API_KEY is not set in .env -- fill that in first.")
        return

    headers = {AUTH_HEADER: f"{AUTH_SCHEME} {API_KEY}".strip()}
    print(f"Trying {len(CANDIDATE_PATHS)} candidate addresses against {BASE} ...\n")

    for path in CANDIDATE_PATHS:
        url = f"{BASE}{path}"
        try:
            resp = requests.get(url, headers=headers, params={"direction": "inbound"}, timeout=15)
            preview = resp.text[:200].replace("\n", " ")
            print(f"[{resp.status_code}] {url}\n    -> {preview}\n")
        except requests.RequestException as exc:
            print(f"[ERROR] {url}\n    -> {exc}\n")

    print(
        "Look for a status code that is NOT 404 -- 200 means it worked, "
        "401/403 means the address is right but something else needs fixing "
        "(also useful to know). Paste this whole output back."
    )


if __name__ == "__main__":
    main()
