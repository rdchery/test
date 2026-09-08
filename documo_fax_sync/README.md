# Documo Fax -> Network Share Sync

Polls the Documo (mFax) API for new inbound faxes, downloads each one, and
copies it to a folder on a network share. Already-copied faxes are tracked
in a local state file so re-runs never duplicate a file.

**Setting this up on a Windows Server, step by step (no coding involved)?
See [`WINDOWS_SETUP.md`](WINDOWS_SETUP.md) instead of this file.** The rest
of this README is the technical reference / Linux instructions.

## API endpoints -- confirmed vs. still-unverified

This was built without direct access to Documo's docs during development
(`docs.documo.com` was blocked by this environment's network egress proxy),
so the endpoints below were pinned down through live testing against a real
account rather than by reading the docs directly.

**Confirmed working, by an actual successful call:**

- Base URL: `https://api.documo.com` (note: Documo is inconsistent about a
  `/v1` prefix -- some endpoints have it, some don't; fax endpoints do, and
  that's baked into the paths below rather than into the base URL)
- Auth: `Authorization: Basic <api_key>` -- the literal word `Basic`, not
  `Bearer`, and not standard HTTP Basic auth (no base64, no colon/password)
- `GET /v1/fax/history` -- returns fax activity as `{"rows": [...]}`. No
  confirmed server-side filter for inbound-only or unread-only, so
  `sync.py` filters to inbound client-side (via `classificationLabel`) and
  tracks "already saved" itself via the local state file rather than
  trusting a read/unread flag from Documo.
- `GET /v1/fax/{id}/download?format=pdf` -- downloads a fax's PDF
- Fax record field names: `messageId`, `faxNumber`, `createdAt`,
  `classificationLabel` (`"inbound"`/`"outbound"`)

**Still an unverified guess:**

- `PATCH /v1/fax/{id}` to mark a fax as read (`DOCUMO_MARK_READ_PATH`).
  `/v1/fax/history` looks like an activity log with no obvious read/unread
  field, so this may not even be the right concept for this endpoint. To
  stay safe, `sync.py` treats it as best-effort: a failure here is logged
  as a warning but never blocks the fax from being saved or tracked as
  processed (see `sync_once()` in `sync.py`).

If you confirm or need to change any of this, everything above is a config
value, not a code change:

- Endpoint paths: `DOCUMO_LIST_PATH`, `DOCUMO_DOWNLOAD_PATH`, `DOCUMO_MARK_READ_PATH`
- Auth shape: `DOCUMO_AUTH_HEADER`, `DOCUMO_AUTH_SCHEME`
- Response field names: edit `build_filename()`, `_is_inbound()`, and the
  `all_faxes = ...` line in `sync.py`

## Setup

```bash
cd documo_fax_sync
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set DOCUMO_API_KEY and either SHARE_DIR or the SMB_* variables
```

### Destination

- **Mounted share (default, recommended when available):** set `SHARE_DIR`
  to a path already mounted on this host -- a Windows mapped drive/UNC
  path, or a Linux `mount -t cifs ...` / NFS mount point.
- **Direct SMB write:** if this process can't have the share mounted
  (e.g. a container), set `SMB_HOST`, `SMB_SHARE`, `SMB_USERNAME`,
  `SMB_PASSWORD` instead -- it connects over SMB directly via
  `smbprotocol`, no OS mount needed. `SMB_HOST` takes priority over
  `SHARE_DIR` when both are set.

## Running

One-shot (for cron / Task Scheduler):

```bash
python sync.py
```

Continuous polling loop (every 60s):

```bash
python sync.py --interval 60
```

### cron (every 5 minutes)

```
*/5 * * * * cd /path/to/documo_fax_sync && .venv/bin/python sync.py >> sync.log 2>&1
```

### systemd (continuous)

```ini
# /etc/systemd/system/documo-fax-sync.service
[Unit]
Description=Documo fax -> network share sync
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/documo_fax_sync
EnvironmentFile=/path/to/documo_fax_sync/.env
ExecStart=/path/to/documo_fax_sync/.venv/bin/python sync.py --interval 60
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Tests

```bash
pytest
```

Tests cover the sync logic (skip-already-processed, filename sanitizing,
continuing past a single fax failure) with the Documo client and share
writer mocked out -- no network or real credentials needed.
