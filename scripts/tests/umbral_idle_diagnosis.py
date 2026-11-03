# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import shutil
import time
import psutil
from umbral_fixture import profile, launch, close

samples=[]
def snapshot(driver):
    return driver.execute_async_script('''const done=arguments[0];ChromeUtils.requestProcInfo().then(root=>{
      const result=[];const visit=p=>{result.push({pid:p.pid,type:p.type,cpu:p.cpuTime});for(const child of p.children??[])visit(child)};
      visit(root);done(result);
    });''')

def measure(driver,label):
    before={p['pid']:p for p in snapshot(driver)}
    started=time.monotonic();time.sleep(10)
    after=snapshot(driver);elapsed=time.monotonic()-started
    entries=[]
    for p in after:
        if p['pid'] not in before:continue
        try:
            memory=psutil.Process(p['pid']).memory_full_info()
            entries.append({'pid':p['pid'],'type':p['type'],'cpuPercent':round((p['cpu']-before[p['pid']]['cpu'])/1e9/elapsed*100,2),'rssMiB':round(memory.rss/1048576,1),'pssMiB':round(getattr(memory,'pss',0)/1048576,1)})
        except psutil.Error:pass
    sample={'phase':label,'seconds':round(elapsed,2),'processes':entries,'cpuPercent':round(sum(p['cpuPercent'] for p in entries),2),'rssMiB':round(sum(p['rssMiB'] for p in entries),1),'pssMiB':round(sum(p['pssMiB'] for p in entries),1)}
    samples.append(sample)
    print(json.dumps(sample),flush=True)
    return sample

if __name__ == '__main__':
    proc,driver=launch()
    try:
        driver.set_context('content');driver.navigate('about:home');driver.set_context('chrome')
        assert driver.execute_script('return Services.dirsvc.get("ProfD",Ci.nsIFile).path')==str(profile)
        for i in range(3):measure(driver,'fresh-'+str(i))
        driver.execute_async_script('const done=arguments[0];ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs").AddonManager.getAddonByID("uBlock0@raymondhill.net").then(a=>a.disable()).then(()=>done(true))')
        measure(driver,'diagnostic-ubo-disabled')
        driver.execute_async_script('const done=arguments[0];ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs").AddonManager.getAddonByID("uBlock0@raymondhill.net").then(a=>a.enable()).then(()=>done(true))')
        measure(driver,'ubo-reenabled')
    finally:close(proc,driver)
    proc,driver=launch()
    try:
        driver.set_context('content');driver.navigate('about:home');driver.set_context('chrome')
        measure(driver,'warm-restart-0');measure(driver,'warm-restart-1')
    finally:close(proc,driver);shutil.rmtree(profile,ignore_errors=True)
