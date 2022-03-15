import sys
import json
import os
from tokenizers import Tokenizer
import chardet
from pathlib import Path
# Need this to make python-debian visible; you can also just pip install debian
sys.path.append('/usr/lib/python3/dist-packages')
from debian.copyright import Copyright, NotMachineReadableError, MachineReadableFormatError

BASEDIR = '/fastdata/src/'
tok = Tokenizer.from_file('/fastdata/neox_20b/gpt-neox/20B_checkpoints/20B_tokenizer.json')

# Filter dataset based on criteria given in "Evaluating large language models trained on code.":
# - Remove files larger than 1MB.
# - Remove files with lines longer than 1000 characters.
# - Remove files with average line length longer than 100 characters.
# - Remove files with more than 90% non-alphanumeric characters.
# 
# "We filtered out files which were likely auto-generated, had average line length
#  greater than 100, had maximum line length greater than 1000, or contained a
#  small percentage of alphanumeric characters"
#
# Finally, also use the GPT-NeoX-20B tokenizer and remove files with fewer than 128 tokens

# Find the longest line and average line length
def linestats(lines):
    return max(len(l) for l in lines), sum(len(l) for l in lines)/len(lines)

def alphanum_ratio(text):
    return sum(c.isalnum() for c in text)/len(text)

copyrights = {}
def get_copyright(fname):
    global copyrights
    pkg = fname.split('/')[0]
    if pkg not in copyrights:
        try:
            with open(os.path.join(BASEDIR, pkg, 'debian/copyright')) as f:
                c = Copyright(f.read())
                copyrights[pkg] = c
        except NotMachineReadableError:
            copyrights[pkg] = None
        except MachineReadableFormatError:
            print('Error parsing copyright file for {}'.format(pkg), file=sys.stderr)
            copyrights[pkg] = None
        except FileNotFoundError:
            copyrights[pkg] = None
        except UnicodeDecodeError:
            copyrights[pkg] = None
    c = copyrights[pkg]
    if c is None:
        return "unknown", "unknown"
    para = None
    try:
        para = c.find_files_paragraph(fname)
        if para is None:
            return "unknown", "unknown"
        owner, license = para.copyright, para.license.to_str().split('\n')[0]
        return owner, license
    except MachineReadableFormatError:
        print('Error parsing copyright file for {}'.format(pkg), file=sys.stderr)
        return "unknown", "unknown"

infile = sys.argv[1]
failed_logname = Path(infile).with_suffix('.failed.txt')
failed_log = open(failed_logname, 'w')
jlog_name = Path(infile).with_suffix('.jsonl')
jlog = open(jlog_name, 'w') 
for name in open(infile):
    name = name.strip()
    #print(f"Working on {name}", file=sys.stderr)
    sys.stderr.flush()
    fullpath = os.path.join(BASEDIR, name)
    if not os.path.exists(fullpath):
        print(f"{name} does not exist", file=failed_log)
        continue
    # Filter out files larger than 1MB
    if os.path.getsize(fullpath) > 1024*1024:
        print(f"{name} too large", file=failed_log)
        continue

    try:
        data = open(fullpath, 'r').read()
        encoding = 'utf-8'
        confidence = 1.0
    except UnicodeDecodeError: 
        rawdata = open(fullpath, 'rb').read()
        res = chardet.detect(rawdata)
        encoding = res['encoding']
        confidence = res['confidence']
        if confidence < 0.7:
            print(f"{name} chardet confidence too low {encoding} {confidence}", file=failed_log)
            continue
        try:
            data = rawdata.decode(encoding)
        except UnicodeDecodeError:
            print(f"{name} unicode decode error {encoding} {confidence}", file=failed_log)
            continue
            
    js = {'url': name, 'text': data, 'encoding': encoding, 'confidence': confidence}

    # License info
    owner, license = get_copyright(name)
    js['license'] = license
    js['copyright'] = owner

    # Filter out files with lines longer than 1000 characters
    lines = data.splitlines()
    if not lines:
        print(f"{name} empty file", file=failed_log)
        continue
    maxl, meanl = linestats(lines)
    if maxl > 1000:
        print(f"{name} overly long line {maxl}", file=failed_log)
        continue
    if meanl > 100:
        print(f"{name} overly long average lines {meanl}", file=failed_log)
        continue
    alnum_pct = alphanum_ratio(data)
    if alnum_pct < 0.1:
        print(f"{name} low alphanumeric characters {alnum_pct}", file=failed_log)
        continue
    # Filter out files with fewer than 128 tokens
    tokens = tok.encode(data).ids
    if len(tokens) < 128:
        print(f"{name} too few tokens {len(tokens)}", file=failed_log)
        continue
    print(json.dumps(js), file=jlog)
