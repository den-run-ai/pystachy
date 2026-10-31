# Documentation

Pystachy compiles a typed subset of Python to native code. Start with a small
program you can also run under CPython, then check the APIs your application uses.

## Start here

1. [Install Pystachy](install.md): native archives, Docker or a source build.
2. [Run your first program](getting-started.md): compare CPython, JIT and AOT;
   read a real diagnostic, fix the program and measure it fairly.
3. [Check supported Python](language.md) and [library APIs](../lib/README.md).
   Import success alone does not establish that a package works.

## Use Pystachy

| I want to… | Read |
|---|---|
| Understand types, inference or a rejected program | [Language](language.md), [typing](language/typing.md), [compatibility limits](language/compatibility.md) |
| Choose an appropriate workload | [Support surface](support-surface.md), [application examples](../examples/) |
| Use a library or adapt a Python package | [Shipped libraries](../lib/README.md), [porting](stdlib.md), [third-party ports](../ports/README.md) |
| Read or write JSON | [Native JSON](json.md): API, recursive values, dynamic storage and limits |
| Use mixed values or large integers | [Dynamic `Any`](dynamic-any.md), [promoting integers](python-int.md), [explicit `mpz`](mpz.md); these remain experimental |
| Call C or Python, or build a Python extension | [Interoperability](ffi.md), including ABI and ownership contracts |
| Handle I/O readiness or weak references | [POSIX select](select.md), [weak references](weakref.md) |
| Package a library or deploy an application | [Packages and deployment](packages.md), [package tutorial](../examples/package/README.md) |
| Run work in parallel | [Concurrency](concurrency.md) |

## Measure and improve performance

Start with the [performance guide](performance.md) for compilation, execution,
memory and emitted LLVM. Then choose a workload-specific guide:

| Workload | Guide |
|---|---|
| Text, regex and memoization | [Caching](caching.md), [router example](../examples/route/README.md) |
| JSON and data repair | [JSON benchmarks](json-benchmark.md), [json_repair](../bench/json_repair/README.md) |
| General Python workloads | [Extended benchmarks](extended-performance.md), [adapted pyperformance](pyperformance.md) |
| Numerical and machine-learning code | [microGPT](../bench/microgpt/README.md), [nanoGPT](../examples/nanogpt/README.md), [arrays](../examples/ndarray/README.md) |
| Integer representation | [Integer benchmarks](../bench/integers/README.md) |

Measurements describe the source revision and inputs recorded with them.
Historical evidence is linked to that revision; rerun a benchmark before treating
its numbers as results for your build.

## Develop the compiler

| Task | Guide |
|---|---|
| Make a first contribution | [Contributing](../CONTRIBUTING.md), [agent workflow](../AGENTS.md) |
| Follow a program through compilation | [Compiler internals](internals.md#compilation-pipeline), [source map](../src/README.md) |
| Understand or change optimization | [Typed IR](typed-ir.md) |
| Work on runtime code or its ABI | [Runtime in the subset](runtime-in-subset.md) |
| Choose a check or investigation tool | [Development tools](../tools/README.md), [testing and CI](testing.md) |
| Prepare a release | [Release procedure](releasing.md), [published releases](https://github.com/den-run-ai/pystachy/releases) |

Keep these guides focused on current behavior. Superseded designs, dated audit
dumps and chronological development logs remain in Git history and their PRs.
