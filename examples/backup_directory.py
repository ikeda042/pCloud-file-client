"""Upload a local directory tree to a pCloud folder.

Usage:
    PCLOUD_ACCESS_TOKEN=... PCLOUD_API_HOST=eapi.pcloud.com \
      python examples/backup_directory.py ./data /Backups/data
"""

from __future__ import annotations

import argparse

from pcloud_client import PCloudClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("local_dir")
    parser.add_argument("remote_dir")
    parser.add_argument("--rename-if-exists", action="store_true")
    args = parser.parse_args()

    client = PCloudClient.from_env()
    uploaded = client.upload_directory(
        args.local_dir,
        remote_dir=args.remote_dir,
        rename_if_exists=args.rename_if_exists,
    )
    print(f"uploaded {len(uploaded)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
