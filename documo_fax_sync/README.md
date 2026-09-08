# Documo Fax -> Network Share Sync

Polls the Documo (mFax) API for new inbound faxes, downloads each one, and
copies it to a folder on a network share. Already-copied faxes are tracked
in a local state file so re-runs never duplicate a file.

**Setting this up on a Windows Server, step by step (no coding involved)?
See [`WINDOWS_SETUP.md`](WINDOWS_SETUP.md) instead of this file.** The rest
of this README is the technical reference / Linux instructions.

## ⚠️ Verify against the Documo docs

This was built without direct access to the Documo docs page you linked
(`docs.documo.com` was blocked by this environment's network egress proxy).
Confirmed so far, from a real request against `api.documo.com` and from the
Folders/Files section of the docs:

- Base URL is `https://api.documo.com` (no `/v1` prefix)
- Auth: `Authorization: Basic <api_key>` -- note the literal word `Basic`,
  not `Bearer`, and not standard HTTP Basic auth (no base64, no colon/password)

Still unconfirmed -- `documo_client.py` currently guesses these by analogy
with the rest of Documo's REST API and they have NOT been verified against
the Fax section of the docs yet:

- `GET /fax?direction=inbound&status=new` -- list inbound faxes
- `GET /fax/{id}/download` -- download a fax file
- `PATCH /fax/{id}` -- mark a fax as read
- The response field names (`id`/`faxId`, `from`, `receivedAt`, and the
  list envelope key `faxes`/`data`)

Before relying on this, open the linked docs page's **Fax** section and
confirm those paths and field names. Everything that might differ is a
config value, not a code change:

- Endpoint paths: `DOCUMO_LIST_PATH`, `DOCUMO_DOWNLOAD_PATH`, `DOCUMO_MARK_READ_PATH`
- Auth shape: `DOCUMO_AUTH_HEADER`, `DOCUMO_AUTH_SCHEME`
- Response field names: edit `build_filename()` and the `faxes = ...` line in `sync.py`

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
