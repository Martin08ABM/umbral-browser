#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:---check}"
case "$mode" in
  --check) test_root="${2:-$(mktemp -d /tmp/umbral-flatpak-test.XXXXXX)}" ;;
  --run) test_root="${2:?Use the directory printed by --check}" ;;
  *) printf 'Usage: %s --check [test-directory] | --run test-directory\n' "$0" >&2; exit 2 ;;
esac
[[ "$test_root" == /tmp/umbral-flatpak-test.* && ! -L "$test_root" ]]
[[ "$(realpath -e "$test_root")" == "$test_root" ]]
[[ "$(stat -c %u "$test_root")" == "$(id -u)" ]]
marker="$test_root/.umbral-isolated-test"
if [[ "$mode" == --check && ! -e "$marker" ]]; then
  [[ -z "$(ls -A "$test_root")" ]]
  printf '%s\n' 'io.github.martin08abm.umbralbrowser isolated test' > "$marker"
fi
[[ -f "$marker" && ! -L "$marker" ]]
[[ "$(cat "$marker")" == 'io.github.martin08abm.umbralbrowser isolated test' ]]
[[ -x "$repo_root/dist/flatpak-build/files/umbral/zen" ]]

python3 - "$repo_root" "$test_root" <<'PY'
from pathlib import Path
import sys
repo, temporary = map(Path, sys.argv[1:])
manifest = (repo / 'build/flatpak/io.github.martin08abm.umbralbrowser.yml.template').read_text()
manifest = manifest.replace('{archive_url}', 'file:///unused-isolated-test.tar.xz')
manifest = manifest.replace('{archive_sha256}', '0' * 64)
(temporary / 'sandbox.yml').write_text(manifest)
PY

graphics=()
wayland_socket="${WAYLAND_DISPLAY-}"
if [[ "$wayland_socket" != /* ]]; then
  wayland_socket="${XDG_RUNTIME_DIR-}/$wayland_socket"
fi
if [[ -n "${WAYLAND_DISPLAY-}" && -S "$wayland_socket" && "${MOZ_ENABLE_WAYLAND-}" != 0 ]]; then
  graphics+=(--socket=wayland "--env=WAYLAND_DISPLAY=$WAYLAND_DISPLAY" --env=MOZ_ENABLE_WAYLAND=1)
elif [[ -n "${DISPLAY-}" ]]; then
  graphics+=(--nosocket=wayland --nosocket=fallback-x11 --socket=x11 "--env=DISPLAY=$DISPLAY" --env=MOZ_ENABLE_WAYLAND=0)
else
  printf 'No usable desktop session. Run this script from a Wayland or X11 terminal.\n' >&2
  exit 1
fi

flatpak-builder --run "${graphics[@]}" --filesystem="$test_root" \
  "$repo_root/dist/flatpak-build" "$test_root/sandbox.yml" \
  /bin/sh -eu -c '
    root="$1"
    printf "DISPLAY: %s\nWAYLAND_DISPLAY: %s\nXDG_RUNTIME_DIR: %s\nMOZ_ENABLE_WAYLAND: %s\n" \
      "${DISPLAY-}" "${WAYLAND_DISPLAY-}" "${XDG_RUNTIME_DIR-}" "${MOZ_ENABLE_WAYLAND-}"
    if [ "${MOZ_ENABLE_WAYLAND-}" = 1 ]; then
      socket="${WAYLAND_DISPLAY:?}"
      case "$socket" in /*) ;; *) socket="${XDG_RUNTIME_DIR:?}/$socket" ;; esac
      [ -S "$socket" ] || { printf "Wayland socket unavailable: %s\n" "$socket" >&2; exit 1; }
      printf "Graphics backend: Wayland (socket available)\n"
    else
      [ -n "${DISPLAY-}" ] || { printf "X11 DISPLAY unavailable\n" >&2; exit 1; }
      display_number="${DISPLAY##*:}"
      display_number="${display_number%%.*}"
      [ -S "/tmp/.X11-unix/X$display_number" ] || { printf "X11 socket unavailable\n" >&2; exit 1; }
      printf "Graphics backend: X11 (socket available)\n"
    fi
    [ "$(realpath -e "$root")" = "$root" ]
    for name in profile data config cache tmp; do
      path="$root/$name"
      [ ! -L "$path" ]
      mkdir -p "$path"
      [ "$(realpath -e "$path")" = "$path" ]
    done
    export XDG_DATA_HOME="$root/data"
    export XDG_CONFIG_HOME="$root/config"
    export XDG_CACHE_HOME="$root/cache"
    export TMPDIR="$root/tmp"
    profile="$root/profile"
    printf "Effective profile: %s\nXDG_DATA_HOME: %s\nXDG_CONFIG_HOME: %s\nXDG_CACHE_HOME: %s\nTMPDIR: %s\n" \
      "$profile" "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$TMPDIR"
    printf "Command: /app/umbral/zen --no-remote --profile %s\n" "$profile"
    [ "$2" = --run ] || exit 0
    exec /app/umbral/zen --no-remote --profile "$profile"
  ' umbral-isolated-test "$test_root" "$mode"

if [[ "$mode" == --check ]]; then
  printf '\nNo browser started. To launch with this exact isolated profile:\n'
  printf 'bash %q --run %q\n' "$repo_root/scripts/test-flatpak-isolated.sh" "$test_root"
fi
