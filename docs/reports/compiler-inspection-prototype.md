# Compiler inspection prototype: bounded usefulness evaluation

Date: 31 October 2026 (UTC). Baseline source:
`06e3ad5d08514ba31fb231fe4636a962fe6578e3`.

## Question and scope

Can inspection of Pystachy's existing typed-IR pipeline make debugging an
optimization or a rejected specialization easier without changing program
semantics?

The prototype exposes snapshots and structured diagnostics through a hosted
developer tool. It retains the typed-IR-to-LLVM pipeline and does not add MLIR,
an MCP service, a new native command or a persistent compiler session. The
[usage guide](../compiler-inspection.md) gives the commands and output contract.

## Tasks and independent oracles

The inputs are maintained, small examples under `tools/inspection_examples/`.
They exercise distinct questions rather than measuring only whether a report
file can be written.

| Task | Input | Independent CPython oracle | Useful inspection evidence |
|---|---|---|---|
| Explain a list-loop optimization | `score_samples.py` | Prints `3.5` | `listget` changes checked `list.get` to inline `list.load` |
| Check a mutation barrier | `record_lookup.py` | Prints `7`, then `-1` after the key is deleted | Plain lookup fuses; a lookup after a mutating helper remains checked |
| Locate and repair an imported specialization | `specialization_error.py`, then `specialization_fixed.py` | First raises `TypeError`; repaired caller prints `8` | Imported helper location and specialization context identify the incompatible call |

The bad specialization is also invalid Python at execution time. Its rejection
is expected, not a newly discovered compatibility bug. The repair changes the
caller argument from a string to an integer without changing the imported helper.

## Direct pass observations

Independent wrappers around the existing `Gen.listget` and `Gen.dictfuse`
implementations observed the real passes on the two successful examples:

| Function | Reported rewrites | Before | After |
|---|---:|---|---|
| `score_samples` | 1 | One checked `list.get` | One inline `list.load`, no `list.get` |
| `lookup` | 2 | One `dict.has`, one `dict.getitem` | One `dict.find`, one `dict.val` |
| `lookup_after_update` | 0 | One `dict.has`, one `dict.getitem`, one helper call | The same checked lookup and helper call remain |

This is a useful boundary to make inspectable. The helper called by
`lookup_after_update` deletes the key, so reusing the successful membership lookup
would be unsound.
Reading the same-run snapshots and pass diff makes the distinction visible
without locating the corresponding LLVM operations manually. The interpretation
also uses the source and the documented `dictfuse` contract; a zero rewrite count
alone does not explain why a transformation was declined.

## End-to-end tool checks

The four documented inspector invocations were executed with CPython **3.13.16**
on Linux x86-64. Each inspector request used a fresh worker and enabled the typed
IR verifier. The output below is from the prototype on the baseline above; it
includes the small diagnostic-capture additions and the new hosted tool.

| Input | Outcome | Selected functions | Verifier calls | Changed pass/function pairs | Approximate retained output |
|---|---|---:|---:|---:|---:|
| `score_samples.py`, filter `score_samples` | `ok` | 1 | 3 | 1 | 49.5 KiB |
| `record_lookup.py`, filter `lookup` | `ok` | 2 | 6 | 2 | 76.0 KiB |
| `specialization_error.py` | `rejected` | Not available | 0 | 0 | 11.3 KiB |
| `specialization_fixed.py` | `ok` | 3 | 3 | 0 | 48.5 KiB |

Sizes include snapshots, report, LLVM and diffs. They depend on path lengths and
report metadata and are descriptive, not regression thresholds. Verifier calls
cover the entire compilation even when the snapshot filter selects fewer
functions. The second changed pair in `record_lookup.py` is exception lowering,
which is correctly reported separately from dictionary fusion.

All **three successful inputs emitted byte-identical LLVM** to ordinary
`pystachy.py ir` under matching settings. All **four captured stderr streams
matched the ordinary compiler byte for byte**. The bad specialization produced
`PYS0001` in phase `semantic`, with `inspection_support.py` line 5 and the caller
context. Its typed/LLVM stages remained unavailable, with no false successful
verification or LLVM artifact. The repaired input completed all three stages.

The four invocations were repeated after the output-staging and source-read
provenance fixes. All results and byte comparisons remained the same. The two
single-file examples each recorded one source read; each specialization example
recorded two. Every `input.changed_during_compilation` flag was false. The output
sizes above are from that repeat, including tool/source-read hashes. The tool
SHA-256 at that checkpoint was
`a60b5b51f7c6c85e2c93b59dc1cf345bd9505874d5abed32932dfca12d258da1`.

These checks establish the tool's observations on these examples, not native
execution. The separate CPython runs produced the oracles above.

### Existing JSON workload

The same tool was also run on `bench/smoke/json_decode_any32.py` with
`--function object`. The complete compilation contained **38 typed functions**;
the filter retained two. All **46 verifier calls** completed. In
`@f._pystachy_json_any$_object`, the existing `nullcheck` pass reported **two
rewrites**: `check` operations fell from four to two, pointer comparisons from
three to one, and raises from five to three. The final LLVM and captured stderr
were byte-identical to ordinary hosted compilation under matching settings.

The report and artifacts occupied 325,910 bytes (about 318 KiB). This is evidence
that inspection exposes a real existing optimization beyond the small examples;
the prototype does not introduce that optimization or demonstrate a runtime
speedup.

### Inspection cost

After the heavy local checks finished, ordinary hosted IR generation and the
inspector were measured in five alternating pairs per workload, following one
untimed correctness pair. Both modes enabled `PYSTACHY_IRCHECK=1`, used identical
source/library paths and wrote LLVM to disk. Each invocation started a fresh
process. The inspector measurements include its extra worker, hashes, snapshots,
diffs and artifact publication; neither mode runs an LLVM backend or the program.

| Workload and filter | Ordinary median | Inspector median | Median paired added time | Median retained artifacts |
|---|---:|---:|---:|---:|
| `score_samples.py`, `score_samples` | 56.3 ms | 164.2 ms | 107.3 ms | 49.5 KiB |
| `json_decode_any32.py`, `object` | 223.1 ms | 360.3 ms | 136.4 ms | 318.3 KiB |

Paired added time is the median of the five inspected-minus-ordinary differences,
not the difference between the two medians. All 12 pairs, including preflights,
had byte-identical LLVM and stderr. Compiler, tool and workload identities stayed
constant, with no source-change flags. The final measured tool SHA-256 was
`454a0296d61a12a733a7a45be4b040cd260d2b17f59e7db8393dfd787ed9baa2`;
the compiler-source manifest SHA-256 was
`79ebc209b630347eae3baad1005a006d6f6a78595373049f560a58134ef2d7d1`.

The environment was CPython 3.13.16 on Linux x86-64, AMD EPYC 9V74, with all
children pinned to one CPU. This remained a shared host: load average was about
3.2, and inspected times ranged from 152-249 ms for the small example and
305-371 ms for JSON. An earlier run before the FIFO robustness fix measured
53.8/162.1 ms for the small example and 214.7/314.6 ms for JSON. These short
samples do not isolate an effect of that fix or establish a general scaling
model. The final-hash measurements support an opt-in debugging tool with visible
overhead, not an always-on default or a native execution performance claim.

## Integrated correctness validation

The compiler with the small capture hook bootstrapped natively using CPython
3.13.16 and LLVM 18.1.3. Stages 1, 2 and 3 produced byte-identical compiler IR
(775,228 lines) and runtime IR (18,805 lines). Initial bootstrap attempts exposed
missing explicit field annotations on `Diagnostic`; those were corrected before
this successful bootstrap.

- All **26 new tests** pass: 8 diagnostic-record tests, 17 inspection tests and
  one state-inventory negative-control test.
  The complete `make check-fast` target passed **333 tests**, Ruff and mypy.
- The separate CI-equivalent compiler-state suite passed **108 tests**. The
  first GitHub lint run identified missing ownership metadata for the diagnostic
  buffer. The fix explicitly registers observer-owned lifetime and the sole
  compiler writer; the new negative control rejects additional writers and stale
  declarations. No audit rule was weakened.
- `make lint` passed, including shell checks, C warnings and the runtime root
  audit. The runtime ABI/effect checker passed with 592 runtime entries.
- Native typed-IR verification and LLVM assembly accepted the three successful
  examples and the existing `tests/ir/dictfuse.py` regression.
- **12 native executions** matched fresh CPython output, stderr and status:
  each of the three successful examples in JIT, JIT with program GC stress,
  AOT and AOT with GC stress. All three AOT builds succeeded.
- **5 native/hosted rejection comparisons** were byte-identical, covering the
  imported specialization, syntax, missing import, annotation mismatch and
  missing name.
- All **3,903 corpus cases** matched the baseline's emitted LLVM, diagnostics and
  exit status under matching inputs. The first `tools/irsame.sh` run matched
  3,665 cases directly; 238 differed because separate checkout paths appeared in
  library-derived IR or diagnostics. After verifying that all 74 library files
  and both runtime inputs were byte-identical, those 238 cases were rerun with a
  common `PYSTACHY_HOME` and all matched. The raw first run was not a clean pass;
  the second comparison resolved its input-path differences without normalizing
  away output text.

The native binary SHA-256 was
`36a81fab6e0daa62e538ef65bc9f3d51bb5ea28f1fe138a9aad05ead0e557d39`.
Its source manifest stayed unchanged through the native checks. These are local,
focused results; they do not substitute for the full applicable CI matrix.

Independent review found and the integration suite now guards three observation
errors: output directories changing namespace-import resolution, after-the-fact
hashes identifying replacement source rather than consumed text, and missing
inputs being mislabeled as language rejection. The final tool stages output,
captures consumed-source hashes, flags provenance changes and distinguishes setup
errors. All three regressions pass with the fixes. A further bounded FIFO probe
found that the parent's timeout-report hashing could itself block on a pipe.
Hashing now accepts only regular files, checks the opened descriptor and uses a
nonblocking open; the worker rejects non-regular input as an operational error.
The new regression covers both error and timeout reporting, with a regular-file
symlink as a positive control.

## Assessment

The interface has a concrete debugging use: it shows what changed in a pass,
what representation survived to the next stage, and where a rejected imported
specialization originated. It is especially relevant when reviewing dictionary
lookup, union-storage or identity-related compiler work.

This evaluation does not establish improved autonomous-agent repair rates, time
saved by human developers, or faster native programs. Those need a separate
trial with multiple tasks, fixed prompts/documentation and independently checked
outcomes. The small examples and existing JSON workload justify retaining and
evaluating the tool; they do not justify a compiler architecture rewrite.

## Practical limitations

- Function definitions are source-linked, but individual instructions lack source
  spans. A future instruction-location design must handle synthesized and
  transformed operations explicitly.
- Structured codes distinguish ordinary rejection, internal failure and worker
  failure; they do not yet categorize every language restriction.
- General pass contracts are explanatory context, not per-operation proof traces
  or exhaustive missed-optimization reasons.
- The worker proves frontend/typed-IR compilation only. Runtime behavior still
  needs CPython-versus-native JIT/AOT checks.
- Report generation adds host-side cost and retained artifacts. The paired
  measurements above cover only two workloads on one shared host; they do not
  establish cost for larger programs or human/agent repair-time savings.
- Process isolation avoids cross-request interference for this tool; it does not
  make the compiler's existing global tables safe for concurrent in-process use.

## Reproduce

Run the commands in the [usage guide](../compiler-inspection.md) from the checkout
root. Use a new output directory for each input. Keep failed reports as failed
outcomes; the intentionally bad specialization must not be counted as a
successful native compilation. Compare emitted LLVM with an ordinary
`python3 pystachy.py ir SOURCE.py` run under matching feature settings before
attributing any change to inspection.
