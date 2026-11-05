# Pystachy

[![CI](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/den-run-ai/pystachy/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Pystachy compiles a typed subset of Python to native code through LLVM. Use it
for CPU-bound work such as text processing, data repair, and simulation while
keeping your code in Python. The compiler is self-hosting, and its JIT and AOT
modes share the same [typed intermediate representation](docs/typed-ir.md).

## Quick start

Follow the [installation guide](docs/install.md), then save this as `demo.py`:

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
The [getting started guide](docs/getting-started.md) walks through a diagnostic
and shows how to measure compilation and execution separately.

## What you can build

| Example | What it shows |
|---|---|
| [Event router](examples/route/README.md) | Route logs and traces using pattern matching and memoization. |
| [JSON repair](examples/json_repair/README.md) | Repair malformed JSON through a native CLI or a CPython extension. |
| [Coding agent](examples/agent/README.md) | Run a typed tool loop and edit files from a native executable. |
| [nanoGPT](examples/nanogpt/README.md) | Run inference and training with native arrays and optional BLAS. |

See the [performance guide](docs/performance.md) for measured workloads, startup
and memory costs, and reproduction commands. `run` compiles the program on every
invocation. `build` lets you reuse the executable.

## Compatibility

Pystachy is experimental. It supports typed containers, classes, generators and
other common Python constructs. General multiple inheritance, `async` and
`match` are outside the supported subset. Integers are checked 64-bit values by
default. [Promoting integers](docs/python-int.md) and [dynamic `Any`](docs/dynamic-any.md)
are opt-in.

Check the [language guide](docs/language.md#support-at-a-glance) and
[library support table](docs/stdlib.md#library-support-at-a-glance) for the
features and APIs your code uses. The library includes bounded `argparse` and
`enum` support. Some packages compile from installed sources, and others need
adaptations like the [maintained ports](ports/README.md). The optional
[CPython bridge](docs/ffi.md#calling-cpython) lets native code call
packages that need CPython at runtime.

## Learn more

- [Documentation](docs/README.md) covers installation, packaging, interoperability and compiler internals.
- [Testing](docs/testing.md) explains CPython comparisons, bootstrap checks and CI.
- [Contributing](CONTRIBUTING.md) covers development setup, focused tests and submissions.

Pystachy is [MIT-licensed](LICENSE). See the [third-party notices](THIRD_PARTY_NOTICES)
for licenses of adapted code.
