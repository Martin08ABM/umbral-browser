# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json, shutil, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'engine/testing/marionette/client'))
from marionette_driver.marionette import Marionette
BIN=Path(__file__).resolve().parents[2]/'engine/obj-x86_64-pc-linux-gnu/dist/bin/zen'
profile=Path(tempfile.mkdtemp(prefix='umbral-shortcuts-smoke-'))
(profile/'user.js').write_text('\n'.join([
'user_pref("zen.welcome-screen.seen", true);',
'user_pref("remote.prefs.recommended", false);',
'user_pref("marionette.port", 0);',
'user_pref("browser.shell.checkDefaultBrowser", false);',
'user_pref("browser.startup.homepage", "about:home");',
'user_pref("browser.startup.page", 1);',
'user_pref("extensions.update.enabled", false);',
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

def click(driver,selector):
    driver.find_element('css selector',selector).click()

def fill(driver,name,url):
    driver.execute_script('document.getElementById("umbral-shortcut-name").value=arguments[0];document.getElementById("umbral-shortcut-url").value=arguments[1];document.getElementById("umbral-shortcut-form").requestSubmit()',[name,url])

def action(driver,index,name):
    summary=f'.shortcut[data-index="{index}"] summary'
    click(driver,summary)
    click(driver,f'.shortcut[data-index="{index}"] [data-shortcut-action="{name}"]')

proc,driver=launch()
try:
    driver.set_context('content');driver.navigate('about:home')
    wait_js(driver,'!!document.getElementById("umbral-shortcuts-add")')
    assert driver.execute_script('return document.querySelectorAll(".shortcut[data-index]").length')==0
    click(driver,'#umbral-shortcuts-add');fill(driver,'Docs','https://example.com/docs')
    wait_js(driver,'document.querySelectorAll(".shortcut[data-index]").length===1')
    click(driver,'#umbral-shortcuts-add');fill(driver,'Local','http://127.0.0.1:8080/start')
    wait_js(driver,'document.querySelectorAll(".shortcut[data-index]").length===2')
    action(driver,0,'edit');fill(driver,'Guide','https://example.com/guide?q=a%20b')
    wait_js(driver,'document.querySelectorAll(".shortcut[data-index] a")[0].textContent.includes("Guide")')
    action(driver,1,'move-up')
    wait_js(driver,'document.querySelectorAll(".shortcut[data-index] a")[0].textContent.includes("Local")')
    action(driver,0,'delete')
    wait_js(driver,'document.querySelectorAll(".shortcut[data-index]").length===1')
    click(driver,'#umbral-shortcuts-add');fill(driver,'','javascript:alert(1)')
    wait_js(driver,'document.getElementById("umbral-shortcut-name").getAttribute("aria-invalid")==="true" && document.getElementById("umbral-shortcut-url").getAttribute("aria-invalid")==="true"')
    assert driver.execute_script('return document.activeElement.id')=='umbral-shortcut-name'
    click(driver,'#umbral-shortcut-cancel')
finally:
    close(proc,driver)
proc,driver=launch()
try:
    driver.set_context('content');driver.navigate('about:home')
    wait_js(driver,'document.querySelector(".shortcut[data-index] a")?.textContent.includes("Guide")')
    summary=driver.find_element('css selector','.shortcut summary')
    driver.execute_script('document.querySelector(".shortcut summary").focus()')
    summary.send_keys('\ue007')
    wait_js(driver,'document.querySelector(".shortcut details").open')
    summary.send_keys('\ue00c')
    wait_js(driver,'!document.querySelector(".shortcut details").open')
    import base64,os
    output=Path(os.environ.get('UMBRAL_VISUAL_DIR') or tempfile.mkdtemp(prefix='umbral-shortcuts-visual-'))
    output.mkdir(exist_ok=True,parents=True)
    cases=[('empty',[],1100),('several',[{'name':n,'url':'https://example.com/'+str(i)} for i,n in enumerate(['Notes','Work','Reading','Music','Projects'])],1100),('long',[{'name':'A very long shortcut name with forty characters','url':'https://example.com/long'}],1100),('narrow',[{'name':n,'url':'https://example.com/'+str(i)} for i,n in enumerate(['Reading and research','Work','Projects','Notes'])],360)]
    for theme,mode in [('light',1),('dark',0)]:
        for name,links,width in cases:
            driver.set_window_rect(width=width,height=850)
            driver.set_context('chrome')
            driver.execute_script('Services.prefs.setIntPref("layout.css.prefers-color-scheme.content-override",arguments[0]);Services.prefs.setStringPref("browser.newtabpage.umbral.shortcuts",JSON.stringify(arguments[1]))',[mode,links])
            driver.set_context('content');driver.navigate('about:home')
            wait_js(driver,'document.querySelectorAll(".shortcut[data-index]").length==='+str(len(links)))
            assert driver.execute_script('return document.documentElement.scrollWidth<=innerWidth')
            (output/f'{name}-{theme}.png').write_bytes(base64.b64decode(driver.screenshot()))
            if name=='narrow':
                click(driver,'.shortcut summary')
                bounds=driver.execute_script('const r=document.querySelector("details[open] .shortcut-menu-actions").getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth}')
                assert bounds['left']>=0 and bounds['right']<=bounds['width'],bounds
                (output/f'menu-{theme}.png').write_bytes(base64.b64decode(driver.screenshot()))
    driver.find_element('css selector','details[open] summary').send_keys('\ue00c')
    wait_js(driver,'!document.querySelector("details[open]")')
    click(driver,'#umbral-shortcuts-add');fill(driver,'','bad url')
    wait_js(driver,'document.getElementById("umbral-shortcut-url").getAttribute("aria-invalid")==="true"')
    wait_js(driver,'document.getElementById("umbral-shortcut-name-error").textContent.trim() && document.getElementById("umbral-shortcut-url-error").textContent.trim()')
    (output/'form-errors.png').write_bytes(base64.b64decode(driver.screenshot()))
    print(json.dumps({'result':'PASS','crud':True,'restartPersistence':True,'keyboardMenu':True,'responsiveThemes':True,'screenshots':str(output)}))
finally:
    close(proc,driver);shutil.rmtree(profile,ignore_errors=True)
