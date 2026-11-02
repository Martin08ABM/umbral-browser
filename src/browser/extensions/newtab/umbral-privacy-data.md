# Umbral homepage privacy data

The two count cards read the Firefox `TrackingDBService` aggregates for
`TRACKERS_ID` and `TRACKING_COOKIES_ID`. Each stored unit is a classified
third-party-origin entry from a content-blocking log, not an ad, network
request, or unique domain. The database stores only category, count, and UTC
date; the homepage receives only the two aggregate numbers.

The period covers exactly seven UTC dates: today and the preceding six days.
The `browser.contentblocking.database.enabled` preference must be enabled and
the query must succeed to display counts. An empty successful query is a valid
zero; a disabled source or query error is shown as “No data”.

`WindowGlobalParent.MaybeReportContentBlockingLog` returns before recording
logs from private browsing contexts. Read paths also flush live content-blocking
logs before querying, so a recently blocked resource can appear without
waiting for the tab to close. The homepage actor accepts requests only from
`about:home` and `about:newtab`, validates the response schema, and sends no
URLs, domains, history, or tab identifiers to the document.

uBlock Origin remains the original signed XPI. Its AddonManager state is shown
separately; ETP and uBO values are never combined. The homepage refreshes on
initial load and when it becomes visible again. Firefox's database service
offers milestone notifications, not a reliable notification for each new
aggregate row, so no per-event observer or polling is used.
