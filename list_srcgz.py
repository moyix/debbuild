from email.policy import default
import debian.deb822
import os
import sys
import gzip
from collections import defaultdict
import argparse
import apt_pkg
from functools import cmp_to_key
import pickle
import re

def urljoin(*args):
    return "/".join(map(lambda x: str(x).rstrip("/"), args))

def parse_package_list(pkglist):
    ret = []
    for line in pkglist.splitlines():
        line = line.strip()
        if not line: continue
        parts = line.split()
        if len(parts) >= 5:
            name, ext, section, priority, arch = parts[:5]
            arch = arch.split('=',1)[-1]
        elif len(parts) == 4:
            name, ext, section, priority = line.split()
            arch = None
        else:
            print('Bad Package-List line:', line)
            continue

        ret.append({
            'name': name,
            'ext': ext,
            'section': section,
            'priority': priority,
            'arch': arch.split(',') if arch else []
        })
    return ret

def create_package_list(pkg):
    pkg_list = []
    for b in pkg['Binary'].split(', '):
        pkg_list.append({
            'name': b,
            'ext': 'deb',
            'section': pkg['Section'],
            'priority': pkg['Priority'],
            'arch': pkg['Architecture'].split(' ')
        })
    return pkg_list

PKG_CACHE = '/fastdata/SourcesGzCache.pkl'
ROOT_URL = 'http://ftp.us.debian.org/debian/'
DEFAULT_SOURCES = [
    '/fastdata/debian_allsrc/main/Sources.gz',
    '/fastdata/debian_allsrc/contrib/Sources.gz',
    '/fastdata/debian_allsrc/non-free/Sources.gz',
]

parser = argparse.ArgumentParser(description='Extract urls for specified source packages')
parser.add_argument('command', choices=['env', 'dump', 'md5s', 'urls', 'clean', 'cleandebs', 'check'], help='which command to run')
parser.add_argument('pkg', nargs='*', help='package names')
parser.add_argument('-f', '--file', action='append', default=DEFAULT_SOURCES, help='Sources.gz to read from (can give multiple)')
parser.add_argument('-a', '--all', action='store_true', help='list all versions of packages')
parser.add_argument('-r', '--rebuild-cache', action='store_true', help='rebuild the cache')
parser.add_argument('-u', '--url', default=ROOT_URL, help='root url to use instead of default')
parser.add_argument('-c', '--cache', default=PKG_CACHE, help='cache file to use')
args = parser.parse_args()

# Accept packages on stdin
if args.pkg == ['-']:
    args.pkg = sys.stdin.read().splitlines()

# Some subcommands need one or more packages specified
if args.command not in ['dump', 'check', 'urls', 'md5s'] and not args.pkg:
    parser.error('No packages specified')
elif args.command == 'env' and len(args.pkg) != 1:
    parser.error('Only one package can be specified for the env command')

# Allow specifying a version for each package with name=version
requested_versions = defaultdict(list)
for i,pkg in enumerate(args.pkg):
    if '=' in pkg:
        name, version = pkg.split('=', 1)
        requested_versions[name].append(version)
        args.pkg[i] = name
requested_versions = dict(requested_versions)
args.pkg = list(set(args.pkg))

def select_version(name, candidates):
    if name in requested_versions and requested_versions[name] != 'any':
        ver = requested_versions[name]
        return [c for c in candidates if c['PkgVersion'] in ver]
    else:
        return [candidates[0]]

def get_cache():
    # As long as the cache exists we can use it -- unless the user explicitly
    # says to rebuild it.
    if os.path.exists(args.cache) and not args.rebuild_cache:
        with open(args.cache, 'rb') as f:
            return pickle.load(f)
    print('Building cache...', file=sys.stderr)
    # Otherwise, we need to build the cache.
    packages = defaultdict(list)
    for fname in args.file:
        with gzip.open(fname, 'rb') as f:
            for pkg in debian.deb822.Sources.iter_paragraphs(f):
                packages[pkg['Package']].append(pkg)

    def cmp_version(x,y):
        return apt_pkg.version_compare(x['Version'], y['Version'])

    # For duplicates, sort by version, and convert everything to
    # a plain dict.
    for pkg in packages:
        if len(packages[pkg]) > 1:
            packages[pkg].sort(key=cmp_to_key(cmp_version), reverse=True)
        packages[pkg] = [dict(p) for p in packages[pkg]]
        for p in packages[pkg]:
            p['Files'] = [dict(f) for f in p['Files']]
            p['Checksums-Sha256'] = [dict(f) for f in p['Checksums-Sha256']]
            pkg_ver = p['Version'].split(':', 1)[-1]
            short_ver = apt_pkg.upstream_version(p['Version'])
            p['PkgVersion'] = pkg_ver
            p['ShortVersion'] = short_ver
            if 'Package-List' in p:
                p['Package-List'] = parse_package_list(p['Package-List'])
            else:
                p['Package-List'] = create_package_list(p)

    # Cache for next time
    packages = dict(packages)
    with open(args.cache, 'wb') as f:
        pickle.dump(packages, f)
    return packages

def dedup_cache(cache):
    # Remove duplicates from the cache
    for pkg in cache:
        versions = set()
        for p in cache[pkg]:
            if p['Version'] in versions:
                cache[pkg].remove(p)
            else:
                versions.add(p['Version'])
    return cache

packages = dedup_cache(get_cache())

if args.command == 'check':
    if not args.pkg:
        args.pkg = packages.keys()
    rv = 0
    for pkg in args.pkg:
        if pkg not in packages:
            print(f"CheckSrc: No source package record found for {pkg}", file=sys.stderr)
            rv = 1
        else:
            if args.all:
                pkgs = packages[pkg]
            else:
                pkgs = select_version(pkg, packages[pkg])
                if not pkgs:
                    reqver = requested_versions.get(pkg, 'any')
                    for v in reqver: print(f"CheckSrc: No source package record found for {pkg}={v}", file=sys.stderr)
                    rv = 1
                    continue
            for p in pkgs:
                print(f"CheckSrc: {pkg} {p['ShortVersion']} {p['PkgVersion']} {p['Version']}")
    sys.exit(rv)
elif args.command == 'env':
    assert len(args.pkg) == 1
    pkg = select_version(args.pkg[0], packages[args.pkg[0]])
    if not pkg:
        reqver = requested_versions.get(args.pkg[0], 'any')
        print(f"No source package record found for {args.pkg[0]}={reqver[0]}", file=sys.stderr)
        sys.exit(1)
    pkg = pkg[0]
    dsc = pkg['Files'][0]['name']
    name, short_ver, long_ver = (pkg['Package'], pkg['ShortVersion'], pkg['PkgVersion'])
    print(f'PKG="{name}" VER="{short_ver}" LONGVER="{long_ver}" DSC="{dsc}"')
elif args.command == 'urls':
    if not args.pkg:
        args.pkg = packages.keys()
    for p in args.pkg:
        if p in packages:
            pkgs = select_version(p, packages[p])
            if not pkgs:
                reqver = requested_versions.get(p, 'any')
                for v in reqver: print(f"CheckSrc: No source package record found for {p}={v}", file=sys.stderr)
                continue
            for pkg in pkgs:
                for f in pkg['Files']:
                    #print(f'{p}={pkg["PkgVersion"]}', urljoin(args.url, pkg['Directory'], f['name']))
                    print(urljoin(args.url, pkg['Directory'], f['name']))
        else:
            reqver = requested_versions.get(p, 'any')
            for v in reqver: print(f"CheckSrc: No source package record found for {p}={v}", file=sys.stderr)
elif args.command == 'md5s':
    if not args.pkg:
        args.pkg = packages.keys()
    for p in args.pkg:
        if p in packages:
            pkgs = select_version(p, packages[p])
            if not pkgs:
                reqver = requested_versions.get(p, 'any')
                for v in reqver: print(f"CheckSrc: No source package record found for {p}={v}", file=sys.stderr)
                continue
            for pkg in pkgs:
                for f in pkg['Files']:
                    print(f['md5sum'],f['name'])
        else:
            reqver = requested_versions.get(p, 'any')
            for v in reqver: print(f"CheckSrc: No source package record found for {p}={v}", file=sys.stderr)
elif args.command == 'clean' or args.command == 'cleandebs':
    assert len(args.pkg) == 1
    pkg = select_version(args.pkg[0], packages[args.pkg[0]])
    if not pkg:
        reqver = requested_versions.get(args.pkg[0], 'any')
        print(f"No source package found for {args.pkg[0]}={reqver[0]}", file=sys.stderr)
        sys.exit(1)
    pkg = pkg[0]
    native_arch = apt_pkg.get_architectures()[0]
    pkg_ver = pkg['PkgVersion']
    debs = []
    for p in pkg['Package-List']:
        if not p['arch'] or p['arch'][0] == 'any' or native_arch in p['arch']:
            arch = native_arch
        elif p['arch'] == 'all':
            arch = 'all'
        else:
            continue
        name = p['name']
        ext = p['ext']
        debs.append(f'{name}_{pkg_ver}_{arch}.{ext}')
        # And the -dbgsym debs
        debs.append(f'{name}-dbgsym_{pkg_ver}_{arch}.{ext}')
    if args.command == 'clean':
        other_files = [f["name"] for f in pkg['Files']]
    else:
        other_files = []
    print('rm -f ' + ' '.join(debs + other_files))
elif args.command == 'dump':
    if not args.pkg:
        args.pkg = packages.keys()
    for p in args.pkg:
        # We're only printing the name here so there's no point in
        # checking for a requested version.
        for pkg in packages[p]:
            print(f"{p}={pkg['PkgVersion']}")
else:
    assert False
