#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
archive_file="${1:-}"
app_id='io.github.martin08abm.umbralbrowser'
branch='stable'
arch='x86_64'
build_root="$repo_root/dist/flatpak-build"
repo_dir="$repo_root/dist/flatpak-repo"
input_root="$repo_root/dist/flatpak-input"
manifest="$input_root/${app_id}.yml"
template="$repo_root/build/flatpak/${app_id}.yml.template"
metadata_source="$repo_root/build/flatpak/metadata"

if [[ -z "$archive_file" ]]; then
  printf 'Usage: %s dist/zen-<version>.tar.xz\n' "$0" >&2
  exit 2
fi
[[ "$archive_file" = /* ]] || archive_file="$repo_root/$archive_file"
[[ -f "$archive_file" ]] || { printf 'Archive not found: %s\n' "$archive_file" >&2; exit 1; }
command -v flatpak-builder >/dev/null
command -v flatpak >/dev/null
command -v sha256sum >/dev/null
command -v python3 >/dev/null

python3 - "$archive_file" <<'PY'
import sys
import tarfile
import io
import zipfile

with tarfile.open(sys.argv[1], "r:xz") as archive:
    names = archive.getnames()
    if not any(name.endswith("/browser/omni.ja") or name == "browser/omni.ja" for name in names):
        raise SystemExit("Package does not contain browser/omni.ja")
    if not any(name.endswith("/distribution/extensions/uBlock0@raymondhill.net.xpi") for name in names):
        raise SystemExit("Package does not contain the bundled uBlock Origin XPI")
    xpi_name = next(name for name in names if name.endswith("/distribution/extensions/uBlock0@raymondhill.net.xpi"))
    xpi_member = archive.extractfile(xpi_name)
    if xpi_member is None:
        raise SystemExit("Could not read the bundled uBlock Origin XPI")
    with zipfile.ZipFile(io.BytesIO(xpi_member.read())) as xpi:
        xpi_names = set(xpi.namelist())
        if xpi.testzip() is not None or not {"META-INF/mozilla.rsa", "META-INF/mozilla.sf"}.issubset(xpi_names):
            raise SystemExit("Bundled uBlock Origin XPI is incomplete or lacks Mozilla signature files")
    executables = [name for name in names if name == "zen/zen" or name.endswith("/zen/zen")]
    if len(executables) != 1:
        raise SystemExit(f"Expected one zen/zen executable in the archive, found {len(executables)}")
    member = archive.extractfile(executables[0])
    if member is None or member.read(5) != b"\x7fELF\x02":
        raise SystemExit("Browser executable is not a 64-bit ELF binary")
    member.seek(0)
    header = member.read(20)
    if header[18:20] != b"\x3e\x00":
        raise SystemExit("Browser executable is not x86_64")
PY

archive_hash="$(sha256sum "$archive_file" | cut -d ' ' -f1)"
archive_url="$(python3 - "$archive_file" <<'PY'
from pathlib import Path
from urllib.parse import quote
import sys

print("file://" + quote(str(Path(sys.argv[1]).resolve())))
PY
)"

mkdir -p "$input_root"
rm -rf "$input_root/metadata"
cp -a "$metadata_source" "$input_root/metadata"
python3 - "$template" "$manifest" "$archive_url" "$archive_hash" <<'PY'
from pathlib import Path
import sys

template_path, output_path = map(Path, sys.argv[1:3])
text = template_path.read_text()
text = text.replace("{archive_url}", sys.argv[3])
text = text.replace("{archive_sha256}", sys.argv[4])
output_path.write_text(text)
PY

flatpak-builder --force-clean --default-branch="$branch" --repo="$repo_dir" "$build_root" "$manifest"
bundle="$repo_root/dist/umbral-linux-x86_64.flatpak"
flatpak build-bundle \
  --arch="$arch" \
  --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
  "$repo_dir" "$bundle" "$app_id" "$branch"
printf 'Created %s\n' "$bundle"
