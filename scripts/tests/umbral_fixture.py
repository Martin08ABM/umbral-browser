# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json, shutil, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'engine/testing/marionette/client'))
from marionette_driver.marionette import Marionette
BIN=Path(__file__).resolve().parents[2]/'engine/obj-x86_64-pc-linux-gnu/dist/bin/zen'
profile=Path(tempfile.mkdtemp(prefix='umbral-feature-test-'))
(profile/'user.js').write_text('\n'.join([
'user_pref("zen.welcome-screen.seen", true);',
'user_pref("remote.prefs.recommended", false);',
'user_pref("marionette.port", 0);',
'user_pref("browser.shell.checkDefaultBrowser", false);',
'user_pref("browser.startup.homepage", "about:home");',
'user_pref("browser.startup.page", 1);',

])+'\n')

def launch():
    (profile/'MarionetteActivePort').unlink(missing_ok=True)
    proc=subprocess.Popen([str(BIN),'-headless','-no-remote','-profile',str(profile),'-marionette','-remote-allow-system-access'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    end=time.monotonic()+90
    while time.monotonic()<end:
        if proc.poll() is not None: raise RuntimeError(f'browser exit {proc.returncode}')
        try:
            port=int((profile/'MarionetteActivePort').read_text().strip())
            driver=Marionette(host='127.0.0.1',port=port); driver.start_session()
            return proc,driver
        except Exception: time.sleep(.25)
    proc.terminate()
    try: proc.wait(timeout=10)
    except Exception: proc.kill();proc.wait()
    raise RuntimeError('Marionette unavailable')

def close(proc,driver):
    try:
        driver.set_context('chrome')
        driver.execute_script('Services.tm.dispatchToMainThread(() => Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit))')
        proc.wait(timeout=20)
        if proc.returncode != 0:
            raise RuntimeError('Browser shutdown failed')
        return
    except Exception:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=10)
            except Exception: proc.kill();proc.wait()
        raise RuntimeError('Test browser did not shut down normally') from None

def wait_js(driver, script, timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=driver.execute_script('return ('+script+')')
        if value: return value
        time.sleep(.05)
    raise RuntimeError('Condition timed out: '+script)

