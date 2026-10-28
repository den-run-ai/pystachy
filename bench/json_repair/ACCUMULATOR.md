# Bounded string-accumulator probes

The parser keeps completed immutable chunks and a tail of at most 64 code
points. Appending or replacing a trailing escape copies only the tail. Cached
length, final character and regex-class whitespace state serve intermediate
reads; finalization joins once. This bounds the accumulator's repeated-prefix
work, rather than asserting that every parser path is linear.

`tools/test_json_repair_accumulator.py` instruments the actual parser under
CPython and counts lengths of concat/slice results and explicit snapshots.
N/2N/4N, Unicode and regex-tail cases have bounded copying; negative controls
restore an unbounded tail or materialize after every append and fail those
bounds while preserving the complete repaired result. These are **logical
copied-code-point counts**, not native allocation traffic or GC statistics.
The separate differential fixture covers 63/64/65-code-point boundaries,
snapshots, surrogates, structural escapes, regex whitespace, strict/streaming
modes and trailing removal/rstrip. The existing 645-case replay remains required;
its known signed-64-bit mismatch is retained without a checker waiver.

## Paired timings

Build both probes against each integrated parser variant using the same compiler
and the same probe sources. Keep compilation separate from timing. The optional
final arguments are measured batches and discarded warmup batches; defaults
remain one measured batch and no warmup. Both probes check the complete output
before timing; scaling checks it again after every batch, and mixed checks its
checksum after every batch.

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/scaling.py -o /tmp/after-scaling
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/bench.py -o /tmp/after-mixed
/tmp/after-scaling escaped 4000 5 5 6
/tmp/after-mixed 200 5 6
```

Create a config like this, replacing paths and adding CPython/PyPy variants with
explicit `PYTHONPATH` to the corresponding parser. Each `source` is the checkout
actually supplying compiler/library/port sources. `identity` records additional
verified toolchain/version details; the runner hashes each executable and script
in the command as well as all Python files under the consumed source roots,
including untracked/ignored ones.

```json
{
  "variants": [
    {"name": "before-aot", "source": "/path/to/baseline", "commands": {
      "scaling": ["/tmp/before-scaling"], "mixed": ["/tmp/before-mixed"]}},
    {"name": "after-aot", "source": "/path/to/candidate", "commands": {
      "scaling": ["/tmp/after-scaling"], "mixed": ["/tmp/after-mixed"]}}
  ],
  "cases": [
    {"name": "escaped-N", "probe": "scaling", "args": ["escaped", "1000", "5"]},
    {"name": "escaped-2N", "probe": "scaling", "args": ["escaped", "2000", "5"]},
    {"name": "escaped-4N", "probe": "scaling", "args": ["escaped", "4000", "5"]},
    {"name": "unicode", "probe": "scaling", "args": ["escaped-unicode", "1000", "5"]},
    {"name": "short", "probe": "scaling", "args": ["escaped", "4", "500"]},
    {"name": "sparse", "probe": "scaling", "args": ["sparse", "4000", "5"]},
    {"name": "valid", "probe": "scaling", "args": ["valid", "4000", "5"]},
    {"name": "mixed", "probe": "mixed", "args": ["200"]}
  ]
}
```

Choose an allowed CPU from `os.sched_getaffinity(0)`, stop other local builds and
run the campaign. Never edit either source tree or executable during timing.

```sh
python3.13 tools/json_repair_bench.py /tmp/variants.json --cpu 0 \
  --pairs 5 --batches 5 --warmups 6 --output /tmp/accumulator-results.json
```

The runner rotates execution order, checks exact witnesses across all variants,
retains warmup and measured batches, and reports the median of each process's
measured median. NaN/negative timings, missing batches, unsuccessful processes,
changed source/executables and witness mismatches fail. It removes inherited
`PYSTACHY_*`/Python import overrides; provide required JIT LLVM/cache settings in
that variant's `env`. Retained raw samples include command, stdout/stderr,
source/executable hashes, host, core and source status. A shared host remains
noisy despite affinity and interleaving; report overlapping ranges honestly.

RSS comes from `wait4` for the **whole child process**, including startup, JIT,
input creation and validation. It is not retained heap, total allocated bytes or
the repair-loop peak alone. For memory attribution and instruction profiles, run
separate native profiling jobs; do not mix instrumented and ordinary timings.
