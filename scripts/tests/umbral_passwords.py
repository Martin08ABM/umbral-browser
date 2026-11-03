# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import http.server
import json
import shutil
import threading
from umbral_fixture import profile, launch, close, wait_js

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data=b'<!doctype html><form method="post" action="/done"><input id="user" name="username" autocomplete="username"><input id="pass" name="password" type="password" autocomplete="current-password"><button>Sign in</button></form>'
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(data)
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length',0)))
        self.send_response(200);self.end_headers();self.wfile.write(b'Submitted')
    def log_message(self,*args):pass

server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}'
proc,driver=launch()
try:
    driver.set_context('chrome')
    driver.execute_script('Services.prefs.setBoolPref("signon.autofillForms.http",true)')
    result=driver.execute_async_script('''const done=arguments[arguments.length-1];const origin=arguments[0];
      const LoginInfo=Components.Constructor("@mozilla.org/login-manager/loginInfo;1",Ci.nsILoginInfo,"init");
      Services.logins.addLoginAsync(new LoginInfo(origin,origin,null,"saved-user","saved-pass","username","password")).then(()=>done(true),e=>done(String(e)));''',[origin])
    assert result is True,result
    driver.set_context('content');driver.navigate('about:preferences#passwordsAutofill')
    wait_js(driver,'document.getElementById("offerToSavePasswords")?.checkVisibility()')
    driver.execute_script('document.getElementById("offerToSavePasswords").shadowRoot.querySelector("input").click()')
    wait_js(driver,'Services.prefs.getBoolPref("umbral.passwords.offerToSave")===false')
    assert driver.execute_script('return Services.prefs.getBoolPref("signon.rememberSignons") && Services.prefs.getBoolPref("signon.autofillForms")')
    driver.navigate(origin)
    wait_js(driver,'document.getElementById("pass").value==="saved-pass"')
    driver.set_context('chrome')
    result=driver.execute_async_script('''const done=arguments[arguments.length-1];const origin=arguments[0];
      (async()=>{
        const browser=gBrowser.selectedBrowser;
        const actor=browser.browsingContext.currentWindowGlobal.getActor("LoginManager");
        let calls=0;
        const original=actor._getPrompter;
        actor._getPrompter=()=>({promptToSavePassword(){calls++},promptToChangePassword(){calls++}});
        const data={browsingContextId:browser.browsingContext.id,formActionOrigin:origin,usernameField:{value:"new-user",name:"username"},newPasswordField:{value:"new-pass",name:"password"}};
        try {
          await actor.showDoorhanger(browser,origin,data);
          const off=calls;
          Services.prefs.setBoolPref("umbral.passwords.offerToSave",true);
          await actor.showDoorhanger(browser,origin,data);
          return {off,on:calls,autofill:Services.prefs.getBoolPref("signon.autofillForms"),count:(await Services.logins.searchLoginsAsync({origin})).length};
        } finally {actor._getPrompter=original;}
      })().then(done,e=>done({error:String(e)}));''',[origin])
    assert result=={'off':0,'on':1,'autofill':True,'count':1},result
    driver.execute_script('Services.prefs.setBoolPref("signon.autofillForms",false);Services.prefs.setBoolPref("umbral.passwords.offerToSave",false)')
    driver.set_context('content');driver.navigate(origin)
    assert driver.execute_script('return document.getElementById("pass").value')==''
    driver.set_context('chrome')
    driver.execute_script('Services.prefs.setBoolPref("signon.rememberSignons",false)')
    driver.set_context('content');driver.navigate('about:preferences#passwordsAutofill')
    wait_js(driver,'!!document.getElementById("offerToSavePasswords")')
    assert driver.execute_script('return !Services.prefs.getBoolPref("signon.rememberSignons") && !Services.prefs.getBoolPref("signon.autofillForms")')
    print(json.dumps({'result':'PASS','savingOnlyToggle':True,'autofillWhileOffersOff':True,'promptGate':result,'existingDisabledChoicesRetained':True}))
finally:
    close(proc,driver);server.shutdown();shutil.rmtree(profile,ignore_errors=True)
