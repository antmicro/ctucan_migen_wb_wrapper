#!/usr/bin/env python3

import os
import tempfile
import argparse
import shutil
import subprocess

parser = argparse.ArgumentParser(description='Generate CTUCAN sources')
parser.add_argument('src', help='CTUCAN source directory')
parser.add_argument('dest', help="output direstory")
parser.add_argument('-p', action="append", help="Patch to apply", default=[])
parser.add_argument(
    '-f',
    action="store_true",
    default=False,
    help="force overwriting existing output directory"
)

args = parser.parse_args()

if not os.path.exists(args.src):
    raise FileNotFoundError(f"Source directory {args.src} does not exist")
src_abs = os.path.abspath(args.src)

if os.path.exists(args.dest):
    if not args.f:
        raise FileExistsError(f"Destination directory {args.dest} exists")
    else:
        shutil.rmtree(args.dest)

dest_abs = os.path.abspath(args.dest)

patches_abs = []
for patch in args.p:
    if not os.path.exists(patch):
        raise FileNotFoundError(f"Patch file {patch} does not exist")
    else:
        patches_abs.append(os.path.abspath(patch))

with tempfile.TemporaryDirectory() as dirname:
    ctucan_dir = os.path.join(dirname, os.path.basename(src_abs))
    ctucan_scripts_dir = os.path.join(ctucan_dir, "scripts")

    subprocess.check_call(f"cp -R {src_abs} .", shell=True, cwd=dirname)

    for patch in patches_abs:
        cmd = f"patch -p1 < {patch}"
        subprocess.check_call(cmd, shell=True, cwd=ctucan_dir)

    cmd = f"python3 create_release.py --output_dir={ctucan_dir}/build"
    subprocess.check_call(cmd, shell=True, cwd=ctucan_scripts_dir)

    cmd = f"cp -R {ctucan_dir}/build*/src/ {dest_abs}"
    subprocess.check_call(cmd, shell=True, cwd=dirname)
