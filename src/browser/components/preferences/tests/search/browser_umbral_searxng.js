/* Any copyright is dedicated to the Public Domain.
 * http://creativecommons.org/publicdomain/zero/1.0/ */

"use strict";

const { HttpServer } = ChromeUtils.importESModule(
  "resource://testing-common/httpd.sys.mjs"
);
const { SearchService } = ChromeUtils.importESModule(
  "moz-src:///toolkit/components/search/SearchService.sys.mjs"
);
const { AddonManager } = ChromeUtils.importESModule(
  "resource://gre/modules/AddonManager.sys.mjs"
);

add_task(async function test_umbral_searxng_controls_in_redesigned_preferences() {
  Services.prefs.setBoolPref("browser.settings-redesign.enabled", true);
  const tab = await BrowserTestUtils.openNewForegroundTab(gBrowser, "about:blank");
  await openPreferences("search");
  await TestUtils.waitForCondition(
    () => gBrowser.contentDocument?.getElementById("umbralSearxngUrl"),
    "SearXNG controls render in the redesigned Preferences search pane"
  );
  Assert.ok(
    gBrowser.contentDocument.getElementById("umbralSearxngAdd"),
    "The add action is available in the redesigned Preferences pane"
  );
  Assert.ok(
    gBrowser.contentDocument.getElementById("umbralSearxngRemove"),
    "The remove action is available in the redesigned Preferences pane"
  );
  BrowserTestUtils.removeTab(gBrowser.selectedTab);
  if (tab.isConnected) {
    BrowserTestUtils.removeTab(tab);
  }
  Services.prefs.setBoolPref("browser.settings-redesign.enabled", false);
});

add_task(async function test_umbral_privacy_defaults_and_searxng() {
  Assert.equal(
    Services.prefs.getStringPref("browser.contentblocking.category"),
    "strict",
    "Fresh profiles default to ETP Strict"
  );
  Assert.ok(
    !Services.prefs.getBoolPref("privacy.resistFingerprinting", false),
    "Resist Fingerprinting remains off"
  );
  for (const category of ["standard", "custom", "strict"]) {
    Services.prefs.setStringPref("browser.contentblocking.category", category);
    Assert.equal(
      Services.prefs.getStringPref("browser.contentblocking.category"),
      category,
      `An explicit ${category} choice remains selected`
    );
  }
  Assert.equal(
    await AddonManager.getAddonByID("uBlock0@raymondhill.net"),
    null,
    "This isolated SearXNG test run stages no distro XPI, avoiding external filter-list requests"
  );

  const server = new HttpServer();
  let searchRequests = [];
  server.registerPathHandler("/nested/opensearch.xml", (_request, response) => {
    response.setHeader("Content-Type", "application/opensearchdescription+xml", false);
    response.write(`<?xml version="1.0"?>
      <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
        <ShortName>SearXNG Local Test</ShortName>
        <Description>Controlled SearXNG test endpoint</Description>
        <InputEncoding>UTF-8</InputEncoding>
        <Url type="text/html" method="GET" template="http://127.0.0.1:${server.identity.primaryPort}/nested/search?q={searchTerms}" />
      </OpenSearchDescription>`);
  });
  server.registerPathHandler("/changed/opensearch.xml", (_request, response) => {
    response.setHeader("Content-Type", "application/opensearchdescription+xml", false);
    response.write(`<?xml version="1.0"?>
      <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
        <ShortName>SearXNG Local Test</ShortName>
        <Description>Changed controlled test endpoint</Description>
        <InputEncoding>UTF-8</InputEncoding>
        <Url type="text/html" method="GET" template="http://127.0.0.1:${server.identity.primaryPort}/changed/search?q={searchTerms}" />
      </OpenSearchDescription>`);
  });
  server.registerPathHandler("/suggest/opensearch.xml", (_request, response) => {
    response.setHeader("Content-Type", "application/opensearchdescription+xml", false);
    response.write(`<?xml version="1.0"?>
      <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
        <ShortName>SearXNG Suggestions Test</ShortName>
        <Url type="text/html" template="http://127.0.0.1:${server.identity.primaryPort}/nested/search?q={searchTerms}" />
        <Url type="application/x-suggestions+json" template="http://127.0.0.1:${server.identity.primaryPort}/suggest?q={searchTerms}" />
      </OpenSearchDescription>`);
  });
  for (const path of ["/nested/search", "/changed/search"]) {
    server.registerPathHandler(path, (request, response) => {
      searchRequests.push({ path, query: request.queryString });
      response.setHeader("Content-Type", "text/html; charset=utf-8", false);
      response.write("<!doctype html><title>Local SearXNG result</title>ok");
    });
  }
  server.start(-1);
  registerCleanupFunction(() => server.stop(() => {}));

  const prefs = await openPreferencesViaOpenPreferencesAPI("search", {
    leaveOpen: true,
  });
  const doc = gBrowser.contentDocument;
  const urlInput = doc.getElementById("umbralSearxngUrl");
  const addButton = doc.getElementById("umbralSearxngAdd");
  const removeButton = doc.getElementById("umbralSearxngRemove");
  const status = doc.getElementById("umbralSearxngStatus");
  Assert.ok(urlInput && addButton && removeButton && status, "SearXNG controls are present");

  urlInput.value = `http://127.0.0.1:${server.identity.primaryPort}/nested`;
  Assert.equal(searchRequests.length, 0, "Typing an instance URL sends no requests");
  let addClicked = false;
  addButton.addEventListener("click", () => (addClicked = true), {
    once: true,
  });
  addButton.click();
  Assert.ok(addClicked, "The SearXNG add control dispatches a click event");
  Assert.equal(
    status.getAttribute("data-l10n-id"),
    "zen-searxng-http-local-confirm",
    "The first local HTTP action displays its warning"
  );
  Assert.equal(searchRequests.length, 0, "Confirmation has not contacted the instance yet");
  addButton.click();
  await TestUtils.waitForCondition(
    () => SearchService.getEngineByName("SearXNG Local Test"),
    "Explicit confirmation adds the OpenSearch engine"
  );
  let engine = SearchService.getEngineByName("SearXNG Local Test");
  Assert.ok(engine, "Engine was registered through Firefox SearchService");
  Assert.equal(searchRequests.length, 0, "Adding the engine did not submit a search");

  const query = "special & café / 雪";
  const beforeNormal = SearchService.defaultEngine;
  Assert.notEqual(beforeNormal.id, engine.id, "Adding does not change the normal default");
  const submission = engine.getSubmission(query);
  Assert.equal(
    new URL(submission.uri.spec).searchParams.get("q"),
    query,
    "OpenSearch encodes reserved and non-ASCII characters as one search term"
  );

  await SearchService.setDefault(engine, SearchService.CHANGE_REASON.USER);
  const searchTab = await BrowserTestUtils.openNewForegroundTab(gBrowser, "about:blank");
  const loaded = BrowserTestUtils.browserLoaded(
    searchTab.linkedBrowser,
    false,
    url => url.includes("/nested/search?")
  );
  gURLBar.value = query;
  gURLBar.handleCommand();
  await loaded;
  Assert.equal(
    new URLSearchParams(searchRequests.at(-1).query).get("q"),
    query,
    "Address-bar search reached the controlled instance with the original query"
  );
  BrowserTestUtils.removeTab(searchTab);

  await SearchService.setDefaultPrivate(engine, SearchService.CHANGE_REASON.USER);
  const privateWindow = await BrowserTestUtils.openNewBrowserWindow({
    private: true,
  });
  const privateLoaded = BrowserTestUtils.browserLoaded(
    privateWindow.gBrowser.selectedBrowser,
    false,
    url => url.includes("/nested/search?")
  );
  privateWindow.gURLBar.value = "private test";
  privateWindow.gURLBar.handleCommand();
  await privateLoaded;
  Assert.equal(
    new URLSearchParams(searchRequests.at(-1).query).get("q"),
    "private test",
    "Private address-bar search uses the independently selected private default"
  );
  await BrowserTestUtils.closeWindow(privateWindow);

  const normalEngine = SearchService.defaultEngine;
  const privateEngine = SearchService.defaultPrivateEngine;
  urlInput.value = `http://127.0.0.1:${server.identity.primaryPort}/changed`;
  addButton.click();
  Assert.equal(
    status.getAttribute("data-l10n-id"),
    "zen-searxng-http-local-confirm",
    "Updating a local HTTP instance requires confirmation again"
  );
  addButton.click();
  await TestUtils.waitForCondition(
    () => {
      const updated = SearchService.getEngineByName("SearXNG Local Test");
      return updated && updated.id !== engine.id;
    },
    "Editing replaces the previous engine"
  );
  engine = SearchService.getEngineByName("SearXNG Local Test");
  Assert.equal(
    (await SearchService.getEngines()).filter(e => e.name === "SearXNG Local Test").length,
    1,
    "Editing does not duplicate the engine"
  );
  Assert.equal(SearchService.defaultEngine.id, engine.id, "Normal default follows the edited engine");
  Assert.equal(SearchService.defaultPrivateEngine.id, engine.id, "Private default follows the edited engine");
  Assert.notEqual(normalEngine.id, engine.id, "The edited engine has a new stored identity");
  Assert.equal(privateEngine.id, normalEngine.id, "Both defaults were aligned before the edit");
  await TestUtils.waitForCondition(
    () =>
      Services.prefs.getStringPref("umbral.search.searxng.engineId", "") ===
      engine.id,
    "The edited engine identity is persisted before removal"
  );

  removeButton.click();
  await TestUtils.waitForCondition(
    () => status.getAttribute("data-l10n-id") === "zen-searxng-remove-active",
    "The asynchronous remove handler asks before removing an active engine"
  );
  Assert.equal(
    status.getAttribute("data-l10n-id"),
    "zen-searxng-remove-active",
    "Removing an active search engine requires explicit confirmation"
  );
  Assert.ok(SearchService.getEngineByName("SearXNG Local Test"));
  removeButton.click();
  await TestUtils.waitForCondition(
    () => !SearchService.getEngineByName("SearXNG Local Test"),
    "Confirmed removal deletes the managed engine"
  );
  Assert.equal(SearchService.defaultEngine.id, "ddg", "Deleting an active engine chooses DDG explicitly");
  Assert.equal(SearchService.defaultPrivateEngine.id, "ddg", "Private default also returns to DDG");
  Assert.equal(searchRequests.length, 2, "No search was sent during add, edit, or removal");

  urlInput.value = "not a URL";
  addButton.click();
  Assert.equal(
    status.getAttribute("data-l10n-id"),
    "zen-searxng-invalid-url",
    "Malformed instance URLs are rejected without network access"
  );

  urlInput.value = `http://127.0.0.1:${server.identity.primaryPort + 1}/offline`;
  addButton.click();
  Assert.equal(
    status.getAttribute("data-l10n-id"),
    "zen-searxng-http-local-confirm",
    "Local HTTP warning appears before testing an inaccessible instance"
  );
  addButton.click();
  await TestUtils.waitForCondition(
    () => status.getAttribute("data-l10n-id") === "zen-searxng-error",
    "An inaccessible instance reports an error instead of falling back"
  );
  Assert.equal(SearchService.defaultEngine.id, "ddg", "A failed instance leaves the selected default unchanged");

  urlInput.value = `http://127.0.0.1:${server.identity.primaryPort}/suggest`;
  addButton.click();
  addButton.click();
  await TestUtils.waitForCondition(
    () => status.getAttribute("data-l10n-id") === "zen-searxng-error",
    "An OpenSearch endpoint that advertises remote suggestions is rejected"
  );
  Assert.equal(
    SearchService.getEngineByName("SearXNG Suggestions Test"),
    null,
    "The rejected suggestions endpoint is not added as a search engine"
  );
  BrowserTestUtils.removeTab(gBrowser.selectedTab);
});
