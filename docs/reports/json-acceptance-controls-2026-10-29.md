# JSON delimiter cost and retained acceptance controls, 29 October 2026

The remaining broad JSON instruction gap after #986 is removed by reading each
typed array/object delimiter once. The retained broad workload is now below the
actual alpha.3 tag, as are all three typed 32-key controls. New observed-`Any`
32-key controls cover the same input bytes through the other decoder path; they
are also below both the actual alpha.3 tag and the historical post-tag baseline.

This does **not** recover the original approximately 124M-instruction benchmark.
Its exact source and input were not retained in the available project evidence.
The replacement suite makes future acceptance reproducible without presenting a
new workload as a replay of that old claim. Refs #969.

## Change and attribution

The typed `array()` and `object()` loops read `data[i]` once for a closing
delimiter and again for a comma. They now check end-of-input, load the byte once,
and reuse it. Closing-delimiter bounds, callback points, error messages, character
positions and trailing-comma positions are preserved. The scanner uses native
`bytes`; this does not omit user-defined indexing callbacks.

The deterministic IR guard limits these methods to three and five byte-indexing
calls respectively. Restoring the original source fails both limits (four and
six). A recorded 31-input CPython regression covers valid/nested values, EOF,
wrong delimiters, missing commas, trailing commas, whitespace and Unicode offsets.
No compiler, runtime, dictionary geometry, numeric identity or Any decoder code
changes are needed.

The earlier profile's key-parser self-cost remains larger than alpha.3's, while
other costs offset it. This change removes avoidable work in container parsing;
it does not claim every individual function has returned to its historical count.
A tuple-cache experiment was rejected before adoption because the bytes tuple
form is outside the supported subset. It is not part of this change.

## Source pins and method

| Source | Commit |
|---|---|
| Actual alpha.3 tag | `f5a09d4223139d7255e31051be97fc509e1ca1fe` |
| Historical post-tag baseline | `dcdc1a281d218038c2041a5e381396edd43beaea` |
| #986 evaluated head | `ca798a9d1f6a2767d4ec3c83cb7574bacde5d63b` |
| #986 merged main | `2ae4745202d3f9f648fc813aedad95a8859abec0` |
| Evaluated follow-up code and tests | `b781fc508da74e4cf8b438594938017e2115c6f5` |

The follow-up includes merged main. Subsequent report-only changes do not change
consumed compiler, runtime, library or benchmark bytes. All four sources were built
with their own libraries/runtime and private caches, using CPython 3.13.16,
LLVM/Clang 18.1.3 and Valgrind 3.22.0 on Linux x86-64. Profiles ran sequentially,
pinned to CPU 0 (AMD EPYC 9V74), without another session-owned heavy job.
Inherited `PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME` settings were cleared;
`PYTHONHASHSEED=0` and `LC_ALL=C.UTF-8` were set. Every profiled stdout matched
pinned CPython. Source/input/binary hashes and consumed-source checks are retained
with the private evidence, along with the replay harness.

The broad workload uses 300 outer loops, every 32-key control uses 3,000 loads,
and the short Any control uses 2,000. Counts cover the complete AOT process,
including setup, validation and output. Whole-process counts can vary slightly
with startup and collector behavior; these are instruction comparisons, not
wall-time speedups.

## Executed instructions

| Control | alpha.3 | Post-tag baseline | #986 | Follow-up | vs alpha.3 |
|---|---:|---:|---:|---:|---:|
| Broad JSON | 1,300,357,999 | 1,300,358,108 | 1,301,840,560 | 1,299,270,260 | −0.084% |
| Typed 32-key numeric | 91,425,823 | 91,425,810 | 90,959,418 | 90,680,503 | −0.815% |
| Typed 32-key strings | 108,664,668 | 108,664,654 | 108,225,156 | 107,946,240 | −0.661% |
| Typed 32-key mixed | 127,320,233 | 127,320,276 | 126,940,849 | 126,626,066 | −0.545% |
| Short observed Any | 29,964,359 | 29,964,359 | 29,445,027 | 29,445,024 | −1.733% |
| Observed Any 32-key numeric | 106,791,283 | 106,791,269 | 101,890,686 | 101,890,700 | −4.589% |
| Observed Any 32-key strings | 116,925,786 | 116,925,739 | 116,458,058 | 116,458,073 | −0.400% |
| Observed Any 32-key mixed | 142,725,100 | 142,725,110 | 139,725,423 | 139,725,378 | −2.102% |

The new edit affects typed container decoding. The observed-Any controls retain
#986's gains; their differences of at most 45 instructions between #986 and this
source are process/layout effects, not a new Any algorithm improvement.
Three additional interleaved broad runs on the same binaries reproduce the gap's
removal: alpha.3 ranges from 1,300,336,418 to 1,300,357,229 instructions, #986 from
1,301,981,987 to 1,301,982,020, and the follow-up from 1,299,269,477 to
1,299,269,490. Every follow-up run is below every alpha.3 run (about 0.082–0.084%).
The [earlier report](json-residual-cost-2026-10-29.md) remains the record of #986's
original measurements and its +0.126% broad residual.

## Historical benchmark disposition

The original release-sweep commits `7fc1432c` and `90f505ab` retained the report,
not the 32-key benchmark program, input hash or bisect-command manifest. Searches
of available repository history, research branches and earlier workspaces found
only explicitly labeled later reconstructions. The old baseline `dcdc1a28` is
four first-parent merges after the alpha.3 tag (#880, #883, #884 and #885).

The missing source also means “opt-in JSON” cannot establish which decoder ran:
discarded loads use typed `JSONValue`, while consuming the result as `Any` uses
the boxed adapter. The retained suite now tests both against both baseline commits.
The historical 124M number remains unverified; none of these measurements proves
that exact old criterion passed. #969 should distinguish this evidence gap from
the now-removed residual on the retained workload, and only advance its merged-main
checkpoint after the follow-up lands and its required checks pass.

## Replay and validation

See the [retained-control instructions](../../bench/smoke/README.md#retained-json-decoder-controls)
for paired builds and Callgrind commands. Use `json_decode.py` for discarded typed
results and `json_decode_any32.py` for observed Any, with the same case and load
count. Use `bench/pyperformance/json_loads.py 300` and
`bench/smoke/json_decode_any.py 2000` for the broad and short controls.

Every timed Any32 iteration consumes dictionary length and a field; the final
checksum is asserted and the complete last value is printed. Unit tests preserve
exact input parity and reject a corrupted intermediate result even with a correct
final result. This is an observation/checksum guard, not full validation of every
field of every intermediate result. The differential JSON suite supplies semantic
coverage independently.

Local validation on the follow-up includes 22,449 hosted JSON differential/limit
checks and 14,444 native cases each in JIT and AOT with collection at every
allocation. The benchmark and identity-scope unit suites pass 11 and 17 tests.
The new recorded delimiter outputs match pinned CPython. Independent review found
no defects. The full native bootstrap and required verification matrix are reported
by the PR's exact-head CI, separately from these focused local checks.
