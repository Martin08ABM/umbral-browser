/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

import { setTimeout, clearTimeout } from "resource://gre/modules/Timer.sys.mjs";

export async function requestCompletion(prompt, { signal } = {}) {
  if (
    !Services.prefs.getBoolPref("umbral.ai.enabled", false) ||
    typeof prompt !== "string" ||
    !prompt.trim() ||
    prompt.length > 4000
  ) {
    throw new Error("Local assistant unavailable");
  }
  const endpoint = new URL(
    Services.prefs.getStringPref("umbral.ai.endpoint", "")
  );
  const model = Services.prefs.getStringPref("umbral.ai.model", "");
  if (
    !["http:", "https:"].includes(endpoint.protocol) ||
    !["localhost", "127.0.0.1", "[::1]"].includes(endpoint.hostname) ||
    endpoint.username ||
    endpoint.password ||
    endpoint.search ||
    endpoint.hash ||
    !model ||
    model.length > 80
  ) {
    throw new Error("Invalid local assistant configuration");
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  const onDisabled = () => {
    if (!Services.prefs.getBoolPref("umbral.ai.enabled", false)) abort();
  };
  signal?.addEventListener("abort", abort, { once: true });
  Services.prefs.addObserver("umbral.ai.enabled", onDisabled);
  const timeout = setTimeout(abort, 60000);
  try {
    const logins = await Services.logins.searchLoginsAsync({
      origin: "chrome://umbral-ai",
      httpRealm: "Umbral local AI",
    });
    if (signal?.aborted) abort();
    onDisabled();
    controller.signal.throwIfAborted();
    const headers = { "Content-Type": "application/json" };
    if (logins[0]?.password)
      headers.Authorization = `Bearer ${logins[0].password}`;
    const response = await fetch(
      `${endpoint.href.replace(/\/$/, "")}/chat/completions`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          model,
          messages: [{ role: "user", content: prompt }],
        }),
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        referrerPolicy: "no-referrer",
        signal: controller.signal,
      }
    );
    if (!response.ok) throw new Error("Local server request failed");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let body = "";
    let size = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 65536) {
        await reader.cancel();
        throw Object.assign(new Error("Local server response too large"), {
          name: "UmbralLocalAIResponseError",
        });
      }
      body += decoder.decode(value, { stream: true });
    }
    body += decoder.decode();
    const answer = JSON.parse(body)?.choices?.[0]?.message?.content;
    if (typeof answer !== "string" || answer.length > 12000) {
      throw Object.assign(new Error("Unsupported local server response"), {
        name: "UmbralLocalAIResponseError",
      });
    }
    return answer;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
    Services.prefs.removeObserver("umbral.ai.enabled", onDisabled);
  }
}
