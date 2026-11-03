# Local features, performance and updates

Results below are from Linux x86_64 temporary profiles on 3 November 2026. No personal profile, installed Umbral deployment, default-browser setting, production key, public update endpoint, commit or release was changed.

## Homepage shortcuts and passwords

The shortcuts section is centered and limited to 580 px, with a responsive grid of small cards, local glyph icons, two-line names and an Add shortcut tile. An empty list shows that tile and a short explanation. Each card has a keyboard/touch-accessible disclosure for editing, deleting and moving it. Escape closes the disclosure; context-menu activation is supported. Narrow windows use an inset action sheet. Form errors are adjacent to their fields, associated with `aria-describedby`, and focus the first invalid field. Both neutral light and dark themes retain visible focus and reduced-motion behavior. The three privacy cards remain separate and unchanged at the bottom.

Storage remains `browser.newtabpage.umbral.shortcuts`: twelve user-entered HTTP(S) links maximum, names up to 48 characters, validated again in the parent actor. Existing order and stored entries are retained. No sites are seeded; no history, suggestions or remote icon service is consulted. Homepage content retains its principal and CSP.

Password controls now have distinct scopes:

- **Use Umbral's password manager** is Firefox's existing `signon.rememberSignons` master control. Existing values are preserved. In this base disabling it affects both saving and filling.
- **Offer to save passwords** controls the new `umbral.passwords.offerToSave` preference only. Disabling it suppresses new/update doorhangers and generated-password autosaving; it neither deletes credentials nor changes the master or autofill preferences. Previously stored passwords can still fill while the manager and autofill remain enabled. Matching an unchanged stored login still records its use.
- **Autofill** remains the native `signon.autofillForms` control. Its value is not changed by either new code path. Old profiles with the master or autofill disabled are not silently enabled.

English and Spanish descriptions explain these scopes and offer optional external managers without installing extensions or contacting their services. The controls do not disable external managers.

## Local AI and cancellation

Settings → Local AI is disabled initially. It accepts an OpenAI-compatible API **base** URL, for example `http://127.0.0.1:1234/v1`, and a model name. Only `localhost`, `127.0.0.1` and `[::1]` are accepted. Remote/LAN hosts, credentials in URLs, query strings and fragments are rejected. Saving configuration makes no request. Each Send posts the newly submitted text and model to `/chat/completions`; displayed earlier exchanges are not submitted as context. This is a stateless text exchange, not yet a conversation with model-side history. There is no automatic page extraction or action tool. Sharing page text requires reviewing and pasting it manually.

An optional key uses Firefox LoginManager (`chrome://umbral-ai`, realm `Umbral local AI`), including its encryption/primary-password handling. The reopened key field stays blank; blank preserves the key and a separate control deletes it. The key is absent from preferences and homepage content. System-module networking leaves Preferences CSP intact. Redirects are rejected, cookies and referrers omitted, input limited to 4,000 characters and output to 64 KiB/12,000 answer characters. HTTPS uses normal certificate validation.

The Cancel button aborts the request and response-body reader. Disabling the feature, closing/navigating away from Preferences, or the 60-second deadline also aborts it. A temporary preference observer exists only during a request and is removed in `finally`; there is no background polling. Cancellation prevents displaying a completed answer after an aborted body. A server may continue inference after its client disconnects: Umbral cannot guarantee cancellation of that server's model computation.

**Real model limitation:** LM Studio's CLI is present, but its server reports stopped and no functioning daemon/model installation was available. No model was downloaded or started. Actual inference, model-specific protocol behavior and server-side cancellation remain pending. The HTTP fixture tests below exercise real browser networking and transport cancellation, but return simulated model answers. The 60-second timeout and screen-reader announcements have not been separately exercised.

## Functional validation

The reproducible tests use temporary profiles, dynamic Marionette/HTTP ports, fixture credentials, and only their own browser subprocesses. `remote.prefs.recommended=false` avoids Marionette silently changing product privacy/password defaults.

- `umbral_shortcuts.py`: real card/disclosure clicks, add/edit/delete/order, invalid name and URL with field focus, keyboard Enter/Escape, persistence after normal restart, empty/several/long-name/narrow layouts, both themes and no horizontal overflow. Screenshots are written to `UMBRAL_VISUAL_DIR` or a temporary output directory.
- `umbral_passwords.py`: a saved fixture credential actually fills a local HTML form with save offers disabled; master/autofill values and stored credentials remain unchanged. The real parent doorhanger path makes zero save prompts while disabled and one when enabled. Explicit old master/autofill choices are preserved.
- `umbral_local_ai.py`: saving sends zero requests; explicit Send produces exactly the expected model/text/Authorization header; the credential survives restart. Tests cover HTTP 503, invalid authentication, oversized answers, no retries/fallbacks, manual cancellation, disabling during a response and leaving Preferences. The server observes the cancelled sockets closing. Disabled API calls fail before networking. It also checks the native and preference update URLs and the independent extension-update setting.

Run from the repository root:

```sh
cd engine
./mach python --virtualenv common ../scripts/tests/umbral_shortcuts.py
./mach python --virtualenv common ../scripts/tests/umbral_passwords.py
./mach python --virtualenv common ../scripts/tests/umbral_local_ai.py
UMBRAL_TEST_FLATPAK=1 ./mach python --virtualenv common ../scripts/tests/umbral_local_ai.py
cd ..
python3 scripts/tests/umbral_updates.py
python3 scripts/tests/umbral_managed_updates.py
```

The Flatpak variant mounts the current development binary/resources read-only inside the existing installed sandbox and passes an explicit exclusive temporary profile. The later profile-safety audit found that its outer XDG overrides were ineffective; temporary XDG isolation was not established by those earlier runs. The harness now assigns and checks those variables inside its shell, before invoking the binary; this corrected harness has not been rerun during the shell-only audit. It does **not** replace the installed app or open its profile. This tests the current code against the sandbox/runtime and host-loopback access, not the contents of a newly generated bundle. A rebuilt bundle still needs manual end-to-end testing. Native-messaging applications retain Flatpak's existing host-access limitations.

Final results: all three native browser tests pass. The same eight-request AI suite also passed inside the existing Flatpak sandbox with the current development binary and an explicit temporary profile; see the later XDG-isolation correction above. Manual cancel, preference disable and page departure close three server-observed sockets in each run. Both runtime checks report an empty embedded update URL, browser updates disabled and extension updates enabled. Homepage screenshots were visually inspected, including the translated inline errors after Fluent completed. Full assistive-technology testing, visible Spanish UI and the regenerated bundle remain pending. An earlier native password mochitest run stopped when uBO fetched a live default filter list that the harness forbids; it is not counted as passed. No harness network restriction was disabled. The targeted Marionette checks do not replace the broader native suite.

## Privacy defaults preserved

A new profile with Marionette overrides disabled reports ETP `strict`, `privacy.fingerprintingProtection=true`, and `privacy.resistFingerprinting=false`. No FPP/ETP weakening, extra list, custom UA/canvas/font/hardware randomization or global RFP setting was introduced. Site compatibility controls remain native. There is no anonymity claim. The original signed uBO XPI and its default lists are unchanged.

## CPU investigation and equivalent reference

`profiler-cli` 0.12.0 analyzed a 15.734-second first-profile capture after ten seconds of settling. Main-thread CPU was 2,192 ms in WebExtensions, 1,765 ms in the parent and only 8.6 ms in the homepage's privileged-content process. In the extension's 2,340 active samples, uBO's `compileFilters` appeared in 645, static-net `fromCompiled` in 659 and `assetCacheWrite` in 909. These are overlapping inclusive counts, **not percentages to add**. Source locations were checked against the unchanged XPI. The CLI attributed extension frames to “Form Autofill”; that display label was not used to identify the cause. Function/source evidence and temporarily disabling/re-enabling uBO in an exclusive diagnostic profile identify uBO filter/cache initialization as a substantial contributor.

The profile also recorded 78 completed network requests, including initial filter lists, Mozilla remote-settings data and media-component downloads. Thus not all parent/background CPU is attributed to uBO. Umbral chrome hooks had only three parent samples in this capture. No AI request or model process was started.

An uninterrupted new-profile run initially reached 52.33% CPU and 1,847.7 MiB PSS, then settled. Its final three ten-second windows were 0.15%, 0.13%, 0.61% CPU and approximately 590–592 MiB PSS. This observed peak and decay explains why the old five-/ten-second “idle” measurements were misleading: they included first-run work. It does not prove that every report of high CPU has this cause, particularly with other pages/extensions or a personal profile that was not inspected. No security feature or list was disabled as an optimization.

A dedicated settled fixture was then copied before **each** run. Three runs per variant used the same native engine, ETP/FPP, original uBO, fixture state, headless mode, ten seconds of settling, ten seconds of idle sampling and three identical local data-page navigations. The reference is an isolated distribution copy with only historical homepage HTML/CSS and actors restored from Umbral revision `70621a2f2720a2f661191f710269cfc4dd0656c2`. It is a resource comparison, **not a complete historical browser build**. The update-disabling policy is preserved in both.

| Median | Homepage-resource reference | Current homepage |
| --- | ---: | ---: |
| Startup through Marionette to homepage | 1.963 s | 1.283 s |
| Idle CPU, one-core equivalent | 0.5% | 0.6% |
| Sum of process PSS | 571.6 MiB | 638.9 MiB |
| Sum of process RSS | 1,225.4 MiB | 1,290.3 MiB |
| Mean of three local navigations | 43.7 ms | 39.7 ms |

This establishes low sustained idle CPU under these conditions, **not a performance improvement**. Memory is higher in this small current-homepage sample, and startup/file-cache/process variation remains relevant. A broader memory attribution and representative website benchmark are still needed before claiming a regression or improvement. RSS counts shared pages repeatedly; PSS apportions them. CPU sums all browser descendants and can exceed 100%. Very short-lived processes can be missed. Navigation CPU was also recorded, but its sub-second interval makes percentage comparisons noisy. Raw results and sanitized first-run process samples are in [validation/](validation/). Previous fresh-profile results remain there for traceability and are not sustained-idle evidence.

Reproduce without personal profiles or a modified engine:

```sh
cd engine
./mach python --virtualenv common ../scripts/tests/umbral_steady_idle.py \
  --template /tmp/umbral-settled-benchmark
UMBRAL_BENCH_TEMPLATE=/tmp/umbral-settled-benchmark UMBRAL_PERF_SETTLE=10 \
  ./mach python --virtualenv common ../scripts/measure-umbral.py
cd ..
python3 scripts/reconstruct-homepage-reference.py \
  --revision 70621a2f2720a2f661191f710269cfc4dd0656c2 \
  --output /tmp/umbral-homepage-reference
cd engine
UMBRAL_BENCH_BINARY=/tmp/umbral-homepage-reference/zen \
UMBRAL_BENCH_TEMPLATE=/tmp/umbral-settled-benchmark UMBRAL_PERF_SETTLE=10 \
  ./mach python --virtualenv common ../scripts/measure-umbral.py
./mach python --virtualenv common ../scripts/tests/umbral_capture_profile.py \
  --output /tmp/umbral-first-run-profile.json
cd ..
```

Use new output directories. The reference copy needs about 3.4 GiB. The fixture builder waits for three consecutive low-CPU windows, with a four-minute bound; an unsettled run does not produce a valid benchmark seed. The initial seed-copy attempt encountered Firefox's dangling `lock` symlink after normal shutdown; the reproducible script now excludes lock/port files and writes its validation marker only after a successful copy. No browser failure was hidden.

## Updates: implemented local route and production gaps

`DisableAppUpdate` remains installed, `app.update.url` is locked empty, and manual/details links point to the Umbral repository. Extension updates remain enabled. Importantly, this Firefox base uses **`Services.appinfo.updateURL` embedded in the launcher**, not just the preference. `src/build/application-ini-in.patch` empties that actual URL and `src/build/moz-build.patch` removes the old `.invalid` fallback. A small native launcher rebuild is required; UI compilation alone is insufficient. There is no Zen, Mozilla or pretend public update endpoint. Runtime assertions check all these properties.

### Signed download

`scripts/verify-umbral-update.py` uses the shared `scripts/umbral_update.py`. It verifies a detached Ed25519 signature over exact manifest bytes with an independently trusted public key, checks app/platform/exact source version/increasing target version, then streams and verifies SHA-256 before publishing the download. It rejects redirects, non-HTTPS outside explicit loopback tests, oversized input and existing output paths. It does not install or execute anything.

The download tests pass valid data and reject modified signatures/manifests, wrong digest/platform/source version/application ID, downgrade and malformed types. Keys exist only in the temporary fixture and are deleted afterwards.

### Explicit managed Linux archive activation

`scripts/manage-umbral-update.py` adds a **manual CLI prototype**, not a background or in-browser updater. It requires a **new, separate managed root** initialized from an already trusted, extracted standalone Umbral archive. It does not convert or overwrite an existing installation. `current` points to a retained version under `releases/`; a pinned public key belongs to that managed root. Existing profile directories are not migrated or modified.

On an explicit update it derives the installed source version/build from `application.ini`, verifies the signed download, requires `unofficial`, the exact source build and the same Firefox version, and cross-checks signed target version/build/Firefox metadata against the extracted archive. Python's maintained [`tarfile` data filter](https://docs.python.org/3/library/tarfile.html#extraction-filters), path/type/size limits and external-symlink rejection constrain extraction. It checks an executable Linux x86_64 ELF, required resource/XPI paths and the browser-update-disabling policy. It rejects use inside Flatpak and refuses activation while an executable under the managed root is running.

Candidate files/directories are flushed, the previous release is retained, and `os.replace` atomically switches the relative `current` symlink. Explicit rollback switches back. Existing output releases are not overwritten. Abandoned preparation directories do not change the active link. This is manual recovery, not automatic startup health checking or a guarantee against every filesystem/power failure. Close the managed browser before updating; the tool cannot prevent a separate launcher racing to start it.

The controlled test uses `/bin/sleep` ELF fixture applications, placeholder resources, a loopback server and ephemeral Ed25519 keys. It verifies activation, retaining/running the candidate fixture, explicit rollback, no downgrade, refusal with the managed fixture running, mismatched channel/source build/Firefox ABI/archive metadata, wrong architecture, path traversal, altered signature, interruption during a real download and an abandoned preparation directory. **No real Umbral package was installed or upgraded.** A complete actual-browser upgrade/restart test, production security review and key-rotation/revocation support remain pending.

After an independently trusted key and release artifacts exist, the intended **manual** commands are:

```sh
# --source must be an extracted standalone archive, not dist/bin symlinks.
python3 scripts/manage-umbral-update.py init \
  --source "$EXTRACTED_UMBRAL_DIRECTORY" --root "$NEW_MANAGED_DIRECTORY" \
  --public-key "$INDEPENDENTLY_TRUSTED_PUBLIC_KEY"
# Launch path becomes "$NEW_MANAGED_DIRECTORY/current/zen"; use a dedicated profile.
python3 scripts/manage-umbral-update.py update \
  --root "$NEW_MANAGED_DIRECTORY" --manifest "$SIGNED_UMBRAL_MANIFEST_URL"
python3 scripts/manage-umbral-update.py rollback --root "$NEW_MANAGED_DIRECTORY"
```

The basic signed manifest contains `appId=io.github.martin08abm.umbralbrowser`, `platform=linux-x86_64`, `fromVersion`, increasing numeric `version`, `archive` and `sha256`. Managed activation additionally requires `channel=unofficial`, `fromBuildID`, target `buildID` and `firefoxVersion`; it deliberately rejects a base-version transition. Raw 64-byte Ed25519 signatures are served at `<manifest URL>.sig`. Never retrieve the trust key from that same untrusted download. OpenSSL with Ed25519 and Python with `tarfile` extraction-filter support are required.

### Maintained updater and Flatpak remain separate

For a future browser-integrated updater, prefer Firefox's maintained [application-update/MAR infrastructure](https://firefox-source-docs.mozilla.org/toolkit/mozapps/update/docs/index.html), with **Umbral's own** embedded trust roots, release channels, update server, signing pipeline and full apply/restart/failure tests. No third-party key is reused. The current prototype does not enable MAR updates or replace that review. Production also needs protected signing credentials, trusted initial key distribution, rotation/revocation, artifact publication, server operation and rollback policy. Keep the browser update policy disabled until this is ready.

Flatpak replaces its read-only `/app` deployment through Flatpak: another user-installed bundle, or a separately operated [signed OSTree repository](https://docs.flatpak.org/en/latest/hosting-a-repository.html). The archive CLI is not used inside it. No remote was added, deployment changed, repository published or production key generated in this task.

Firefox/Zen security updates still require monitoring upstream releases, presenting the base-update scope, importing Umbral patches against that base, building and repeating functional/security checks. There was no base/dependency update here.

## Build/import and package regeneration

Two consecutive full `npm run import` runs pass with patch checks enabled. UI compilation succeeds. Rebuilding `build` and `browser/app` refreshes `application.ini`, its generated header and the launcher; it does not update Firefox. An initial subdirectory build without `--allow-subdirectory-build` was ignored by Mach and was **not** counted as that verification. The successful explicit command is below.

From the repository root:

```sh
python3 scripts/copy_language_pack.py en-US
npm run import
MOZ_PURGE_CACHES=1 npm run build:ui
(cd engine && ./mach build --allow-subdirectory-build build browser/app)
npm run package
archive_file="$(python3 -c 'from pathlib import Path; print(max(Path("dist").glob("zen-*.tar.xz"), key=lambda p: p.stat().st_mtime))')"
printf '%s\n' "$archive_file"
bash scripts/build-flatpak.sh "$archive_file"
```

Outputs are the printed `dist/zen-*.tar.xz` and `dist/umbral-linux-x86_64.flatpak`. Both need regeneration for the final resources and embedded URL change. No package was generated or installed during this task. Prerequisites and separate-profile commands are in [test-builds.md](test-builds.md).

Test the tar archive without installation:

```sh
package_dir="$(mktemp -d /tmp/umbral-package-check.XXXXXX)"
profile_dir="$(mktemp -d /tmp/umbral-profile-check.XXXXXX)"
tar -xJf "$archive_file" -C "$package_dir"
"$package_dir/zen/zen" --no-remote --profile "$profile_dir"
```

For a **newly built but uninstalled** Flatpak tree, use the checked helper. An actual shell-only probe on 3 November found that Flatpak **overwrites outer `--env=XDG_*` arguments** with the app's usual directories. The earlier command using those arguments plus `umbral-launcher` was unsafe and is superseded here. That launcher always prepends its own `-profile`; passing a second profile is not a reliable override.

```sh
bash scripts/test-flatpak-isolated.sh --check
```

This starts only a shell in the build sandbox, never the browser. It creates a marked, owned directory under `/tmp/umbral-flatpak-test.*`, checks canonical paths and rejects profile/XDG directory symlinks. It sets XDG directories and `TMPDIR` **inside** the sandbox, prints their effective values, and constructs a single explicit `--profile` argument. It bypasses `umbral-launcher`. The temporary manifest is used only for the sandbox permissions: `--run` does not download sources or build a package.

The checked probe reported:

```text
Effective profile: /tmp/umbral-flatpak-test.EEjTFL/profile
XDG_DATA_HOME: /tmp/umbral-flatpak-test.EEjTFL/data
XDG_CONFIG_HOME: /tmp/umbral-flatpak-test.EEjTFL/config
XDG_CACHE_HOME: /tmp/umbral-flatpak-test.EEjTFL/cache
TMPDIR: /tmp/umbral-flatpak-test.EEjTFL/tmp
Command: /app/umbral/zen --no-remote --profile /tmp/umbral-flatpak-test.EEjTFL/profile
```

Use the **exact `--run` command printed by your check**, for example:

```sh
bash scripts/test-flatpak-isolated.sh --run /tmp/umbral-flatpak-test.EEjTFL
```

`--run` repeats the same checks in the sandbox immediately before `exec`. Reusing that same temporary directory preserves choices for a restart test. Run `--check` without a directory to create another fresh test. The initial profile audit was shell-only; the subsequent graphical verification below did launch the browser with exclusive temporary profiles. The existing build tree still needs regeneration for the latest UI.

### Graphical-session correction

The shell-only profile check originally missed a graphics failure: `flatpak-builder --run` cleared both `DISPLAY` and `WAYLAND_DISPLAY`, even though finish permissions already declared graphics sockets. `XDG_RUNTIME_DIR` remained `/run/user/1000`; the helper did not replace it. Passing only filesystem/XDG configuration was therefore insufficient for graphical startup.

The helper now explicitly forwards the available Wayland display and enables that backend. It preserves Flatpak's runtime directory and checks that the Wayland socket is accessible. For X11 it forwards `DISPLAY` and selects the X11 socket, disabling the conflicting Wayland/fallback-X11 selection only for that run. No whole runtime directory, home directory or host filesystem permission was added; the Firefox sandbox was not disabled. `--check` now validates graphics as well as profile paths. On Wayland, an empty `DISPLAY` is expected when the fallback-X11 permission suppresses X11.

`scripts/tests/umbral_flatpak_graphics.py` successfully opened the existing packaged application graphically through the corrected helper on both Wayland and X11/XWayland in the current Wayland desktop session. The automation enabled Marionette only for these test instances, used dynamic ports and exclusive fresh profiles, asserted `moz:headless=false`, checked the effective `ProfD` and XDG locations from inside the running browser, captured and visually inspected the welcome screen, then shut down each instance normally. Both reported `security.sandbox.content.level=6` and no `MOZ_DISABLE_CONTENT_SANDBOX` setting. Native Xorg-session testing remains pending; the observed X11 run used this desktop's XWayland server. No installed profile or personal process was opened or modified.

Raw observations are in [validation/flatpak-graphics-20261103.json](validation/flatpak-graphics-20261103.json). Reproduce from the repository root:

```sh
cd engine
./mach python --virtualenv common ../scripts/tests/umbral_flatpak_graphics.py
cd ..
```

For manual use, run `--check`, then the exact `--run` command it prints. To request X11 explicitly, prefix either invocation with `MOZ_ENABLE_WAYLAND=0`. The helper change takes effect immediately and does not require rebuilding or reinstalling the Flatpak.

Check shortcuts/menu/order after restart, independent password controls, AI Cancel with your explicitly started server, the unchanged ETP cards and uBO popup. Do not reuse a Zen/Firefox profile or the installed Umbral profile.

## Persistent changes

- Homepage: `src/browser/actors/AboutNewTabChild-sys-mjs.patch`, existing parent-actor patch, `src/browser/extensions/newtab/prerendered/umbral-home-{html,css}.patch`, bundled Fluent and `locales/{en-US,es-ES}/browser/browser/umbralHome.ftl`.
- Passwords: `prefs/zen/passwords.yaml`, `src/toolkit/components/passwordmgr/LoginManagerParent-sys-mjs.patch`, Preferences `privacy-{inc-xhtml,js}.patch`, `config/passwords-autofill-mjs.patch`, registration in `zen-settings.js` and en/es Fluent.
- AI: `src/zen/common/modules/UmbralLocalAI.sys.mjs`, its `jar.inc.mn`, `prefs/zen/ai.yaml`, Preferences pane/category markup/scripts/styles and en/es Fluent.
- Updates: distribution policy/build patch, `prefs/zen/updates.yaml`, `surfer.json`, unofficial-brand preferences, `src/build/{application-ini-in,moz-build}.patch`, `scripts/{umbral_update,verify-umbral-update,manage-umbral-update}.py`. The shell-only safety audit additionally adds `scripts/test-flatpak-isolated.sh`.
- Tests, profiler capture, measurements and this document under `scripts/`, `scripts/tests/`, `docs/validation/`.

Existing welcome/branding/search/Flatpak changes were preserved. An identical duplicate newtab test-manifest patch was removed earlier in this task; its complete canonical counterpart remains. Import retries never skipped checks or regenerated the engine. When the update-host patch changed, Surfer could not reverse the previous replacement; that generated file was backed up and its single old hostname synchronized with the persistent patch before the two successful imports. No unrelated changes were discarded or staged.
