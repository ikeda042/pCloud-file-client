from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pcloud_client import (
    PCloudClient,
    PCloudError,
    build_authorize_url,
    exchange_code,
    parse_authorization_response,
)


class FakeResponse:
    def __init__(self, payload=None, *, chunks=None, status_code=200):
        self.payload = payload
        self.chunks = chunks or []
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self.payload is None:
            raise ValueError("no JSON")
        return self.payload

    def iter_content(self, chunk_size=1):
        yield from self.chunks


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


class AuthTests(unittest.TestCase):
    def test_build_authorize_url(self):
        url = build_authorize_url(
            "client123",
            redirect_uri="http://localhost:8765/callback",
            state="nonce",
            permissions=["manageshares"],
        )

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "my.pcloud.com")
        self.assertEqual(query["client_id"], ["client123"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["state"], ["nonce"])
        self.assertEqual(query["permissions"], ["manageshares"])

    def test_parse_redirect_url(self):
        result = parse_authorization_response(
            "http://localhost/callback?code=abc&state=nonce&locationid=2&hostname=eapi.pcloud.com"
        )

        self.assertEqual(result.code, "abc")
        self.assertEqual(result.state, "nonce")
        self.assertEqual(result.locationid, 2)
        self.assertEqual(result.hostname, "eapi.pcloud.com")

    def test_exchange_code(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "result": 0,
                        "access_token": "token123",
                        "token_type": "bearer",
                        "uid": 42,
                    }
                )
            ]
        )

        token = exchange_code(
            "client",
            "secret",
            "code",
            api_host="eapi.pcloud.com",
            hostname="eapi.pcloud.com",
            locationid=2,
            session=session,
        )

        self.assertEqual(token.access_token, "token123")
        self.assertEqual(token.hostname, "eapi.pcloud.com")
        self.assertEqual(token.locationid, 2)
        self.assertEqual(session.requests[0]["url"], "https://eapi.pcloud.com/oauth2_token")


class ClientTests(unittest.TestCase):
    def test_pcloud_error_is_raised(self):
        session = FakeSession([FakeResponse({"result": 2003, "error": "Access denied."})])
        client = PCloudClient("token", session=session)

        with self.assertRaises(PCloudError) as raised:
            client.call("listfolder", path="/Private")

        self.assertEqual(raised.exception.result, 2003)

    def test_ensure_folder_creates_each_component_by_id(self):
        session = FakeSession(
            [
                FakeResponse({"result": 0, "metadata": {"folderid": 10, "name": "Backups"}}),
                FakeResponse({"result": 0, "metadata": {"folderid": 11, "name": "Daily"}}),
            ]
        )
        client = PCloudClient("token", session=session)

        metadata = client.ensure_folder("/Backups/Daily")

        self.assertEqual(metadata["folderid"], 11)
        self.assertEqual(session.requests[0]["params"], {"folderid": 0, "name": "Backups"})
        self.assertEqual(session.requests[1]["params"], {"folderid": 10, "name": "Daily"})

    def test_upload_file_posts_multipart(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "result": 0,
                        "fileids": [123],
                        "metadata": [{"fileid": 123, "name": "hello.txt"}],
                    }
                )
            ]
        )
        client = PCloudClient("token", session=session)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "hello.txt"
            source.write_text("hello", encoding="utf-8")
            metadata = client.upload_file(source, remote_dir="/Backups", rename_if_exists=True)

        request = session.requests[0]
        self.assertEqual(metadata["fileid"], 123)
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["url"], "https://api.pcloud.com/uploadfile")
        self.assertEqual(request["data"]["path"], "/Backups")
        self.assertEqual(request["data"]["renameifexists"], 1)
        self.assertEqual(request["files"]["file"][0], "hello.txt")

    def test_download_file_uses_getfilelink(self):
        session = FakeSession(
            [
                FakeResponse({"result": 0, "hosts": ["c1.pcloud.com"], "path": "/hash/file.txt"}),
                FakeResponse(chunks=[b"hello"]),
            ]
        )
        client = PCloudClient("token", session=session)

        with tempfile.TemporaryDirectory() as tmp:
            target = client.download_file(
                remote_path="/Backups/file.txt",
                local_path=Path(tmp) / "file.txt",
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "hello")

        self.assertEqual(session.requests[0]["url"], "https://api.pcloud.com/getfilelink")
        self.assertEqual(session.requests[1]["url"], "https://c1.pcloud.com/hash/file.txt")


if __name__ == "__main__":
    unittest.main()
