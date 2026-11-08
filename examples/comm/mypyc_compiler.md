# Full compiler under mypyc

All 55 compiler source/package modules ran as mypyc extensions. List, dictionary
and full self-compiler LLVM IR matched CPython byte-for-byte; the self IR was
33,019,357 bytes. [Recorded results](results/mypyc-compiler.json) contain source
and extension hashes, commands/settings, build time and each comparison.

This used Linux x86-64, CPython 3.13.16, cached mypy/mypyc 2.4.0, setuptools
84.2.1 and Clang 18.1.3. The repository pins mypy 2.4.1; that version was not
tested. Compiler C was built at **`-O0 -g0`** to establish compatibility.
Optimized mypyc compiler performance remains untested. The single self-IR runs
(CPython 31.96s, mypyc 33.79s) are diagnostic timings, not a speed comparison.

## Reproduce

Use a Python environment with the versions above and `clang` on `PATH`. From a
repository checkout, set `PYSTACHY_HOME` to that checkout and copy `src/`,
`pystachy.py` and `mypy.ini` into a separate work directory. Run the following
inside that directory. These commands normalize the paths from the executed
two-phase build; they require no compiler-source adaptations.

First generate C, then let that Python process exit to release mypy's AST:

```sh
python - <<'PY'
from pathlib import Path
from mypyc.build import mypycify
sources = ['pystachy.py'] + sorted(str(p) for p in Path('src').rglob('*.py'))
extensions = mypycify(['--config-file=mypy.ini'] + sources,
                     target_dir='build/mypyc')
print(len(sources), len(extensions))
PY
```

Compile the generated native group and import shims one at a time. Package shims
must be named `__init__` inside their package directories:

```sh
python - <<'PY'
from pathlib import Path
import os, subprocess, sysconfig
import mypyc
root = Path.cwd()
build = root / 'build' / 'mypyc'
runtime = Path(mypyc.__file__).parent / 'lib-rt'
suffix = sysconfig.get_config_var('EXT_SUFFIX')
files = sorted(build.rglob('*.c'),
               key=lambda p: (not p.name.startswith('__native_'), str(p)))
for source in files:
    relative = source.relative_to(build)
    output = root / relative.with_suffix(suffix)
    if source.name.startswith('__native_'):
        output = root / (source.stem.removeprefix('__native_') + '__mypyc' + suffix)
    if (root / relative.with_suffix('') / '__init__.py').is_file():
        output = root / relative.with_suffix('') / ('__init__' + suffix)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([os.environ.get('CC', 'clang'), '-shared', '-pthread',
                    '-fPIC', '-O0', '-g0', '-I' + sysconfig.get_path('include'),
                    '-I' + str(runtime), '-I' + str(build),
                    str(source), '-o', str(output)], check=True)
PY
```

Verify that imports resolve to extensions before invoking the real compiler:

```sh
python - <<'PY'
from pathlib import Path
import importlib, importlib.machinery, sys
paths = [Path('pystachy.py')] + sorted(Path('src').rglob('*.py'))
for path in paths:
    parts = list(path.with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    module = importlib.import_module('.'.join(parts))
    assert any(module.__file__.endswith(suffix)
               for suffix in importlib.machinery.EXTENSION_SUFFIXES), module.__file__
import pystachy
sys.argv = ['mypyc-compiler', '--version']
pystachy.main()
PY
python -c 'import pystachy; pystachy.main()' ir "$PYSTACHY_HOME/pystachy.py" -o self-mypyc.ll
python "$PYSTACHY_HOME/pystachy.py" ir "$PYSTACHY_HOME/pystachy.py" -o self-cpython.ll
cmp self-mypyc.ll self-cpython.ll
```

Initial monolithic C generation succeeded. A subsequent official
`multi_file=True` generation attempt was killed during concurrent bootstrap in
an 8 GiB environment, with an OOM kill recorded. Reusing the successful generated
C in a fresh process completed the C build in 55.42s. Generated C and binaries
are intentionally excluded from the repository.

The separate [feature check](mypyc_check.py) compiles communication consumers
and, optionally, the wrapper with only its annotation-inspecting `@extern`
declarations left interpreted. That FFI boundary limitation does not prevent
compiling Pystachy's complete compiler.
