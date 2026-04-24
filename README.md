# pCloud Python Client

A small, typed Python client for the [pCloud HTTP JSON API](https://docs.pcloud.com/).
It focuses on the workflows people actually automate from scripts: OAuth app
authorization, listing folders, creating private backup folders, uploading files,
downloading files through temporary links, and deleting files.

This project is not affiliated with pCloud.

## Why this library

- OAuth 2.0 code-flow helpers for `Client ID` and `Client secret`
- US/EU API host support via pCloud's `hostname` redirect parameter
- Safe folder creation with `folderid + name` instead of fragile path-only calls
- Simple file operations: `list`, `mkdir -p`, `upload`, `download`, `delete`
- Directory backup helper that preserves relative paths
- CLI for quick scripts and cron jobs
- No credential files or token storage policy baked in

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
python -m unittest discover -s tests
```

## OAuth quick start

pCloud apps use OAuth 2.0. The `Client ID` and `Client secret` are used once to
exchange an authorization code for a bearer token. pCloud's own OAuth docs note
that bearer tokens can then be sent as `Authorization: Bearer ...` or as the
global `access_token` parameter.

```python
from pcloud_client import (
    PCloudClient,
    build_authorize_url,
    exchange_code,
    parse_authorization_response,
)

client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"

print(build_authorize_url(client_id, redirect_uri="http://localhost:8765/callback"))

# After approving, paste the full redirect URL here.
redirect = "http://localhost:8765/callback?code=...&hostname=eapi.pcloud.com&locationid=2"
result = parse_authorization_response(redirect)

token = exchange_code(
    client_id,
    client_secret,
    result.code,
    api_host=result.hostname or "api.pcloud.com",
    hostname=result.hostname,
    locationid=result.locationid,
)

client = PCloudClient.from_oauth_token(token)
print(client.userinfo())
```

For headless use, export the token and API host:

```bash
export PCLOUD_ACCESS_TOKEN="..."
export PCLOUD_API_HOST="eapi.pcloud.com" # use api.pcloud.com for US accounts
```

## File operations

```python
from pcloud_client import PCloudClient

client = PCloudClient.from_env()

client.ensure_folder("/Backups/laptop")

metadata = client.upload_file(
    "notes.db",
    remote_dir="/Backups/laptop",
    ensure=True,
    rename_if_exists=True,
)
print(metadata["fileid"], metadata["path"])

for item in client.iter_folder(path="/Backups/laptop"):
    print(item["name"], item.get("size"))

client.download_file(
    remote_path="/Backups/laptop/notes.db",
    local_path="./restore/notes.db",
    overwrite=True,
)

client.delete_file(path="/Backups/laptop/old-notes.db")
```

Upload a whole directory tree:

```python
client.upload_directory("./data", remote_dir="/Backups/data")
```

## CLI

```bash
pcloud-client auth-url --client-id "$PCLOUD_CLIENT_ID" \
  --redirect-uri http://localhost:8765/callback

pcloud-client exchange-code \
  --client-id "$PCLOUD_CLIENT_ID" \
  --client-secret "$PCLOUD_CLIENT_SECRET" \
  --redirect-url "http://localhost:8765/callback?code=...&hostname=eapi.pcloud.com&locationid=2"

pcloud-client mkdir /Backups/laptop
pcloud-client ls /Backups/laptop
pcloud-client upload ./notes.db --remote-dir /Backups/laptop --ensure --rename-if-exists
pcloud-client download /Backups/laptop/notes.db ./restore/notes.db --overwrite
pcloud-client backup-dir ./data --remote-dir /Backups/data
```

## Creating a pCloud My App

Open [pCloud My Apps](https://docs.pcloud.com/my_apps/) while signed in. After
approval, that page should show the `Client ID` and `Client secret` for your app.
The general API documentation is available at [docs.pcloud.com](https://docs.pcloud.com/).

If the app creation button is unavailable or pCloud Support asks for manual
approval, send only the minimum information needed. Do not publish the resulting
credentials, access token, email address, or real personal details in this repo.

Suggested request format:

```text
Hello pCloud Support,

I would like to request approval for a pCloud API app.

1. App Name:
mybackupapp042

2. Folder Access:
Private

3. Write access:
Yes

4. Why I need this and how I plan to use it:
I need this app for a personal automated backup workflow.

I plan to use the official pCloud API from a local Python script to back up my
own data to one specific private folder in my pCloud account. The script will
periodically check a local backup source and upload changed backup files to the
designated pCloud folder.

Write access is required because the script needs to upload files into that
private backup folder. The expected frequency is low, approximately once per day.

The app will not be used as a public service or shared with other users. It will
only run from my local environment for backing up my own data. API credentials
and tokens will be stored locally and will not be committed to a public
repository.

The intended API usage is limited to:
- listing the target folder contents when needed
- uploading backup files to the designated private backup folder
- reading metadata needed to confirm backup status

It will not be used for public file sharing, mass uploads, account management,
or abusive automation.

Thank you.
```

App-name notes based on Support guidance:

- Use a globally distinctive name, not just a name unique to your account.
- Use standard English letters and numbers only.
- Avoid spaces and symbols.
- Pick a neutral example like `mybackupapp042`, not a real name, email, or
  credential-like value.

## API notes

- pCloud has US and EU API hosts. Use the `hostname` returned from OAuth
  authorization for later API calls: usually `api.pcloud.com` or
  `eapi.pcloud.com`.
- pCloud paths start with `/` and must not have trailing slashes, except `/`.
- pCloud recommends using `fileid` and `folderid` for many operations. This
  client accepts paths for convenience but uses `folderid + name` for nested
  folder creation.
- `download_file()` calls `getfilelink` and then streams the returned temporary
  content URL.

## Security

- Never commit `Client secret`, bearer tokens, or redirect URLs containing codes.
- Prefer a private app with `Private` folder access and the minimum permissions
  required for your automation.
- Store tokens in your OS secret manager, a local `.env` file excluded from Git,
  or your CI secret store.
- Rotate/delete tokens from pCloud if they are exposed.
