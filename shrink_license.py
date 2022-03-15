#!/usr/bin/env python3

import sys
import json

for line in sys.stdin:
    js = json.loads(line)
    js['license'] = js['license'].split('\n')[0]
    print(json.dumps(js))
