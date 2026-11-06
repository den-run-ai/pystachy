# GC application workloads

These workloads measure application execution. Build binaries before the measurement
window. Keep compilation time out of runtime comparisons. No driver explicitly calls
`gc.collect()` or makes a claim about the input representing a production distribution.

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
[port README](../../ports/json_repair/README.md) and its upstream notices). It repairs
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
