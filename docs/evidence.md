# Compatibility and performance evidence

Claims about compatibility, ports and performance need evidence a reader can check. These
rules apply to pull requests, issues, documentation and reports, whether a person or a
coding agent writes them; the [writing guide](writing.md) covers how to word them.

- Separate **import compilation**, **working APIs**, **adapted ports**, **upstream
  tests** and **embedded CPython**. Throwing stubs are probes; native ndarray/BLAS is not
  NumPy support. Name a prototype's verified consumer, or say none is verified.
- New inference/dispatch machinery needs a representative workload, not one library's
  special case. Prefer explicit annotations, report net compiler/runtime lines and
  keep port-discovered fixes general. Record failed/parked approaches with measurements
  ([#238](https://github.com/den-run-ai/pystachy/pull/238),
  [#264](https://github.com/den-run-ai/pystachy/issues/264)).
- Reuse `tools/import_sweep.py` and port/audit tooling. Pin compiler/source/input versions
  and overlay exclusions; denominator changes need not mean lost coverage. Retain
  repros/first errors as dated, commit-pinned evidence in PRs or research branches.
- Account for every consumed input before generating outputs, including untracked/ignored
  importable files or their hashes/deviations. `git status --untracked-files=no` cannot
  certify clean evidence. Incomplete replays must not advance the evaluated checkpoint
  ([#743](https://github.com/den-run-ai/pystachy/pull/743)). Count cases via `tests/corpus.sh`,
  not globs including helpers; move sidecars and recheck recordings after layout changes
  ([#762](https://github.com/den-run-ai/pystachy/pull/762),
  [#771](https://github.com/den-run-ai/pystachy/pull/771)).
- Preserve upstream provenance/licenses and `# Pystachy port:` explanations; hash fetched
  sources, never guess. Try unchanged upstream, then minimal adaptations; preserve
  CPython executability where promised.
- Check output/checksums before timing. Separate original/adapted CPython, old/new
  Pystachy, JIT startup/compilation, AOT build and steady-state costs. Record flags,
  hardware, input size, samples, shared-host load and BLAS provider. Compare JIT/AOT,
  memory/GC trade-offs and short, sparse, adversarial and repeated-use inputs.
- Interleave same-compiler variants pinned to one core; use medians/callgrind counts
  and call noisy differences inconclusive. First JIT use builds a runtime cache;
  inlining skips IR over `PYSTACHY_JIT_INLINE`. Remove avoidable allocations before GC
  tuning; check thresholds across workloads. Add deterministic count/operation bounds
  (as `make re-probe` does) before optimizing, rather than noisy timing gates.
- Profile an end-to-end consumer: separate parsing, hashing/lookups, boxing/GC and
  dispatch. Test skewed/mixed/changing types and misses/fallbacks; guards or one new
  import alone prove no application win ([#784](https://github.com/den-run-ai/pystachy/pull/784)).
  Separate raw/optimized IR, binary size, frontend/backend time and allocations; scale
  depth/hierarchy sizes. Less IR can run slower ([#785](https://github.com/den-run-ai/pystachy/pull/785)).
  Normalize only demonstrated checkout-path differences in `irsame`; sharing a home
  requires identical library/runtime inputs or can hide changes.
