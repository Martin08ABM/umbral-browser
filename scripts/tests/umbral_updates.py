# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import functools, hashlib, http.server, json, pathlib, subprocess, tempfile, threading
script=pathlib.Path(__file__).resolve().parents[1]/'verify-umbral-update.py'
with tempfile.TemporaryDirectory(prefix='umbral-update-test-') as d:
    root=pathlib.Path(d)
    subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(root/'key')],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['openssl','pkey','-in',str(root/'key'),'-pubout','-out',str(root/'public')],check=True,stdout=subprocess.DEVNULL)
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*a):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=d))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    data=b'controlled update integrity fixture'
    (root/'archive').write_bytes(data)
    manifest={'appId':'io.github.martin08abm.umbralbrowser','platform':'linux-x86_64','fromVersion':'1.0.0','version':'1.0.1','archive':base+'/archive','sha256':hashlib.sha256(data).hexdigest()}
    def run(name, changes=None,tamper=False):
        m=dict(manifest);m.update(changes or {})
        (root/'manifest').write_text(json.dumps(m))
        subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(root/'key'),'-rawin','-in',str(root/'manifest'),'-out',str(root/'manifest.sig')],check=True)
        if tamper:(root/'manifest').write_text(json.dumps(m)+' ')
        result=subprocess.run(['python3',str(script),base+'/manifest','--public-key',str(root/'public'),'--current-version','1.0.0','--output',str(root/name),'--allow-loopback-http'],capture_output=True,text=True)
        assert (result.returncode==0)==(name=='valid'),(name,result.stdout,result.stderr)
        assert (root/name).exists()==(name=='valid')
        print(name+': PASS')
    run('valid');run('tampered',tamper=True);run('digest',{'sha256':'0'*64});run('platform',{'platform':'windows-x86_64'});run('downgrade',{'version':'0.9.0'});run('wrong-source',{'fromVersion':'0.8.0'});run('application',{'appId':'firefox'});run('malformed',{'version':1})
    server.shutdown()
