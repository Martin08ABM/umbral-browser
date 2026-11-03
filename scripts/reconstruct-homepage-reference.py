#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Copy the current Linux distribution and restore historical homepage assets."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
engine = root / 'engine'
args.output.mkdir(parents=True, exist_ok=False)
subprocess.run(['cp', '-aL', '--reflink=auto', str(engine / 'obj-x86_64-pc-linux-gnu/dist/bin') + '/.', str(args.output)], check=True)
with tempfile.TemporaryDirectory(prefix='umbral-reference-assets-') as tmp:
    tmp = Path(tmp)
    mappings = []
    for name in ['AboutNewTabChild', 'AboutNewTabParent']:
        path = f'browser/actors/{name}.sys.mjs'
        p = tmp / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(subprocess.check_output(['git', '-C', str(engine), 'show', 'HEAD:' + path]))
        mappings.append((f'src/browser/actors/{name}-sys-mjs.patch', path, path))
    for extension in ['html', 'css']:
        mappings.append((f'src/browser/extensions/newtab/prerendered/umbral-home-{extension}.patch',
                         f'browser/extensions/newtab/prerendered/umbral-home.{extension}',
                         f'browser/chrome/browser/builtin-addons/newtab/prerendered/umbral-home.{extension}'))
    for patch, source, target in mappings:
        content = subprocess.check_output(['git', '-C', str(root), 'show', args.revision + ':' + patch])
        subprocess.run(['git', 'apply', '--ignore-whitespace', '-'], input=content, cwd=tmp, check=True)
        shutil.copyfile(tmp / source, args.output / target)
print(args.output / 'zen')
