# JSON repair readiness, 2026-11-09

This covers the port, the CPython companion and its "JSON verifier", the benchmarks and the
wheel. Main is `f60df76d` (v0.4.0-alpha.2 merged). In the links below,
`M` = `https://github.com/den-run-ai/pystachy/blob/f60df76d2bcef35dd11142c5f1219ca3bc6f53f6`.

A Claude Code subagent did the review, read-only; its scripts and outputs are in [scripts/](scripts/)
and [results/](results/). The coordinating session reproduced the claims marked *checked*.

## Verdict

**Correct on its recorded corpus and checked in CI, but not ready to share upstream or publish as a
package.** A narrow, precisely worded claim is fine today; the draft is under "Public claim" below.

The "JSON verifier" is `tests/upstream/json_repair/extension.py` from #1073, which replays the
corpus through the CPython companion. It is not `tools/json_check.py`.

## Evidence

### Version gap (*checked*)

| | Version | Date |
|---|---|---|
| Ported | json_repair 0.64.1 (`ace9b23c`) | 19 Oct |
| Current on PyPI | 0.64.8 | uploaded today 08:29 UTC |

- PyPI has had six releases since 0.64.1: 0.64.2, 0.64.3, 0.64.4, 0.64.5, 0.64.6 and 0.64.8.
- 0.64.8 changes 10 of the 22 pinned source files (+223/−140 lines).
- Upstream has since fixed bugs the port still carries: #247, #250, #251, and serializing `""`.
- On CPython, the port fails 41 of 0.64.8's 321 schema-free tests:
  - 20 are behavior differences;
  - 21 come from removed APIs or changed internals.

### Correctness on main (*CI logs checked*)

- **CI** (run 42633594969, `f60df76d`):
  - Contracts on x86_64 and aarch64: the extension verifier matched `837/837` with `PYSTACHY_GC_STRESS=1`, and FFI gave `196 passed`.
  - Benchmarks: `json_repair CLI: 20 process cases matched CPython 3.13.16 in JIT and AOT`.
- **Spot check** with a main-equivalent compiler (tree `0e84b32e`), all 837/837:
  - AOT;
  - JIT;
  - `pystachy ext` plus the verifier (host CPython 3.13.18);
  - AOT under per-allocation GC stress, which took 54 s.

  53 inputs outside the corpus gave identical results in adapted CPython, AOT and JIT
  ([results/native.log](results/native.log)).
- **Upstream's own tests are never run natively.** The native check is an API replay of 837 cases:
  - 438 calls extracted from 7 upstream test modules;
  - 399 added multilingual, strict, streaming and logging cases.
- **Upstream v0.64.1's tests on CPython against the port:** 234 of 246 pass. The 12 failures are 9
  from the removed file API and 3 from changed internal signatures, none from different repair
  results.
- **Excluded upstream tests:** the schema, file, CLI, performance and pattern-properties modules,
  plus two resource-dependent calls.

### Divergences from upstream outside the corpus (*stray slash checked on 0.64.1 and 0.64.8*)

| Input | 0.64.1 and 0.64.8 | Port |
|---|---|---|
| `[/1,2]` | `[2]` | `[1, 2]` |
| `[/abc]` | `['bc']` | `['abc']` |
| `{"k":/42}` | `{'k': ''}` | `{'k': 42}` |
| `{"k":/ /*x*/true}` | `{'k': ''}` | `{'k': True}` |

The rows come from [results/probes-cpython.txt](results/probes-cpython.txt). Upstream also returns
`[1]` for `[1, /2]` and `{'path': ''}` for `{"path": /usr/bin}` (*checked*).

- The port's stray-slash recovery is its own behavior. [PORT.md](https://github.com/den-run-ai/pystachy/blob/f60df76d2bcef35dd11142c5f1219ca3bc6f53f6/ports/json_repair/PORT.md) does not list it as a deviation from upstream.
- The port follows upstream 0.64.3's comment-handling fix on purpose.

### Gaps in CI coverage (*checked*)

- **The verifier can skip without failing CI.** It runs only when `$PY` is exactly the pinned
  3.13.16 (`tests/ffi/run.sh` L151–161). Otherwise it prints nothing, and CI's guard (`ci.yml`
  L185–193) only looks for `; skipped:` lines.
- **No CI job runs the standalone native JIT/AOT `replay.py`.**

### Performance has not stabilized

- **Committed numbers:** measured 2 Nov at `ec442a20`, against 0.64.1
  ([`bench/json_repair`](https://github.com/den-run-ai/pystachy/blob/f60df76d2bcef35dd11142c5f1219ca3bc6f53f6/bench/json_repair/README.md)). AOT against upstream:

  | Workload | AOT / upstream |
  |---|---|
  | Ten-record mix | 5.3× |
  | Valid input | 2.7× and 1.4× |
  | Malformed | 5.8–6.1× |
  | Escaped | 187× |
  | Non-ASCII | 1.7× |
  | Comma-dense | 3.8× |
  | Logs | 3.4× |

- **Re-measured 9 Nov** on a different host
  ([`../../json-repair/json-repair-remeasure-2026-11-09.json`](../../json-repair/json-repair-remeasure-2026-11-09.json)).
  Port changes merged on 4 Nov moved AOT instruction counts by −81% to +6%:

  | Workload | 2 Nov | 9 Nov |
  |---|---|---|
  | Escaped newlines | 187× | 1,541× |
  | Valid 8 KB string | 1.41× | 0.94× |
  | Non-ASCII | 1.7× | 4.1–4.3× |
  | Logs | 3.4× | 22× |

  - The two 9 Nov campaigns agree within about 4%.
  - On non-ASCII input, native AOT is 4.5× slower than the same port running on CPython. The
    cause has not been profiled.
- **The escaped-string multipliers no longer apply.** Upstream removed its quadratic escape
  handling in 0.64.4 (#245).
- **Memory:** the companion uses about 2.5× upstream's RSS, recorded only in the draft #1110.

### Bug-bashing has not stabilized

| Date | Bug | Fix |
|---|---|---|
| 22 Oct – 2 Nov | Wide integers returned `""` or crashed | #997, #1003 |
| 2–3 Nov | JIT `RecursionError` at 257-deep valid JSON | #1021, #1029 |
| 4 Nov | Value lost at comment boundaries, inherited from upstream | #1074 |
| 6–7 Nov | Unquoted non-ASCII text silently dropped | #1109 |
| 9 Nov | `-O0` JIT broke `port_json_repair_bounds.py` | #1188 (open, green) |

- **Churn:** port sources last changed on 4 Nov, the runtime on 7 Nov.
- **Review:** none of #1064, #1073, #1074, #1076, #1109 or #1147 had a human GitHub review. CI
  passed before each merge. Codex's automatic review finished 61–74 s after each one merged and
  found nothing.

### Wheel (*version and tag checked*)

[`tools/build_json_repair_wheel.py`](https://github.com/den-run-ai/pystachy/blob/f60df76d2bcef35dd11142c5f1219ca3bc6f53f6/tools/build_json_repair_wheel.py) builds `pystachy-json-repair` with:

| Field | Value |
|---|---|
| Version | hard-coded `0.1.0.dev3` |
| Tag | `cp312-abi3-linux_{arch}`, which PyPI rejects |
| Compatibility | glibc 2.38 or later, x86-64 only |
| Compiler | `python pystachy.py` |
| Metadata | no License-Expression or URLs |
| CI | none builds or installs it (Lint mocks it) |

The licenses are complete, and the names are free on PyPI.

## Possible upstream reports (none filed)

- **New:** a stray `/` before a value drops data (table above; *checked* on 0.64.8).
- **Closed upstream but still reproducing on 0.64.8:**
  - #227 (*checked*): an escaped surrogate pair stays as two lone surrogates, U+D83D U+DE00.
  - #163: forced repair drops top-level primitives.
  - #249 (*checked*): `'{}, {"id": 1}'` gives `{'id': 1}`.
- **Never submitted:** a `str.find` lookahead patch for `skip_to_character` (24.65× on a 100 KB
  key). The function is unchanged in 0.64.8.

## Next steps

1. Rebase the port onto 0.64.8 or later and regenerate the corpus.
2. Document the stray-slash recovery as a deviation, or report it upstream.
3. Make the verifier fail visibly when the pinned CPython is missing. Add the standalone JIT/AOT
   replay to CI; it takes about 1.5 minutes.
4. Re-measure on the release commit against both 0.64.1 and current upstream. Look into the
   non-ASCII gap. Land or close #1110.
5. Wheel: build to a manylinux tag, take the version from the release, fill in the metadata, and
   build it in CI.
6. Merge #1188.

## Public claim

"Pystachy compiles an adapted, schema-free port of json_repair 0.64.1 (MIT) to native code. On 837
recorded API calls (438 from json_repair 0.64.1's tests plus 399 multilingual, strict, streaming and
logging cases), its JIT, AOT executables and a CPython extension return the same values, types, key
order, code points, logs and errors as json_repair 0.64.1 on CPython 3.13. CI checks the extension
under forced GC on Linux x86-64 and ARM64. The port omits schema and file APIs and does not include
upstream fixes released after 0.64.1."

- Leave speed numbers out until they are re-measured on the release commit.
- Avoid "drop-in", "passes upstream's tests" and the escaped-string multipliers.

## Not checked

`make verify`, timings, macOS, a real wheel build and install, and `cli.py` run locally (it needs
CPython 3.13.16).
