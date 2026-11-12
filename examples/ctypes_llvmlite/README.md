# LLVM verification through a small ctypes binding

This optional example loads **llvmlite 0.46.0's real native library**, parses and
verifies LLVM assembly, prints canonical IR, and releases all native resources.
It exercises opaque pointer returns, nullable output cells, `byref`, integer
results, bytes arguments and copied native strings through Pystachy's ctypes
prototype. No native adapter or embedded CPython is used by the compiled program.

The consumer is an original, deliberately small C-ABI client. It replaces
llvmlite's dynamic Python loader/object layer with explicit ctypes declarations
and deterministic `try`/`finally` ownership. It does **not** demonstrate unmodified
`import llvmlite.binding`, the full upstream test suite, JIT compilation of the
input IR, or Numba compatibility.

## Run

Build Pystachy as described in [installation](../../docs/install.md), then use a
Python 3.13 environment containing the pinned optional dependency:

```sh
python3.13 -m venv /tmp/pystachy-llvmlite
/tmp/pystachy-llvmlite/bin/python -m pip install -r examples/ctypes_llvmlite/requirements.txt
/tmp/pystachy-llvmlite/bin/python examples/ctypes_llvmlite/check.py --compiler ./pystachy
```

The checker discovers the wheel's native library directory and adds it to each
child's `LD_LIBRARY_PATH`. This first example requires a Linux wheel containing
`libllvmlite.so`; no LLVM source build is needed for llvmlite. Pystachy's own
compiler still needs its supported LLVM toolchain.

`--cpython-only` checks the low-level consumer against the upstream Python API
without invoking Pystachy. To exercise the hosted compiler, pass
`--compiler 'python3.13 pystachy.py'`. `--json PATH` saves a completed report with
source/library/input/output hashes, versions and executed modes.

## What the check establishes

Ten inputs cover ordinary IR, an illustrative reward function, Unicode source
names, a C-string NUL terminator, a larger module, two syntax errors and two LLVM
verification errors. Each mode repeats every complete context/module/string
lifecycle 16 times by default. Every output byte, including diagnostic text,
must match llvmlite's unmodified `create_context`, `parse_assembly`, `verify` and
module stringification APIs. The default modes are CPython ctypes, Pystachy JIT
and AOT, then both native modes with collection at every allocation.

Repetition and GC-stressed correctness exercise cleanup paths; they do not prove
the absence of native memory leaks. Foreign pointers are freed with
llvmlite's matching functions after their contents have been copied.

## ABI and provenance

The declarations follow llvmlite tag `v0.46.0`, commit
[`50404fd444be60fc038ff0464b51b50c8bc42f8f`](https://github.com/numba/llvmlite/tree/50404fd444be60fc038ff0464b51b50c8bc42f8f):

- [`ffi/core.cpp`](https://github.com/numba/llvmlite/blob/50404fd444be60fc038ff0464b51b50c8bc42f8f/ffi/core.cpp): context and native-string lifetime.
- [`ffi/assembly.cpp`](https://github.com/numba/llvmlite/blob/50404fd444be60fc038ff0464b51b50c8bc42f8f/ffi/assembly.cpp): parse result and error output.
- [`ffi/module.cpp`](https://github.com/numba/llvmlite/blob/50404fd444be60fc038ff0464b51b50c8bc42f8f/ffi/module.cpp): verification, printing and module disposal.
- [`llvmlite/binding/module.py`](https://github.com/numba/llvmlite/blob/50404fd444be60fc038ff0464b51b50c8bc42f8f/llvmlite/binding/module.py): independent CPython oracle.

`LLVMPY_VerifyModule` actually returns C `int`; this client declares `c_int`
even though upstream's Python wrapper uses `c_bool`. Owned `char **` results
use `POINTER(c_void_p)` so the original allocation address remains available
for `LLVMPY_DisposeString`. The opaque LLVM context/module types likewise use
`c_void_p`; this does not implement ctypes `Structure` classes.

No upstream implementation is copied into this directory. The separately
installed llvmlite distribution retains its own BSD-style license and notices.
