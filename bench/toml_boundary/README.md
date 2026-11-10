# TOML dynamic boundary measurements

This consumer parses a generated worker configuration containing dotted table
names, nested inline tables, lists and arrays of tables, then processes the
result through concrete int, float, bool and string annotations. Its own module
does not opt in to dynamic `Any`. `width` controls independent worker tables and
`rounds` controls repeated parsing of the same input. A separate arithmetic
formula checks the complete scoring checksum; the runner also executes the same
fixture with CPython before accepting native measurements.

Run from a candidate checkout with the pinned Python and a supported complete
LLVM toolchain. Stop unrelated builds and timing jobs. The output directory must
be new; the runner creates private runtime caches and pins its subprocesses to
one allowed CPU. Use `--cpu` to select a different allowed CPU.

```sh
python3.13 bench/toml_boundary/run.py \
  --baseline /path/to/baseline-checkout \
  --candidate /path/to/candidate-checkout \
  --output /path/to/new-results \
  --width 16 --rounds 100 --processes 5 --samples 3
```

Both variants use their own CPython-hosted compiler, runtime and library sources.
The same absolute consumer input is used for both. Repeat with widths 8, 16 and
32 to distinguish input growth from repeated-use cost; use `--rounds 1` for a
short-use control. These are focused configuration workloads, not a claim about
all applications that import TOML. No timing threshold is a CI gate.

The report separates frontend IR emission, AOT build including the first runtime
cache construction, later AOT builds with a warm runtime cache, whole-process
JIT/AOT wall time, and the consumer's in-process parsing/processing durations.
Baseline/candidate order reverses on alternate repetitions. Each in-process
sample has the same checked checksum; medians across processes avoid counting
correlated samples as independent trials. Shared-host timing remains noisy.

Raw and LLVM-O2 program IR inventories count direct C dynamic helper call sites
(`pys_dyn_*`) separately from generated dispatcher calls (`dyn.*`), before runtime
linking. The named identity-helper counts are not a census of all numeric
identity operations. Static counts and smaller IR do not establish runtime
speed or allocation savings. The report includes executable sizes, Python and
LLVM versions, relevant environment settings, source hashes, and raw samples.
It rejects sources changed during measurement. Candidate Git status is recorded;
an uncommitted candidate is identified by the source manifest, including root
Python/C entry points and glue, imported source trees and extensionless/untracked
library inputs. Interpreter/system libraries are identified by tool versions,
not a complete hash of the host environment.

## Allocation requests and retained memory

Allocation measurements use a separate AOT binary built with
`PYSTACHY_CFLAGS=-DPYSTACHY_PROFILE_DATA`. The existing `pystachy-data` counters
record C allocation requests and requested bytes before allocator rounding, plus
managed-heap peak. They include process initialization and all repeated samples.
They exclude foreign allocator traffic; they are not RSS, live bytes, or physical
memory traffic. JIT fast allocation bypasses these C counters, so this runner
does not use them to characterize JIT allocations. Instrumented execution is
excluded from ordinary timing summaries.

`retained.py` is a separate diagnostic AOT program. After repeated parsing, it
retains one parsed document and its source, calls the existing conservative
collector, and reads the collector's live-byte total. It then uses the document
again and checks its checksum. `retained.h`, force-included only for this plain
AOT build, exposes that private collector to the diagnostic through `@extern`.
The production runtime source and public API are unchanged. Do not use this
header with JIT, extensions or embedded CPython: those modes compile additional
C glue, whereas the supported plain AOT path compiles only `runtime.c` as C.
The wrapper is marked `used` and explicitly exported for `@extern`'s dynamic
symbol lookup; otherwise the executable can report an undefined symbol even
when compiling the header succeeds. The runner chooses the Linux or macOS
linker spelling. Native probe execution has been checked on Linux; macOS remains
unverified.

The live-byte total includes module globals, caches, input source, the retained
document and conservatively retained objects. It is not an ideal reachable-object
census or process RSS. The runner samples independent processes and reports
median/minimum/maximum live bytes, since incidental conservative roots can vary.
Compare repeated-use and input-size samples rather than
interpreting one total as an exact document-size measurement. CPython supplies
the behavior oracle; its memory layout is not the native collector's oracle.
