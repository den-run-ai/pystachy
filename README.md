# Pystachy

<!-- PyPI uses this README as its description. Keep repository links absolute. -->

[![CI](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Installation](https://github.com/den-run-ai/pystachy/actions/workflows/install.yml/badge.svg?branch=main&event=push)](https://github.com/den-run-ai/pystachy/actions/workflows/install.yml?query=branch%3Amain+event%3Apush)
[![Lint](https://github.com/den-run-ai/pystachy/actions/workflows/lint.yml/badge.svg?branch=main&event=push)](https://github.com/den-run-ai/pystachy/actions/workflows/lint.yml?query=branch%3Amain+event%3Apush)
[![Release](https://img.shields.io/github/v/release/den-run-ai/pystachy)](https://github.com/den-run-ai/pystachy/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/pystachy?logo=pypi&logoColor=white)](https://pypi.org/project/pystachy/)
[![Docker](https://img.shields.io/docker/v/dta67/pystachy?sort=semver&logo=docker&logoColor=white&label=Docker)](https://hub.docker.com/r/dta67/pystachy)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/den-run-ai/pystachy/blob/main/LICENSE)
[![Hosted compiler coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fden-run-ai%2Fpystachy%2Fbadges%2Fcoverage.json)](https://github.com/den-run-ai/pystachy/blob/main/docs/testing.md#compiler-coverage)
[![Native runtime coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fden-run-ai%2Fpystachy%2Fbadges%2Fruntime-coverage.json)](https://github.com/den-run-ai/pystachy/blob/main/docs/testing.md#native-runtime-coverage)

Pystachy compiles a typed subset of Python to native code through LLVM. Use it
for CPU-bound work such as text processing, data repair, and simulation while
keeping your code in Python. The compiler is self-hosting, and its JIT and AOT
modes share the same [typed intermediate representation](https://github.com/den-run-ai/pystachy/blob/main/docs/typed-ir.md).

## Quick start

Install the [PyPI package](https://pypi.org/project/pystachy/) in a Python 3.11+
virtual environment:

```sh
pip install pystachy
```

The [installation guide](https://github.com/den-run-ai/pystachy/blob/main/docs/install.md) covers LLVM requirements and automatic
toolchain setup. [Native archives](https://github.com/den-run-ai/pystachy/releases/latest) and
[Docker images](https://hub.docker.com/r/dta67/pystachy) are also available.

Then save this as `demo.py`:

```python
from fnmatch import fnmatchcase
from functools import lru_cache


@lru_cache(maxsize=256)
def classify(name: str) -> str:
    return "api" if fnmatchcase(name, "api.*") else "other"


print(classify("api.request"), classify("worker.done"))
```

```sh
python3 demo.py                  # CPython reference
pystachy run demo.py             # Compile and run with JIT
pystachy build demo.py -o demo   # Build a native executable
./demo
```

All three executions print `api other`. The executable runs without Python.
The [getting started guide](https://github.com/den-run-ai/pystachy/blob/main/docs/getting-started.md) walks through a diagnostic
and shows how to measure compilation and execution separately.

## What you can build

| Example | What it shows |
|---|---|
| [Event router](https://github.com/den-run-ai/pystachy/blob/main/examples/route/README.md) | Route logs and traces using pattern matching and memoization. |
| [JSON repair](https://github.com/den-run-ai/pystachy/blob/main/examples/json_repair/README.md) | Repair malformed JSON through a native CLI or a CPython extension. |
| [Byte BPE](https://github.com/den-run-ai/pystachy/blob/main/examples/byte_bpe/README.md) | Train a byte tokenizer and encode/decode Unicode text natively. |
| [Coding agent](https://github.com/den-run-ai/pystachy/blob/main/examples/agent/README.md) | Run a typed tool loop and edit files from a native executable. |
| [nanoGPT](https://github.com/den-run-ai/pystachy/blob/main/examples/nanogpt/README.md) | Run inference and training with native arrays and optional BLAS. |

Browse [all examples](https://github.com/den-run-ai/pystachy/blob/main/examples/README.md) for their purposes, checks and requirements.
See the [performance guide](https://github.com/den-run-ai/pystachy/blob/main/docs/performance.md) for measured workloads, startup
and memory costs, and reproduction commands. On supported Linux native installs,
`run` automatically [reuses unchanged programs](https://github.com/den-run-ai/pystachy/blob/main/docs/program-cache.md).
`PYSTACHY_PROGRAM_CACHE=0` forces compilation; `build` produces a standalone executable.

## Compatibility

Pystachy is experimental. It supports typed containers, classes, generators and
other common Python constructs. General multiple inheritance, `async` and
`match` are outside the supported subset. Integers are checked 64-bit values by
default. [Promoting integers](https://github.com/den-run-ai/pystachy/blob/main/docs/python-int.md) and [dynamic `Any`](https://github.com/den-run-ai/pystachy/blob/main/docs/dynamic-any.md)
are opt-in. Dynamic `Any` includes a bounded prototype for
[class values, type-keyed registries, generic calls and annotated factories](https://github.com/den-run-ai/pystachy/blob/main/docs/dynamic-any.md#class-values-and-type-keyed-registries).

Check the [language guide](https://github.com/den-run-ai/pystachy/blob/main/docs/language.md#support-at-a-glance) and
[library support table](https://github.com/den-run-ai/pystachy/blob/main/docs/stdlib.md#library-support-at-a-glance) for the
features and APIs your code uses. The library includes bounded `argparse`, `enum`
and experimental [static ctypes declarations](https://github.com/den-run-ai/pystachy/blob/main/docs/ffi.md#static-ctypes-declarations).
Some packages compile from installed sources, and others need
adaptations like the [maintained ports](https://github.com/den-run-ai/pystachy/blob/main/ports/README.md). The optional
[CPython bridge](https://github.com/den-run-ai/pystachy/blob/main/docs/ffi.md#calling-cpython) lets native code call
packages that need CPython at runtime.

## Roadmap

Pystachy is focused on stronger type inference, broader library support backed by
CPython comparisons, and lower compilation and execution costs.

## Learn more

- [Documentation](https://github.com/den-run-ai/pystachy/blob/main/docs/README.md) covers installation, packaging, interoperability and compiler internals.
- [Testing](https://github.com/den-run-ai/pystachy/blob/main/docs/testing.md) explains CPython comparisons, bootstrap checks and CI.
- [Contributing](https://github.com/den-run-ai/pystachy/blob/main/CONTRIBUTING.md) covers development setup, focused tests and submissions.

Pystachy is [MIT-licensed](https://github.com/den-run-ai/pystachy/blob/main/LICENSE). See the [third-party notices](https://github.com/den-run-ai/pystachy/blob/main/THIRD_PARTY_NOTICES)
for licenses of adapted code.
