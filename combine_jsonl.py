import sys
import json

for line in sys.stdin:
    js = json.loads(line)
    if 'encoding' not in js:
        js['encoding'] = 'utf-8'
        js['confidence'] = 1.0
        js['url'] = js['name']
    print(json.dumps(js))
