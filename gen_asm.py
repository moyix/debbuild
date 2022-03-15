#!/usr/bin/env python3

from calendar import c
import sys, os
import shutil
from pathlib import Path
import json
import subprocess
import multiprocessing
from multiprocessing.pool import Pool
import time

ASMDIR = Path("/fastdata2/debian_allsrc/asm")
LLVMIRDIR = Path("/fastdata2/debian_allsrc/llvm-ir")
OLD_ROOT = Path("/fastdata/debian_allsrc/build")
NEW_ROOT = Path("/build")

PKG_VERSION_MAP = '/fastdata2/pkg_version_map.txt'
BUILD_DEP_ROOT = '/fastdata2/builddep_debs'
BUILD_DEP_MAP = BUILD_DEP_ROOT + '/.meta/all_builddep_pkgvers.txt'
def find_build_deps(pkg):
    for line in open(PKG_VERSION_MAP):
        parts = line.strip().split()
        if parts[0] == pkg:
            name = parts[1]
            ver= parts[3]
            fullver = parts[4]
            break
    else:
        print(f"No build deps found for {pkg}")
        return []
    deps = []
    for line in open(BUILD_DEP_MAP):
        parts = line.strip().split()
        if parts[0] == name:
            deps.append(parts[1])
    debs = []
    for d in deps:
        depname, depver, deparch = d.split('_')
        if ':' in depver: depver = depver.split(':')[1]
        debfile = os.path.join(BUILD_DEP_ROOT, f'{depname}_{depver}_{deparch}.deb')
        udebfile = os.path.join(BUILD_DEP_ROOT, f'{depname}_{depver}_{deparch}.udeb')
        if os.path.exists(debfile):
            debs.append(debfile)
        elif os.path.exists(udebfile):
            debs.append(udebfile)
        else:
            print(f"No deb found for {d}")
    return debs

# Take a compile_commands.json and build assembly listing for each source file
# in the compilation database.
database = json.load(open(sys.argv[1]))
assert len(database) > 0

for command in database:
    dir = Path(command['directory'])
    if str(dir).startswith(str(OLD_ROOT)):
        ROOT = OLD_ROOT
        # Get the package name from the directory
        break
    elif str(dir).startswith(str(NEW_ROOT)):
        ROOT = NEW_ROOT
        break
else:
    print(f"No root found in {database}", file=sys.stderr)
    sys.exit(1)
pkg_name = dir.relative_to(ROOT).parts[0]

# Install build dependencies so that hopefully the environment
# is very similar to the one used to compile the source files.
debs = find_build_deps(pkg_name)
subprocess.run(['sudo', '-E', 'dpkg', '-i', '--force-all'] + debs)
subprocess.run(['sudo', '-E', 'apt-get', '-y', '-f', 'install'])

# Exclude special files like named pipes and sockets
def ignore_special(dir, files):
    to_ignore = []
    for f in files:
        path = Path(dir) / f
        if f.startswith('.') or path.is_symlink() \
                             or path.is_socket()  \
                             or path.is_fifo()    \
                             or path.is_block_device() \
                             or path.is_char_device():
            to_ignore.append(f)
    return to_ignore

# We moved the source files so copy them back
archive_path = Path("/data/research/debbuild_artifacts/")
src = archive_path / pkg_name
dest = ROOT / pkg_name
if not dest.exists():
    print(f"Copying over source files from {src} to {dest}")
    shutil.copytree(src, dest, symlinks=True, ignore=ignore_special)

BLACKLISTED_EXTENSIONS = { '.h', '.gch' }

def asm_ignore_file(command):
    if any(command['file'].endswith(ext) for ext in BLACKLISTED_EXTENSIONS):
        return True
    if 'output'in command and any(command['output'].endswith(ext) for ext in BLACKLISTED_EXTENSIONS):
        return True
    args = command['arguments']
    for i in range(len(command['arguments'])):
        if args[i] == '-x':
            lang = args[i+1]
            if lang == 'c-header' or lang == 'c++-header':
                return True
    return False

def remove_warnings(args):
    # Go through the args and remove any -W* flags EXCEPT for -Wl,*. We
    # iterate in reverse order so that we can remove items from the list
    # while iterating.
    for i in range(len(args)-1, -1, -1):
        if args[i].startswith('-W') and not args[i].startswith('-Wl,'):
            del args[i]
    return args

def generate_asm(command, filename):
    if asm_ignore_file(command): return None

    # This is where we'll put the ASM output
    asm_path = ASMDIR / pkg_name
    os.makedirs(asm_path, exist_ok=True)
    asm_dest = (asm_path/filename).with_suffix(".s")
    asm_dest.parent.mkdir(parents=True, exist_ok=True)
    args = command["arguments"][:]

    # Remove -W* flags
    args = remove_warnings(args)

    # If args[0] doesn't exist (which happens during LLVM bootstrap),
    # replace it with our own compiler.
    if not os.path.exists(args[0]):
        if '++' in args[0]:
            args[0] = 'clang++-14'
        else:
            args[0] = 'clang-14'

    if 'output' in command:
        for i,arg in enumerate(args):
            if arg == "-c":
                args[i] = "-S"
            if arg == "-o":
                args[i+1] = str(asm_dest)
    else:
        asm_dest.parent.mkdir(parents=True, exist_ok=True)
        args.append("-S")
        args += ['-o', (str(asm_dest))]
    cmd_dir = Path(command['directory'])
    if not cmd_dir.exists() and str(cmd_dir).startswith(str(ROOT)):
        # Make it
        cmd_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating assembly for {filename} => {asm_dest}")
    print("CMD:"," ".join(args))
    return ('ASM', str(cmd_dir), filename, args, str(asm_dest))

def generate_llvm(command, filename):
    if asm_ignore_file(command): return None

    # This is where we'll put the LLVM output
    llvm_path = LLVMIRDIR / pkg_name
    os.makedirs(llvm_path, exist_ok=True)

    llvm_dest = (llvm_path/filename).with_suffix(".bc")
    llvm_dest.parent.mkdir(parents=True, exist_ok=True)
    args = command["arguments"][:]
    args = remove_warnings(args)

    # Select clang or clang++
    if '++' in args[0]:
        args[0] = 'clang++-14'
    else:
        args[0] = 'clang-14'

    if 'output' in command:
        for i,arg in enumerate(args):
            if arg == "-o":
                args[i+1] = str(llvm_dest)
        # Still have to put the -emit-llvm flag in
        args.append("-emit-llvm")
    else:
        args.append("-emit-llvm")
        args += ['-o', (str(llvm_dest))]
    cmd_dir = Path(command['directory'])
    if not cmd_dir.exists() and str(cmd_dir).startswith(str(ROOT)):
        # Make it
        cmd_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating LLVM for {filename} => {llvm_dest}")
    print("CMD:"," ".join(args))
    return ('LLVM-IR', str(cmd_dir), filename, args, str(llvm_dest))

HANDLERS = [generate_asm, generate_llvm]

commands_to_run = []

for command in database:
    try:
        filename = Path(command["file"]).relative_to(ROOT / pkg_name)
    except ValueError:
        # Source file is outside the package, skip it
        continue

    for handler in HANDLERS:
        cmd = handler(command, filename)
        if cmd:
            commands_to_run.append(cmd)

# Deduplicate any output files that are the same
seen_outputs = set()
for i in range(len(commands_to_run)):
    cmd = commands_to_run[i]
    args = cmd[3]
    output = cmd[4]
    if output in seen_outputs:
        j = args.index(output)
        new_output = f"{output}.{i}"
        args[j] = new_output
        commands_to_run[i] = (cmd[0], cmd[1], cmd[2], args, new_output)
        print(f"Duplicate output file {output} => {new_output}")
    else:
        seen_outputs.add(cmd[4])

def run_command(args):
    p = subprocess.run(args[3], cwd=args[1], capture_output=True)
    # If the command failed, save the output
    if p.returncode != 0:
        with open(args[4] + '.out', 'wb') as f:
            f.write(p.stdout)
        with open(args[4] + ".err", 'wb') as f:
            f.write(p.stderr)
    print(f"[{args[0]:^9}] {args[2]}: {p.returncode}")

# Run the commands in parallel using Pool
pool = Pool(multiprocessing.cpu_count())
pool.map(run_command, commands_to_run)
pool.close()
pool.join()

# Get rid of the copied source files
shutil.rmtree(f'{dest}')

tar_path = Path('/data/research/debbuild_tars/')
# Tar up the LLVM IR
llvm_tar = tar_path/f"{pkg_name}.llvm-ir.tar.zst"
try:
    subprocess.check_call(['tar', '--zst', '-cf', str(llvm_tar), '-C', str(LLVMIRDIR), pkg_name])
    shutil.rmtree(str(LLVMIRDIR/pkg_name))
except subprocess.CalledProcessError:
    print("Error creating LLVM-IR tarball")
    pass

# Tar up the ASM
asm_tar = tar_path/f"{pkg_name}.asm.tar.zst"
try:
    subprocess.check_call(['tar', '--zst', '-cf', str(asm_tar), '-C', str(ASMDIR), pkg_name])
    shutil.rmtree(str(ASMDIR/pkg_name))
except subprocess.CalledProcessError:
    print("Error creating ASM tarball")
    pass
