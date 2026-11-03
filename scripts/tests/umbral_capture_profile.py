# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import shutil
import time
from pathlib import Path
from umbral_fixture import profile, launch, close

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--settle',type=float,default=10)
parser.add_argument('--seconds',type=float,default=15)
args=parser.parse_args()
proc,driver=launch()
try:
    driver.set_context('content');driver.navigate('about:home')
    time.sleep(args.settle)
    driver.set_context('chrome')
    driver.execute_async_script('const done=arguments[0];Services.profiler.StartProfiler(2000000,1,["js","stackwalk","cpu"],["GeckoMain"]).then(()=>done(true),e=>done(String(e)))')
    time.sleep(args.seconds)
    result=driver.execute_async_script('const done=arguments[arguments.length-1];Services.profiler.dumpProfileToFileAsync(arguments[0]).then(()=>Services.profiler.StopProfiler()).then(()=>done(true),e=>done(String(e)))',[str(args.output.resolve())])
    assert result is True,result
    print(args.output)
finally:
    close(proc,driver);shutil.rmtree(profile,ignore_errors=True)
