# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import json
from json_with_comments import JSONWithCommentsDecoder

DUMPS_FOLDER = os.path.join(
    'configs', 'dumps'
)
ENGINE_DUMPS_FOLDER = os.path.join(
    'engine', 'services', 'settings', 'dumps', 'main'
)


def merge_dumps(original, updates):
  """Filters entries from the original dump, removing those whose identifiers are specified in the updates removal list."""
  remove_ids = updates.get('remove', {"identifiers": []}).get('identifiers', [])

  # Filter out entries in original that are in remove_ids.
  #  We may find example-* patterns, so we need to handle that as well.
  merged_data = [
      entry for entry in original.get('data', [])
      if not any(
          entry.get('identifier', '') == rid or
          (rid.endswith('*') and entry.get('identifier', '').startswith(rid[:-1]))
          for rid in remove_ids
      )
  ]

  apply_default_engines(merged_data, updates.get('defaultEngines'))

  return {
      'data': merged_data,
      **{k: v for k, v in original.items() if k != 'data'},
      'timestamp': updates.get('timestamp', original.get('timestamp'))
  }


def apply_default_engines(entries, defaults):
  """Sets the application default search engine without touching a profile's saved choice."""
  if not defaults:
    return

  global_default = defaults.get('globalDefault')
  if not global_default:
    return

  known = {
      entry.get('identifier')
      for entry in entries
      if entry.get('recordType') == 'engine'
  }
  if global_default not in known:
    raise SystemExit(
        f"defaultEngines.globalDefault {global_default!r} is not a search engine in this dump"
    )

  updated = False
  for entry in entries:
    if entry.get('recordType') == 'defaultEngines':
      entry['globalDefault'] = global_default
      if 'globalDefaultPrivate' in defaults:
        entry['globalDefaultPrivate'] = defaults['globalDefaultPrivate']
      updated = True
  if not updated:
    raise SystemExit("search dump has no defaultEngines record to update")


def main():
  for filename in os.listdir(DUMPS_FOLDER):
    if filename.endswith('.json'):
      #  parse json with comments
      with open(os.path.join(DUMPS_FOLDER, filename), 'r') as f:
        data = json.load(f, cls=JSONWithCommentsDecoder)
      original_path = os.path.join(ENGINE_DUMPS_FOLDER, filename)
      if os.path.exists(original_path):
        with open(original_path, 'r', encoding='utf-8') as f:
          original_content = f.read()
          original_content = '\n'.join(
              line for line in original_content.split('\n') if not line.lstrip(' ').startswith('//')
          )
          original_data = json.loads(original_content)
        merged_data = merge_dumps(original_data, data)
        with open(original_path, 'w', encoding='utf-8') as f:
          json.dump(merged_data, f, indent=2, ensure_ascii=False)
        print(f"Updated dump: {filename}")
      else:
        print(f"Original dump file not found: {original_path}")
        exit(1)


if __name__ == "__main__":
  main()
