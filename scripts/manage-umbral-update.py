#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Explicit, offline-capable Linux archive activation in a separate managed root."""
import argparse
import configparser
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

from umbral_update import download_verified

APP_ID = "io.github.martin08abm.umbralbrowser"


def application(path):
    if not path.is_dir() or path.is_symlink():
        raise ValueError("Application must be a real directory")
    resolved = path.resolve()
    for link in path.rglob("*"):
        if link.is_symlink() and not link.resolve().is_relative_to(resolved):
            raise ValueError("Application contains an external symlink")
    config = configparser.ConfigParser(interpolation=None)
    config.read(path / "application.ini")
    app = config["App"]
    version, build = app["Version"], app["BuildID"]
    if (app.get("CodeName") != "Umbral" or not re.fullmatch(r"\d+\.\d+\.\d+", version)
            or not re.fullmatch(r"\d{14}", build)):
        raise ValueError("Not a supported Umbral application")
    with (path / "zen").open("rb") as executable:
        header = executable.read(20)
    if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\x3e\x00":
        raise ValueError("Expected a Linux x86_64 executable")
    if not os.access(path / "zen", os.X_OK):
        raise ValueError("Browser executable lacks execute permission")
    for name in ("omni.ja", "browser/omni.ja", "distribution/policies.json",
                 "distribution/extensions/uBlock0@raymondhill.net.xpi"):
        if not (path / name).is_file():
            raise ValueError("Incomplete application: " + name)
    policy = json.loads((path / "distribution/policies.json").read_text())
    if policy.get("policies", {}).get("DisableAppUpdate") is not True:
        raise ValueError("Native browser update disabling policy is required")
    return {"version": version, "buildID": build,
            "firefoxVersion": config["Gecko"]["MaxVersion"]}


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json(path, data):
    with path.open("x") as target:
        json.dump(data, target)
        target.flush()
        os.fsync(target.fileno())


def activate(root, target):
    temporary = root / "switch.tmp"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, root / "current")
    sync_directory(root)


def current_release(root):
    link = root / "current"
    if not link.is_symlink():
        raise ValueError("Missing managed current link")
    target = Path(os.readlink(link))
    if target.is_absolute() or len(target.parts) != 2 or target.parts[0] != "releases":
        raise ValueError("Invalid managed release link")
    path = root / target
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Invalid release directory")
    return target, application(path)


def refuse_running(root):
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            executable = (entry / "exe").resolve(strict=True)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if executable.is_relative_to(root):
            raise ValueError("Close all browsers using this managed root first")


def extract_archive(archive, destination):
    with tarfile.open(archive, "r:xz") as source:
        members = []
        total = 0
        for member in source:
            members.append(member)
            total += member.size
            if len(members) > 50000 or total > 4 * 1024**3:
                raise ValueError("Archive exceeds extraction limits")
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "zen":
                raise ValueError("Unexpected archive path")
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError("Unsupported archive member")
            if member.mode & 0o6000:
                raise ValueError("Unexpected privileged archive mode")
        source.extractall(destination, members=members, filter="data")
    return destination / "zen"


def initialize(args):
    source = args.source.resolve(strict=True)
    metadata = application(source)
    root = args.root.absolute()
    if root.resolve().is_relative_to(source):
        raise ValueError("Managed root must be outside the source application")
    if root.exists() or root.is_symlink():
        raise ValueError("Initialization requires a new, separate directory")
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".umbral-init-", dir=root.parent) as temporary:
        stage = Path(temporary) / "managed"
        stage.mkdir(mode=0o700)
        (stage / "releases").mkdir()
        target = Path("releases") / (metadata["version"] + "-" + metadata["buildID"])
        shutil.copytree(source, stage / target, symlinks=True)
        shutil.copyfile(args.public_key, stage / "trusted-key.pem")
        write_json(stage / "umbral-managed.json", {"appId": APP_ID, "schema": 1})
        activate(stage, target)
        stage.rename(root)
    sync_directory(root.parent)
    print("Initialized separate managed copy: " + str(root / "current" / "zen"))


def manage(args):
    root = args.root.resolve(strict=True)
    marker = json.loads((root / "umbral-managed.json").read_text())
    if marker != {"appId": APP_ID, "schema": 1}:
        raise ValueError("Unknown managed root")
    with (root / ".update.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refuse_running(root)
        current, metadata = current_release(root)
        if args.command == "rollback":
            previous = Path((root / "previous").read_text().strip())
            if previous.is_absolute() or previous.parent != Path("releases") or previous == current:
                raise ValueError("No previous release available")
            application(root / previous)
            activate(root, previous)
            print("Rolled back to " + str(previous))
            return
        with tempfile.TemporaryDirectory(prefix=".candidate-", dir=root) as temporary:
            temporary = Path(temporary)
            release = download_verified(args.manifest, root / "trusted-key.pem", metadata["version"],
                                        temporary / "archive.tar.xz", args.allow_loopback_http)
            if (release.get("fromBuildID") != metadata["buildID"] or release.get("channel") != "unofficial"
                    or release.get("firefoxVersion") != metadata["firefoxVersion"]):
                raise ValueError("Source build, channel or Firefox ABI mismatch")
            candidate = extract_archive(temporary / "archive.tar.xz", temporary / "unpacked")
            actual = application(candidate)
            if any(actual[key] != release.get(key) for key in ("version", "buildID", "firefoxVersion")):
                raise ValueError("Signed metadata does not match archive")
            target = Path("releases") / (actual["version"] + "-" + actual["buildID"])
            if (root / target).exists():
                raise ValueError("Release already present")
            # Flush extracted files before the atomic activation; retain the old release.
            for file in candidate.rglob("*"):
                if file.is_file() and not file.is_symlink():
                    with file.open("rb") as contents:
                        os.fsync(contents.fileno())
            directories = [file for file in candidate.rglob("*") if file.is_dir() and not file.is_symlink()]
            for directory in sorted(directories, key=lambda file: len(file.parts), reverse=True):
                sync_directory(directory)
            sync_directory(candidate)
            candidate.rename(root / target)
            sync_directory(root / "releases")
            previous_tmp = root / "previous.tmp"
            with previous_tmp.open("w") as journal:
                journal.write(str(current))
                journal.flush()
                os.fsync(journal.fileno())
            os.replace(previous_tmp, root / "previous")
            refuse_running(root)
            activate(root, target)
            print("Activated " + str(target) + "; previous release retained for rollback")


def main():
    if Path("/.flatpak-info").exists():
        raise ValueError("Flatpak deployments must be updated through Flatpak")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Copy an extracted archive to a NEW managed root")
    init.add_argument("--source", type=Path, required=True)
    init.add_argument("--root", type=Path, required=True)
    init.add_argument("--public-key", type=Path, required=True)
    update = commands.add_parser("update")
    update.add_argument("--root", type=Path, required=True)
    update.add_argument("--manifest", required=True)
    update.add_argument("--allow-loopback-http", action="store_true")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "init":
        initialize(args)
    else:
        manage(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, tarfile.TarError,
            configparser.Error) as error:
        raise SystemExit(f"Update rejected: {error}")
