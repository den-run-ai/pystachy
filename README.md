# Pystachy

**Typed Python in, fast native code out.**

[![CI](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml/badge.svg)](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Pystachy compiles a statically typed subset of Python to native code, retaining Python
readability and reusing existing CPython library code. It targets CPU-intensive workloads
where Python's runtime overhead gets in the way.

Write ordinary `.py` files, then use `pystachy run` for JIT execution or `pystachy build`
for a standalone native executable. Python is needed at runtime only if you opt into
the [embedded CPython bridge](docs/ffi.md#calling-cpython-libpyobjpy).

The self-hosting compiler and parts of the runtime are written in this same typed subset.
Both compilation modes share a [fully typed instruction IR](docs/typed-ir.md) before LLVM lowering.
The compiler runs under CPython and compiles itself; CI checks that successive builds
produce byte-identical LLVM IR.

**Highlights:**

- **Native machine learning:** an adapted microGPT trains and generates text with scalar
  autograd, without a tensor library or embedded Python; measured AOT training is **16.9×
  faster** than the original CPython program over 100 steps ([results](bench/microgpt/README.md)).
- **1,200+ differential programs** checked against CPython, plus **1,600+ rejection tests**,
  with JIT/AOT, self-hosting, sanitizer and garbage-collection stress coverage
  ([verification](docs/testing.md)).
- **Python and C interoperability:** call C libraries, build CPython extensions, or explicitly
  call existing Python packages through embedded CPython ([guide](docs/ffi.md)).

## A taste

This example uses typed Python, shell-style pattern matching and a bounded cache:

```python
from fnmatch import fnmatchcase
from functools import lru_cache


@lru_cache(maxsize=256)
def classify(name: str) -> str:
    return "api" if fnmatchcase(name, "api.*") else "other"


print(classify("api.request"), classify("worker.done"))
# api other
```

Repeated event names reuse their classification. The larger
[event router example](examples/route/README.md) applies this to log and trace routing.

The [minimal coding agent](examples/agent/README.md) demonstrates a complete
typed control loop, native tool calls and file edits in a standalone executable.

## Quick start

Use a [native release package or Docker image](docs/install.md) to skip bootstrapping.
Release packages require LLVM; the image includes it. For a source build:

Install LLVM, **Python 3.11+** and `make` with your package manager.
On Ubuntu 24.04:

```sh
sudo apt update
sudo apt install git make python3 clang-18 llvm-18 llvm-18-runtime
```

On macOS 14+, with [Homebrew](https://brew.sh) and the Xcode Command Line Tools installed:

```sh
brew install llvm@20 python@3.13
```

Then build and install on either platform. LLVM is discovered automatically; no pip
dependencies are needed:

```sh
git clone https://github.com/den-run-ai/pystachy
cd pystachy
make
make install                          # installs to ~/.local; no sudo
export PATH="$HOME/.local/bin:$PATH"   # add to your shell configuration once if needed
```

Save the example above as `demo.py`, then run it with CPython, JIT or AOT:

```sh
python3 demo.py
pystachy run demo.py
pystachy build demo.py -o demo
./demo
```

You can also use `./pystachy` from the checkout without installing. Before bootstrapping,
use `python3 -m pystachy run demo.py` with Python 3.11+ on Ubuntu, or
`python3.13 -m pystachy run demo.py` with Homebrew.
See [installation and setup](docs/install.md) for uv, custom prefixes and dependency checks,
or [compiler commands and settings](docs/internals.md). Full verification uses Python 3.13
on Linux x86-64.

## Performance

| Measured workload | CPython | JIT (`run`) | AOT (built executable) |
|---|---|---|---|
| [microGPT, 100 training steps](bench/microgpt/README.md#measured-snapshot) | 15.152 s | 0.908 s | **0.896 s (16.9× faster)** |
| microGPT, five generated names | 260.6 ms | 14.26 ms | **13.45 ms (19.4× faster)** |
| [4M integer list, peak RSS](docs/performance.md#start-up-and-memory) | 169 MiB | Not recorded | 34.2 MiB |

These are published snapshots, not a rerun on the latest compiler. microGPT timings are
training/inference phases, excluding startup and compilation; all parameters, losses and
sampled names are checked against the original program. The adapted source also runs under
CPython as a second baseline.

Across [18 adapted pyperformance workloads](docs/pyperformance.md), the historical AOT
snapshot was **1.5–84× faster** for 14, **2.5–2.7× slower** for three regex workloads;
one optimized-away workload has no meaningful AOT ratio. These are workload-specific
measurements on adapted sources, not official pyperformance scores or a general Python speedup.
JIT compiles each run; AOT builds once. See [performance](docs/performance.md) for startup,
memory trade-offs and reproduction details, and the [caching guide](docs/caching.md) for text workloads.

## Libraries and compatibility

Pystachy supports typed containers, classes and dataclasses, exceptions, functions as values,
closures, decorators, generators (`send` / `throw` / `close`), context managers and generic typing.
Unannotated functions and supported `Any` annotations specialize to concrete types;
`Any` does not introduce dynamically typed storage. See the
[typing rules](docs/language/typing.md#function-and-method-templates).

Some standard-library modules compile unchanged. Others, including `fnmatch`, `textwrap`,
`difflib`, `statistics` and `random`, use localized adaptations marked `# Pystachy port:`.
The adapted code remains valid Python and can be diffed against upstream.
The library also includes `re`, `itertools`, Unicode normalization, `functools.cache` /
`lru_cache`, `collections.namedtuple`, and in-memory binary I/O with `io.BytesIO`.
See [library coverage and port notes](lib/README.md) for supported APIs and remaining limits.
There are also [15 third-party ports](ports/README.md), with scoped APIs and documented adaptations.
The [compatibility audit](docs/reports/compatibility-updates.md) records measured coverage and blockers.

For numerical work, the [float64 array example](examples/ndarray/README.md) provides
multidimensional views, broadcasting, fused expressions and optional BLAS matrix products.
It is a focused native implementation; existing packages such as NumPy can instead run
through the explicit CPython bridge, which requires Python and those packages at runtime.

Reuse and ship libraries as ordinary Python wheels; uv/pip handles dependencies,
and Pystachy compiles the installed `.py` sources. The [short package tutorial](examples/package/README.md)
shares one library between CPython and native apps. See [packages and deployment](docs/packages.md)
for locked installs, the ports wheel and standalone executables.

## Status and limitations

Pystachy is experimental and supports a subset of Python. It is a good fit for typed,
algorithmic code; broad compatibility with arbitrary PyPI packages is still limited.

- Ordinary single inheritance is supported; multiple inheritance, `async`,
  native `bytearray` and binary filesystem I/O remain unsupported. `io.BytesIO` is supported.
  See the [class rules](docs/language/typing.md#single-inheritance).
- Integers are checked 64-bit values; overflow raises `OverflowError`.
- Strings store UTF-8 with code-point lengths, indexing, slicing and search offsets; Unicode case mapping remains incomplete.
  Use the opt-in [Unicode porting audit](docs/language/compatibility.md#text-and-file-positions)
  to flag byte-oriented operations on non-ASCII input.
- Many unsupported constructs produce compile-time diagnostics; this is not a complete
  compatibility check. Known semantic differences are listed in
  [deviations from CPython](docs/language.md#deviations-from-cpython).

The [language reference](docs/language.md) documents supported features and typing rules.

## Roadmap

The next priorities are:

- Richer generic typing and better inference.
- Broader library coverage, with localized ports checked against CPython.
- Further compiler and runtime optimizations, backed by reproducible benchmarks.

The [library survey](docs/stdlib.md) and
[open issues](https://github.com/den-run-ai/pystachy/issues) track coverage gaps and planned work.

## Documentation

Start with the [documentation index](docs/README.md) for task-based navigation.

| Guide | Covers |
|---|---|
| [Language](docs/language.md) | Supported Python, typing rules and semantic differences |
| [Libraries](lib/README.md) | Available modules, port adaptations and upstream tests |
| [Performance](docs/performance.md) | Speed, startup, memory and compile-time measurements |
| [Caching](docs/caching.md) | Regex, text processing and memoization benchmarks |
| [Testing](docs/testing.md) | Differential tests, bootstrap checks and CI |
| [Internals](docs/internals.md) | Compiler, runtime, commands and settings |
| [Typed IR](docs/typed-ir.md) | Shared intermediate representation and optimizations |
| [Interoperability](docs/ffi.md) | C calls, embedded CPython and CPython extension modules |
| [Runtime in Python](docs/runtime-in-subset.md) | Runtime functions compiled from the typed subset |
| [History](docs/history.md) | Design decisions and the Ouro v1 lineage |

## Get involved

Feedback, bug reports and small library ports are welcome. Share a program that fails to
compile or differs from CPython in the [issue tracker](https://github.com/den-run-ai/pystachy/issues).

For code changes, run `make verify`, `make lint` and `make check-recordings` before opening a
pull request. See the [testing guide](docs/testing.md) for adding differential tests and
checking code-generator refactors.

## License

MIT ([LICENSE](LICENSE)). CPython-derived code is covered by the PSF License Version 2;
see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES). Ryu float-formatting code uses the Boost
Software License 1.0 ([ryu/README.md](ryu/README.md)).

