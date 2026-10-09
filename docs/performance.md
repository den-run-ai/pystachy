# Performance

Pystachy compiles each program to native code through LLVM, so compute-bound Python runs one to
two orders of magnitude faster than under CPython, and code that spends its time in strings and
dicts runs a few times faster. This page has the numbers, what they include, and where the time
goes.

## Benchmarks

`bench/run.sh` on a 4-core x86-64 VM (Linux, CPython 3.13.16, LLVM 18), median of three warm
runs, October 2026. JIT times include compilation, and every output is checked against
CPython's.

| benchmark | CPython | Pystachy JIT | Pystachy AOT | AOT speedup |
|---|---:|---:|---:|---:|
| `fib.py`: fib(35), calls | 0.80 s | 0.08 s | 0.04 s | 23× |
| `mandel.py`: mandelbrot, float loops | 1.26 s | 0.09 s | 0.04 s | 34× |
| `nbody.py`: n-body, floats and objects | 1.82 s | 0.10 s | 0.03 s | 59× |
| `spectral.py`: spectral norm, nested loops | 1.07 s | 0.14 s | 0.02 s | 67× |
| `sieve.py`: a 4M-element list | 0.76 s | 0.21 s | 0.15 s | 5× |
| `words.py`: word count, strings and dicts | 0.17 s | 0.10 s | 0.05 s | 3× |
| `dictlookup.py`: dict lookups, int and str keys | 0.90 s | 0.47 s | 0.39 s | 2× |
| `dictkeys.py`: dict keys that defeat a weak hash | 0.50 s | 0.25 s | 0.16 s | 3× |

The speedup column is computed by `bench/run.sh` from the unrounded times. The first `run` after a
build also compiles and caches the runtime, which adds one to two seconds once. `bench/dictcount.py`
is measured [below](#optimizations-on-the-typed-ir).

Run them yourself with `make bench` (`bench/run.sh`): each program runs once under CPython, under
the JIT and as an AOT executable, and the script reports any output that differs from CPython's;
the benchmarks step of `make verify` fails on one.

## Where the gains are smaller

The sieve is memory-bound, and string- and dict-heavy code spends its time in the C runtime, as
CPython does, so their gains are smaller. Integer arithmetic is overflow-checked, which costs
most on call-heavy integer code: `fib` took 0.050 s instead of the 0.024 s of Ouro v1's
wrapping arithmetic when the two were compared, because LLVM can no longer turn
`fib(n - 1) + fib(n - 2)` into a loop; the other benchmarks are unaffected.

## Optimizations on the typed IR

The passes on the typed IR ([internals.md](internals.md#the-typed-ir)) remove repeated work: a
for loop reads the items of a list it steps through without a bounds check (`listget`), and a
dict lookup that a membership test or a read of the same key made is reused (`dictfuse`), so
`if k in d: d[k] += 1` hashes `k` once. `bench/dictcount.py` counts keys that way; best of 11
runs, with the dict lookup fusion turned off (`PYSTACHY_OPT=-dictfuse`) and on:

| `bench/dictcount.py` | CPython | Pystachy JIT | Pystachy AOT |
|---|---:|---:|---:|
| without `dictfuse` | 0.85–0.93 s | 0.254 s | 0.162 s |
| with `dictfuse` | 0.85–0.93 s | 0.183 s | 0.112 s |

The fused lookups make it 31% faster AOT and 28% faster under the JIT. `PYSTACHY_OPT=-all` turns
every pass off, for comparisons like this one.

## The cost of exceptions

Code that does not raise pays nothing for a `try` statement (under the JIT, two runtime calls as
it is entered), and a raise that a `try` of the same function catches is a branch, which costs
tens of nanoseconds. A raise that leaves its function unwinds the stack with the Itanium C++
ABI's unwinder, which reads each frame's tables and is slower than CPython: a `KeyError` raised
in a callee and caught by its caller, 500,000 times, takes 0.44 s AOT and 0.54 s under the JIT,
against 0.11 s under CPython, about a microsecond per raise
([internals.md](internals.md#exceptions-by-table-driven-unwinding)).

## Start-up and memory

The JIT tier starts a program in under 0.1 s: `pystachy run` of a hello world takes 60 to
80 ms on the machine above, compilation included. The collector keeps peak memory near the live set:
ten million short-lived strings (`str(i)` in a loop) peak at 35 MiB instead of 155 MiB with Ouro
v1's bump allocator, and building and discarding fifty 2M-element lists at 50 MiB instead of
1.5 GiB, while running faster (0.47 s instead of 0.52 s, and 0.30 s instead of 2.0 s). Sorting is
CPython's timsort: 2M random ints sort in 0.32 s, against 0.53 s with the earlier merge sort.

## Compile time

The native compiler translates its own 16,000 lines to LLVM IR in about 0.45 s of CPU time,
against 2.6 s when CPython runs it, and a full AOT build of itself, with clang -O2, takes about
17 s of CPU. Before the typed IR and exceptions, its 11,000 lines took 0.2 s, 1.4 s and 12 s on
the same machine, and the compiler of 7,000 lines took 0.09 s to translate itself and 7.5 s to
build. Per source line, translation to LLVM IR has grown from about 13 µs (7,000 lines) to
18 µs (11,000 lines, which added CPython's syntax checks and the definition-time checks of
imported modules) and 28 µs now, with the typed IR built, optimized and lowered as steps of
their own; the clang build stays near 1 ms per line.

Compile time grows linearly with the program: `tools/scaling.py` generates programs that grow in
one dimension at a time (functions, globals, classes, modules, fields, call and import chains,
`elif` chains, comprehensions), and `make verify` fails if what the CPython-hosted compiler
executes grows faster than the program. Dict lookups stay fast for adversarial keys too:
`make verify`'s dict-probes step counts the table slots visited for twelve key patterns that
defeat a weak hash, so no timing threshold is needed ([testing.md](testing.md#make-verify)).
