# Historical measurement inputs

These are evidence snapshots for measurements made on **2026-11-07 UTC**, using
the byte-BPE port at `3d0f56d82e3f7e3e0799d37e014f73391913f1ca` and unchanged
compiler/runtime sources from `f7103067545b43cdcd8ce20dc66b1571425b3a8d`.
Recorded source snapshots retain their original bytes, including absolute paths
from that environment.
The `.py.txt` suffix marks archived source for review; these are not portable
commands for a new checkout. Use the [portable comparison runner](../../../compare/)
for new measurements, and [the evidence verifier](../verify.py) to audit this data.

The original pyperformance/tiktoken tokenizer, Frankenstein corpus, port changes,
licenses and attribution are already recorded in the parent showcase's
[upstream provenance](../../../upstream/provenance.json),
[upstream source](../../../upstream/bpe_tokeniser.py), and repository notices.
The comparator source patches here apply to that pinned upstream source;
`cython_scalar.diff` is regenerated with zero context to avoid trailing whitespace
on blank context lines, with its original diff hash retained in the manifest;
`scalar_tuple.diff` applies to the pinned Pystachy port. No algorithmic change is
included in the Cython or mypyc variants.

| Snapshot | Purpose |
|---|---|
| `stages_warm.py.txt` | Identical timed driver for the main and secondary series: two training warmups, 20 encoding warmups, 100 decoding warmups. |
| `run_comparison.py.txt` | Exact main-series controller before its timing parser was hardened. |
| `run_secondary.py.txt` | Revised controller used for the separate JIT/inlining/GC series; records mode environment overrides and rejects duplicate timing keys. |
| `prepare_native.py.txt` | Historical environment sanitation, native preparation and correctness commands. |
| `correctness.py.txt` | Native-compatible fixture accepting the known CPython/PyPy empty-`max` wording difference; the error type and behavior still match. |
| `comparator_run.py.txt` | Imports and asserts a native `.so` module before entering the common driver. |
| `comparator_check.py.txt` | Comparator validation against complete fixture and corpus state. Its `fixture.py` is byte-identical to the pinned `tests/programs/apps/byte_bpe.py`; its `corpus.txt` is the pinned Frankenstein corpus. |
| `comparator-build-inputs.json` | Exact `setup.py`, unused `pyperf` import helper and mypyc type stub, with hashes. |
| `cython_scalar.diff`, `mypyc_original.diff` | Minimal adaptations; unchanged Cython and the Cython port control use the already committed sources directly. |
| `scalar_tuple.diff` | One-line diagnostic removing comparison tuples for this exact builtin-bytes kernel. Its timing effect was inconclusive. |
| `encoding_phases.py.txt`, `run_encoding_phases.py.txt` | Separate, nonadditive phase diagnostic with a six-line complete-state witness. |
| `run_full_warm.py.txt` | Separate full-only series: 200 warmups and 200 timed encodes using the same decomposition binary. |
| `count_bpe_operations.py.txt` | Source-operation counters. Instrumented wall times are not performance evidence. |
| `probe_language_gaps.py.txt` | Independent adaptation reversions and small library probes. Successful results establish IR emission only. |
| `native-sites.txt` | Compact excerpts from optimized native disassembly, with binary identities; trailing whitespace stripped. |

The original main-series parser allowed a repeated timing key to overwrite a
previous one. Publication-time verification rechecks every raw sample using a
strict parser: all 45 have exactly five distinct, finite, positive timing rows
and the recorded per-operation divisors. No timing sample was changed or rerun
to obtain that result. The separate nine-sample secondary series is also audited.

The full four-line pristine oracle is stored once. Five identical comparator
JSON states are represented by their verified hashes in
[`comparator-correctness.json`](../comparator-correctness.json); the verifier
reconstructs their exact original JSON bytes from the retained oracle. The
encoding diagnostics' additional word and byte-word witnesses are reconstructed
from the same corpus and pinned regex, then checked against their recorded hashes.

`manifest.json` in the parent directory distinguishes byte-exact recorded files
from publication-time derived artifacts. It identifies omitted native binaries
and full disassemblies by hash; neither regenerated timing results nor bitwise
reproducible builds are implied. Main, secondary, phase and longer-warmup series
remain separate, and no samples are excluded from their summaries.
