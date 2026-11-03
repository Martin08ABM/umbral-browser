/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

function currentPageContent() {
  return document.querySelector(
    "#zen-welcome-page-content > .zen-welcome-page:not([exiting])"
  );
}

async function waitForWelcomePage(page) {
  await TestUtils.waitForCondition(
    () => currentPageContent()?.getAttribute("page") === page,
    `the ${page} welcome step is visible`
  );
}

async function clickWelcomeButton(l10nId, nextPage = null) {
  const previousPage = currentPageContent()?.getAttribute("page");
  const button = document.querySelector(
    `#zen-welcome-page-buttons button[data-l10n-id="${l10nId}"]`
  );
  if (!button) {
    throw new Error(`Button with l10n-id "${l10nId}" not found`);
  }
  await TestUtils.waitForCondition(
    () => button.isConnected && !button.disabled,
    `the ${l10nId} welcome button is ready`
  );
  button.click();
  if (nextPage) {
    await waitForWelcomePage(nextPage);
  } else {
    await TestUtils.waitForCondition(
      () =>
        !document.getElementById("zen-welcome") ||
        currentPageContent()?.getAttribute("page") !== previousPage,
      "the welcome step changed"
    );
  }
}
