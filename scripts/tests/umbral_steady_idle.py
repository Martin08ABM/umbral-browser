# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import shutil
from pathlib import Path
from umbral_fixture import profile, launch, close
from umbral_idle_diagnosis import measure

parser=argparse.ArgumentParser()
parser.add_argument('--template',type=Path)
args=parser.parse_args()
proc,driver=launch()
stable=0
try:
    driver.set_context('content');driver.navigate('about:home');driver.set_context('chrome')
    metadata=driver.execute_script('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID,etp:Services.prefs.getStringPref("browser.contentblocking.category"),ai:Services.prefs.getBoolPref("umbral.ai.enabled",false)}')
    for i in range(24):
        sample=measure(driver,'uninterrupted-fresh-'+str(i))
        stable=stable+1 if sample['cpuPercent']<2 else 0
        if stable>=3:break
finally:close(proc,driver)
if args.template and stable>=3:
    shutil.copytree(profile,args.template,ignore=shutil.ignore_patterns('lock','.parentlock','MarionetteActivePort'))
    (args.template/'umbral-benchmark-fixture.json').write_text(json.dumps(dict(metadata,stable=True)))
    print(json.dumps({'template':str(args.template),'metadata':metadata}),flush=True)
proc,driver=launch()
try:
    driver.set_context('content');driver.navigate('about:home');driver.set_context('chrome')
    for i in range(3):measure(driver,'uninterrupted-warm-'+str(i))
finally:close(proc,driver);shutil.rmtree(profile,ignore_errors=True)
