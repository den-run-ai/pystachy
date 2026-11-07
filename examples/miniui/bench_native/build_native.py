#!/usr/bin/env python3
"""Compile unchanged production adapter with timed stub, hash stub and real raylib."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    parser.add_argument('--pkg-config', default='pkg-config')
    parser.add_argument('--raylib-dir', type=Path,
                        help='directory containing raylib.h and libraylib.so; otherwise pkg-config')
    parser.add_argument('--stub-only', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    adapter = here.parent / 'raylib_adapter.c'
    common = [args.cc, '-std=c99', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fPIC', '-shared']
    manifest = {
        'adapter': str(adapter),
        'adapter_sha256': hashlib.sha256(adapter.read_bytes()).hexdigest(),
        'cc': subprocess.check_output([args.cc, '--version'], text=True).splitlines()[0],
        'commands': [],
        'libraries': {},
    }
    for variant, hashing in [('stub', 0), ('verify', 1)]:
        target = out / variant / 'libminiui.so'
        target.parent.mkdir(parents=True, exist_ok=True)
        command = common + [f'-DMINIUI_BENCH_HASH={hashing}', '-I' + str(here / 'stub'),
                            str(adapter), str(here / 'stub_raylib.c'), '-o', str(target)]
        subprocess.run(command, check=True)
        manifest['commands'].append(command)
        manifest['libraries'][variant] = str(target)
    if not args.stub_only:
        if args.raylib_dir:
            raylib = args.raylib_dir.resolve()
            raylib_flags = ['-I' + str(raylib), '-L' + str(raylib), '-lraylib']
        else:
            subprocess.run([args.pkg_config, '--atleast-version=5.5', 'raylib'], check=True)
            raylib_flags = shlex.split(subprocess.check_output(
                [args.pkg_config, '--cflags', '--libs', 'raylib'], text=True))
        target = out / 'real' / 'libminiui.so'
        target.parent.mkdir(parents=True, exist_ok=True)
        command = common + [str(adapter), str(here / 'real_control.c'), '-o', str(target)] + raylib_flags
        subprocess.run(command, check=True)
        manifest['commands'].append(command)
        manifest['libraries']['real'] = str(target)
    for variant, path in manifest['libraries'].items():
        manifest.setdefault('library_sha256', {})[variant] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    (out / 'native-build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
