# Documentation

Start with the [README](../README.md) to build the compiler and run a first program.
The guides below describe current behavior; detailed contracts and historical measurements
are linked from the relevant guide.

## Write and port programs

| Guide | Use it for |
|---|---|
| [Installation](install.md) | Native releases, Docker, Linux/macOS source setup, uv and custom prefixes |
| [Packages and apps](packages.md) | Source wheels, dependency locks, CPython reuse and standalone deployment |
| [Language](language.md) | Supported Python, types, inference and compatibility limits |
| [Standard library](../lib/README.md) | Available modules, supported APIs and port provenance |
| [Porting and coverage](stdlib.md) | Choosing a library, adapting it and checking it against CPython |
| [Third-party ports](../ports/README.md) | Port examples, usage and per-package restrictions |
| [C and CPython interoperability](ffi.md) | Native C calls and CPython extension modules |
| [Caching](caching.md) | Memoization, regex and text-processing workloads |
| [Performance](performance.md) | Published speed, memory and startup measurements |
| [Extended benchmarks](extended-performance.md) | Reproducing diagnostic benchmark runs |
| [Application examples](../examples/) | Small compiled command-line applications |

## Work on the compiler

| Guide | Use it for |
|---|---|
| [Internals](internals.md) | Compiler stages, runtime, commands and settings |
| [Typed IR](typed-ir.md) | Intermediate representation, validation and optimization |
| [Runtime in the subset](runtime-in-subset.md) | Runtime functions written in Python and their build contract |
| [Testing](testing.md) | Bootstrap, differential tests, CI and targeted checks |
| [Releases](releasing.md) | Binary packaging, Docker publishing and release gates |
| [History](history.md) | Design decisions and project lineage |

Historical surveys, prototypes and development reports are retained in [the archive](archive/).
They explain how decisions were made; their counts, timings and feature gaps describe the
recorded revision rather than today's compiler.

