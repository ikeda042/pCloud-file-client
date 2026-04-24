"""Command-line interface for pcloud-client."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Optional

from .auth import build_authorize_url, exchange_code, parse_authorization_response
from .client import PCloudClient


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="pcloud-client")
    subcommands = parser.add_subparsers(dest="command", required=True)

    auth_url = subcommands.add_parser("auth-url", help="print a pCloud OAuth authorization URL")
    auth_url.add_argument("--client-id", required=True)
    auth_url.add_argument("--redirect-uri")
    auth_url.add_argument("--state")
    auth_url.add_argument("--force-reapprove", action="store_true")

    exchange = subcommands.add_parser("exchange-code", help="exchange an OAuth code for a token")
    exchange.add_argument("--client-id", required=True)
    exchange.add_argument("--client-secret", required=True)
    exchange.add_argument("--code")
    exchange.add_argument("--redirect-url")
    exchange.add_argument("--api-host", default="api.pcloud.com")

    ls = subcommands.add_parser("ls", help="list a pCloud folder")
    _add_client_args(ls)
    ls.add_argument("path", nargs="?", default="/")
    ls.add_argument("--recursive", action="store_true")

    mkdir = subcommands.add_parser("mkdir", help="create a pCloud folder path if needed")
    _add_client_args(mkdir)
    mkdir.add_argument("path")

    upload = subcommands.add_parser("upload", help="upload a local file")
    _add_client_args(upload)
    upload.add_argument("local_path")
    upload.add_argument("--remote-dir", default="/")
    upload.add_argument("--filename")
    upload.add_argument("--ensure", action="store_true")
    upload.add_argument("--rename-if-exists", action="store_true")

    backup = subcommands.add_parser("backup-dir", help="upload a local directory tree")
    _add_client_args(backup)
    backup.add_argument("local_dir")
    backup.add_argument("--remote-dir", required=True)
    backup.add_argument("--rename-if-exists", action="store_true")

    download = subcommands.add_parser("download", help="download a pCloud file")
    _add_client_args(download)
    download.add_argument("remote_path")
    download.add_argument("local_path")
    download.add_argument("--overwrite", action="store_true")

    delete = subcommands.add_parser("rm", help="delete a pCloud file")
    _add_client_args(delete)
    delete.add_argument("remote_path")

    args = parser.parse_args(argv)

    if args.command == "auth-url":
        print(
            build_authorize_url(
                args.client_id,
                redirect_uri=args.redirect_uri,
                state=args.state,
                force_reapprove=args.force_reapprove,
            )
        )
        return 0

    if args.command == "exchange-code":
        parsed = parse_authorization_response(args.redirect_url) if args.redirect_url else None
        code = args.code or (parsed.code if parsed else None)
        if not code:
            parser.error("--code or --redirect-url is required")
        token = exchange_code(
            args.client_id,
            args.client_secret,
            code,
            api_host=args.api_host,
            hostname=parsed.hostname if parsed else None,
            locationid=parsed.locationid if parsed else None,
        )
        _print_json(token.__dict__)
        return 0

    client = _client_from_args(args)
    if args.command == "ls":
        _print_json(client.list_folder(path=args.path, recursive=args.recursive))
    elif args.command == "mkdir":
        _print_json(client.ensure_folder(args.path))
    elif args.command == "upload":
        _print_json(
            client.upload_file(
                args.local_path,
                remote_dir=args.remote_dir,
                filename=args.filename,
                ensure=args.ensure,
                rename_if_exists=args.rename_if_exists,
            )
        )
    elif args.command == "backup-dir":
        _print_json(
            client.upload_directory(
                args.local_dir,
                remote_dir=args.remote_dir,
                rename_if_exists=args.rename_if_exists,
            )
        )
    elif args.command == "download":
        path = client.download_file(
            remote_path=args.remote_path,
            local_path=Path(args.local_path),
            overwrite=args.overwrite,
        )
        print(path)
    elif args.command == "rm":
        _print_json(client.delete_file(path=args.remote_path))
    return 0


def _add_client_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--access-token", default=os.environ.get("PCLOUD_ACCESS_TOKEN"))
    parser.add_argument("--api-host", default=os.environ.get("PCLOUD_API_HOST", "api.pcloud.com"))


def _client_from_args(args: argparse.Namespace) -> PCloudClient:
    if not args.access_token:
        raise SystemExit("set PCLOUD_ACCESS_TOKEN or pass --access-token")
    return PCloudClient(args.access_token, api_host=args.api_host)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
