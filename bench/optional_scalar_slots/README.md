# Private optional scalar slots

This study extends `unionslots` to private optional numeric locals whose producers
are scalar boxes, `None`, or their phis and whose uses only test presence or read
the payload. Presence and payload use separate integer slots. Initialization flags
and numeric identity companions remain independent. Unknown producers, escaping
values, optional copies, non-null pointer comparisons and generator frames retain
their existing representation. `dict.getbox` is unchanged.

The compiler change is 40 inserted and 15 deleted lines across `optimizations.py`
and its `Gen` forwarding method. It adds no runtime ABI or LLVM operations.

## Recorded result

[Raw samples and source/binary hashes](results/aot-linux-x86_64-2026-11-07.json)
compare exact main `f7103067545b43cdcd8ce20dc66b1571425b3a8d` with candidate
`f3410cf358210ab4c68f863c7666214b4797b583`, both with default optimizations.
The candidate includes compiler core `defcaaee`; `f3410cf3` adds the unbound-local
regression only. Subsequent evidence files do not change the measured compiler.

Linux x86-64, AMD EPYC 9V74, LLVM 18.1.3, CPython 3.13.16. Each workload used one
warmup and seven alternating pairs, pinned to CPU 0. Other team builds/tests were
paused during timing. Each subprocess has a 180-second timeout. Compilation was
completed first; its timings are provenance only because main's compiler was
CPython-hosted and the candidate was self-hosted.

| AOT workload | Main median [min, max] | Candidate median [min, max] | Main / candidate median |
|---|---:|---:|---:|
| Direct minimum, process ms | 36.090 [34.781, 38.551] | 10.652 [9.370, 11.294] | 3.388x |
| Rank lookup minimum, process ms | 115.397 [102.808, 177.920] | 82.562 [78.618, 139.606] | 1.398x |
| BPE encode, ms per corpus | 11.925 [10.905, 13.067] | 12.038 [10.290, 13.157] | 0.991x |
| BPE driver, process seconds | 2.181 [2.014, 2.456] | 2.165 [1.933, 2.280] | 1.007x |

The microbenchmarks scan 320 descending values/keys for 30,000 rounds (9.6 million
visits). They deliberately update minima frequently. Direct minimum improved in
all seven pairs; rank lookup improved in six, with overlapping overall ranges.
These are representation microbenchmarks.

**The full BPE consumer showed no demonstrated speedup.** The driver trains a
1,024-token vocabulary on the pinned Frankenstein introduction, then performs
100 encodes and 100 decodes. Its encode ranges overlap substantially and pair
directions reverse. Training/decode timing variations are retained in the raw
file and are not attributed to this change. No allocation-byte or dynamic
allocation counts, JIT performance, or general tokenizer speedup are established.

Every warmup and timed native run matched CPython's complete output. BPE first
compares the adapted source with unchanged upstream kernels under CPython, then
checks all 130,147 output bytes (vocabulary, tokens and decoded data) for each
native run. The controller extracts the exact upstream kernel text after checking
its hash; it does not time pyperf's runner or copy a compiler result as an oracle.

## IR and executable size

The [BPE structural control](results/bpe-ir-2026-11-07.json) compares the candidate
with `-unionslots` against default optimization. `bpe_encode` loses its two scalar
boxing call sites and the `min_idx`/`min_rank` optional slots; its `dict.getbox`
call and `rank` optional slot remain. Typed operations increase from 184 to 189,
and whole-driver LLVM text grows from 1,869,124 to 1,869,606 bytes (+482, 0.026%).
These are static IR counts, not surviving allocation counts. The AOT performance
comparison uses exact main; its micro executable is 90,616 versus 90,584 bytes,
and both BPE executables are 424,648 bytes.

## Reproduce

Use this branch as `OPTIONAL_CANDIDATE`, a clean exact-main worktree as
`OPTIONAL_BASE`, and a worktree at
`3d0f56d82e3f7e3e0799d37e014f73391913f1ca` as `OPTIONAL_BPE` (the byte-BPE
showcase, Refs #1107 and #1126). `OPTIONAL_LLVM` names the complete LLVM bin
directory; `OPTIONAL_PY` names the pinned interpreter. Build a fresh candidate
with `make PY="$OPTIONAL_PY" PYSTACHY_LLVM="$OPTIONAL_LLVM"` in its checkout.

```sh
OPTIONAL_WORK=$(mktemp -d)
for stage in prepare measure; do
  "$OPTIONAL_PY" "$OPTIONAL_CANDIDATE/bench/optional_scalar_slots/compare.py" "$stage" \
    --base "$OPTIONAL_BASE" --changed "$OPTIONAL_CANDIDATE" \
    --bpe "$OPTIONAL_BPE" --workdir "$OPTIONAL_WORK" --llvm "$OPTIONAL_LLVM"
done
```

The controller checks main's revision and all four BPE input hashes, copies inputs
into private directories, keeps original/adapted imports separate, clears inherited
`PYSTACHY_*` settings, uses private runtime caches, and checks every prepared binary's
hash before timing. It writes `builds.json`, `sources.json` and `results.json`.

## Validation and limits

[Validation records](results/validation-2026-11-07.json) retain commands and source
identities. Final native bootstrap reproduced compiler IR (832,800 lines) and
runtime IR (18,805 lines) exactly across all three stages. Native checks passed
114/114 JIT+AOT checks, 12/12 program-only GC-stress checks, 12/12 disabled-`unionslots`
controls and 5/5 typed IR plus `llvm-as` programs. Coverage includes zero/miss,
`False`, negative zero, NaN, infinities, escape/copy/identity boundaries, exceptions,
and both annotated/inferred conditionally initialized locals. Seven focused hosted
tests pass; the compiler core also passed `make check-fast`, hosted self-compilation
and 58 hosted IR checks before the unbound-only test addition.

Full `make verify` and an exact-main full-corpus `irsame` were not run for this
branch. This remains research evidence for draft review; broader required CI is
still needed before merge.
