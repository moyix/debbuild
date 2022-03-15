import requests
import time
import sys

# try:
#     import http.client as http_client
# except ImportError:
#     # Python 2
#     import httplib as http_client
# http_client.HTTPConnection.debuglevel = 1

# # You must initialize logging, otherwise you'll not see debug output.
# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

#BASEURL = 'http://snapshot.notset.fr'
BASEURL = 'http://snapshot.debian.org'

session = requests.Session()

for line in open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin:
    line = line.strip()
    pkg,ver,arch = line.split('_')
    pkg_info = session.get(f'{BASEURL}/mr/binary/{pkg}/{ver}/binfiles')
    if pkg_info.status_code != 200:
        print(f"{pkg} {ver} {arch} {pkg_info.status_code}", file=sys.stderr)
        continue
    pkg_info = pkg_info.json()
    res = [p['hash'] for p in pkg_info['result'] if p['architecture'] == arch]
    if not res:
        print(f"{pkg} {ver} {arch} no hash", file=sys.stderr)
        continue
    binhash = res[0]
    time.sleep(5)
    binary_info = session.get(f'{BASEURL}/mr/file/{binhash}/info')
    if binary_info.status_code != 200:
        print(f"{pkg} {ver} {arch} {binhash} {binary_info.status_code}", file=sys.stderr)
    binary_info = binary_info.json()
    binary_info = binary_info['result']
    archive_name = binary_info[0]["archive_name"]
    timestamp = binary_info[0]["first_seen"]
    #suite_name = binary_info[0]["suite_name"]
    #component_name = binary_info[0]["component_name"]
    name = binary_info[0]["name"]
    path = binary_info[0]["path"]
    print(f"{pkg} {ver} {arch} {binhash} {timestamp} {archive_name} - - {name} {path}")
    time.sleep(5)
