import os
import sys
import json
import chardet

failed_log = open('.log/failed_chardet.txt', 'w')
jlog = open('all_code_chardet.jsonl', 'w')
i = 0
for name in sys.stdin:
    name = name.strip()
    if not os.path.exists(name): continue
    rawdata = open(name, 'rb').read()
    res = chardet.detect(rawdata)
    encoding = res['encoding']
    confidence = res['confidence']
    if confidence < 0.7:
        print(f"Confidence too low for {name}, {encoding} {confidence}", file=sys.stderr)
        print(f"{name} {encoding} {confidence}", file=failed_log)
        continue
    try:
        data = rawdata.decode(encoding)
    except UnicodeDecodeError:
        print(f"UnicodeDecodeError for {name}, {encoding} {confidence}", file=sys.stderr)
        print(f"{name} {encoding} {confidence}", file=failed_log)
        continue
    jlog.write(json.dumps({'name': name, 'text': data, 'encoding': encoding, 'confidence': confidence}) + '\n')
    i += 1
    if i % 100000 == 0:
        print(f"{i}")
            
print(f"{i}")
