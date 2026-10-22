# Numeric identity allocation measurements

These are research evidence for PR #864 / issue #780, not a stable-Any claim or a merge gate by themselves.

The local-copy mitigation recovers the supplied loops' time and memory. The mutable-global loops remain substantially slower and allocate more memory. Those residuals are not accepted by this evidence.

| Exact probe / input | Baseline median | Before local proof | With local proof | Baseline → proof peak RSS |
|---|---:|---:|---:|---:|
| Local integer copies, 2,000,000 iterations | 10.961 ms | 21.812 ms | 11.151 ms | 768 → 768 KiB |
| Local float copies, 1,000,000 iterations | 5.133 ms | 10.127 ms | 5.303 ms | 768 → 768 KiB |
| Mutable integer global, 2,000,000 iterations | 10.791 ms | 25.511 ms | 25.793 ms | 768 → 32,512 KiB |
| Mutable float global, 1,000,000 iterations | 6.530 ms | 13.357 ms | 13.428 ms | 768 → 16,640 KiB |

All four cases use seed 123. The baseline and optimized local-copy heap peaks are 1.0 MiB. The mutable-global heap peaks remain 32.1 MiB for integers and 16.1 MiB for floats. None of these samples triggered a collection.

## Provenance and limits

- `numeric_copy.py` and `numeric_global.py` are byte-identical copies of the original supplied probes, renamed only. Their SHA-256 values are recorded in each JSON file. They are not rewritten versions of the maintained smoke benchmark; their stdout protocol includes checksum, elapsed nanoseconds, and CPU nanoseconds.
- The recorded labels are `baseline` = compiler source `3939db4748270199f5319c4e1dd7f683a1081c0c`, `copies` = `dc753ee8f4eef6de97cfb84552ac87593649079f`, and `proof` = `738fe1a400f7b5c96d7a10f393414dd806dfec29`. The `copies` tree matches the published constant-global mitigation tree `94c2b80c4f9b8e29f997194b381897725ba08045`; the local proof is a subsequent change.
- This is **compiler-only isolation**: all three compilers used the same current runtime/lib checkout, recorded by commit, runtime hashes and library tree. It is not a historical end-to-end comparison of each commit's entire stack. Compiler binaries, generated AOT programs, LLVM tools and source hashes are recorded.
- All programs were compiled by native compilers. The proof compiler passed the three-stage compiler and runtime IR fixed points before these measurements. Every timed checksum matched CPython 3.13.16.
- Each case has one warmup per compiler and ten measured samples with alternating order. The process was pinned to CPU 0 on the recorded AMD EPYC host. Raw per-sample load averages remain in the JSON; this was a shared host, so small timing differences are inconclusive.
- Loop clocks come from inside the program. RSS is the program child's `wait4().ru_maxrss`, in Linux KiB, reported by the included `rss_meter.c`. Process CPU time is also recorded. Separate `PYSTACHY_GC=stats` samples are excluded from timing medians. The original meter C source and binary hashes are in the JSON.
- `copy-results.json` and `global-results.json` preserve every original measured sample, GC sample, checksum, program hash and median. Session paths were removed from metadata and protocol/provenance fields added; measurements were not rerun or selected.
- The mutable-global AOT program hash is identical before and after the local proof, consistent with those functions being outside its scope. A proof requiring scalar parameters/returns and a closed local body does not cover global mutation, callbacks, containers, closures, identity observations, or functions with `print`/`None` returns.

## Reconstruct the measured compiler source

The measured `738fe1a4` commit was local and is not the final published PR head. `mitigation-source.diff` is the exact binary-capable Git diff from published base `db50db1a981a52e376d428ba7a6cd4d60fd89f71` to that local commit. Applying it to a clean checkout of the base reconstructs the measured tree `9f8d71da305b920a1e582277a819a9fcb072f872`:

```sh
git switch --detach db50db1a981a52e376d428ba7a6cd4d60fd89f71
git apply --index /path/to/mitigation-source.diff
git write-tree
# expected: 9f8d71da305b920a1e582277a819a9fcb072f872
```

Rebuild the compiler from that tree with the repository's documented bootstrap before rerunning. Published head `db4b8517` additionally contains merged PR #865 and maintained benchmarks. These raw measurements did **not** use that final head; its paired CI evidence is separate. This patch is a research reconstruction artifact, not a proposed additional change to main.

## Reproduce

Use Linux, a native compiler for each revision, compatible runtime/lib homes, LLVM 18, a C compiler, and CPython 3.13.16. Keep heavy builds and other timing jobs off the selected CPU. Build compilers and verify their source identities before running this script; the optional commit flags label their provenance and do not verify the binary's source by themselves.

For the same compiler-only comparison, pass the same current runtime/lib directory as both homes:

```sh
python3.13 reproduce.py \
  --baseline-compiler /path/to/baseline/pystachy \
  --baseline-home /path/to/shared-runtime-and-lib \
  --baseline-commit 3939db4748270199f5319c4e1dd7f683a1081c0c \
  --head-compiler /path/to/proof/pystachy \
  --head-home /path/to/shared-runtime-and-lib \
  --head-commit 738fe1a400f7b5c96d7a10f393414dd806dfec29 \
  --llvm /path/to/llvm-18/bin \
  --source numeric_copy.py --output reproduced-copy.json --cpu 0
```

Repeat with `--source numeric_global.py --output reproduced-global.json`. The defaults are the recorded ten samples, integer 2,000,000 iterations, float 1,000,000 iterations, and seed 123. Add `--intermediate-compiler`, `--intermediate-home` and `--intermediate-commit` for the three-way comparison; the new runner names these labels `baseline`, `intermediate`, `head` rather than the historical `baseline`, `copies`, `proof`.

The runner compiles the included C RSS helper into a temporary directory, builds each AOT program, checks a CPython oracle, warms each variant, interleaves runs and records raw data plus medians. It clears inherited `PYSTACHY_*`, `PYTHONHOME` and `PYTHONPATH` settings, then sets only the selected homes, LLVM and a private cache. Timing runs use no extra compiler flags; GC reporting is a separate final sample. It preserves other environment settings, including any `LD_LIBRARY_PATH` needed by the chosen LLVM installation.

This packaged runner uses the same measurement protocol and RSS helper as the original run. Packaging validation checked syntax, CLI help, source hashes, unchanged sample data, absence of session paths, patch tree reconstruction, and a tiny fake-compiler end-to-end runner check; no new native performance run was performed.
