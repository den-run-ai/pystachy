# AskMe harness on five runtimes, with kept connections, 2026-11-12

The typed AskMe port from one source on CPython, PyPy, mypyc, the Pystachy JIT
and a Pystachy executable, beside the reference `askme.py`. Model replies are
recorded, so the times are the harness alone; the transport runs then add a
loopback server. Method and reproduction are in the
[benchmark guide](../README.md); every sample is in
[2026-11-12-kept-connections.json](2026-11-12-kept-connections.json).

This run follows [the first one](2026-11-12-runtimes.md) on the same machine
and day. Two things changed: the compiler compares a union with a `str` or a
number by its tag, and the port sends requests itself over a kept connection
instead of starting `curl`.

| | |
|---|---|
| Machine | 4 virtual cores of an Intel Xeon at 2.10 GHz (shared host), Linux 6.18, Ubuntu 24.04; runs pinned to one core |
| Pystachy | `d51eebbfecc9d4d6dcefc76da4c006fd54a040d3`, default settings (`PYSTACHY_AOT_OPT=2`), LLVM 18.1.3 |
| Port | `examples/askme` as pinned from AskMe `2373cf8235e91507faf4e089cd99a8d8dfdfbac2` |
| Reference | `askme.py` at the same AskMe commit, `requests` 2.34.2 |
| CPython | 3.13.18, bytecode precompiled |
| PyPy | 7.3.23 (Python 3.11.15), bytecode precompiled |
| mypyc | mypy 2.4.1 on CPython 3.13.18 |
| TLS | OpenSSL 3.0.13; a 2048-bit RSA certificate from a private CA |
| Samples | 15 per short run, 5 per long run; medians |
| Correctness | Each runtime reproduced CPython's transcript on all 19 workloads before timing |

## Summary

- **The executable is now the fastest runtime on long runs.** Over 2,001
  requests it is 1.3 to 1.4 times faster than the same source on CPython and
  1.06 to 1.14 times faster than mypyc, which led the first run. Built from
  one port source by the compiler before and after the equality change, and
  timed in interleaved runs, the executable gained 1.25 times on the navigation
  run and 1.35 times on the controller run.
- **Startup and short runs are unchanged in kind.** The executable starts in
  2.4 ms against 47 ms for CPython, and finishes the 17-run suite in 0.24 s
  against 1.04 s (4.4 times) and 2.95 s for `askme.py` (12.6 times). Each
  shell action now starts through `env`, which restores `SIGPIPE`: one more
  process per command than in the first run.
- **A kept connection removes the transport's cost.** With the harness
  included, a request takes 0.84 ms from the executable, where starting `curl`
  took 7.7 ms and `askme.py`'s `requests.post` takes 4.1 ms. Over TLS it takes
  1.5 ms against 56 ms for `curl` and 28 ms for `askme.py`, which both
  handshake for every request.
- **`pystachy run` compiles the port at every launch**, 4.4 s, because the
  program cache skips a program that declares `@ffi.extern` libraries
  ([#1320](https://github.com/den-run-ai/pystachy/issues/1320)). Its long-run
  rows are that compilation plus the executable's speed.
- **The shared host was slower than during the first run**: `askme.py`, which
  did not change, took 9% to 19% longer on the long runs. Compare rows within
  this table, not across the two files.

## Startup and short runs

`--help` starts the program and exits. The suite is the sum of the median wall times of 17 complete scripted runs (3 to 15 model requests each, some with shell actions).

| Runtime | `--help` ms | Suite ms | Suite vs CPython | Peak RSS MB |
|---|---:|---:|---:|---:|
| Pystachy AOT | 2.4 | 235 | 4.4x | 5 |
| Pystachy JIT | 4,411 | 75,572 | 72.5x slower | 146 |
| mypyc + CPython | 45.9 | 995 | 1.0x | 19 |
| CPython | 47.0 | 1,042 | 1.0x | 17 |
| PyPy | 117 | 2,928 | 2.8x slower | 124 |
| `askme.py` on CPython | 165 | 2,951 | 2.8x slower | 29 |
| `askme.py` on PyPy | 421 | 7,935 | 7.6x slower | 210 |

## Long runs

One scripted run of 2,001 model requests (20 tasks of 100 steps: reads, searches, edits, writes and tree listings, no shell). *Navigation* scans 240-line files; *controller* uses tiny files, so prompt building, reply decoding and policy checks dominate. Per-step time excludes nothing: it is wall time divided by requests.

| Runtime | Navigation ms | ms/step | vs CPython | Controller ms | ms/step | vs CPython | Peak RSS MB |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pystachy AOT | 1,662 | 0.83 | 1.3x | 1,449 | 0.72 | 1.4x | 60 |
| Pystachy JIT | 6,483 | 3.24 | 2.9x slower | 6,071 | 3.03 | 3.0x slower | 156 |
| mypyc + CPython | 1,765 | 0.88 | 1.2x | 1,654 | 0.83 | 1.2x | 44 |
| CPython | 2,201 | 1.10 | 1.0x | 2,024 | 1.01 | 1.0x | 43 |
| PyPy | 3,381 | 1.69 | 1.5x slower | 3,152 | 1.58 | 1.6x slower | 250 |
| `askme.py` on CPython | 2,726 | 1.36 | 1.2x slower | 2,795 | 1.40 | 1.4x slower | 46 |
| `askme.py` on PyPy | 4,629 | 2.31 | 2.1x slower | 4,578 | 2.29 | 2.3x slower | 264 |

## Real HTTP transport

The same kind of run (103 requests) against an instant loopback server instead of in-process replies: milliseconds per request, harness included. The port keeps one connection open and, in the `curl` columns, starts a `curl` process per request instead; `askme.py` calls `requests.post`, which opens a connection per request. TLS uses a 2048-bit RSA certificate from a private CA.

| Runtime | HTTP | HTTP, `curl` | HTTPS | HTTPS, `curl` |
|---|---:|---:|---:|---:|
| Pystachy AOT | 0.84 | 7.69 | 1.50 | 56.49 |
| Pystachy JIT | 43.71 | 50.67 | 44.56 | 99.80 |
| mypyc + CPython | 1.51 | 8.43 | 1.99 | 57.06 |
| CPython | 1.54 | 8.76 | 2.14 | 57.05 |
| PyPy | 4.08 | 12.23 | 4.66 | 60.17 |
| `askme.py` on CPython | 4.10 |  | 28.33 |  |

## Per-scenario medians (ms)

| Scenario | Pystachy AOT | Pystachy JIT | mypyc + CPython | CPython | PyPy | `askme.py` on CPython | `askme.py` on PyPy |
|---|---:|---:|---:|---:|---:|---:|---:|
| compile_repair | 21.6 | 4,502 | 66.8 | 71.4 | 178 | 181 | 489 |
| compile_repair_disabled | 22.1 | 4,418 | 67.5 | 68.4 | 179 | 179 | 474 |
| duplicate_guards | 21.0 | 4,499 | 65.8 | 68.8 | 182 | 177 | 469 |
| exhausted | 7.3 | 4,432 | 50.9 | 52.5 | 158 | 169 | 456 |
| hello | 7.0 | 4,469 | 51.6 | 54.1 | 165 | 167 | 467 |
| lifecycle | 15.1 | 4,523 | 61.5 | 62.5 | 176 | 172 | 485 |
| limits | 8.0 | 4,482 | 52.7 | 56.4 | 166 | 178 | 451 |
| navigate_and_edit | 31.5 | 4,390 | 78.1 | 80.2 | 192 | 187 | 495 |
| observe_tail_exhausted | 8.0 | 4,410 | 52.2 | 54.9 | 165 | 165 | 456 |
| openrouter | 7.3 | 4,421 | 51.8 | 52.9 | 164 | 164 | 451 |
| read_pages | 9.1 | 4,491 | 54.2 | 56.2 | 165 | 170 | 474 |
| replan_after_failure | 21.1 | 4,432 | 65.7 | 70.9 | 194 | 177 | 495 |
| retries | 8.3 | 4,413 | 51.9 | 56.8 | 167 | 168 | 449 |
| rewrite_loop | 15.6 | 4,324 | 59.9 | 63.1 | 167 | 166 | 462 |
| truncated_write | 8.2 | 4,443 | 52.2 | 55.0 | 165 | 175 | 455 |
| validation_rejected | 15.5 | 4,506 | 60.1 | 62.9 | 178 | 189 | 466 |
| write_pressure | 7.7 | 4,417 | 52.0 | 54.8 | 168 | 168 | 442 |

## Build cost

| Runtime | Build | Artifact |
|---|---:|---|
| Pystachy AOT | 16.6 s | 1.05 MB executable; links libc, libm and libgcc |
| Pystachy JIT | 4.6 s first launch | every launch compiles: the program cache skips programs with `@ffi.extern` |
| mypyc | 60.0 s | 3.62 MB of extension modules; needs CPython |

## What this means for a fast hosted model

These are estimates from the rows above, not measurements of a hosted model.

| Per request | Executable | `askme.py` on CPython |
|---|---:|---:|
| Harness (controller run) | 0.72 ms | 1.40 ms |
| Transport over TLS, loopback | about 0.7 ms, connection kept | about 27 ms, handshake each time |

With a model that answers in 300 ms, the executable's harness and transport
are about half a percent of a request. `askme.py` spends about a tenth of it
on the handshake here, and a real network adds one or two round trips to
every new connection, so keeping the connection matters more than the
runtime does. The runtime decides startup, memory and how the program ships.

## Limits

- No model was called. A hosted model adds its own latency to every request,
  and a network round trip or two to every new connection; the loopback rows
  bound what the harness and transport themselves cost.
- One machine, one run of the benchmark, Linux x86-64 only.
- The reference harness is timed through its recorded-reply shim for the first
  three tables and through `requests` for the transport table.
