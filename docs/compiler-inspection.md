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
worker.

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
| `compiler.stderr`, `compiler.stdout` | The ordinary compiler's captured text streams |

The snapshots are serialized from the live IR in the same compilation. They do
not come from separate compilations with different optimization settings.
Failed compilations may stop before any typed IR or LLVM output is available;
read `report.json` first.

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
- **Passes:** `listget`, `dictfuse`, `unionslots` and `nullcheck` are the four
  whole-function passes. Other [optimization settings](typed-ir.md#71-language-level-optimizations)
  control frontend or lowering choices and have no invented pass snapshot here.
  Exception lowering has its own `exceptions` record and diff when applicable.
- **Phases:** the compiler still combines name resolution, typing, folding and
  specialization while building IR. The report does not imply a new independent
  type-checking stage.
- **Retries:** inference may restart compilation. An incomplete attempt is not
  a successful compilation; interpret stages together with the final outcome.

Diagnostic codes are deliberately coarse in this prototype:

| Code | Meaning |
|---|---|
| `PYS0001` | Ordinary terminal compiler rejection |
| `PYS9000` | An explicitly identified internal compiler error |
| `PYS9001` | Unexpected worker exception |
| `PYS9002` | Worker timeout |
| `PYS9003` | Source changed during compilation; provenance is inconsistent |

An ordinary rejection is not automatically a compiler defect. The existing text
message and specialization notes remain the explanation; the code provides a
stable category, not one unique identifier for every language restriction. The
tool stops at the compiler's first terminal diagnostic and adds no error recovery.
An unavailable input also retains `PYS0001`, with phase `input`, but has outcome
`error` rather than a language rejection.

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

The [prototype evaluation](reports/compiler-inspection-prototype.md) records the
bounded tasks and findings. More precise source spans, explicit rejection-reason
events and a native inspection interface remain possible extensions.
