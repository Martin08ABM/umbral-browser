# Umbral test builds

This guide describes local Linux packaging and the manually triggered Windows and macOS test-build workflows. They produce temporary test artifacts only; they do not publish a release.

The packages are built from the checked-out Umbral sources and work independently of the source repository and `engine/` build directory. The Linux archive still relies on the host system’s supported shared libraries.

## Linux x86_64: build, package, install

The main `engine/obj-x86_64-pc-linux-gnu/dist/bin/zen` executable is dated **October 25, 2026**. A separate clean-tree build was compiled later as a source-regeneration check; it is validation evidence, not the packaging target. The timestamp of the main executable alone does not establish whether it contains a particular UI change. The commands below use the main checkout: import the current persistent sources, rebuild that object tree, then package it. They do not download a new Firefox/Zen base. On this machine, the engine tree occupies about 23 GiB, including a 17 GiB Linux object directory; the workspace volume has 546 GiB free, and `~/.mozbuild` occupies 3.1 GiB on a home volume with 109 GiB free.

From the repository root:

```sh
npm run import
SURFER_PLATFORM=linux SURFER_COMPAT=x86_64 MOZ_PURGE_CACHES=1 npm run build
SURFER_PLATFORM=linux SURFER_COMPAT=x86_64 npm run package
ls -lh dist/zen-*.tar.xz
```

`npm run import` applies the persistent sources and patches to the existing generated engine tree. `npm run build` compiles them, reusing valid build outputs. `npm run package` creates the compressed Linux archive under `dist/`; the exact archive name includes the application version and locale.

Before installing, check the archive’s browser files, Umbral icon, signed uBlock Origin XPI, and x86_64 executable:

```sh
set -euo pipefail
archive_file="$(find dist -maxdepth 1 -type f -name 'zen-*.tar.xz' -printf '%T@ %p\n' | sort -nr | sed -n '1s/^[^ ]* //p')"
test -n "$archive_file"
entries="$(tar -tJf "$archive_file")"
printf '%s\n' "$entries" | grep -Eq '(^|/)browser/omni\.ja$'
printf '%s\n' "$entries" | grep -Eq '(^|/)browser/chrome/icons/default/default128\.png$'
xpi_path="$(printf '%s\n' "$entries" | awk '$0 ~ /(^|\/)distribution\/extensions\/uBlock0@raymondhill\.net\.xpi$/ { print; exit }')"
binary_path="$(printf '%s\n' "$entries" | awk '$0 ~ /(^|\/)zen$/ { print; exit }')"
test -n "$xpi_path"
test -n "$binary_path"
verify_dir="$(mktemp -d)"
trap 'rm -rf "$verify_dir"' EXIT
tar -xJOf "$archive_file" "$xpi_path" > "$verify_dir/umbral-ublock.xpi"
tar -xJOf "$archive_file" "$binary_path" > "$verify_dir/umbral-zen"
file "$verify_dir/umbral-zen" | grep -Eq 'ELF 64-bit LSB.*x86-64'
unzip -tq "$verify_dir/umbral-ublock.xpi"
echo '5b74415860456370644bd80f16125e865b0e6c356bb5dfcfb84069967eaa5287  '"$verify_dir/umbral-ublock.xpi" | sha256sum -c -
xpi_entries="$(unzip -Z1 "$verify_dir/umbral-ublock.xpi")"
printf '%s\n' "$xpi_entries" | grep -Fxq 'META-INF/mozilla.rsa'
printf '%s\n' "$xpi_entries" | grep -Fxq 'META-INF/mozilla.sf'
```

To install the newest archive into `~/.local/opt/umbral`, back up any earlier app directory, install the application icon, and create a desktop launcher with a dedicated Umbral profile:

```sh
set -euo pipefail

archive_file="$(find dist -maxdepth 1 -type f -name 'zen-*.tar.xz' -printf '%T@ %p\n' | sort -nr | sed -n '1s/^[^ ]* //p')"
test -n "$archive_file"
stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT
tar -xJf "$archive_file" -C "$stage_dir"
app_binary="$(find "$stage_dir" -type f -name zen -perm -u+x -print -quit)"
test -n "$app_binary"
package_root="$(dirname "$app_binary")"

install_dir="$HOME/.local/opt/umbral"
if [ -e "$install_dir" ]; then
  backup_dir="${install_dir}.backup.$(date +%Y%m%d-%H%M%S)"
  mv "$install_dir" "$backup_dir"
  printf 'Previous app files backed up to %s\n' "$backup_dir"
fi
mkdir -p "$install_dir"
cp -a "$package_root"/. "$install_dir"/

profile_dir="$HOME/.local/share/umbral-test-profile"
mkdir -p "$profile_dir"
install -Dm644 \
  "$install_dir/browser/chrome/icons/default/default128.png" \
  "$HOME/.local/share/icons/hicolor/128x128/apps/umbral.png"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/umbral.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Umbral Browser
Comment=Browse with Umbral
Exec="$install_dir/zen" -no-remote -profile "$profile_dir" %u
Icon=umbral
Terminal=false
Categories=Network;WebBrowser;
MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;
EOF
```

Open **Umbral Browser** from the desktop application menu. It launches with `~/.local/share/umbral-test-profile`, separate from Firefox and Zen profiles. To run it from a terminal instead:

```sh
"$HOME/.local/opt/umbral/zen" -no-remote \
  -profile "$HOME/.local/share/umbral-test-profile"
```

The executable is named `zen` by the inherited build configuration; its product name and packaged application icon are Umbral.

## Windows x86_64: portable ZIP artifact

1. Open [Actions](https://github.com/Martin08ABM/umbral-browser/actions) in the Umbral repository.
2. Select **Manual Windows x86_64 test build**, choose **Run workflow**, and provide a test version label if desired.
3. When it finishes, download the `umbral-windows-x86_64` artifact. GitHub downloads an outer artifact ZIP; extract it once to get `umbral-windows-x86_64.zip`, then extract that portable browser ZIP.
4. In PowerShell, from the extracted browser files, create and use a dedicated profile:

```powershell
$profilePath = Join-Path $env:LOCALAPPDATA 'Umbral\TestProfile'
New-Item -ItemType Directory -Force -Path $profilePath | Out-Null
$browser = Get-ChildItem -Path . -Filter zen.exe -Recurse | Select-Object -First 1
if (-not $browser) { throw 'zen.exe was not found in the extracted package' }
& $browser.FullName -no-remote -profile $profilePath
```

This is a ZIP with no installer. The `-no-remote` flag and explicit profile path keep the test session separate from Firefox and Zen profiles.

The build is unsigned. Windows may identify it as an unknown publisher or show a SmartScreen warning; Smart App Control can block unsigned executables under some configurations. The workflow does not disable or alter those protections. Windows signing would require an Authenticode signing identity and protected signing credentials.

## macOS Apple Silicon ARM64: DMG artifact

1. Open [Actions](https://github.com/Martin08ABM/umbral-browser/actions) in the Umbral repository.
2. Select **Manual macOS Apple Silicon test build**, choose **Run workflow**, and provide a test version label if desired.
3. Download the `umbral-macos-arm64` artifact. Extract GitHub’s outer artifact ZIP to get `umbral-macos-arm64.dmg`.
4. Open the DMG, copy `Umbral.app` to `/Applications`, then eject the mounted image.
5. Launch it with a profile dedicated to Umbral:

```sh
profile_dir="$HOME/Library/Application Support/Umbral/TestProfile"
mkdir -p "$profile_dir"
open -na "/Applications/Umbral.app" --args \
  -no-remote -profile "$profile_dir"
```

The build targets **Apple Silicon ARM64** and **macOS 11 Big Sur or newer**. Firefox’s build configuration sets the ARM64 macOS deployment target to 11.0.

This test artifact is not signed with an Apple Developer ID and is not notarized. Gatekeeper may prevent its first launch. On macOS Sequoia and later, Control-click is not the override path; after attempting to open the app, review it under **System Settings → Privacy & Security → Open Anyway**. This is a per-app approval, and managed Macs may disallow it. The workflow does not turn Gatekeeper off. Signed and notarized distribution would require a Developer ID certificate, protected credentials, and a notarization step.

## What the workflows build

Both workflows follow the existing Zen release-build setup and run on Ubuntu. Windows obtains Wine and a Visual Studio 2026 sysroot with the Windows SDK through Mozilla’s `get_vs.py`, bootstraps Clang, installs the pinned Rust MSVC target and downloads the Windows API bindings version named by the source tree. The workflow checks those paths before compiling. macOS obtains `cctools`, DMG and HFS+ tools, installs Rust’s Apple Silicon target, and uses Firefox’s macOS SDK bootstrap; the configured SDK is checked after compilation. Mozilla documents that the build system bootstraps a suitable macOS SDK by default. [Firefox macOS SDK notes](https://github.com/mozilla-firefox/firefox/blob/main/widget/cocoa/docs/sdks.md)

The macOS workflow cross-compiles an ARM64 `.app` and packages it in a DMG. Both cross-build workflows validate the archive, required browser bundle, included signed uBlock XPI and executable architecture before upload. The DMG has not been opened on a physical Apple Silicon Mac yet; your friend’s test is the first target-Mac runtime check.

The imported Umbral sources include the homepage, search configuration and SearXNG setup, Firefox ETP settings and ETP statistics service, and the original signed uBlock Origin XPI. New profiles default Firefox Accounts off and hide its account entry points. Windows `.ico`/Start tiles and macOS `.icns` are supplied by the persistent Umbral platform-icon patch. The Linux launcher uses the Umbral icon from the packaged browser.

## Runner resources and artifact lifetime

The workflows use GitHub’s standard `ubuntu-24.04` hosted runner and reclaim cached runtimes and large preinstalled packages before checkout. They stop before downloading/building if less than 40 GiB is free, recheck for 30 GiB before compilation, and require 4 GiB before packaging. Mozilla documents 30 GiB free for a Linux Firefox build; the guard uses that minimum after source and cross-toolchains are present. The checks fail early if the runner image or cleanup leaves less than the build budget, instead of running out of disk partway through. The cleanup action reports up to 31 GiB reclaimed on a typical Ubuntu runner, with roughly 6 GiB more when cached runtimes are also removed; that is not a guaranteed amount, which is why the workflow checks actual free space. On public repositories, GitHub lists the standard Linux runner at 4 CPUs, 16 GB RAM, and 14 GB SSD, and its use is free. GitHub-hosted jobs have a six-hour limit. If an early disk guard fails, use an eligible larger runner with more storage; availability depends on the account plan, and larger runners are billed separately, including for public repositories. These workflows do not depend on the inherited Blacksmith runner labels.

The workflows retain artifacts for three days to limit storage use. GitHub Free currently includes 500 MB of Actions artifact storage, shared by the account’s repositories. Download the artifact before it expires; no release or public download page is created.

Runner labels and limits: [GitHub-hosted runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [Actions limits and storage](https://docs.github.com/en/actions/reference/limits).
