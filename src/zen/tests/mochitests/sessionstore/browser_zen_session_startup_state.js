/* Any copyright is dedicated to the Public Domain.
   https://creativecommons.org/publicdomain/zero/1.0/ */

"use strict";

add_task(async function test_new_profile_and_saved_group_state() {
  Assert.ok(Services.prefs.getBoolPref("zen.window-sync.enabled"));

  const { ZenSessionStore } = ChromeUtils.importESModule(
    "resource:///modules/zen/ZenSessionManager.sys.mjs"
  );
  const emptyState = ZenSessionStore.onFileRead(null);
  Assert.ok(Array.isArray(emptyState?.windows), "A fresh profile has windows.");
  Assert.deepEqual(
    emptyState.savedGroups,
    [],
    "A fresh profile initializes savedGroups as an empty array."
  );
  Assert.equal(
    ZenSessionStore.onFileRead({ windows: [], savedGroups: null }),
    null,
    "A malformed savedGroups field is rejected rather than treated as absent."
  );

  const state = JSON.parse(SessionStore.getBrowserState());
  const groupId = "umbral-session-startup-regression";
  const savedGroup = {
    id: groupId,
    name: "startup session group",
    color: "blue",
    collapsed: false,
    saveOnWindowClose: true,
    saved: true,
    closedAt: Date.now(),
    tabs: [
      {
        state: {
          entries: [{ url: "about:robots", title: "about:robots" }],
          index: 1,
          userContextId: 0,
          attributes: {},
        },
        title: "about:robots",
        closedAt: Date.now(),
      },
    ],
    splitViews: [],
  };
  state.savedGroups = [savedGroup];
  const normalizedState = ZenSessionStore.onFileRead(state);
  Assert.ok(
    normalizedState.savedGroups.some(savedGroup => savedGroup.id === groupId),
    "Session normalization preserves saved groups."
  );
  Assert.deepEqual(normalizedState.savedGroups, [savedGroup]);
});

add_task(async function test_restore_saved_group_from_session_state() {
  const tabs = [
    BrowserTestUtils.addTab(gBrowser, "about:robots"),
    BrowserTestUtils.addTab(gBrowser, "about:about"),
  ];
  await Promise.all(
    tabs.map(tab => BrowserTestUtils.browserLoaded(tab.linkedBrowser))
  );
  const group = gBrowser.addTabGroup(tabs, {
    color: "blue",
    label: "restored session group",
    insertBefore: tabs[0],
  });
  const groupId = group.id;
  await TabStateFlusher.flushWindow(window);
  const saved = BrowserTestUtils.waitForEvent(group, "TabGroupSaved");
  group.save();
  await saved;
  const removed = BrowserTestUtils.waitForEvent(group, "TabGroupRemoved");
  await gBrowser.removeTabGroup(group);
  await removed;

  Assert.ok(SessionStore.getSavedTabGroup(groupId));
  const restoredPromise = BrowserTestUtils.waitForEvent(
    window,
    "SSWindowStateReady"
  );
  const restoredGroup = SessionStore.openSavedTabGroup(groupId, window);
  await restoredPromise;
  Assert.equal(restoredGroup.tabs.length, 2);
  Assert.equal(restoredGroup.label, "restored session group");

  const closed = BrowserTestUtils.waitForEvent(
    restoredGroup,
    "TabGroupRemoved"
  );
  await gBrowser.removeTabGroup(restoredGroup);
  await closed;
});
