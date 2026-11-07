# Guarded callback experiment

Does knowing the identity of a runtime-selected callback pay for an extra compiled
body? This benchmark uses Pystachy's shipped `bisect_left` to find 509 insertion
positions in 1,024 sorted records per batch. All four callbacks have the same
Python signature. One reads the text length, one reads a different field and two
share a function body but capture different offsets. The caller reads the callback
from a list.

[The earlier bisection experiment](https://github.com/den-run-ai/pystachy/pull/389)
compared online compilation with a source-written AOT guard.
[The v0.2.0 evaluation](https://github.com/den-run-ai/pystachy/issues/1054)
asks whether a precompiled variant helps once an explicit
[`Callable`](../../docs/language/typing.md#functions-callables-and-closures) erases the target.

## Run

Use Linux, the repository's pinned CPython and its LLVM toolchain. Choose an
available CPU and two new output directories. The default run compares two
invocations of the same hosted compiler on identical Python input.

```sh
taskset -c 2 python3.13 bench/callbacks/measure.py /tmp/callback-descriptor
make
taskset -c 2 python3.13 bench/callbacks/measure.py /tmp/callback-source --source-compiler ./pystachy
```

Each pair has its own comparison. The second command using `measure.py` builds a
source-written guard with the native compiler. It tests `key is text_length`
at the batch boundary, then passes the known function to the ordinary template.
The existing template specialization can propagate that identity into bisection.

The hosted experiment selects the compiled `bisect_left` body whose `key` has
the erased callable signature. It tests the incoming pointer against the
compiler's interned constant descriptor for `text_length` once per bisection.
On a hit, LLVM sees the constant adapter and its null environment. On a miss,
the original body receives the original pointer, including its live environment.
The comparison is sufficient for the fast path. A distinct descriptor for an
equivalent function can safely miss.

The experiment runs from [variant.py](variant.py). Its allowlist names one target
per fixture. It accepts a single internal body with the ordinary argument ABI and
caps additional unoptimized IR at 16 KiB. It rejects missing and ambiguous matches.
Target selection is supplied in advance. Both JIT and AOT use the normal optimizer
and runtime, with no runtime profiles or online compilation.

## Read the results

The controller alternates pair order and checks each checksum against an independent
insertion-position calculation. It saves raw timings in `samples.json` and
`long.json`, the run settings and input hashes in `metadata.json`, both executables
and the unoptimized IR. `--rounds 1
--batches 2 --long-batches 4` runs a correctness smoke. Use the defaults for timings.

| Measurement | What it includes |
|---|---|
| Hit, skew, mixed, miss, change | 100%, 90%, 25%, 0%, or a hit → miss → hit phase change. The kernel timer includes callback selection and search. Process wall time also includes fixture construction. |
| Startup and short run | Fresh process with zero or one batch. OS caches and the compiler's runtime cache are warm. |
| Long invocation | Fresh build immediately followed by the first process running 150,000 batches, or 76.35 million searches. |
| Memory and size | Peak Linux RSS for toolchain invocations and a separate AOT process reading its own `VmHWM`. Build rows include executable bytes. |

Inspect the optimized executable to check what the guard bought. For the tested
Linux x86-64 build, the commands below show the inlined search inside
`f.call_search`, its indirect fallback and the direct text-length call on a hit.

```sh
llvm-objdump -d --disassemble-symbols=f.call_search /tmp/callback-descriptor/guarded/app
llvm-objdump -d --disassemble-symbols=f.call_search /tmp/callback-descriptor/generic/app
llvm-size -A /tmp/callback-descriptor/{generic,guarded}/app
```

Both variants also run [callback_effects.py](callback_effects.py) against CPython
with normal and stressed GC in JIT and AOT. It changes the callback table during
a call, exercises two live closure environments and two bound receivers, and
checks the side effects before an exception.
