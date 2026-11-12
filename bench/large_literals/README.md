# Large scalar list literals

This workload measures the initialization-code growth tracked by
[#111](https://github.com/den-run-ai/pystachy/issues/111). Large homogeneous literal
lists of fixed-width `int`, `float` and `bool` values can use immutable typed data
and a bounded copy into a fresh list. Pointer-bearing lists, tuples, computed
items, dynamic-Any graphs and promoting-int graphs retain their existing paths.
The fixture deliberately includes the 31/32-item boundary as well as 4,096 items.

The [final evaluation](results/final/README.md) records repeated narrow timings,
the seven reviewed corpus IR changes and complete local validation. The
[inline-policy screen](results/policy-screen/README.md) explains why the helper
uses normal LLVM eligibility; the [initial record](results/initial/README.md)
preserves earlier validation and corrected test/setup attempts.

## Reproduce

Use unchanged baseline and candidate source checkouts, a matching complete LLVM
toolchain and the pinned CPython interpreter. The runner prepares each runtime
separately, emits raw IR with **hosted source**, and checks native output against
CPython before recording execution samples. It does not use a checkout's existing
native compiler binary.

```sh
python3 bench/large_literals/run.py \
  --baseline ../baseline --candidate . --llvm /path/to/llvm/bin \
  --work /tmp/literal-screen --report /tmp/literal-screen.json \
  --shapes int,float,bool --sizes 31,32,4096 \
  --consumers escape,local --samples 3 --execution-samples 5 --cpus 3
```

`--work` must name a new directory. Every generated source, LLVM artifact and
command log remains there. The JSON records source/tool identities, source and
artifact hashes, command arguments, affinity, host load, wall/CPU time, per-command
maximum RSS, raw/optimized IR size and instruction counts, object text/data sizes,
and instruction-selection/register-allocation timing lines. Maximum RSS is the
`wait4` maximum of a command and its waited children; it is **not** a sampled
aggregate of simultaneously running processes.

The backend replay separates Clang's O2 optimization from machine-code generation
to expose their costs. Runtime preparation and the separate disassembly/size
inspection are excluded from backend totals. These totals therefore describe
the replay, not the driver's combined command or a complete compiler bootstrap.
The runner rotates policy order between samples; no timing threshold determines
correctness.

## Execution controls and policy screening

The `escape` consumer stores constructed lists in a global batch, retaining up to
32 lists. The `local` consumer uses a private list whose length and last element
may become visible to LLVM optimization. Both consume a checksum and print a full
constructed list for the CPython witness. Reporting both exposes a possible loss
of scalar replacement or constant folding when construction crosses a helper
call. Samples use at least 5,000 constructions and 20 million total elements by
default, include fresh-process startup, and report their repetition count.

For a candidate that marks the copy helper `noinline`, `--inline-control` adds a
third policy that removes only that attribute from the exact same linked bitcode
before program O2. It checks that the two policies have byte-identical raw IR and
linked input before the attribute edit. That edit is separately timed and excluded
from backend totals. This is an isolated LLVM policy screen; adopting a different
C declaration still requires a new native bootstrap and correctness validation.

`--shapes tuple` is an excluded-path control: tuple-item lists do not receive
this optimization. `tools/test_typed_list_constants.py` provides a deterministic
initialization-instruction bound; the CPython-recorded literal fixtures and
`tools/listprobe.c` cover fresh storage, aliases, order, exact scalar bits,
atomic payloads and collection.
