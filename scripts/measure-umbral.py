# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json, os, shutil, socket, subprocess, sys, tempfile, time, statistics
from pathlib import Path
import psutil
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine/testing/marionette/client'))
from marionette_driver.marionette import Marionette
BIN = os.environ.get('UMBRAL_BENCH_BINARY', str(Path(__file__).resolve().parents[1] / 'engine/obj-x86_64-pc-linux-gnu/dist/bin/zen'))
REPEATS = int(os.environ.get('UMBRAL_PERF_REPEATS', '3'))
SETTLE_SECONDS = float(os.environ.get('UMBRAL_PERF_SETTLE', '2'))
IDLE_SECONDS = float(os.environ.get('UMBRAL_PERF_IDLE', '10'))
TEMPLATE = os.environ.get('UMBRAL_BENCH_TEMPLATE')
PAGE = os.environ.get('UMBRAL_BENCH_PAGE', 'about:home')
if TEMPLATE:
    marker = json.loads((Path(TEMPLATE) / 'umbral-benchmark-fixture.json').read_text())
    if marker.get('stable') is not True or marker.get('ai') is not False or marker.get('etp') != 'strict':
        raise ValueError('Use only a settled, dedicated benchmark fixture with AI disabled and ETP Strict')

def proc_stats(root_pid):
    try:
        root = psutil.Process(root_pid)
        procs = [root] + root.children(recursive=True)
    except psutil.Error:
        return 0, 0, 0.0
    rss = pss = cpu = 0
    for p in procs:
        try:
            memory = p.memory_full_info()
            rss += memory.rss
            pss += getattr(memory, "pss", 0)
            t = p.cpu_times(); cpu += t.user + t.system
        except psutil.Error: pass
    return rss, pss, cpu

results=[]
for run in range(REPEATS):
    profile = Path(tempfile.mkdtemp(prefix='umbral-perf-measure-'))
    if TEMPLATE:
        shutil.copytree(TEMPLATE, profile, dirs_exist_ok=True, ignore=shutil.ignore_patterns('lock', '.parentlock', 'MarionetteActivePort'))
    (profile / 'user.js').write_text('\n'.join([
        'user_pref("zen.welcome-screen.seen", true);',
        'user_pref("remote.prefs.recommended", false);',
'user_pref("marionette.port", 0);',
        'user_pref("browser.startup.page", 1);',
        'user_pref("browser.startup.homepage", "about:home");',
        'user_pref("browser.shell.checkDefaultBrowser", false);',
        'user_pref("browser.newtabpage.activity-stream.showSponsored", false);',
    ]) + '\n')
    argv=[BIN, '-headless', '-no-remote', '-profile', str(profile), '-marionette', '-remote-allow-system-access']
    started=time.monotonic(); proc=subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    driver=None
    connected=False
    try:
        until=time.monotonic()+90
        port_file=profile / 'MarionetteActivePort'
        while time.monotonic()<until:
            if proc.poll() is not None: raise RuntimeError(f'browser exited {proc.returncode}')
            try:
                port=int(port_file.read_text().strip())
                driver=Marionette(host='127.0.0.1', port=port)
                driver.start_session(); connected=True; break
            except Exception: time.sleep(.25)
        if not connected: raise RuntimeError('Marionette startup timeout')
        driver.set_context('content')
        driver.navigate(PAGE)
        driver.execute_async_script('const done=arguments[0]; if(document.readyState==="complete") done(); else addEventListener("load", done, {once:true});')
        home=time.monotonic()-started
        startup_rss,startup_pss,startup_cpu=proc_stats(proc.pid)
        time.sleep(SETTLE_SECONDS)
        rss_idle,pss_idle,cpu_start=proc_stats(proc.pid)
        time.sleep(IDLE_SECONDS); rss_idle2,pss_idle2,cpu_end=proc_stats(proc.pid)
        idle_cpu=(cpu_end-cpu_start)/IDLE_SECONDS
        markup='<main>'+''.join(f'<article><h2>Umbral test {i}</h2><p>Static repeatable local content.</p></article>' for i in range(200))+'</main>'
        nav=[]
        _,_,nav_cpu_start=proc_stats(proc.pid)
        nav_start=time.monotonic()
        for i in range(3):
            uri='data:text/html;charset=utf-8,'+__import__('urllib.parse').parse.quote(markup)
            t=time.monotonic(); driver.navigate(uri)
            nav.append(time.monotonic()-t)
        rss_nav,pss_nav,nav_cpu_end=proc_stats(proc.pid)
        nav_cpu=(nav_cpu_end-nav_cpu_start)/(time.monotonic()-nav_start)
        results.append({'run':run+1,'startup_cpu_s':round(startup_cpu,3),'navigation_cpu_percent_one_core':round(nav_cpu*100,2),'startup_to_home_s':round(home,3),'idle_rss_mib':round(rss_idle2/1048576,1),'idle_pss_mib':round(pss_idle2/1048576,1),'idle_cpu_percent_one_core':round(idle_cpu*100,2),'nav_data_page_s': [round(x,3) for x in nav],'nav_rss_mib':round(rss_nav/1048576,1)})
    finally:
        try:
            if connected:
                driver.set_context('chrome')
                driver.execute_script('Services.tm.dispatchToMainThread(() => Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit))')
                proc.wait(timeout=20)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        shutil.rmtree(profile, ignore_errors=True)
print(json.dumps({'binary':BIN,'repeats':REPEATS,'conditions':{'headless':True,'profile':'copy of settled fixture' if TEMPLATE else 'fresh','template':TEMPLATE,'page':PAGE,'settleSeconds':SETTLE_SECONDS,'idleSeconds':IDLE_SECONDS},'runs':results,'median':{'startup_to_home_s':statistics.median(x['startup_to_home_s'] for x in results),'idle_pss_mib':statistics.median(x['idle_pss_mib'] for x in results),'idle_rss_mib':statistics.median(x['idle_rss_mib'] for x in results),'idle_cpu_percent_one_core':statistics.median(x['idle_cpu_percent_one_core'] for x in results),'nav_data_page_s':statistics.median(sum(x['nav_data_page_s'])/3 for x in results),'nav_rss_mib':statistics.median(x['nav_rss_mib'] for x in results)}},indent=2))
