# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine/testing/marionette/client"))
sys.path.extend(str(path) for path in (ROOT / "engine/testing/mozbase").iterdir() if path.is_dir())
sys.path.insert(0, str(ROOT / "engine/python/mozterm"))
from marionette_driver.marionette import ActionSequence, Marionette
BIN = ROOT / "engine/obj-x86_64-pc-linux-gnu/dist/bin/zen"
PROFILE = Path(tempfile.mkdtemp(prefix="umbral-ai-sidebar-"))
ENDPOINT_REQUESTS = []
DISCONNECTED = []

(PROFILE / "user.js").write_text("\n".join([
    'user_pref("remote.prefs.recommended", false);',
    'user_pref("marionette.port", 0);',
    'user_pref("browser.shell.checkDefaultBrowser", false);',
    'user_pref("browser.startup.homepage", "about:home");',
    'user_pref("browser.startup.page", 1);',
    'user_pref("umbral.ai.enabled", false);',
]) + "\n")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ENDPOINT_REQUESTS.append({"path": self.path, "body": body, "auth": self.headers.get("Authorization")})
        if self.headers.get("Authorization") != "Bearer temporary-test-secret":
            self.send_response(401)
            self.end_headers()
            return
        latest = body["messages"][-1]["content"]
        if latest == "slow":
            self.send_response(200)
            self.end_headers()
            try:
                self.wfile.write(b'{"choices":[')
                self.wfile.flush()
                for _ in range(100):
                    time.sleep(0.1)
                    self.wfile.write(b" ")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                DISCONNECTED.append(True)
            return
        data = json.dumps({"choices": [{"message": {"content": "Local reply: " + latest}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()


def launch():
    (PROFILE / "MarionetteActivePort").unlink(missing_ok=True)
    command = [str(BIN), "-no-remote", "-profile", str(PROFILE), "-marionette", "-remote-allow-system-access"]
    if shutil.which("xvfb-run"):
        command = ["xvfb-run", "-a", *command]
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Browser exited with status {proc.returncode}")
        try:
            port = int((PROFILE / "MarionetteActivePort").read_text().strip())
            driver = Marionette(host="127.0.0.1", port=port)
            driver.start_session()
            return proc, driver
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Marionette did not start")


def wait_js(driver, script, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = driver.execute_script("return (" + script + ")")
            if value:
                return value
        except Exception:
            pass
        time.sleep(0.05)
    raise RuntimeError("Condition timed out: " + script)


def close(proc, driver):
    try:
        driver.set_context("chrome")
        driver.execute_script("Services.tm.dispatchToMainThread(() => Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit))")
        proc.wait(timeout=20)
        if proc.returncode != 0:
            raise RuntimeError("Browser shutdown failed")
    except Exception:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
                proc.wait()
        raise RuntimeError("Browser did not shut down normally") from None


def click(driver, selector):
    driver.execute_script("document.querySelector(arguments[0]).click()", [selector])


def open_window(driver, private):
    driver.set_context("chrome")
    old = set(driver.chrome_window_handles)
    driver.execute_script("OpenBrowserWindow({private: arguments[0]})", [private])
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        added = set(driver.chrome_window_handles) - old
        if added:
            handle = added.pop()
            driver.switch_to_window(handle)
            driver.set_context("chrome")
            wait_js(driver, "!!window.gUmbralLocalAISidebar")
            return handle
        time.sleep(0.1)
    raise RuntimeError("New browser chrome window was not exposed to Marionette")


proc = driver = None
try:
    proc, driver = launch()
    initial_handle = driver.current_window_handle
    driver.set_context("chrome")
    initial_chrome_handle = driver.current_chrome_window_handle
    wait_js(driver, 'document.getElementById("zen-welcome-start-button")')
    assert driver.execute_script('return Services.prefs.getBoolPref("umbral.ai.enabled", false)') is False
    click(driver, "#zen-welcome-start-button")
    wait_js(driver, 'document.querySelector(".zen-welcome-page[page=search]")')
    click(driver, "#zen-welcome-page-buttons button")
    wait_js(driver, 'document.querySelector(".zen-welcome-page[page=theme]")')
    click(driver, "#zen-welcome-page-buttons button")
    wait_js(driver, 'document.querySelector(".zen-welcome-page[page=finish]")')
    wait_js(driver, 'document.getElementById("zen-welcome-ai-not-now")')
    wait_js(driver, 'document.getElementById("zen-welcome-ai-not-now").checked')
    assert not ENDPOINT_REQUESTS, "Welcome caused local-server traffic"
    click(driver, "#zen-welcome-ai-enable")
    wait_js(driver, 'Services.prefs.getBoolPref("umbral.ai.enabled", false)')
    assert not ENDPOINT_REQUESTS, "Enabling AI caused local-server traffic"
    click(driver, "#zen-welcome-ai-not-now")
    wait_js(driver, '!Services.prefs.getBoolPref("umbral.ai.enabled", false)')
    click(driver, "#zen-welcome-page-buttons button:last-child")
    wait_js(driver, '!document.getElementById("zen-welcome")')
    new_handles = set(driver.window_handles)
    driver.switch_to_window((new_handles - {initial_handle}).pop())

    driver.set_context("content")
    driver.navigate("about:preferences#umbralAI")
    wait_js(driver, 'document.getElementById("umbralAISettings").checkVisibility() && !!gUmbralAISettings.initialized')
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"
    driver.execute_script('''
      document.getElementById("umbralAIEndpoint").value=arguments[0];
      document.getElementById("umbralAIModel").value="controlled-model";
      document.getElementById("umbralAIKey").value="temporary-test-secret";
      document.getElementById("umbralAIEnabled").checked=true;
      gUmbralAISettings.saveConfiguration();
    ''', [endpoint])
    wait_js(driver, 'document.getElementById("umbralAIConfigStatus").dataset.l10nId === "umbral-ai-config-saved"')
    assert not ENDPOINT_REQUESTS, "Saving settings caused local-server traffic"

    driver.set_context("chrome")
    wait_js(driver, 'window.gUmbralLocalAISidebar && !document.getElementById("umbral-ai-sidebar-toggle").hidden')
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar-toggle").getAttribute("aria-label") === "Toggle local AI panel"')
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar").getAttribute("role")') == "region"
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar-splitter").getAttribute("role")') == "separator"
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar-clear").getAttribute("aria-label")') == "Clear conversation"
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar").parentElement.id') == "zen-tabbox-wrapper"
    click(driver, "#umbral-ai-sidebar-toggle")
    wait_js(driver, '!document.getElementById("umbral-ai-sidebar").collapsed')
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar-toggle").getAttribute("aria-expanded")') == "true"
    assert not ENDPOINT_REQUESTS, "Opening the panel caused local-server traffic"
    panel = driver.find_element("css selector", "#umbral-ai-sidebar")
    splitter = driver.find_element("css selector", "#umbral-ai-sidebar-splitter")
    before_width = driver.execute_script("return arguments[0].getBoundingClientRect().width", [panel])
    ActionSequence(driver, "pointer", "ai-panel-resize", {"pointerType": "mouse"}).pointer_move(0, 0, origin=splitter).pointer_down().pointer_move(-48, 0, origin="pointer").pointer_up().perform()
    time.sleep(0.3)
    after_width = driver.execute_script("return arguments[0].getBoundingClientRect().width", [panel])
    assert after_width != before_width, f"Panel did not resize: {before_width} -> {after_width}"

    driver.execute_script('''
      const input=document.getElementById("umbral-ai-sidebar-prompt");
      input.value="Only manually submitted text";
      input.dispatchEvent(new Event("input", {bubbles:true}));
      document.getElementById("umbral-ai-sidebar-form").requestSubmit();
    ''')
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar-conversation").textContent.includes("Local reply: Only manually submitted text")')
    assert len(ENDPOINT_REQUESTS) == 1
    assert ENDPOINT_REQUESTS[0]["path"] == "/v1/chat/completions"
    assert ENDPOINT_REQUESTS[0]["body"]["messages"] == [{"role": "user", "content": "Only manually submitted text"}]
    assert ENDPOINT_REQUESTS[0]["auth"] == "Bearer temporary-test-secret"
    assert "about:preferences" not in json.dumps(ENDPOINT_REQUESTS[0]["body"])

    click(driver, "#umbral-ai-sidebar-close")
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar").collapsed')
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar-toggle").getAttribute("aria-expanded")') == "false"
    click(driver, "#umbral-ai-sidebar-toggle")
    wait_js(driver, '!document.getElementById("umbral-ai-sidebar").collapsed')
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar-conversation").textContent.includes("Only manually submitted text")')
    click(driver, "#umbral-ai-sidebar-clear")
    wait_js(driver, '!document.getElementById("umbral-ai-sidebar-conversation").textContent')

    driver.execute_script('''
      const input=document.getElementById("umbral-ai-sidebar-prompt");
      input.value="Window one"; input.dispatchEvent(new Event("input", {bubbles:true}));
      document.getElementById("umbral-ai-sidebar-form").requestSubmit();
    ''')
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar-conversation").textContent.includes("Local reply: Window one")')
    original_handle = driver.current_window_handle
    regular_handle = open_window(driver, False)
    assert not driver.execute_script('return document.getElementById("umbral-ai-sidebar-conversation").textContent')
    assert driver.execute_script('return !PrivateBrowsingUtils.isWindowPrivate(window)')
    private_handle = open_window(driver, True)
    assert not driver.execute_script('return document.getElementById("umbral-ai-sidebar-conversation").textContent')
    assert driver.execute_script('return PrivateBrowsingUtils.isWindowPrivate(window)')
    driver.execute_script("window.close()")
    driver.switch_to_window(regular_handle)
    driver.set_context("chrome")
    driver.execute_script("window.close()")
    driver.switch_to_window(initial_chrome_handle)
    driver.set_context("chrome")
    assert driver.execute_script('return document.getElementById("umbral-ai-sidebar-conversation").textContent.includes("Window one")')
    assert len(ENDPOINT_REQUESTS) == 2
    assert ENDPOINT_REQUESTS[1]["body"]["messages"][-1]["content"] == "Window one"

    driver.execute_script('''
      const input=document.getElementById("umbral-ai-sidebar-prompt");
      input.value="slow"; input.dispatchEvent(new Event("input", {bubbles:true}));
      document.getElementById("umbral-ai-sidebar-form").requestSubmit();
    ''')
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar-status").dataset.l10nId === "umbral-ai-request-pending"')
    deadline = time.monotonic() + 10
    while len(ENDPOINT_REQUESTS) < 3 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(ENDPOINT_REQUESTS) == 3
    click(driver, "#umbral-ai-sidebar-cancel")
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar-status").dataset.l10nId === "umbral-ai-request-cancelled"')
    deadline = time.monotonic() + 5
    while not DISCONNECTED and time.monotonic() < deadline:
        time.sleep(0.05)
    assert DISCONNECTED, "Cancel left the local request socket open"

    driver.execute_script('''
      const input=document.getElementById("umbral-ai-sidebar-prompt");
      input.value="slow"; input.dispatchEvent(new Event("input", {bubbles:true}));
      document.getElementById("umbral-ai-sidebar-form").requestSubmit();
    ''')
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar-status").dataset.l10nId === "umbral-ai-request-pending"')
    deadline = time.monotonic() + 10
    while len(ENDPOINT_REQUESTS) < 4 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(ENDPOINT_REQUESTS) == 4
    driver.set_context("content")
    driver.navigate("about:preferences#umbralAI")
    wait_js(driver, 'document.getElementById("umbralAISettings").checkVisibility() && !!gUmbralAISettings.initialized')
    driver.execute_script('document.getElementById("umbralAIEnabled").checked=false;document.getElementById("umbralAIEnabled").dispatchEvent(new Event("command",{bubbles:true}))')
    driver.set_context("chrome")
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar").collapsed && document.getElementById("umbral-ai-sidebar-toggle").hidden')
    wait_js(driver, 'document.getElementById("umbral-ai-sidebar-status").dataset.l10nId === "umbral-ai-request-cancelled"')
    deadline = time.monotonic() + 5
    while len(DISCONNECTED) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(DISCONNECTED) == 2, "Disabling left the active local request open"
    credentials = driver.execute_async_script('const done=arguments[0];Services.logins.searchLoginsAsync({origin:"chrome://umbral-ai",httpRealm:"Umbral local AI"}).then(v=>done(v.map(x=>x.password)))')
    assert credentials == ["temporary-test-secret"], "Disabling AI removed the saved credential"
    assert len(ENDPOINT_REQUESTS) == 4, "Settings/window operations sent an automatic request"
    print(json.dumps({
        "result": "PASS",
        "welcome_default_off_and_not_now": True,
        "enable_save_open_no_traffic": True,
        "manual_send_only": True,
        "right_sidebar_resize_and_toggle": True,
        "hide_preserves_clear_erases": True,
        "per_window_and_private_conversations": True,
        "cancel_closes_request": True,
        "disable_closes_panel_and_retains_credentials": True,
        "local_requests": len(ENDPOINT_REQUESTS),
    }))
finally:
    if proc and driver:
        close(proc, driver)
    server.shutdown()
    shutil.rmtree(PROFILE, ignore_errors=True)
