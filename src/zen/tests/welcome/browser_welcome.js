/* Any copyright is dedicated to the Public Domain.
   https://creativecommons.org/publicdomain/zero/1.0/ */

"use strict";

let lazy = {};

ChromeUtils.defineESModuleGetters(lazy, {
  SearchService: "moz-src:///toolkit/components/search/SearchService.sys.mjs",
});

const { DefaultBrowserHelper } = ChromeUtils.importESModule(
  "chrome://browser/content/preferences/DefaultBrowserHelper.mjs",
  { global: "current" }
);

function currentPageContent() {
  return document.querySelector(
    "#zen-welcome-page-content > .zen-welcome-page:not([exiting])"
  );
}

add_task(async function test_UmbralWelcomeFlow() {
  Assert.ok(
    !Services.prefs
      .getDefaultBranch("")
      .getBoolPref("zen.welcome-screen.seen", false),
    "Fresh profiles should show the welcome screen by default"
  );
  Assert.ok(document.getElementById("zen-welcome"), "Welcome is visible");
  Assert.ok(
    document.querySelector("#zen-welcome-start .umbral-welcome-logo"),
    "The landing step uses an Umbral logo"
  );

  await TestUtils.waitForCondition(() => {
    const button = document.getElementById("zen-welcome-start-button");
    return button && Number(getComputedStyle(button).opacity) > 0.99;
  }, "the start button is ready");
  EventUtils.synthesizeMouseAtCenter(
    document.getElementById("zen-welcome-start-button"),
    {}
  );
  await waitForWelcomePage("search");
  Assert.equal(
    document.querySelectorAll("#zen-welcome-stepper li").length,
    4,
    "The setup has four steps"
  );
  Assert.equal(
    document.querySelector('#zen-welcome-stepper li[aria-current="step"]')
      .dataset.l10nId,
    "zen-welcome-step-search",
    "Search is the second step"
  );

  await TestUtils.waitForCondition(
    () => currentPageContent()?.querySelectorAll(".zen-welcome-option").length,
    "search engines are rendered"
  );
  const searchOptions = currentPageContent().querySelectorAll(
    ".zen-welcome-search-engines .zen-welcome-option"
  );
  Assert.greater(searchOptions.length, 1, "Search alternatives are available");
  const defaultEngine = await lazy.SearchService.getDefault();
  Assert.equal(defaultEngine.name, "DuckDuckGo", "DuckDuckGo is the default");
  Assert.ok(
    [...searchOptions]
      .find(option =>
        option
          .querySelector(".zen-welcome-option-label")
          .textContent.includes(defaultEngine.name)
      )
      .querySelector("input").checked,
    "The default engine is selected"
  );
  Assert.ok(
    currentPageContent().querySelector("#zen-welcome-searxng-url"),
    "The search step offers a SearXNG URL field"
  );
  Assert.ok(
    currentPageContent().querySelector("#zen-welcome-searxng-add"),
    "SearXNG requires an explicit Add action"
  );

  const searchField = currentPageContent().querySelector(
    "#zen-welcome-searxng-url"
  );
  searchField.value = "not a URL";
  EventUtils.synthesizeMouseAtCenter(
    currentPageContent().querySelector("#zen-welcome-searxng-add"),
    {}
  );
  Assert.equal(
    currentPageContent()
      .querySelector("#zen-welcome-searxng-status")
      .getAttribute("data-l10n-id"),
    "zen-welcome-searxng-invalid-url",
    "An invalid SearXNG address reports an error without contacting it"
  );
  Assert.equal(
    (await lazy.SearchService.getDefault()).name,
    defaultEngine.name,
    "SearXNG setup does not change the selected engine"
  );

  await EventUtils.synthesizeMouseAtCenter(searchOptions[1], {});
  await TestUtils.waitForCondition(
    async () =>
      (await lazy.SearchService.getDefault()).name !== defaultEngine.name,
    "the selected search engine is applied"
  );
  const selectedEngine = await lazy.SearchService.getDefault();
  Assert.ok(searchOptions[1].querySelector("input").checked);
  Assert.equal(
    selectedEngine.name,
    searchOptions[1]
      .querySelector(".zen-welcome-option-label")
      .textContent.trim(),
    "The chosen search engine matches the checked option"
  );

  await clickWelcomeButton("zen-welcome-continue", "theme");
  const themeChoices = currentPageContent().querySelectorAll(
    ".zen-welcome-option"
  );
  Assert.equal(
    themeChoices.length,
    3,
    "All three appearance choices are shown"
  );
  Assert.ok(
    currentPageContent().querySelector("#zen-welcome-theme-system").checked,
    "A new profile starts with the system appearance"
  );
  for (const [mode, expected] of [
    ["light", 0],
    ["dark", 1],
  ]) {
    const themeInput = currentPageContent().querySelector(
      `#zen-welcome-theme-${mode}`
    );
    themeInput.click();
    await TestUtils.waitForCondition(
      () =>
        Services.prefs.getIntPref("ui.systemUsesDarkTheme", -1) === expected,
      `${mode} appearance is selected`
    );
    Assert.equal(
      Services.prefs.getIntPref("ui.systemUsesDarkTheme"),
      expected,
      `${mode} uses Firefox's existing appearance preference`
    );
    const expectedBackground =
      mode === "light" ? "rgb(244, 244, 245)" : "rgb(17, 18, 20)";
    await TestUtils.waitForCondition(
      () =>
        getComputedStyle(document.getElementById("zen-welcome"))
          .backgroundColor === expectedBackground,
      `${mode} welcome colors are applied`
    );
    Assert.equal(
      getComputedStyle(document.getElementById("zen-welcome")).backgroundColor,
      expectedBackground,
      `${mode} uses a neutral welcome background`
    );
  }
  const systemThemeInput = currentPageContent().querySelector(
    "#zen-welcome-theme-system"
  );
  systemThemeInput.click();
  Assert.ok(
    !Services.prefs.prefHasUserValue("ui.systemUsesDarkTheme"),
    "System appearance clears the override"
  );

  document.getElementById("zen-welcome-back").click();
  await waitForWelcomePage("search");
  Assert.equal(
    (await lazy.SearchService.getDefault()).name,
    selectedEngine.name,
    "Going back preserves the search choice"
  );
  await clickWelcomeButton("zen-welcome-continue", "theme");
  Assert.ok(
    currentPageContent().querySelector("#zen-welcome-theme-system").checked,
    "Returning preserves the system appearance choice"
  );

  let defaultBrowserSandbox;
  let setDefaultStub;
  if (DefaultBrowserHelper.canCheck) {
    const { sinon } = ChromeUtils.importESModule(
      "resource://testing-common/Sinon.sys.mjs"
    );
    defaultBrowserSandbox = sinon.createSandbox();
    let isDefault = false;
    const mockShellService = {
      isDefaultBrowser: () => isDefault,
      async setDefaultBrowser() {
        isDefault = true;
      },
    };
    defaultBrowserSandbox
      .stub(window, "getShellService")
      .returns(mockShellService);
    setDefaultStub = sinon.spy(mockShellService, "setDefaultBrowser");
  }

  await clickWelcomeButton("zen-welcome-continue", "finish");
  await TestUtils.waitForCondition(
    () => document.getElementById("zen-welcome-set-default-browser"),
    "the default-browser action is ready"
  );
  Assert.equal(
    currentPageContent().querySelectorAll(".zen-welcome-summary article")
      .length,
    2,
    "The last step explains privacy protections and containers"
  );
  const defaultBrowserButton = document.getElementById(
    "zen-welcome-set-default-browser"
  );
  Assert.ok(
    defaultBrowserButton,
    "The final step offers a default-browser action"
  );
  const spanish = Services.locale.appLocaleAsBCP47 === "es-ES";
  Assert.equal(
    defaultBrowserButton.textContent.trim(),
    spanish
      ? "Establecer Umbral como navegador predeterminado"
      : "Set Umbral as default browser",
    "The default-browser action is localized"
  );
  Assert.equal(
    document
      .querySelector(
        "#zen-welcome-page-buttons button:not(#zen-welcome-set-default-browser)"
      )
      .textContent.trim(),
    spanish ? "Ahora no" : "Not now",
    "The defer action is localized"
  );
  Assert.ok(
    currentPageContent().querySelector("#zen-welcome-default-browser-status"),
    "The default-browser state is announced accessibly"
  );
  if (DefaultBrowserHelper.canCheck) {
    defaultBrowserButton.click();
    await TestUtils.waitForCondition(
      () =>
        currentPageContent()
          .querySelector("#zen-welcome-default-browser-status")
          ?.getAttribute("data-l10n-id") ===
        "zen-welcome-default-browser-current",
      "the UI confirms the default state only after checking it"
    );
    Assert.equal(
      setDefaultStub.callCount,
      1,
      "The native setter runs after explicit activation"
    );
    Assert.ok(
      defaultBrowserButton.disabled,
      "The action is disabled after confirmation"
    );
    Assert.equal(
      defaultBrowserButton.textContent.trim(),
      spanish
        ? "Umbral ya es el navegador predeterminado"
        : "Umbral is already the default browser",
      "The verified state is localized"
    );
    defaultBrowserSandbox.restore();
  } else {
    Assert.ok(
      defaultBrowserButton.disabled,
      "Unsupported environments disable the action"
    );
    Assert.equal(
      currentPageContent()
        .querySelector("#zen-welcome-default-browser-status")
        .getAttribute("data-l10n-id"),
      "zen-welcome-default-browser-unavailable",
      "The unsupported environment is explained"
    );
  }
  await clickWelcomeButton("zen-welcome-not-now");
  await TestUtils.waitForCondition(
    () => !document.getElementById("zen-welcome"),
    "the welcome flow closes"
  );
  await TestUtils.waitForCondition(
    () => gBrowser.selectedBrowser.currentURI.spec === "about:home",
    "the Umbral homepage opens"
  );
  Assert.ok(
    Services.prefs.getBoolPref("zen.welcome-screen.seen"),
    "Completing the flow records the welcome as seen"
  );
  Assert.equal(
    (await lazy.SearchService.getDefault()).name,
    selectedEngine.name,
    "The selected search engine remains active at completion"
  );
});
