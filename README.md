# Pystachy

**Typed Python in, fast native code out.**

[![CI](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Installation](https://github.com/den-run-ai/pystachy/actions/workflows/install.yml/badge.svg?branch=main&event=push)](https://github.com/den-run-ai/pystachy/actions/workflows/install.yml?query=branch%3Amain+event%3Apush)
[![Lint](https://github.com/den-run-ai/pystachy/actions/workflows/lint.yml/badge.svg?branch=main&event=push)](https://github.com/den-run-ai/pystachy/actions/workflows/lint.yml?query=branch%3Amain+event%3Apush)
[![Release](https://img.shields.io/github/v/release/den-run-ai/pystachy?include_prereleases)](https://github.com/den-run-ai/pystachy/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Hosted compiler coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fden-run-ai%2Fpystachy%2Fbadges%2Fcoverage.json)](docs/testing.md#compiler-coverage)
[![Native runtime coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fden-run-ai%2Fpystachy%2Fbadges%2Fruntime-coverage.json)](docs/testing.md#native-runtime-coverage)

Pystachy compiles a statically typed subset of Python to native code through LLVM. It is
aimed at CPU-bound code where CPython's interpreter overhead gets in the way, while keeping
Python's readability and reusing existing Python library code.

Write ordinary `.py` files, then use `pystachy run` to compile and run them (JIT) or
`pystachy build` to produce a standalone executable (AOT). Compiled programs need Python
only if you opt into the [embedded CPython bridge](docs/ffi.md#calling-cpython-libpyobjpy).

The compiler and parts of the runtime are written in the same typed subset. The compiler
compiles itself, and CI checks that successive self-builds produce byte-identical LLVM IR.
Both modes share one [fully typed IR](docs/typed-ir.md).

**Highlights:**

- **Machine learning without a tensor library:** an adapted microGPT trains with scalar
  autograd and no embedded Python; AOT training is **16.9× faster** than the original
  CPython program over 100 steps ([results](bench/microgpt/README.md)).
- **Native nanoGPT:** inference and training run without CPython, NumPy or PyTorch. On a small
  108K-parameter float64 model with single-threaded OpenBLAS, AOT inference is **faster than
  CPython + NumPy and PyTorch** (0.5–0.7× and 0.8–0.9× their latency) and about 200× faster
  than the same model in pure Python; results match PyTorch within 1.4e-14
  ([example](examples/nanogpt/README.md#paired-measurement-after-the-array-and-blas-work)).
- **Checked against CPython:** 1,900+ differential programs and 1,700+ rejection tests, run in
  JIT and AOT modes, with self-hosting, sanitizer and garbage-collection stress coverage
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

To skip bootstrapping, use a [native release archive or Docker image](docs/install.md).
Archives require LLVM; the image includes it. The current prerelease is
[v0.1.0-alpha.4](https://github.com/den-run-ai/pystachy/releases/tag/v0.1.0-alpha.4); its
release page lists changes, known issues, supported platforms and downloads. Source `main`
can contain newer changes.

Source builds support Linux (x86-64 and ARM64) and macOS (Apple Silicon and Intel). Install
LLVM, **Python 3.11+** and `make` with your package manager. On Ubuntu 24.04:

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

Save the example above as `demo.py`, then run it with CPython, the JIT or an AOT build:

```sh
python3 demo.py
pystachy run demo.py
pystachy build demo.py -o demo
./demo
```

Without installing, use `./pystachy` from the checkout. Before the first `make`, run the
compiler under CPython instead: `python3 -m pystachy run demo.py` (use `python3.13` with
Homebrew). See [installation and setup](docs/install.md) for uv, custom prefixes and dependency
checks, and [compiler commands and settings](docs/internals.md) for options.

Continue with [your first compiled program](docs/getting-started.md) for a short
run–diagnose–fix walkthrough and a fair comparison of execution modes.

## Performance

| Measured workload | CPython | JIT (`run`) | AOT (built executable) |
|---|---|---|---|
| [microGPT, 100 training steps](bench/microgpt/README.md#measured-snapshot) | 15.152 s | 0.908 s | **0.896 s (16.9× faster)** |
| microGPT, five generated names | 260.6 ms | 14.26 ms | **13.45 ms (19.4× faster)** |
| [4M integer list, peak RSS](docs/performance.md#start-up-and-memory) | 169 MiB | Not recorded | 34.2 MiB |

The microGPT timings cover training and inference, excluding startup and compilation.
Parameters, losses and generated names match the original CPython program, and the adapted
source still runs under CPython.

Performance depends on the workload: the JIT compiles on every run, while AOT builds once.
See the [pyperformance results](docs/pyperformance.md) for how alpha.4 compares with alpha.3 on
22 adapted benchmarks, the [performance guide](docs/performance.md) for startup, memory use and
reproduction, and the [caching guide](docs/caching.md) for regex and text processing.

## Libraries and compatibility

**Language.** Pystachy supports typed containers, classes and dataclasses, exceptions,
closures, decorators, functions as values, generators (`send` / `throw` / `close`), context
managers and generic typing. Unannotated functions and supported `Any` annotations specialize
to concrete types; modules that opt in to the experimental [dynamic `Any`](docs/dynamic-any.md)
can also hold values whose type is known only at run time. See the
[typing rules](docs/language/typing.md#function-and-method-templates).

**Standard library.** Some modules compile unchanged. Others, such as `fnmatch`, `textwrap`,
`difflib`, `statistics` and `random`, carry small adaptations marked `# Pystachy port:`; the
adapted code remains valid Python and can be diffed against upstream. The library also
provides `re`, `itertools`, Unicode normalization, a bounded native `json`, `tomllib.loads()`,
`functools.cache` / `lru_cache`, `collections.namedtuple` and `io.BytesIO`. See
[library coverage](lib/README.md) for supported APIs and limits, and the
[CPython support map](docs/support-surface.md) for what broader compatibility would cost.

**Third-party code.** [14 ported packages](ports/README.md) have scoped APIs and documented
adaptations. Libraries ship as ordinary Python wheels: uv or pip installs them, and Pystachy
compiles the installed `.py` sources. The [package tutorial](examples/package/README.md) shares
one library between CPython and native apps; [packages and deployment](docs/packages.md) covers
locked installs, the ports wheel and standalone executables.

**Numerical work.** The [float64 array example](examples/ndarray/README.md) provides
multidimensional views, broadcasting, fused expressions and optional BLAS matrix products.
It is a focused native implementation, not NumPy; NumPy itself can run through the explicit
CPython bridge, which needs Python and NumPy at run time.

## Status and limitations

Pystachy is experimental and supports a subset of Python. It fits typed, algorithmic code
best; most PyPI packages do not compile unchanged.

- **Unsupported features:** multiple inheritance, `async`/`await`, `match`, native `bytearray`
  and binary file I/O (`io.BytesIO` works). Single inheritance follows the
  [class rules](docs/language/typing.md#single-inheritance).
- **Integers** are checked 64-bit values; overflow raises `OverflowError`. A module can opt in
  to experimental [promoting ints](docs/python-int.md), which behave like CPython's `int` in
  variables, calls, fields, tuples, generators, and lists, dicts and sets of ints or of tuples
  of ints; other containers keep 64-bit ints. The explicit experimental [`mpz`](docs/mpz.md)
  type also provides arbitrary-precision arithmetic.
- **Dynamic `Any`** is experimental and opt-in. It covers common operations,
  [iteration](docs/dynamic-any.md#iteration) and comparisons, but some cross-type comparison
  bodies raise an explicit error, and numeric identity can differ at typed storage boundaries.
  Read the [contract and deviations](docs/dynamic-any.md#deviations) before enabling it.
- **Strings** are stored as UTF-8 with code-point lengths, indexing, slicing and search
  offsets; Unicode case mapping is incomplete. The opt-in
  [Unicode porting audit](docs/language/compatibility.md#text-and-file-positions) flags
  byte-oriented operations on non-ASCII input.
- **Recursion** respects `sys.setrecursionlimit()` and raises a catchable `RecursionError`.
  Only recursive calls count, so the reachable depth differs from CPython's, and recursion that
  the native stack cannot hold raises `RecursionError` before the stack runs out, even below a
  raised limit ([recursion policy](docs/language/compatibility.md#errors-and-control-flow)).
- **Diagnostics** catch many unsupported constructs at compile time, but not all. Known
  semantic differences are listed under
  [deviations from CPython](docs/language.md#deviations-from-cpython).

The [language guide](docs/language.md#support-at-a-glance) summarizes each feature area's
status, gaps and costs, and links the detailed typing and compatibility rules.

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
| [Getting started](docs/getting-started.md) | One program, a compiler diagnostic, a fix and measurement basics |
| [Language](docs/language.md) | Support by feature area, performance trade-offs, typing rules and CPython differences |
| [Libraries](lib/README.md) | Available modules, port adaptations and upstream tests |
| [Performance](docs/performance.md) | Speed, startup, memory and compile-time measurements |
| [Caching](docs/caching.md) | Regex, text processing and memoization benchmarks |
| [Testing](docs/testing.md) | Differential tests, bootstrap checks and CI |
| [Internals](docs/internals.md) | Compiler, runtime, commands and settings |
| [Typed IR](docs/typed-ir.md) | Shared intermediate representation and optimizations |
| [Interoperability](docs/ffi.md) | C calls, embedded CPython and CPython extension modules |
| [Runtime in Python](docs/runtime-in-subset.md) | Runtime functions compiled from the typed subset |
| [Development tools](tools/README.md) | Maintained checks, compatibility probes and profiling entry points |

## Get involved

Feedback, bug reports and small library ports are welcome. Share a program that fails to
compile or differs from CPython in the [issue tracker](https://github.com/den-run-ai/pystachy/issues).

Start with the [contributor guide](CONTRIBUTING.md) for setup, focused tests, sign-off and
review expectations. The [testing guide](docs/testing.md) covers differential tests and
full verification before merge.

## License

MIT ([LICENSE](LICENSE)). CPython-derived code is covered by the PSF License Version 2;
see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES). Ryu float-formatting code uses the Boost
Software License 1.0 ([ryu/README.md](ryu/README.md)).
