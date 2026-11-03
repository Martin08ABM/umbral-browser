# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine/testing/marionette/client'))
from marionette_driver.marionette import Marionette

helper = ROOT / 'scripts/test-flatpak-isolated.sh'
flatpak_builder = shutil.which('flatpak-builder')
results = []
with tempfile.TemporaryDirectory(prefix='umbral-graphics-driver-') as temporary:
    temporary = Path(temporary)
    wrapper = temporary / 'flatpak-builder'
    wrapper.write_text('#!/bin/sh\nfirst="$1"; shift\nexec "$UMBRAL_REAL_BUILDER" "$first" --env=MOZ_MARIONETTE=1 --env=MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1 "$@"\n')
    wrapper.chmod(0o700)
    for backend in ['Wayland', 'X11']:
        env = dict(os.environ)
        env['MOZ_ENABLE_WAYLAND'] = '1' if backend == 'Wayland' else '0'
        checked = subprocess.run(['bash', str(helper), '--check'], env=env,
                                 check=True, capture_output=True, text=True)
        profile = Path(next(line.split(': ', 1)[1] for line in checked.stdout.splitlines()
                            if line.startswith('Effective profile: ')))
        test_root = profile.parent
        assert str(test_root).startswith('/tmp/umbral-flatpak-test.')
        assert not list(profile.iterdir())
        (profile / 'user.js').write_text('\n'.join([
            'user_pref("marionette.port", 0);',
            'user_pref("remote.prefs.recommended", false);',
            'user_pref("browser.shell.checkDefaultBrowser", false);',
        ]) + '\n')
        env.update(PATH=str(temporary) + ':' + env['PATH'],
                   UMBRAL_REAL_BUILDER=flatpak_builder)
        driver = None
        with (test_root / 'browser.log').open('w') as log:
            proc = subprocess.Popen(['bash', str(helper), '--run', str(test_root)],
                                    env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError((test_root / 'browser.log').read_text())
                    try:
                        port = int((profile / 'MarionetteActivePort').read_text().strip())
                        driver = Marionette(host='127.0.0.1', port=port)
                        driver.start_session()
                        break
                    except Exception:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Graphical startup/Marionette timed out: ' + str(test_root))
                assert driver.session.get('moz:headless') is False, driver.session
                assert Path(driver.session['moz:profile']) == profile, driver.session
                driver.set_context('chrome')
                effective = driver.execute_script('''return {
                    profile: Services.dirsvc.get("ProfD", Ci.nsIFile).path,
                    data: Services.env.get("XDG_DATA_HOME"),
                    config: Services.env.get("XDG_CONFIG_HOME"),
                    cache: Services.env.get("XDG_CACHE_HOME"),
                    runtime: Services.env.get("XDG_RUNTIME_DIR"),
                    display: Services.env.get("DISPLAY"),
                    wayland: Services.env.get("WAYLAND_DISPLAY"),
                    sandboxDisabled: Services.env.get("MOZ_DISABLE_CONTENT_SANDBOX"),
                    sandboxLevel: Services.prefs.getIntPref("security.sandbox.content.level"),
                    graphics: Cc["@mozilla.org/gfx/info;1"].getService(Ci.nsIGfxInfo).getInfo(),
                    width: window.outerWidth, height: window.outerHeight
                };''')
                assert effective['profile'] == str(profile), effective
                assert effective['wayland'] if backend == 'Wayland' else effective['display'], effective
                for key in ['data', 'config', 'cache']:
                    assert effective[key] == str(test_root / key), effective
                assert effective['sandboxDisabled'] == '' and effective['sandboxLevel'] > 0, effective
                assert effective['width'] > 0 and effective['height'] > 0, effective
                screenshot = test_root / ('graphical-' + backend.lower() + '.png')
                screenshot.write_bytes(base64.b64decode(driver.screenshot()))
                results.append(dict(backend=backend, headless=False, effective=effective,
                                    screenshot=str(screenshot)))
                driver.execute_script('Services.tm.dispatchToMainThread(() => Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit))')
                proc.wait(timeout=30)
                assert proc.returncode == 0, proc.returncode
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=10)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
print(json.dumps({'result': 'PASS', 'runs': results}, indent=2))
