/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

const PROTECT_PREF = "umbral.search.protect-default";
const APPLIED_PREF = "umbral.search.default-applied";
const DEFAULT_ENGINE_ID = "ddg";

let applying = false;
let quitting = false;

function loadSearchService() {
  return ChromeUtils.importESModule(
    "moz-src:///toolkit/components/search/SearchService.sys.mjs"
  ).SearchService;
}

function storedEngineId(SearchService, attribute) {
  return SearchService._settings.getMetaDataAttribute(attribute) || "";
}

function pinEngineId(SearchService, attribute) {
  if (storedEngineId(SearchService, attribute) === DEFAULT_ENGINE_ID) {
    return;
  }
  SearchService._settings.setVerifiedMetaDataAttribute(
    attribute,
    DEFAULT_ENGINE_ID
  );
}

/**
 * DuckDuckGo is Umbral's application default. An empty defaultEngineId means
 * the profile is still following that application default; a non-empty
 * defaultEngineId is the user's stored choice and is never replaced.
 * Remote Settings can change the application default after the first run.
 * This pins DuckDuckGo while the profile has no explicit choice. An empty
 * id after that pin is the user selecting the application default and is
 * kept. It does not initialize the search service itself: doing so
 * schedules a settings write that can stall shutdown.
 */
async function applyUmbralDefaultSearch() {
  if (
    applying ||
    quitting ||
    Services.startup.shuttingDown ||
    !Services.prefs.getBoolPref(PROTECT_PREF, false)
  ) {
    return;
  }
  applying = true;
  try {
    const SearchService = loadSearchService();
    if (!SearchService.isInitialized || !SearchService.hasSuccessfullyInitialized) {
      return;
    }
    const storedId = storedEngineId(SearchService, "defaultEngineId");
    if (storedId && storedId !== DEFAULT_ENGINE_ID) {
      Services.prefs.setBoolPref(PROTECT_PREF, false);
      return;
    }
    if (storedId === DEFAULT_ENGINE_ID) {
      return;
    }
    // An empty id after DuckDuckGo was pinned means the user chose the
    // application default. That choice clears the stored id and is kept.
    if (Services.prefs.getBoolPref(APPLIED_PREF, false)) {
      Services.prefs.setBoolPref(PROTECT_PREF, false);
      return;
    }
    const current = SearchService.defaultEngine;
    if (!current) {
      return;
    }
    const duckDuckGo = SearchService.getEngineById(DEFAULT_ENGINE_ID);
    if (!duckDuckGo || quitting || Services.startup.shuttingDown) {
      if (!duckDuckGo) {
        console.error("UmbralDefaultSearch: DuckDuckGo is not installed");
      }
      return;
    }
    if (current.id !== DEFAULT_ENGINE_ID) {
      await SearchService.setDefault(
        duckDuckGo,
        SearchService.CHANGE_REASON.CONFIG
      );
    }
    const privateEngine = SearchService.defaultPrivateEngine;
    if (
      privateEngine &&
      privateEngine.id !== DEFAULT_ENGINE_ID &&
      !quitting &&
      !Services.startup.shuttingDown
    ) {
      await SearchService.setDefaultPrivate(
        duckDuckGo,
        SearchService.CHANGE_REASON.CONFIG
      );
    }
    if (quitting || Services.startup.shuttingDown) {
      return;
    }
    // setDefault clears the stored id when DuckDuckGo is still the
    // application default. Pin it so a later Remote Settings change does
    // not replace a profile that has not chosen another engine.
    pinEngineId(SearchService, "defaultEngineId");
    pinEngineId(SearchService, "privateDefaultEngineId");
    Services.prefs.setBoolPref(APPLIED_PREF, true);
  } catch (error) {
    console.error("UmbralDefaultSearch: could not apply DuckDuckGo", error);
  } finally {
    applying = false;
  }
}

function onSearchService(subject, topic, data) {
  if (quitting || Services.startup.shuttingDown) {
    return;
  }
  if (data === "init-complete" || data === "engines-reloaded") {
    applyUmbralDefaultSearch();
  }
}

function onQuit() {
  quitting = true;
  Services.obs.removeObserver(onSearchService, "browser-search-service");
  Services.obs.removeObserver(onDelayedStartup, "browser-delayed-startup-finished");
  Services.obs.removeObserver(onQuit, "quit-application-granted");
}

function onDelayedStartup() {
  if (!quitting && !Services.startup.shuttingDown) {
    applyUmbralDefaultSearch();
  }
}

Services.obs.addObserver(onSearchService, "browser-search-service");
Services.obs.addObserver(onDelayedStartup, "browser-delayed-startup-finished");
Services.obs.addObserver(onQuit, "quit-application-granted");
