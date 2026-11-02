/* Any copyright is dedicated to the Public Domain.
   https://creativecommons.org/publicdomain/zero/1.0/ */

"use strict";

add_task(async function test_container_inheritance_user_entrypoints() {
  await SpecialPowers.pushPrefEnv({
    set: [["zen.testing.enabled", false]],
  });

  const { ContextualIdentityService } = ChromeUtils.importESModule(
    "moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs"
  );
  const work = ContextualIdentityService.create(
    "Container inheritance test",
    "briefcase",
    "orange"
  );
  const originalTabs = new Set(gBrowser.tabs);

  registerCleanupFunction(async () => {
    await SpecialPowers.popPrefEnv();
    for (const tab of [...gBrowser.tabs]) {
      if (!originalTabs.has(tab)) {
        BrowserTestUtils.removeTab(tab);
      }
    }
    ContextualIdentityService.remove(work.userContextId);
  });

  const workTab = BrowserTestUtils.addTab(gBrowser, "about:blank", {
    userContextId: work.userContextId,
    skipAnimation: true,
  });
  gBrowser.selectedTab = workTab;

  let opened = BrowserTestUtils.waitForEvent(gBrowser.tabContainer, "TabOpen");
  EventUtils.synthesizeKey("t", { accelKey: true });
  let newTab = (await opened).target;
  Assert.equal(
    newTab.userContextId,
    work.userContextId,
    "Ctrl+T inherits the selected tab's container."
  );

  const activeWorkspace = gZenWorkspaces.activeWorkspaceElement;
  const newTabButton = activeWorkspace.newTabButton;
  Assert.ok(newTabButton && !newTabButton.hidden);
  const previousTabCount = gBrowser.tabs.length;
  opened = BrowserTestUtils.waitForEvent(gBrowser.tabContainer, "TabOpen");
  EventUtils.synthesizeMouseAtCenter(newTabButton, {});
  newTab = (await opened).target;
  Assert.equal(
    gBrowser.tabs.length,
    previousTabCount + 1,
    "The sidebar button opens exactly one tab."
  );
  Assert.equal(
    newTab.userContextId,
    work.userContextId,
    "The sidebar button inherits the selected tab's container."
  );
  const containerButton = activeWorkspace.querySelector(
    ".zen-sidebar-containers-button"
  );
  await TestUtils.waitForCondition(
    () =>
      containerButton.getAttribute("usercontextid") ===
      String(work.userContextId),
    "The selector reflects the newly opened tab's container."
  );

  const uncontaineredTab = BrowserTestUtils.addTab(gBrowser, "about:blank", {
    userContextId: 0,
    skipAnimation: true,
  });
  gBrowser.selectedTab = uncontaineredTab;
  Assert.equal(uncontaineredTab.userContextId, 0);

  opened = BrowserTestUtils.waitForEvent(gBrowser.tabContainer, "TabOpen");
  EventUtils.synthesizeKey("t", { accelKey: true });
  newTab = (await opened).target;
  Assert.equal(
    newTab.userContextId,
    0,
    "A regular tab without a container inherits 0 instead of the last container."
  );

  gBrowser.selectedTab = workTab;
  const emptyTab = [...gBrowser.tabs].find(tab =>
    tab.hasAttribute("zen-empty-tab")
  );
  Assert.ok(
    emptyTab,
    "The internal empty tab is available for the fallback check."
  );
  gBrowser.selectedTab = emptyTab;

  opened = BrowserTestUtils.waitForEvent(gBrowser.tabContainer, "TabOpen");
  EventUtils.synthesizeKey("t", { accelKey: true });
  newTab = (await opened).target;
  Assert.equal(
    newTab.userContextId,
    work.userContextId,
    "The internal empty tab falls back to the last used container."
  );

  const button = [
    ...document.querySelectorAll(".zen-sidebar-containers-button"),
  ].find(item => !item.hidden);
  Assert.ok(button, "The active workspace exposes the containers dropdown.");
  const popup = button.querySelector(".zen-sidebar-containers-popup");
  const popupShown = BrowserTestUtils.waitForEvent(popup, "popupshown");
  EventUtils.synthesizeMouseAtCenter(button, {});
  await popupShown;

  const workItem = popup.querySelector(
    `menuitem[data-usercontextid="${work.userContextId}"]`
  );
  Assert.ok(workItem, "The dropdown contains the test container.");
  Assert.equal(
    workItem.getAttribute("command"),
    "Browser:NewUserContextTab",
    "The dropdown item invokes the normal new-container command."
  );
  opened = BrowserTestUtils.waitForEvent(gBrowser.tabContainer, "TabOpen");
  popup.activateItem(workItem);
  newTab = (await opened).target;
  Assert.equal(
    newTab.userContextId,
    work.userContextId,
    "Choosing a container from the real dropdown opens it in that container."
  );
});
