# Bundled uBlock Origin

Umbral redistributes the unmodified, AMO-signed Firefox XPI for uBlock Origin.

- Add-on ID: `uBlock0@raymondhill.net`
- Bundled version: `1.75.0`
- Source: `https://addons.mozilla.org/firefox/downloads/latest/uBlock0@raymondhill.net/latest.xpi`
- SHA-256: `5b74415860456370644bd80f16125e865b0e6c356bb5dfcfb84069967eaa5287`
- License and attribution: the XPI contains the upstream `LICENSE.txt`, author metadata, and original default filter-list selections. uBlock Origin is GPL-3.0-only.

The package is staged in `distribution/extensions/` by `moz.build` and included
by the browser package manifest. Firefox installs a distribution add-on only
when that profile does not already have the same ID. This keeps the existing
profile installation and its extension storage in place. The user can disable
or remove the add-on. Firefox's add-on update service remains responsible for
updates; a bundled-XPI change alone does not replace an already-installed
distribution copy until an application version changes.
