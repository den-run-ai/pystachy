# GC application workloads

These workloads measure application execution. Build binaries before the measurement
window. Keep compilation time out of runtime comparisons. No driver explicitly calls
`gc.collect()` or makes a claim about the input representing a production distribution.

The [2026-11-06 evaluation](results/2026-11-06.md) compares compiler-proven atomic
allocations, chunk marking, native pacing, and an optional BDWGC backend. It preserves
all primary results, unchanged-binary controls, follow-ups, unsuccessful preparation
and exact input/source identities. New union allocation stays opt-in; the optional
backend is a restricted research adapter.

Use the unchanged adaptations in `bench/pyperformance/` for float, chaos, raytrace,
JSON loads/dumps, Richards and n-body. Their provenance and adaptation limits are in
[the pyperformance README](../pyperformance/README.md). N-body is a useful compute
control; Richards mostly mutates a small linked task graph. Small instances of the
other workloads may spend very little time collecting, which limits possible gains.

## Application pipelines

`json_retained.py` ingests batches of nested event records, computes a rollup and
retains a configurable recent-batch window. It imports the existing recursive consumer
from `bench/json_records.py`, including its checks of rare amount types. The fixture
comes unchanged from `tools/bench_json.py`: the `changing` profile changes from a
mostly-integer distribution to mixed alternatives halfway through a document. Each
round ingests the same deterministic page, as in a repeated benchmark. The final
retained pages are traversed again and the final page is serialized in full to an
output file. Compare that file's exact bytes with CPython as well as stdout. The cache
creates application-level survival without artificial reachability or forced collection.

`repair_traces.py` uses the existing `ports/json_repair` adaptation of json_repair
0.64.1, upstream commit `ace9b23cb7fc6757775d5fafbfaaa9a88363a573` (MIT; see the
[port notes](../../ports/json_repair/PORT.md) and its upstream notices). It repairs
each trace to objects and serializes normalized JSON. It consumes ten mixed trace
features from `bench/json_repair/bench.py`: valid JSON, trailing commas, bare keys,
single quotes, fenced text, missing commas, escaped/raw code, nested JSON text and
partial input. `prepare.py` extracts the existing literal fixture with `ast.literal_eval`;
it does not execute the old timed benchmark or copy a second fixture into this directory.
These are constructed examples, not captured production traces. The complete final
batch and consumed length checksum provide deterministic stdout for the oracle.

The existing [mailmerge application](../../examples/mailmerge/mailmerge.py) is another
candidate. Run its standard `string.Template.substitute` mode over the generated
`customers.tsv` and `examples/mailmerge/notice.txt`; compare the complete mailbox output.
`prepare.py` reuses the application's existing deterministic record generator.

## Preparation and correctness

Run these commands at the repository root with the pinned CPython 3.13. Preparation
writes input hashes and source hashes to `manifest.json`. Create a small corpus for
quick oracle/build checks, and a larger corpus for runtime calibration:

```sh
python3.13 bench/gc_application/prepare.py --out /tmp/gc-app-smoke --records 64 --customers 20
python3.13 bench/gc_application/prepare.py --out /tmp/gc-app-full --records 100000 --customers 100000
PYTHONPATH=bench python3.13 bench/gc_application/json_retained.py /tmp/gc-app-smoke/records.json 5 3 /tmp/gc-app-smoke/expected.json
PYTHONPATH=ports python3.13 bench/gc_application/repair_traces.py /tmp/gc-app-smoke/repair-inputs.jsonl 2
python3.13 examples/mailmerge/mailmerge.py examples/mailmerge/notice.txt /tmp/gc-app-smoke/customers.tsv
```

Build `json_retained.py` with `PYSTACHY_PATH=bench` and `repair_traces.py` with
`PYSTACHY_PATH=ports`. Run the same source, inputs and arguments with CPython and every
native variant, including the full calibrated runtime inputs. Native and CPython may
use different stdlib implementations; CPython establishes behavior, while the GC
comparison is between native variants. The repair port is shared by CPython and native.

Use `bench/gc_locality/run.py` with an artifact argument `{output}` for JSON retained.
Include each source, imported consumer/library sources, input files and preparation
manifest in the evidence hashes. Keep output validation and unsuccessful runs in the
record. Do not infer equivalence from an exit code or reduced checksum alone.

## Calibration and interpretation

These are starting points, not fixed claims about runtime. Increase outer repetitions
until native end-to-end runs last at least a second. Increase live input size separately
when studying survival: repetitions and live memory answer different questions.

| Case | Quick correctness arguments | Runtime starting point |
| --- | --- | --- |
| pyperformance float | `1 1000` | `40 1000000` |
| pyperformance chaos | `1 200` | `500 5000` |
| pyperformance raytrace | `1 20 20` | `140 100 100` |
| pyperformance json_loads | `1` | `6000` |
| pyperformance json_dumps | `1 smoke` | `240` |
| pyperformance Richards | `1` | `2400` |
| pyperformance n-body | `1 100` | `250 20000` |
| JSON retained | small input, `5 3 OUTPUT` | 100k-record input, `20 4 OUTPUT` |
| JSON repair pipeline | input, `2` | input, `20000` |
| mailmerge, optional | template, 20 customers | template, 100k customers |

Keep the GC minimum/pacing policy equal across a comparison, and report observed peak
RSS rather than calling that minimum a heap cap. Use an explicit identical address-space
limit if testing a hard process memory budget. Run a wider retention window separately
from the primary case. A useful sensitivity check is 20k versus 100k records and window
1 versus 4, keeping the same configuration for every variant within each comparison.
Use randomized/rotating paired order, a warmup, independent process repetitions, and a
byte-identical baseline control to establish local measurement variability. Use GC
stats for headline timing and separate detailed profiling to explain time, allocations
and scanned words. Report runtime, collection time and memory together; lower GC time
alone does not establish an application win.

## Build and measure a recorded matrix

`build.py` consumes a JSON specification, builds AOT executables and compares each
configuration with pinned CPython before it writes measurement configurations. Each
case runs a small input, that input with collection at every allocation, and its full
timing input. It compares complete stdout and any `{output}` artifact. Compiler,
runtime, import and explicit dependency files are hashed and held unchanged throughout
preparation; inherited `PYSTACHY_*` and `GC_*` settings are cleared.

The recorded [native specification](results/2026-11-06/preparation/native-spec.json)
and [optional specification](results/2026-11-06/preparation/optional-spec.json) contain
the actual cases, arguments, variants and environments. Their absolute paths identify
the original checkouts: replace them with separate local checkouts/compilers for the
recorded source revisions. Preserve the input sizes, settings and variant definitions
when reproducing that comparison. The published/local source mapping is in the
[source identity record](results/2026-11-06/code-publication.json).

```sh
# Exact input sizes used by the recorded evaluation.
python3.13 bench/gc_application/prepare.py --out /tmp/gc-app-smoke --records 16 --customers 20
python3.13 bench/gc_application/prepare.py --out /tmp/gc-app-full --records 20000 --customers 10000

# Use an adapted spec and a fresh empty output directory.
python3.13 -I bench/gc_application/build.py --spec /tmp/native-spec.json --out /tmp/native-build
python3.13 -I bench/gc_locality/run.py --config /tmp/native-build/float.json \
  --cpu 3 --rounds 6 --warmups 1 --json /tmp/float-results.json
python3.13 -I bench/gc_application/summarize.py /tmp/float-results.json
```

The specified CPU must be available to the process. `build_from` aliases an earlier
variant's exact executable; use it for identical-code controls and runtime-only policy
changes. `build_env` contains compilation choices such as `PYSTACHY_OPT=+atomicunion`;
`run_env` contains collection settings. `build_inputs` pins headers, archives or other
dependencies outside the normal runtime/import trees. The controller verifies the
executable hash again before timing and rejects output mismatches.

For BDWGC, follow the [optional adapter contract and dependency instructions](../gc_locality/BDWGC.md).
Take `PYSTACHY_CFLAGS` from the generated overlay manifest: its linker forwarding is
required by the normal AOT driver. Supply native pacing only to native variants.
The optional matrix embeds the exact JSON input with:

```sh
python3.13 bench/gc_application/embed_fixture.py \
  --small /tmp/gc-app-smoke/records.json --full /tmp/gc-app-full/records.json \
  --out-dir /tmp/gc-app-embedded
```

Set the in-memory case's import paths to `bench` and that generated directory. Its
`smoke|full ROUNDS WINDOW` interface and complete stdout differ from the file-backed
wrapper; label it separately and apply the same wrapper to every collector. The recorded
primary runs use 40 iterations/window 4; the longer native union follow-up uses 80.

Raw follow-up configurations and historical orchestration snapshots are preserved in
the dated result directory. `summarize.py --pair CANDIDATE/CONTROL` selects explicit
contrasts for pacing or optional backends. It rejects incomplete/mismatching samples,
reports paired ratios and observed ranges, identifies exact-binary controls, and keeps
BDWGC stopped-world counters separate from native collection elapsed time.
