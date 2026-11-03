# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'engine/testing/marionette/client'))
from marionette_driver.marionette import Marionette
BIN=Path(__file__).resolve().parents[2]/'engine/obj-x86_64-pc-linux-gnu/dist/bin/zen'
profile=Path(tempfile.mkdtemp(prefix='umbral-ai-smoke-'))
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
    command=[str(BIN)]
    if os.environ.get('UMBRAL_TEST_FLATPAK') == '1':
        root=Path(__file__).resolve().parents[2]
        command=['flatpak','run',f'--filesystem={root}:ro',f'--filesystem={profile}',
                 '--command=/bin/sh','io.github.martin08abm.umbralbrowser','-eu','-c',
                 'root="$1"; binary="$2"; shift 2; '
                 'export XDG_CONFIG_HOME="$root/xdg-config" XDG_DATA_HOME="$root/xdg-data" '
                 'XDG_CACHE_HOME="$root/xdg-cache" TMPDIR="$root/tmp"; '
                 'mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$TMPDIR"; '
                 'exec "$binary" "$@"', 'umbral-ai-test',str(profile),str(BIN)]
    proc=subprocess.Popen(command+['-headless' ,'-no-remote','-profile',str(profile),'-marionette','-remote-allow-system-access'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
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

def click(driver,selector): driver.execute_script('document.querySelector(arguments[0]).click()',[selector])
def fill(driver,name,url):
    driver.execute_script('document.getElementById("umbral-shortcut-name").value=arguments[0]; document.getElementById("umbral-shortcut-url").value=arguments[1]; document.getElementById("umbral-shortcut-form").requestSubmit()',[name,url])


import http.server, threading
requests=[]
disconnected=[]
class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append({'path':self.path,'body':body,'auth':self.headers.get('Authorization')})
        if self.headers.get('Authorization') != 'Bearer temporary-test-secret':
            self.send_response(401);self.end_headers();return
        if body['model']=='controlled-slow':
            self.send_response(200);self.end_headers()
            try:
                self.wfile.write(b'{"choices":[');self.wfile.flush()
                for _ in range(100):
                    time.sleep(.1);self.wfile.write(b' ');self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):disconnected.append(True)
            return
        if body['model']=='controlled-error':
            self.send_response(503);self.end_headers();return
        answer='x'*13000 if body['model']=='controlled-oversize' else 'Controlled local answer'
        data=json.dumps({'choices':[{'message':{'content':answer}}]}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
proc,driver=launch()
try:
    driver.set_context('content');driver.navigate('about:preferences#umbralAI')
    wait_js(driver,'typeof gUmbralAISettings !== "undefined"')
    wait_js(driver,'document.getElementById("umbralAISettings").checkVisibility() && !!gUmbralAISettings.initialized')
    assert not requests
    endpoint='http://127.0.0.1:'+str(server.server_port)+'/v1'
    driver.execute_script('document.getElementById("umbralAIEndpoint").value=arguments[0];document.getElementById("umbralAIModel").value="controlled-model";document.getElementById("umbralAIKey").value="temporary-test-secret";document.getElementById("umbralAIEnabled").checked=true;gUmbralAISettings.saveConfiguration()',[endpoint])
    wait_js(driver,'!!document.getElementById("umbralAIConfigStatus").getAttribute("data-l10n-id")')
    status=driver.execute_script('return document.getElementById("umbralAIConfigStatus").getAttribute("data-l10n-id")');print(status,flush=True)
    assert status=='umbral-ai-config-saved',status
    assert not requests,'saving configuration contacted server'
    driver.execute_script('document.getElementById("umbralAIPrompt").value="Only this text";document.getElementById("umbralAIPrompt").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("umbralAISend").click()')
    wait_js(driver,'document.getElementById("umbralAIConversation").textContent.includes("Controlled local answer")')
    assert requests==[{'path':'/v1/chat/completions','body':{'model':'controlled-model','messages':[{'role':'user','content':'Only this text'}]},'auth':'Bearer temporary-test-secret'}],requests
    driver.set_context('chrome')
    assert driver.execute_script('return Services.dirsvc.get("ProfD",Ci.nsIFile).path')==str(profile)
    if os.environ.get('UMBRAL_TEST_FLATPAK')=='1':
        for variable,suffix in [('XDG_CONFIG_HOME','xdg-config'),('XDG_DATA_HOME','xdg-data'),('XDG_CACHE_HOME','xdg-cache'),('TMPDIR','tmp')]:
            assert driver.execute_script('return Services.env.get(arguments[0])',[variable])==str(profile/suffix)
    prefs=driver.execute_script('return {etp:Services.prefs.getStringPref("browser.contentblocking.category"),rfp:Services.prefs.getBoolPref("privacy.resistFingerprinting"),fpp:Services.prefs.getBoolPref("privacy.fingerprintingProtection",false),save:Services.prefs.getBoolPref("signon.rememberSignons"),fill:Services.prefs.getBoolPref("signon.autofillForms")}')
    policy=driver.execute_script('return {browserUpdatesAllowed:Services.policies.isAllowed("appUpdate"),embeddedUpdateURL:Services.appinfo.updateURL,extensionUpdates:Services.prefs.getBoolPref("extensions.update.enabled",true),updateURL:Services.prefs.getStringPref("app.update.url"),updateURLLocked:Services.prefs.prefIsLocked("app.update.url"),manualURL:Services.prefs.getStringPref("app.update.url.manual")}')
    assert policy['browserUpdatesAllowed'] is False,policy
    assert policy['embeddedUpdateURL']=='',policy
    assert policy['extensionUpdates'] is True,policy
    assert policy['updateURL']=='' and policy['updateURLLocked'],policy
    assert policy['manualURL']=='https://github.com/Martin08ABM/umbral-browser',policy
    close(proc,driver)
    proc,driver=launch()
    driver.set_context('content');driver.navigate('about:preferences#umbralAI')
    wait_js(driver,'typeof gUmbralAISettings !== "undefined"')
    wait_js(driver,'document.getElementById("umbralAISettings").checkVisibility() && !!gUmbralAISettings.initialized')
    assert driver.execute_script('return document.getElementById("umbralAIKey").value')==''
    driver.execute_script('document.getElementById("umbralAIPrompt").value="After restart";document.getElementById("umbralAIPrompt").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("umbralAISend").click()')
    wait_js(driver,'document.getElementById("umbralAIConversation").textContent.includes("Controlled local answer")')
    assert len(requests)==2 and requests[1]['auth']=='Bearer temporary-test-secret'
    for model,error_id in [('controlled-error','umbral-ai-request-error'),('controlled-oversize','umbral-ai-response-error')]:
        driver.execute_script('document.getElementById("umbralAIModel").value=arguments[0];document.getElementById("umbralAIModel").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("umbralAISave").click()',[model])
        wait_js(driver,'Services.prefs.getStringPref("umbral.ai.model")==='+json.dumps(model))
        driver.execute_script('document.getElementById("umbralAIPrompt").value="Controlled failure";document.getElementById("umbralAIPrompt").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("umbralAISend").click()')
        wait_js(driver,'document.getElementById("umbralAIChatStatus").getAttribute("data-l10n-id")==='+json.dumps(error_id))
    assert len(requests)==4,'errors triggered retries or fallbacks'
    for mode in ['cancel','disable','leave']:
        driver.execute_script('document.getElementById("umbralAIEnabled").checked=true;document.getElementById("umbralAIModel").value="controlled-slow";document.getElementById("umbralAISave").click()')
        wait_js(driver,'Services.prefs.getStringPref("umbral.ai.model")==="controlled-slow"')
        driver.execute_script('document.getElementById("umbralAIPrompt").value="Cancel transport";document.getElementById("umbralAIPrompt").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("umbralAISend").click()')
        wait_js(driver,'document.getElementById("umbralAIChatStatus").getAttribute("data-l10n-id")==="umbral-ai-request-pending"')
        deadline=time.monotonic()+10
        expected={'cancel':5,'disable':6,'leave':7}[mode]
        while len(requests)<expected and time.monotonic()<deadline:time.sleep(.05)
        assert len(requests)==expected
        if mode=='cancel':driver.execute_script('document.getElementById("umbralAICancel").click()')
        elif mode=='disable':driver.execute_script('Services.prefs.setBoolPref("umbral.ai.enabled",false)')
        else:
            driver.navigate('about:home')
            deadline=time.monotonic()+5
            while len(disconnected)<3 and time.monotonic()<deadline:time.sleep(.05)
            driver.navigate('about:preferences#umbralAI')
            wait_js(driver,'typeof gUmbralAISettings !== "undefined" && !!gUmbralAISettings.initialized')
            continue
        wait_js(driver,'document.getElementById("umbralAIChatStatus").getAttribute("data-l10n-id")==="umbral-ai-request-cancelled"')
    deadline=time.monotonic()+5
    while len(disconnected)<3 and time.monotonic()<deadline:time.sleep(.05)
    assert len(disconnected)==3,'cancelled sockets remained open'
    driver.execute_script('document.getElementById("umbralAIEnabled").checked=true;document.getElementById("umbralAIKey").value="wrong-test-key";document.getElementById("umbralAIModel").value="controlled-model";document.getElementById("umbralAISave").click()')
    wait_js(driver,'document.getElementById("umbralAIKey").value==="" && Services.prefs.getBoolPref("umbral.ai.enabled")')
    driver.execute_script('document.getElementById("umbralAIPrompt").value="Authentication failure";document.getElementById("umbralAIPrompt").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("umbralAISend").click()')
    wait_js(driver,'document.getElementById("umbralAIChatStatus").getAttribute("data-l10n-id")==="umbral-ai-request-error"')
    assert len(requests)==8
    driver.navigate('about:preferences#passwordsAutofill')
    wait_js(driver,'!!document.getElementById("offerToSavePasswords")')
    wait_js(driver,'document.getElementById("offerToSavePasswords").checkVisibility()')
    driver.execute_script('document.getElementById("offerToSavePasswords").shadowRoot.querySelector("input").click()')
    wait_js(driver,'Services.prefs.getBoolPref("umbral.passwords.offerToSave")===false')
    count=driver.execute_async_script('const done=arguments[0];Services.logins.searchLoginsAsync({origin:"chrome://umbral-ai",httpRealm:"Umbral local AI"}).then(v=>done(v.length))')
    assert count==1,'saving toggle removed a stored credential'
    assert driver.execute_script('return Services.prefs.getBoolPref("signon.autofillForms")') is True
    driver.set_context('chrome')
    driver.execute_script('Services.prefs.setBoolPref("umbral.ai.enabled",false)')
    denied=driver.execute_async_script('const done=arguments[0];ChromeUtils.importESModule("chrome://browser/content/UmbralLocalAI.sys.mjs").requestCompletion("disabled").then(()=>done(false),()=>done(true))')
    assert denied and len(requests)==8
    print(json.dumps({'result':'PASS','requests':len(requests),'configurationRequests':0,'credentialRestartPersistence':True,'savingToggleRetainsCredential':True,'disabledAIRequests':0,'httpFailureAndOversizeResponse':'PASS','cancelDisableAndPageExitCloseSockets':True,'invalidAuthenticationRejected':True,'flatpak':os.environ.get('UMBRAL_TEST_FLATPAK')=='1','effectivePrefs':prefs,'updatePolicy':policy}))
finally:
    close(proc,driver);server.shutdown();shutil.rmtree(profile,ignore_errors=True)
