# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import functools
import hashlib
import http.server
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import threading

SCRIPT = Path(__file__).resolve().parents[1] / 'manage-umbral-update.py'
with tempfile.TemporaryDirectory(prefix='umbral-managed-update-test-') as directory:
    root = Path(directory)
    def command(*arguments, succeeds=True):
        result = subprocess.run(['python3', str(SCRIPT), *map(str, arguments)], capture_output=True, text=True)
        assert (result.returncode == 0) == succeeds, (arguments, result.stdout, result.stderr)
        return result

    subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(root/'key')], check=True)
    subprocess.run(['openssl', 'pkey', '-in', str(root/'key'), '-pubout', '-out', str(root/'public')], check=True)
    def fixture(path, version, build):
        path.mkdir()
        shutil.copyfile('/bin/sleep', path/'zen'); (path/'zen').chmod(0o755)
        (path/'application.ini').write_text(f'[App]\nCodeName=Umbral\nVersion={version}\nBuildID={build}\n[Gecko]\nMaxVersion=158.0.1\n')
        for name in ['omni.ja', 'browser/omni.ja', 'distribution/extensions/uBlock0@raymondhill.net.xpi']:
            file=path/name;file.parent.mkdir(parents=True, exist_ok=True);file.write_text('fixture, not a real browser')
        (path/'distribution/policies.json').write_text(json.dumps({'policies':{'DisableAppUpdate':True}}))
    fixture(root/'source','1.0.0','20261102000000')
    fixture(root/'target','1.0.1','20261103000000')
    command('init','--source',root/'source','--root',root/'source/nested','--public-key',root/'public',succeeds=False)
    command('init','--source',root/'source','--root',root/'managed','--public-key',root/'public')
    managed=root/'managed'
    original=(managed/'current').readlink()
    command('init','--source',root/'source','--root',managed,'--public-key',root/'public',succeeds=False)
    pause_download=threading.Event()
    download_started=threading.Event()
    continue_download=threading.Event()
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path=='/archive.tar.xz' and pause_download.is_set():
                self.send_response(200);self.end_headers()
                self.wfile.write(b'partial');self.wfile.flush()
                download_started.set();continue_download.wait(timeout=10)
                return
            super().do_GET()
        def log_message(self,*args): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=directory))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    def release(*, changes=None, malicious=False, foreign_arch=False, tamper=False):
        if foreign_arch:
            with (root/'target/zen').open('r+b') as executable:executable.seek(18);executable.write(b'\xb7\x00')
        with tarfile.open(root/'archive.tar.xz','w:xz') as archive:
            archive.add(root/'target',arcname='zen')
            if malicious:
                member=tarfile.TarInfo('zen/../../escaped');member.size=3
                archive.addfile(member,io.BytesIO(b'bad'))
        shutil.copyfile('/bin/sleep',root/'target/zen');(root/'target/zen').chmod(0o755)
        data={'appId':'io.github.martin08abm.umbralbrowser','platform':'linux-x86_64',
              'fromVersion':'1.0.0','version':'1.0.1','fromBuildID':'20261102000000',
              'buildID':'20261103000000','firefoxVersion':'158.0.1','channel':'unofficial',
              'archive':base+'/archive.tar.xz','sha256':hashlib.sha256((root/'archive.tar.xz').read_bytes()).hexdigest()}
        data.update(changes or {})
        (root/'manifest').write_text(json.dumps(data))
        subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(root/'key'),'-rawin','-in',str(root/'manifest'),'-out',str(root/'manifest.sig')],check=True)
        if tamper:(root/'manifest').write_text(json.dumps(data)+' ')
    def update(succeeds=False):
        return command('update','--root',managed,'--manifest',base+'/manifest','--allow-loopback-http',succeeds=succeeds)
    for label,kwargs in [
        ('source build',{'changes':{'fromBuildID':'20260101000000'}}),
        ('Firefox ABI',{'changes':{'firefoxVersion':'159.0'}}),
        ('channel',{'changes':{'channel':'release'}}),
        ('archive metadata',{'changes':{'buildID':'20261104000000'}}),
        ('path traversal',{'malicious':True}),('architecture',{'foreign_arch':True}),
        ('signature',{'tamper':True})]:
        release(**kwargs);update();assert (managed/'current').readlink()==original
        assert not (root/'escaped').exists()
        print(label+': PASS')
    release()
    pause_download.set()
    interrupted=subprocess.Popen(['python3',str(SCRIPT),'update','--root',str(managed),
                                  '--manifest',base+'/manifest','--allow-loopback-http'],
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        assert download_started.wait(timeout=10)
        interrupted.terminate();interrupted.wait(timeout=10)
    finally:
        if interrupted.poll() is None:interrupted.kill();interrupted.wait()
        pause_download.clear();continue_download.set()
    assert (managed/'current').readlink()==original
    print('interrupted download retains current: PASS')
    busy=subprocess.Popen([str(managed/'current/zen'),'30'])
    try:
        update();assert (managed/'current').readlink()==original
    finally:busy.terminate();busy.wait()
    print('live browser rejection: PASS')
    # An orphaned candidate from an interrupted preparation must not change current.
    (managed/'.candidate-interrupted').mkdir()
    update(succeeds=True)
    active=(managed/'current').readlink()
    assert active!=original and (managed/active).exists() and (managed/original).exists()
    result=subprocess.run([str(managed/'current/zen'),'0'],check=True)
    update();assert (managed/'current').readlink()==active
    command('rollback','--root',managed)
    assert (managed/'current').readlink()==original
    print('activation, no downgrade, old release retention, explicit rollback: PASS')
    server.shutdown()
