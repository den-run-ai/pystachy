# Inspecting a compilation

`tools/inspect_compiler.py` is an experimental, CPython-hosted inspection tool for
Pystachy's existing compiler. It records typed IR before and after the function
passes, pass changes, final LLVM IR and structured diagnostics in one directory.
Use it to inspect an optimization or locate a rejected specialization without
adding logging to the compiler.

The tool runs the real `pystachy ir` path in a fresh worker process, with
`PYSTACHY_IRCHECK=1`. It does not execute the input program, run LLVM's optimization
pipeline, build an executable or prove JIT/AOT correctness. `pystachy check`
remains parse-only; it is not the inspection tool's compilation oracle.

## Quick start

Run from the checkout root, using a **new output directory** each time:

```sh
python3 tools/inspect_compiler.py tools/inspection_examples/score_samples.py \
  --output /tmp/pystachy-inspect-score --function score_samples
```

`--function SUBSTRING` selects functions whose symbols or display names contain
the substring for the inspection output. Compilation still processes the whole
input. Omit it to inspect every generated function. `--timeout SECONDS` bounds the
worker. Inputs must be regular source files (symlinks to regular files are
supported); pipes and devices are operational input errors.

The requested output directory must not already exist. The tool stages artifacts
in a hidden temporary directory and creates the requested directory and any
missing parent directories only after compilation. Selecting a report path next
to the source therefore does not introduce a new importable directory while the
compiler is resolving imports.

| File | Contents |
|---|---|
| `report.json` | Outcome, provenance, diagnostics, stage information and pass records |
| `typed-before.json` | Selected typed functions before the function optimization passes |
| `typed-after.json` | Selected functions after optimization and exception lowering, just before LLVM serialization |
| `llvm.ll` | Final LLVM IR, when compilation succeeds |
| `passes/NNNN-name.diff` | A readable before/after diff for a pass that changed a selected function |
| `program-passes/NNNN-name.json` | Whole-program pass snapshots keyed by LLVM symbol (the native recursion depth policy) |
| `program-passes/NNNN-name.diff` | Typed instruction changes across the union of selected before/after functions |
| `compiler.stderr`, `compiler.stdout` | The ordinary compiler's captured text streams |

The snapshots are serialized from the live IR in the same compilation. They do
not come from separate compilations with different optimization settings.
Failed compilations may stop before any typed IR or LLVM output is available;
read `report.json` first.

`--typed-after-only` records only `typed-after.json`, `llvm.ll` and the report:
no `typed-before.json`, pass records or diffs, with `"captures": "typed-after"`
in the report's settings. The snapshot is the same; the compilation is about
three times faster for large programs.

The optional [Lean payload-guard prototype](../tools/lean_boundary/README.md)
consumes a completed `typed-after.json` and checks one selected function, or every
function that reads a dynamic payload. Its theorem establishes guard safety in a small normalized model;
the inspection export, normalization and native execution remain separate trust
obligations. Unsupported instructions are reported rather than skipped.
A `check` op's error block is not among its targets, so each function snapshot
also maps the op's key (its descriptor, else its text) to that block's label in
`check_targets`. `typed-after.json` also lists, in `dynamic_types`, every
DynType descriptor the program emits for its classes, functions and generators.
A dynamic box's tag is the address of one of these or of a runtime.c builtin.
Each entry records the descriptor's kind, class number (the word class
dispatchers switch on), base, secondary role, flags and the static type of the
payload its boxes hold.

## Three questions to try

### Did the list-loop proof remove a checked read?

The `score_samples` example sums positive samples. Its sequence loop checks the
index before reading the element. Inspect its `listget` pass record and diff:
the runtime `list.get` operation should become an inline `list.load`. The
independent CPython result is `3.5`.

```sh
python3 tools/inspection_examples/score_samples.py
```

### Did a mutation prevent unsafe dictionary-lookup reuse?

```sh
python3 tools/inspect_compiler.py tools/inspection_examples/record_lookup.py \
  --output /tmp/pystachy-inspect-record --function lookup
python3 tools/inspection_examples/record_lookup.py
```

`lookup` tests membership and then reads the same key. `dictfuse` can reuse that
lookup. `lookup_after_update` calls a helper that deletes the key between the
test and the read; its checked lookup must remain. CPython prints `7` and `-1`.
Compare the pass records and the retained `call`/`dict.getitem` operations.

A pass record's `rule` explains the pass's general safety contract. A zero
`reported_rewrites` count is not, by itself, an exact explanation of a missed
optimization. The retained operations, effect summaries and source provide the
evidence for this example's mutation barrier.

`report.json` also includes the compiler's four registered `pass_contracts`,
with their required and preserved facts, local analyses, invalidations and
checks to rerun after a rewrite.

### Which imported specialization rejected the program?

```sh
python3 tools/inspect_compiler.py tools/inspection_examples/specialization_error.py \
  --output /tmp/pystachy-inspect-error
python3 tools/inspect_compiler.py tools/inspection_examples/specialization_fixed.py \
  --output /tmp/pystachy-inspect-fixed
python3 tools/inspection_examples/specialization_fixed.py
```

The first command intentionally fails: the imported generic helper tries to add
an integer to a string. Its diagnostic names the helper's source location and
retains the specialization notes leading to that error. The repaired caller
passes an integer; CPython prints `8`.

For a class, inspect `attempts[].class_specializations`. Each class identity
groups its completed compiler request keys, type-variable bindings and ordered
field representations. For example, in
[`generic_distinct_layouts.py`](../tests/programs/generics/generic_distinct_layouts.py),
the recursive annotation and list constructor select the same `Collection`.
The tuple constructor selects a different class with the same binding for `T`.
These are cache keys, so repeated identical calls appear once. Identities are
local to each attempt. On failure, the map contains only completed selections
and the diagnostic context gives the rejected request when available.

## Reading the report accurately

- **Locations:** diagnostics retain the compiler's file and line directly.
  Function snapshots link to the function's definition. Instructions do not
  currently retain source spans; no column or exact instruction location is
  inferred from LLVM text.
- **Types:** signatures and operands preserve Pystachy's native type spellings,
  which can expose distinctions such as `int`, `int+`, `dyn` and closed unions.
- **Effects:** function summaries come from the compiler's last analysis and may
  remain conservative after rewrites. They are not a new post-optimization proof
  or ownership analysis.
- **Passes:** `passes` records the function passes `charslots`, `listget`, `listguard`,
  `dictfuse`, `unionslots`, `nullcheck` and exception lowering. `program_passes` separately
  observes the whole-program `recursionscope` call, the native recursion depth
  policy, which runs whatever `PYSTACHY_OPT` turns off. Other
  [optimization settings](typed-ir.md#71-language-level-optimizations)
  control frontend or lowering choices and have no invented pass snapshot here.
- **Phases:** the compiler still combines name resolution, typing, folding and
  specialization while building IR. The report does not imply a new independent
  type-checking stage.
- **Retries:** inference may restart compilation. An incomplete attempt is not
  a successful compilation; interpret stages together with the final outcome.

### Whole-program recursion observations

For example, inspect which functions count toward the recursion limit:

```sh
python3 tools/inspect_compiler.py tests/programs/language/recursion_guard.py \
  --output /tmp/pystachy-inspect-recursion --function direct
```

The `program_passes` record comes from the real `recursionscope` call. Its snapshot
artifact contains before/after `functions` maps keyed by LLVM symbol, explicit function
order, and immutable full `selected_snapshots`. The record separates added, removed and
changed symbols; changes include metadata as well as instructions. A snapshot hash
detects same-count changes outside the function filter without retaining every
unselected function's complete IR. Before the pass, every source function has only
its entry-depth snapshot (`recursion.depth`); after it, a counted function's entry is
`recursion.enter` and each return restores the caller's depth, and an uncounted one
keeps the snapshot only when a handler restores it. A function of closed recursion
(`recursion.closed` in the after map) keeps its entry without restorations: lowering
passes its depth as an argument.

Global totals remain separate from selected-function totals. Both count block
operations and frame slots separately, and report the five typed runtime operations
`recursion.enter`, `resume` (a generator resume's entry), `leave`, `depth` and `restore`. Function summaries also retain
`counted`, `rdepth`, `landed`, `gdepth`, generator and coroutine metadata. These are
observed state, not an independently rerun proof or an LLVM instruction count.

The raw integer the pass returns, `reported_transformations`, is the number of
counted source functions. It is not an instruction count. A zero result does not
identify a refusal reason; the observer does not rerun the call-graph analysis to
invent explanations. LLVM helper attributes remain available in `llvm.ll`.

### Dynamic boundaries and numeric identity

Each `attempts[].dynamic_boundary` observes the actual `identity_modules` policy
selection. Its `modules` records module names, paths and dependency edges;
dynamic-Any and promoting-int opt-ins; requested and active identity-inert hints;
requested and active [numeric-value modules](dynamic-any.md#numeric-value-modules);
and whether each module's code tracks numeric identity. `tracked_modules` lists
that selected scope. `hints_enabled`, `numeric_values_enabled` and
`full_graph_fallback` retain the driver's actual retry settings. The last means
that a previous crossing requested full tracking; it is distinct from a
dependency closure that already includes every module. `fallback_reason` is the
compiler's exact crossing event for that attempt, or `null` if there was none.
No event is inferred from the final module graph.

For example, an ordinary typed `tomllib.loads` consumer with a typed `parse_float`
callback can first exclude its own module, then retry after `number as an Any
value` with full-graph tracking, which still leaves out numeric-value modules.
Removing an opt-in does not establish that its numeric identity costs
disappeared. Inspect every attempt, not just the final one, to distinguish a
discarded hint from full tracking.

`footprints.before` and `footprints.after` summarize all generated typed-IR
functions at the same boundaries as the selected before/after snapshots. The
function filter does not narrow these maps or totals. Per-function entries give
the owning identity-policy module, tracking choice, counts of `dyn.*` operations
and `rt` calls named `dyn.*`, and named local numeric companion (`.box`) and
generation (`.boxgen`) slots. Shared compiler helpers can have module `?`.

These counts are static observations, not allocation frequency, memory use or
runtime cost. They exclude global/field companions, unnamed identity temporaries,
other runtime operations and helpers emitted only during LLVM lowering. They do
not prove that the selected scope is minimal or justify removing identity checks.
Before a stage is reached its footprint is `unavailable`, with `totals: null`;
retained stages of failed attempts are `partial`. A source-provenance failure
marks every attempt inconsistent and downgrades completed footprints to partial.

Diagnostic codes are deliberately coarse in this prototype:

| Code | Meaning |
|---|---|
| `PYS0001` | Ordinary terminal compiler rejection |
| `PYS9000` | An explicitly identified internal compiler error |
| `PYS9001` | Inspection-tool input or worker failure |
| `PYS9002` | Worker timeout |
| `PYS9003` | Source changed during compilation; provenance is inconsistent |

An ordinary rejection is not automatically a compiler defect. The existing text
message and specialization notes remain the explanation; the code provides a
stable category, not one unique identifier for every language restriction. The
tool stops at the compiler's first terminal diagnostic and adds no error recovery.
An unavailable input also retains `PYS0001`, with phase `input`, but has outcome
`error` rather than a language rejection. An existing non-regular input produces
`PYS9001` in phase `input` without invoking the compiler.

### Exit status

| Exit status | Outcome | Meaning |
|---|---|---|
| `0` | `ok` | Hosted compilation and typed-IR verification completed; the program was not executed |
| `1` | `rejected` | A terminal compiler diagnostic rejected the source |
| `2` | `error` | Missing input, invalid invocation, output failure, internal compiler/worker failure or changed source provenance |
| `124` | `timeout` | The compilation worker exceeded its deadline |

Invalid invocations and output-publication failures may leave no report. For a
published report, inspect its outcome before consuming artifacts. A provenance
failure can retain LLVM or typed snapshots for debugging, but their stages are
marked `partial` and `verification.completed` is false.

## Boundaries and follow-up

The fresh worker is the isolation boundary. Compiler process-global state is
still unsuitable for concurrent independent compilations in one interpreter
([testing](testing.md)); this tool does not resolve that ownership work. It is a
developer tool in the source checkout, not a new native CLI command or MCP server.

Snapshots and diffs add compilation time and disk output. Compare ordinary and
inspected LLVM bytes before interpreting a pass diff as a compiler change, and
measure runtime with the normal JIT/AOT tools. Fewer operations or a successful
inspection does not establish a speedup.

The report records the tool hash, compiler revision and source hashes, relevant
environment settings and each source read at the loader's parser boundary:

| Field | Meaning |
|---|---|
| `input.modules[].sha256` | Hash of raw file bytes observed when the parser receives the source |
| `input.modules[].source_sha256` | Hash of the actual source text passed to that parser, encoded with the compiler's `RAW` encoding |
| `input.modules[].changed_since_read` | A mismatch between the observed file and consumed text, or a later change to the observed file |
| `input.source_sha256` | The consumed-source hash for the main input |
| `input.changed_during_compilation` | At least one recorded source read was inconsistent with the observed file |

In the hosted compiler, `RAW` is Latin-1 and text reads normalize universal
newlines. Raw-file and consumed-source hashes may therefore differ for CRLF or
CR input without implying a change. The report labels that encoding convention.
Retries can produce multiple read records for the same path.

A detected change produces `PYS9003` in phase `provenance`, outcome `error` and
exit status `2`. These hashes identify consumed text but do not archive it or
freeze the compiler tree. Keep sources and compiler files unchanged during
reproduction. The JSON schema and typed instruction format are experimental and
identify their schema version.

The [31 October 2026 evaluation](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/docs/reports/compiler-inspection-prototype.md)
records the bounded tasks and findings. More precise source spans, explicit
rejection-reason events and a native inspection interface remain possible extensions.
