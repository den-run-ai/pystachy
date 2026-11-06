# Source attribution prototype: Linux x86-64 measurements

## Scope and environment

The experiment adds opt-in Python line tables and scoped C-runtime data counters.
It tests Pystachy based on
[`f7103067545b43cdcd8ce20dc66b1571425b3a8d`](https://github.com/den-run-ai/pystachy/commit/f7103067545b43cdcd8ce20dc66b1571425b3a8d).
The executable and source hashes in [linux-x86_64.json](linux-x86_64.json) identify the measured
artifacts independently of the commit ID used to submit this prototype.

Measurements were taken on 2026-11-06 on Linux x86-64, AMD EPYC 9V74 80-Core
Processor, with Python 3.13.16, LLVM 18.1.3 and Valgrind 3.22.0. Execution is
pinned to allowed CPU 0; builds use two workers. The host is
shared, so affinity and serialized experiment jobs do not eliminate external
scheduling noise. Timings describe complete processes, including startup and
shutdown. Each timing group has seven alternating-order rounds following one
warmup per variant. The runner checks deterministic output witnesses before using
samples. Absolute times and small relative changes should not be generalized to
a different host or treated as optimization claims.

The baseline native compiler has SHA-256
`3b59b4e875a89f15777395f5993ccf2e6d51e934dbc7a4e45228d622c7f1cff7`.
The new ordinary compiler has SHA-256
`441e81c4b9e9d3cb3daa0471a144b0a5ee107af6296c86f90a4df4eb1d0e0464`.
All variants compile the same source. The baseline frontend comparison also uses
the current compiler source and a common `PYSTACHY_HOME`, separating the new
compiler's own overhead from changes in the program being compiled.

## Reproduction

See [the experiment guide](../README.md) for exact build/measurement commands and
counter definitions. [linux-x86_64.json](linux-x86_64.json) retains raw timings, witnesses, build
costs, counter values, source and input hashes, flags, tool versions, CPU affinity,
and parsed instruction profiles. Profile inputs are smaller than timing inputs;
counts in the two groups must not be compared as if they cover the same amount
of work. Callgrind instruction counts are not CPU cycles or native wall time.


The complete compressed Callgrind files are retained as
[JSON repair](json_repair.callgrind.gz), [routing](routing.callgrind.gz),
[numerical scoring](numeric.callgrind.gz), and [compiler](compiler.callgrind.gz).
Their decompressed SHA-256 values match the JSON record. To inspect one with
Valgrind's own reader:

```sh
gzip -dc bench/source_attribution/results/numeric.callgrind.gz > /tmp/numeric.callgrind
callgrind_annotate --auto=yes --threshold=100 /tmp/numeric.callgrind
```

The profiles retain original source paths. Run annotation in a checkout with the
matching files available, or supply source search directories to the reader.

## Measurements

Wall times below are medians with the full observed minimum–maximum range in parentheses. All values are milliseconds. The line-table setting and the counter setting are opt-in. The counted compiler still emits ordinary user IR unless `PYSTACHY_DEBUG_LINES=1` is set for that invocation.

| Workload | Ordinary | Line tables | Line tables + counters |
| --- | ---: | ---: | ---: |
| json_repair | 116.046 (111.818–123.159) | 115.802 (112.810–120.856) | 116.404 (110.688–132.457) |
| routing | 64.335 (59.048–78.776) | 68.360 (63.532–84.681) | 79.658 (60.759–84.072) |
| numeric | 163.360 (142.261–186.057) | 155.834 (143.074–200.200) | 190.221 (168.695–196.497) |
| compiler | 6,828.267 (6,548.268–7,423.492) | 6,810.921 (6,572.651–7,573.541) | 6,671.902 (6,331.634–7,515.378) |

These samples do not demonstrate a stable wall-time cost for line tables or for counters on every workload. In particular, the counted compiler was slightly faster in this sample despite doing additional work; that is evidence against interpreting small differences as causal. Routing and numerical samples also have substantial spread. All raw samples remain available for inspection.

### Compiler frontend overhead

This separate comparison compiles the same current `pystachy.py` source to LLVM IR. The base compiler and new default-off compiler emit the same byte-for-byte IR; the enabled variant also emits metadata. Wall time is median (minimum–maximum), in seconds. RSS is median peak KiB from GNU time.

| Compiler / setting | Wall seconds | Peak RSS KiB |
| --- | ---: | ---: |
| Base compiler | 7.033 (6.605–7.543) | 993,868 |
| New compiler, locations off | 6.617 (6.385–7.297) | 996,292 |
| New compiler, locations on | 7.474 (7.126–8.166) | 966,740 |

Adding `Ins.line` increases each instruction object's field count even when debug
output is disabled. Here the new default-off compiler's median peak RSS is
2,424 KiB (0.244%) above the base compiler. The median paired wall-time ratio is
0.967, with individual ratios from 0.892 to 1.036; this noisy sample does not
establish a default-off speedup or a stable runtime penalty.

Enabling source locations has a clearer frontend cost in this workload: the
median paired on/off wall-time ratio is 1.123, with all seven pairs between 1.018
and 1.209. The ratio of group medians is 1.129. Enabled peak RSS happens to be
lower, but different allocation and GC timing can change the high-water mark;
that is not evidence that metadata uses no memory or reduces memory demand.

All seven baseline and new-off emissions have SHA-256
`ecc08b8cb1154d4d1a1eedcb9951c5d62b78b2cefce684a3b7f78d82423736a4`.
All seven enabled emissions have SHA-256
`2e8de6910744659b9e371faf71dd2d279bc2a66a1ecaf7b29b837296612eb8e1`.

### Binary size and build cost

Each application build used a separate previously absent runtime cache. The costs include generating that runtime. Builds were measured once, so they give observed build cost, not a statistical speed comparison. The ordinary compiler was reused from the fixed-point bootstrap; its comparable one-shot build time was not measured.

| Workload | Ordinary bytes | Line-table bytes | Increase | Counted bytes | Ordinary / lines / counted build seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| json_repair | 437,616 | 500,272 | 14.32% | 517,304 | 13.016 / 13.547 / 13.134 |
| routing | 426,824 | 487,248 | 14.16% | 499,792 | 12.861 / 14.757 / 15.186 |
| numeric | 106,944 | 109,432 | 2.33% | 109,624 | 8.225 / 8.793 / 8.314 |
| compiler | 5,234,736 | 6,582,584 | 25.75% | 6,774,240 | not measured / 105.763 / 107.501 |

### Executed Python source locations

Callgrind used the smaller profile inputs described in the guide and binaries containing line tables without counters. These are exclusive instruction costs. File totals in the JSON include line zero; the Python-line totals below count only positive source lines. Runtime C functions, the system libraries and generated bookkeeping can contribute instructions outside the positive Python-line totals.

| Workload | Total instructions | Instructions on positive Python lines | Share |
| --- | ---: | ---: | ---: |
| json_repair | 53,023,476 | 10,207,203 | 19.25% |
| routing | 17,085,377 | 6,938,680 | 40.61% |
| numeric | 10,843,748 | 7,394,890 | 68.19% |
| compiler | 1,947,727,602 | 333,390,636 | 17.12% |

The profiles make these concrete sites visible:

- **JSON repair:** the byte test in [`runtime.py:241`](../../../runtime.py#L241), used by scanning, has 331,280 instructions; the dispatch condition in [`JSONParser.parse_json:323`](../../../ports/json_repair/json_parser.py#L323) has 165,438. These are attributed Python sites, not a ranking of total JSON-repair cost; about 81% of process instructions do not have a positive Python line.

- **Routing:** [`lib/re/_sre.py:1304`](../../../lib/re/_sre.py#L1304), the literal-repeat backtracking loop, has 573,834 instructions. The regex engine contributes the largest file total among Python files in this run.

- **Numerical scoring:** [`bench/smoke/ml.py:71`](../../../bench/smoke/ml.py#L71), the projection multiply-and-accumulate, has 5,484,078 instructions, 50.57% of the complete process. An independent review with upstream `callgrind_annotate` reproduced the exact total of 10,843,748 instructions, the Python-line total of 7,394,890, and this line cost.

- **Compiler:** the range-membership loop and test in [`lexer.py:88`](../../../src/pystachy_compiler/lexer.py#L88) and [`lexer.py:89`](../../../src/pystachy_compiler/lexer.py#L89) each have 12,847,848 instructions. These helpers can appear under their caller’s native function name because front-end expansion preserves their source line without constructing a full inline-frame chain. Only 17.12% of total compiler-profile instructions have positive Python lines, so this does not establish lexing as the overall bottleneck.

### Scoped data counters

Counter runs use the same smaller inputs and output witnesses as the instruction profiles. The three byte columns below mean requested bytes at instrumented C-runtime helper calls, before allocation rounding. They exclude generated LLVM/runtime-Python copy intrinsics, scalar stores, libc internals and foreign allocations; they are not total memory traffic. GC peak is the runtime’s committed-heap peak, not process RSS or live-object size. Counts include process initialization and shutdown through the reporting point.

| Workload | C GC allocation requests | Requested allocation bytes | C memcpy calls / requested bytes | C memmove calls / requested bytes | Collections | Peak GC heap bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| json_repair | 104,943 | 4,684,619 | 48,623 / 1,174,409 | 7,709 / 96 | 0 | 6,815,744 |
| routing | 54,297 | 2,833,100 | 6,873 / 256,550 | 13 / 352 | 0 | 6,172,672 |
| numeric | 10,066 | 1,040,629 | 41,035 / 736,472 | 0 / 0 | 0 | 2,228,224 |
| compiler | 1,492,214 | 91,597,602 | 870,911 / 12,696,125 | 50,499 / 13,976 | 3 | 67,514,368 |

Zero-length copy requests are counted as calls. This explains how JSON repair records 7,709 `memmove` calls but only 96 requested bytes. The three small application profiles did not trigger a collection; the compiler profile did. These are process-level totals, not per-source-line allocation or copy attribution.

## Validation evidence

All local native work used the pinned toolchain above and no concurrent heavy
experiment job. These are focused prototype checks; the full release matrix is
listed separately below.

| Check | Result |
| --- | --- |
| Ordinary bootstrap (`make`) | Compiler stage 1/2/3 IR identical, 833,648 lines; runtime stage 1/2/3 IR identical, 18,805 lines |
| Enabled emission with hosted / stage 1 / stage 2 compilers | Compiler IR identical, 892,452 lines; runtime IR identical, 20,964 lines |
| Enabled LLVM verification | Complete compiler module verifies; runtime module verifies after `default<O2>` |
| Disabled full corpus oracle against base compiler | 4,238 programs identical: emitted IR, diagnostics, and exit status |
| Enabled typed-IR probes | All 54 probes accepted by the internal checker and `llvm-as` |
| Enabled representative native regression cases | 12 cases in both JIT and AOT: 24 passed, 0 failed |
| Enabled GC stress regression cases | Four cases in both JIT and AOT: eight passed, 0 failed |
| Compiler state unit tests | 121 passed |
| Focused source-location / profile parser tests | Four passed, including optimized native DWARF and actual default-ORC registered ELF |
| Hosted versus native quote / exclamation / Latin / CJK source paths | Enabled IR byte-identical |
| Runtime contracts, Python lint and type checks, C warnings, repository hygiene | Passed; final commands and summaries in [validation.txt](validation.txt) |

The enabled compiler IR SHA-256 is
`2e8de6910744659b9e371faf71dd2d279bc2a66a1ecaf7b29b837296612eb8e1`;
the enabled runtime IR SHA-256 is
`ffb27fa91d7af95452d8420a82db153c6892d43f04845562ca37b1533977ab34`.
These hashes are identical across the hosted and two native emitting compilers.
This confirms enabled metadata determinism, alongside the ordinary bootstrap's
compiler and runtime fixed points. All measurements use source and executable
hashes rather than relying on an unverified pre-existing build.

The first corpus comparison used different default home directories and reported
261 differences caused by actual embedded import-error path strings. It was not
a passing run. After verifying that all 87 library Python files were byte-identical
between base and branch, both compilers used the same explicit `PYSTACHY_HOME`;
all 4,238 cases then matched without normalizing program string literals.

The source-location regression checks absent and `0` settings, deterministic
repeated `1` emission, exact equality after stripping only debug attachments and
metadata, imported/nested/specialized functions, generated line-zero scopes, and
real unusual source paths. The native test passes through LLVM optimization,
verifies the resulting ELF DWARF, and checks executable line rows in both the main
and imported file. The JIT observer sees no matching object with locations off;
with locations on it reads the running default ORC JIT's GDB registration list,
saves the real registered ELF, and verifies its Python file table and executable
line rows. A filename string in IR alone would not pass that check.

### Reproduce validation

Use the pinned development environment, build the base compiler independently,
and replace `/path/to/base/pystachy` below. For the common-home oracle, first
verify that the base and branch library sources are identical. The commands
below are the reproducible core of the recorded local runs:

```sh
PYSTACHY_JOBS=2 make PY=python3
python3 -m unittest discover -s tools -p 'test_compiler_state*.py'
python3 -m unittest discover -s tools -p test_source_lines.py
PYSTACHY_HOME="$PWD" tools/irsame.sh /path/to/base/pystachy ./pystachy
PYSTACHY_DEBUG_LINES=1 PYSTACHY_HOME="$PWD" PYSTACHY_IRCHECK=1   tools/check_ir.sh ./pystachy tests/ir/*.py

mkdir -p build/source-checks
export PYSTACHY_DEBUG_LINES=1 PYSTACHY_HOME="$PWD" PYSTACHY_IRCHECK=1
python3 pystachy.py ir pystachy.py -o build/source-checks/compiler-host.ll
build/pystachy1 ir pystachy.py -o build/source-checks/compiler-stage1.ll
build/pystachy2 ir pystachy.py -o build/source-checks/compiler-stage2.ll
cmp build/source-checks/compiler-host.ll build/source-checks/compiler-stage1.ll
cmp build/source-checks/compiler-stage1.ll build/source-checks/compiler-stage2.ll
python3 pystachy.py rt runtime.py -o build/source-checks/runtime-host.ll
build/pystachy1 rt runtime.py -o build/source-checks/runtime-stage1.ll
build/pystachy2 rt runtime.py -o build/source-checks/runtime-stage2.ll
cmp build/source-checks/runtime-host.ll build/source-checks/runtime-stage1.ll
cmp build/source-checks/runtime-stage1.ll build/source-checks/runtime-stage2.ll
opt -passes=verify -disable-output build/source-checks/compiler-host.ll
opt -passes='default<O2>,verify' -disable-output build/source-checks/runtime-host.ll
```

The native subset commands and exact cases are preserved in
[validation.txt](validation.txt). The full corpus check above is the disabled
comparison; it should run with `PYSTACHY_DEBUG_LINES` unset.

### Known metadata-ID limit

This draft uses decimal-prefix placeholder remapping. Sparse existing metadata
IDs can make new debug IDs exceed LLVM's unsigned 32-bit range. A five-line
synthetic module with an existing legal `!500000000` node assembles without debug
metadata. Passing it through enabled `SourceLines.finish` creates
`!5000000016`, which LLVM 18 rejects with
`expected 32-bit integer (too large)`. The measured compiler's maximum ID is
99,758,800, so the recorded workloads are unaffected.

This is a reproduced limitation, not a passing boundary test. Numeric-offset
remapping should replace the current scheme before treating arbitrary metadata-ID
layouts as supported. The minimal reproduction is:

```python
from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.source_lines import SourceLines

diagnostics.FILES.clear()
diagnostics.SRC = "synthetic.py"
lines = ["define i32 @main() {", "entry:", "  ret i32 0", "}",
         "!500000000 = !{i32 0}"]
for enabled in (False, True):
    with open(f"metadata-id-{enabled}.ll", "w") as stream:
        stream.write(SourceLines(enabled).finish(lines))
```

Run `llvm-as metadata-id-False.ll -o /dev/null` (passes) and
`llvm-as metadata-id-True.ll -o /dev/null` (expected failure on this prototype).

## Validation boundaries

This is a draft prototype. Full release verification, all GC configurations,
macOS and MCJIT debug registration, and the complete runtime-cache failure matrix
have not been run. The normal required CI matrix still applies before merging.

The available `perf record` could not record inside this execution environment:
it detected inconsistent process/proc namespaces and produced an empty data
file. No usable perf samples are claimed. Actual source attribution is instead
validated through native DWARF tables, a registered JIT ELF object, and Callgrind
profiles. No system namespace or mount settings were changed.
