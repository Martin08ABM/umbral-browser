#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Verify signed Umbral archive downloads with an independently trusted key."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("Update redirects are not accepted")


def download_verified(manifest_url, public_key, current_version, output, allow_loopback_http=False):
    opener = urllib.request.build_opener(NoRedirect())

    def open_checked(url):
        if not isinstance(url, str) or len(url) > 4096:
            raise ValueError("Invalid update URL")
        parsed = urllib.parse.urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Invalid update URL")
        local_http = (allow_loopback_http and parsed.scheme == "http"
                      and parsed.hostname in ("localhost", "127.0.0.1", "::1"))
        if parsed.scheme != "https" and not local_http:
            raise ValueError("HTTPS required outside explicit loopback tests")
        return opener.open(url, timeout=30)

    def fetch(url, limit):
        with open_checked(url) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Update exceeds size limit")
        return data

    manifest = fetch(manifest_url, 16384)
    signature = fetch(manifest_url + ".sig", 64)
    if len(signature) != 64:
        raise ValueError("Invalid Ed25519 signature length")
    with tempfile.TemporaryDirectory(prefix="umbral-update-") as tmp:
        tmp = Path(tmp)
        (tmp / "manifest").write_bytes(manifest)
        (tmp / "signature").write_bytes(signature)
        subprocess.run([
            "openssl", "pkeyutl", "-verify", "-pubin", "-inkey",
            str(public_key.resolve()), "-rawin", "-in", str(tmp / "manifest"),
            "-sigfile", str(tmp / "signature"),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        release = json.loads(manifest)
        if not isinstance(release, dict):
            raise ValueError("Invalid manifest structure")
        if any(not isinstance(release.get(field), str) for field in
               ["appId", "platform", "fromVersion", "version", "archive", "sha256"]):
            raise ValueError("Invalid manifest field types")
        version = release.get("version", "")
        pattern = r"[0-9]+\.[0-9]+\.[0-9]+"
        if (not re.fullmatch(pattern, version)
                or not re.fullmatch(pattern, current_version)):
            raise ValueError("Unsupported version format")
        if (release.get("appId") != "io.github.martin08abm.umbralbrowser"
                or release.get("platform") != "linux-x86_64"
                or release.get("fromVersion") != current_version
                or tuple(map(int, version.split('.'))) <= tuple(map(int, current_version.split('.')))):
            raise ValueError("Incompatible update or version downgrade")
        if output.exists():
            raise ValueError("Output already exists")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as out:
                temporary = Path(out.name)
                with open_checked(release["archive"]) as response:
                    while block := response.read(1024 * 1024):
                        size += len(block)
                        if size > 1024 * 1024 * 1024:
                            raise ValueError("Archive exceeds size limit")
                        digest.update(block)
                        out.write(block)
            if digest.hexdigest() != release.get("sha256"):
                raise ValueError("Archive integrity check failed")
            with temporary.open("rb") as verified_file:
                os.fsync(verified_file.fileno())
            os.link(temporary, output)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--current-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-loopback-http", action="store_true")
    args = parser.parse_args()
    release = download_verified(args.manifest, args.public_key, args.current_version,
                                args.output, args.allow_loopback_http)
    print(f"Verified Umbral {release['version']}: {args.output}")
