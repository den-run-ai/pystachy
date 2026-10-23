# Documentation

Start with the [README](../README.md) to build the compiler and run a first program.
Use the guides for supported behavior and commands, and the reports below for measurements
at specific compiler revisions.

## Write and port programs

| Guide | Use it for |
|---|---|
| [Installation](install.md) | Native releases, Docker, Linux/macOS source setup, uv and custom prefixes |
| [Packages and apps](packages.md) | Source wheels, dependency locks, CPython reuse and standalone deployment |
| [Language](language.md) | Supported Python, types, inference and compatibility limits |
| [CPython support surface](support-surface.md) | Color-labelled diagrams of the native core, bounded features, costs and compatibility gaps |
| [Dynamic `Any` (prototype)](dynamic-any.md) | Opt-in runtime-typed `Any` values: representation, contract, deviations and costs |
| [Standard library](../lib/README.md) | Available modules, supported APIs and port provenance |
| [Porting and coverage](stdlib.md) | Choosing a library, adapting it and checking it against CPython |
| [Third-party ports](../ports/README.md) | Port examples, usage and per-package restrictions |
| [Native JSON prototype](json-prototype.md) | Recursive JSON values, `json.loads()`/`dumps()`, their limits and [benchmark](json-benchmark.md) |
| [C and CPython interoperability](ffi.md) | Native C calls, embedded CPython and CPython extension modules |
| [Concurrency](concurrency.md) | Process pools and `asyncio` over extension modules today; the contract for threads, parallel loops and `async` |
| [Caching](caching.md) | Memoization, regex and text-processing workloads |
| [Performance](performance.md) | Published speed, memory and startup measurements |
| [Extended benchmarks](extended-performance.md) | Reproducing diagnostic benchmark runs |
| [pyperformance results](pyperformance.md) | Ported pyperformance benchmarks under CPython, JIT and AOT |
| [microGPT benchmark](../bench/microgpt/README.md) | Scalar-autograd transformer training, numerical parity and native performance |
| [Application examples](../examples/) | Small compiled command-line applications |
| [Native nanoGPT](../examples/nanogpt/README.md) | CPU transformer inference and training with ndarray and optional native BLAS |

## Work on the compiler

| Guide | Use it for |
|---|---|
| [Contributing](../CONTRIBUTING.md) | First PR, validation evidence, DCO sign-off and review policy |
| [Agent onboarding](../AGENTS.md) | Shared Codex/Claude Code workflow, verification rules and regression lessons |
| [Internals](internals.md) | Compiler stages, runtime, commands and settings |
| [Typed IR](typed-ir.md) | Intermediate representation, validation and optimization |
| [Runtime in the subset](runtime-in-subset.md) | Runtime functions written in Python and their build contract |
| [Testing](testing.md) | Bootstrap, differential tests, CI and targeted checks |
| [Releases](releasing.md) | Binary packaging, Docker publishing, release gates and [release notes](releases/) |
| [History](history.md) | Design decisions and project lineage |

## Compatibility reports

| Report | Covers |
|---|---|
| [Compatibility audit](reports/compatibility-2026-10-17.md) | Stdlib, PyPI, benchmark and test-suite coverage measured at a pinned revision |
| [Compatibility updates](reports/compatibility-updates.md) | Dated coverage measurements and remaining blockers |
| [Builtin-module prototypes](reports/compatibility-2026-10-19-prototypes.md) | Measured coverage changes from `_imp`, `_ast`, `select` and `_weakref` prototypes |

Historical surveys, prototypes and development reports are retained in [the archive](archive/).
They explain how decisions were made; their counts, timings and feature gaps describe the
recorded revision rather than today's compiler.

