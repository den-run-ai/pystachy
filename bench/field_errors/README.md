# Compact inherited-field error paths

This prototype addresses [#786](https://github.com/den-run-ai/pystachy/issues/786).
An inherited method can be specialized once per receiver class while one of its
arguments keeps a base type. Previously, each potentially uninitialized field read
through that base emitted a selection for every descendant class name. One source
read could therefore create a quadratic number of LLVM instructions.

The candidate uses one immutable class-tag-to-string table, created only when an
ordinary polymorphic missing-field check needs it. A failing check loads the
concrete name by the object's existing tag, then uses the existing AttributeError
formatting and raising path. Successful field reads perform the same flag check as
before. The mutable class-default and `__slots__` selection paths retain their
existing semantics; exception objects retain their runtime class-name operation.

This removes the quadratic **error-name IR expansion**. It does not make every
frontend operation linear: `gen_getfield` still scans the class registry to find
direct subclasses on each read, and class-default and `__slots__` paths retain
their separate descendant scans. Timings must distinguish those remaining costs
from LLVM work avoided by the smaller emitted module.

The global table contains all positively tagged classes in a module. If a module
has many unrelated hierarchies but very few missing-field reads, their additional
names and table entries can outweigh a short former select chain. The `sparse-read`
control exposes this density tradeoff. The prototype does not promise that every
program's raw IR, static data or executable becomes smaller.

Positive tags are assigned before function discovery and are never reused.
Excluded imported classes can lose a tag, leaving an unused slot; later template
specializations have tag zero. The table and its string entries are static data.
Like existing string constants, the table survives a `dry()` probe and nested
compilation. It needs no new runtime ABI, allocation, GC root, worker state or
specialization identity.

The class-value/materialization work in #1102, #1104, #1112 and #1114 is a separate
stack. If it merges, tag stability, table completeness and declaration timing need
revalidation against that new class lifecycle. This prototype is based on main
`f7103067`; it does not validate or rebase the concurrent stack.

## Measured results

The [2026-11-07 evidence](results/2026-11-07/) compares the verified main
`f7103067` executable with production changes at `234dd71e` (benchmark harness
`3ac61739`). Both native compilers were freshly bootstrapped with CPython 3.13.16
and LLVM 18.1.3 on this Linux x86-64 host. Each input is frozen and reused by both
compilers, with CPU affinity 0. There are five interleaved fresh-process frontend
samples and three interleaved warm-runtime native builds per revision/input.
Compiler preparation is excluded. Other local heavy work was scheduled separately,
but the machine is shared; these are bounded observations, not universal speedups.

| Derived classes | Source bytes | Raw IR bytes, baseline → candidate | Total `select` instructions | Frontend median, baseline → candidate | Native-build median, baseline → candidate |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 | 474 | 27,738 → 22,898 | 81 → 1 | 3.396 → 3.328 ms | 0.3620 → 0.3448 s |
| 32 | 1,097 | 147,835 → 69,939 | 1,089 → 1 | 8.917 → 6.861 ms | 0.3700 → 0.3553 s |
| 128 | 3,622 | 1,550,165 → 260,367 | 16,641 → 1 | 77.746 → 38.711 ms | 1.7353 → 0.6179 s |

At 128 derived classes, raw IR is 83.2% smaller, the observed frontend median is
50.2% lower, and the native-build median is 64.4% lower (2.81×). The frontend ranges
are 73.732–79.141 ms and 37.142–41.696 ms; the build ranges are 1.6919–1.7912 s and
0.6006–0.6303 s. The native executable shrinks from 331,144 to 85,384 bytes. Median
frontend maximum process RSS is 56,940 → 38,380 KiB; native-build maximum process
RSS is 112,284 → 100,808 KiB. These memory values include the launched process's
inherited resident high-water mark and are not an aggregate process-tree measure.
CPU tracks wall time closely because every measurement is pinned to one CPU.

The controls qualify that result:

| Control | Raw IR bytes, baseline → candidate | Frontend median and range, baseline → candidate | Native-build median and range, baseline → candidate |
| --- | ---: | --- | --- |
| Exact class | 3,902 → 3,902, byte-identical | 2.256 [2.026–2.660] → 2.163 [1.854–2.584] ms | 0.3588 [0.3556–0.3686] → 0.3527 [0.3506–0.3763] s |
| 128-class hierarchy, no field read | 87,054 → 87,054, byte-identical | 34.162 [31.306–46.923] → 46.751 [31.071–47.259] ms | 0.3841 [0.3805–0.4102] → 0.4024 [0.3904–0.4122] s |
| One small hierarchy's read, 128 unrelated class pairs | 16,405 → 52,381 | 8.102 [7.706–10.832] → 8.461 [8.042–11.392] ms | 0.3584 [0.3514–0.3606] → 0.3676 [0.3627–0.3836] s |

The sparse control adds 35,976 raw IR bytes and its three observed candidate builds
take slightly longer; both final executables remain 47,088 bytes. The no-read
control has identical raw IR yet visibly scattered frontend samples and a higher
candidate median. That rules out claiming a general compiler speedup from this
small cohort. The substantive result is removal of the repeated error-name IR
expansion. Remaining hierarchy scans, generated-program throughput, broader
applications and repeated complete self-build performance are not measured here.

All 60 frontend outputs are deterministic within their revision/input; both
unchanged-path controls also match across revisions. All 36 native builds reproduce
CPython stdout with successful exit and empty stderr. Executable bytes repeat
within every revision/input. The compiler sources, executables and inputs are
hashed before/after and unchanged. Raw samples, process accounting, tool hashes,
source inputs and all ranges are in [timings.json](results/2026-11-07/timings.json).

## Correctness evidence

The candidate completed an ordinary two-build self-hosting bootstrap with all six
nonempty compiler/runtime IR witnesses. This is a correctness run; its 238.96 s
wall time is not a paired performance result. The candidate binary SHA256 is
`31c72be5a542f170743bd968b3737219671750aa7e8001c88adfe3d6ccae0141`.

The full strict corpus comparison deliberately exits **1** because this is an
IR-changing optimization. Across 4,239 cases, 4,096 raw IR/diagnostic/status
comparisons are exact and 143 have intentional raw IR differences; diagnostics
and exit status match in all 4,239. All 143 changed modules pass `llvm-as`. The
changes cover 129 executable program fixtures, eight documented deviations,
four benchmark inputs and two IR fixtures.

The separate [diff audit](results/2026-11-07/diff-audit.json) accounts for every
changed module: 4,437 `icmp`/`select` **pairs** (8,874 instructions) become 2,096
table-GEP/load **pairs** (4,192 instructions). There are 1,975 direct-raise blocks
and 121 handled-exception blocks. The audit checks each old selected tag/name
mapping against the table, requires old fallback names to remain in it, and
permits additional string payloads only for table entries. All other IR agrees
after explicit string/boxed-string symbol, SSA/spill and label renumbering.
This post-comparison analysis neither modifies the strict comparator nor proves
runtime correctness by normalization. Its script is [audit_diffs.py](audit_diffs.py).

Native JIT/AOT execution passed 262 comparisons: all 129 affected program fixtures
plus two focused controls. Another 28 JIT/AOT comparisons cover 14 focused fixtures
with collection on every allocation. Two compiler-GC witnesses (the complete
error-name fixture and first table creation during `dry()`) emit exactly the same
IR normally and under allocation-every-time collection; both modules verify.
The local typed-IR suite passed 190 tests, the frame ownership suite passed 18,
mypy checked 49 source files, and changed Python files passed Ruff.

The corpus explicitly shares a baseline runtime/library home after all 105
runtime/library inputs were hashed equal between checkouts, before and after.
A focused `.path` fixture shows why: independent homes embed different source-path
strings, while a shared home produces exact IR. The first attempt omitted that
fixture's import-path setup and stopped before the corpus; its failure report is
retained. The corrected attempt uses `tests/prepare_path.sh` and keeps the strict
comparison unchanged. Complete raw IR is retained in the validation scratch
capture; all 143 full textual diffs are included in the compressed evidence.

Full `make verify`, macOS execution and integration with concurrent PR stacks are
unrun. No runtime C code, ABI or successful-field access policy changes in this
prototype.

## Reproduce the comparison

Build and validate a baseline and candidate native compiler with the same Python,
LLVM, source checkout and flags. Then run the paired harness on an idle machine:

```sh
python3.13 bench/field_errors/run.py \
  --base /absolute/path/to/baseline \
  --head "$PWD" \
  --output build/field-errors-paired \
  --sizes 8 32 128 --samples 5 --builds 3 --cpu 0
```

Choose a CPU allowed by the host's affinity mask. Set `PYSTACHY_LLVM` to the pinned
LLVM tool directory when it is outside the normal search path. `--hosted` runs both
frontends under the invoking CPython instead of the native compilers; it must be
reported as a separate cohort. Omit `--builds` to measure only the frontend.

The harness freezes each generated source once and alternates baseline/candidate
order. It records command, source and executable identities, affinity, compiler and
LLVM versions, every timing, LLVM IR bytes/lines/select count, and native executable
size. Frontend measurements include process startup and IR writing. Compiler
preparation is excluded. Native-build measurements include the frontend, LLVM and
linking with separate prewarmed runtime caches. CPU time and maximum RSS come from
`wait4`; RSS is the maximum individual-process value including waited children,
not aggregate concurrent memory (macOS byte values are converted to KiB). Compiler
commands must succeed with empty stdout
and stderr; failed or interrupted commands retain logs, metrics and an incomplete
report. Timeout cleanup terminates the command's owned process group.

Every native build must reproduce CPython's exact stdout and exit status. The two
negative controls are an exact single class and a large hierarchy without field
reads. Their IR should remain unchanged. The sparse-read control measures one small
hierarchy's read with many unrelated tagged classes. These inputs establish a pathological
scaling improvement, not a speedup for arbitrary compiler workloads. The execution
checks are correctness witnesses; they do not measure generated-program throughput.

The focused regression fixture separately checks initialized and uninitialized
fields, inherited method reads, post-assignment reads, unrelated hierarchies, and
base/intermediate/leaf/sibling/exception class names. Run it in JIT and AOT modes,
then with `PYSTACHY_GC_STRESS_PROGRAM=1`, alongside the existing inheritance,
class-default and slots fixtures. `tools/test_typed_field_errors.py` covers linear
IR growth, deterministic emission, sparse excluded tags, template tag stability,
and a table first created during a dry run.
