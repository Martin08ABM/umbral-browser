# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from copy_language_pack import copy_browser_locales
import shutil
from pathlib import Path

if __name__ == "__main__":
  copy_browser_locales("en-US")

  # The locale merge reads l10n files below browser/browser. Also put the
  # custom preference catalog at its final Fluent resource path for direct
  # source-tree consumers.
  spanish_resources = {
    "locales/es-ES/browser/browser/preferences/zen-preferences.ftl": (
      "engine/browser/locales/es-ES/browser/browser/preferences/zen-preferences.ftl",
      "engine/browser/locales/es-ES/browser/preferences/zen-preferences.ftl",
    ),
    "locales/es-ES/browser/zen-welcome.ftl": (
      "engine/browser/locales/es-ES/browser/browser/zen-welcome.ftl",
      "engine/browser/locales/es-ES/browser/zen-welcome.ftl",
    ),
  }
  for source, targets in spanish_resources.items():
    for target in targets:
      target_path = Path(target)
      target_path.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(source, target_path)
