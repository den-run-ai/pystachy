# Pystachy

**Typed Python in, fast native code out.**

[![CI](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml/badge.svg)](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Pystachy compiles a statically typed subset of Python to native code, retaining Python
readability and reusing existing CPython library code. It targets CPU-intensive workloads
where Python's runtime overhead gets in the way.

Write ordinary `.py` files, then use `pystachy run` for JIT execution or `pystachy build`
for a standalone executable that needs no Python installation to run.

The self-hosting compiler and parts of the runtime are written in this same typed subset.
Both compilation modes share a [typed IR](docs/typed-ir.md) before LLVM lowering.
The compiler runs under CPython and compiles itself; CI checks that successive builds
produce byte-identical LLVM IR.

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

## Quick start

You need **LLVM 18** and **Python 3.11+** to bootstrap the compiler. CI and full verification
use Python 3.13 on Linux x86-64. On Ubuntu 24.04:

```sh
sudo apt install clang-18 llvm-18 llvm-18-runtime libclang-rt-18-dev
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin
git clone https://github.com/den-run-ai/pystachy
cd pystachy
make
```

Save the example above as `demo.py`, then run it with CPython, JIT or AOT:

```sh
python3 demo.py
./pystachy run demo.py
./pystachy build demo.py -o build/demo
./build/demo
```

Before bootstrapping, `python3 -m pystachy run demo.py` runs the compiler under CPython.
See [compiler commands and settings](docs/internals.md) for more options.

## Performance

Early AOT benchmark results against CPython, rounded for readability:

| Workload | Result |
|---|---|
| Selected compute workloads | Up to about **70× faster** |
| `fnmatch` event router, without event classification caching | About **2× faster** |
| [Event router, with each event name's classification cached](https://github.com/den-run-ai/pystachy/pull/294) | About **1.5× faster** |
| [Large integer list](https://github.com/den-run-ai/pystachy/pull/201) | About **one-fifth the peak memory** |

Both router comparisons use the same caching policy for CPython and Pystachy.
The `fnmatch` variant still caches compiled patterns; caching classifications lets repeated
names skip matching altogether.

These are workload-specific results, not a general speedup for all Python code.
AOT timings exclude compilation; JIT startup includes it. Reproduction commands, exact
measurements and benchmark environments are in [performance](docs/performance.md),
the [router example](examples/route/README.md) and the [caching guide](docs/caching.md).

## Libraries and compatibility

Pystachy supports typed containers, classes and dataclasses, exceptions, functions as values,
closures, decorators and limited generic typing. Unannotated functions can be specialized
for their argument types.

Some standard-library modules compile unchanged. Others, including `fnmatch`, `textwrap`,
`difflib` and `statistics`, use localized adaptations marked `# Pystachy port:`.
The adapted code remains valid Python and can be diffed against upstream.
The library also includes `re` and `functools.cache` / `lru_cache` implementations in the
typed subset. See [library coverage and port notes](lib/README.md) for each module's scope.

Compatibility checks compare **700+ Python programs** with CPython through both JIT and AOT,
using both the CPython-hosted and self-compiled compiler. CI also checks rejected programs,
bootstrap consistency and garbage-collection stress. Details are in
[testing and verification](docs/testing.md).

Native C calls and experimental CPython extension builds are described in the
[interoperability guide](docs/ffi.md).

## Status and limitations

Pystachy is experimental and supports a subset of Python. It is a good fit for typed,
algorithmic code; broad compatibility with arbitrary PyPI packages is still limited.

- Generators, `async`, general class inheritance and `bytes` are not supported.
- Integers are checked 64-bit values; overflow raises `OverflowError`.
- Strings store UTF-8 bytes, so indexing and length differ from CPython for non-ASCII text.
- Unsupported constructs produce compile-time diagnostics. Known semantic differences are
  listed in [deviations from CPython](docs/language.md#deviations-from-cpython).

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
| [Interoperability](docs/ffi.md) | C calls and CPython extension modules |
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

