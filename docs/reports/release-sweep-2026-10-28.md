# Release-preparation sweep, 28 October 2026

A fast, scoped compatibility and performance sweep before the next prerelease after
[v0.1.0-alpha.3](../releases/v0.1.0-alpha.3.md). It reran existing harnesses against the
alpha.3 tag and the committed baselines. It looked for regressions, crashes, silent wrong
results, performance regressions and the next useful expansion targets. It does not
replace the broad audit's denominator, and it does not advance the latest-evaluated-main
checkpoint in the [rolling log](compatibility-updates.md): the stub-assisted import sweep
and the full verification matrix were not rerun here.

## Summary

- **No regression found.** Native stdlib imports, the CPython-derived corpus, all 14
  shipped ports, the 645-case json_repair replay and 23 package first errors either match
  their baselines or have moved forward. No baseline success was lost.
- **No new silent wrong result.** Every probe that compiled printed exactly what CPython
  printed. This covered 29 stdlib API probes, 12 CPython test-method extractions,
  127 CPython-derived corpus programs, 33 port programs and 16 libm functions in AOT.
- **Open correctness issues, reproduced on this main:**
  - [#908](https://github.com/den-run-ai/pystachy/issues/908): valid chained
    comparisons over a class hierarchy whose ordering always raises fail to compile, in
    both JIT and AOT. The fix is in draft [#911](https://github.com/den-run-ai/pystachy/pull/911).
  - [#94](https://github.com/den-run-ai/pystachy/issues/94): `list()` and `sorted()`
    propagate a `TypeError` raised by `__len__`. CPython ignores such length-hint errors
    and returns the list. This is a wrong result, and it is not yet documented as a deviation.
  - [#151](https://github.com/den-run-ai/pystachy/issues/151) private-name mangling
    remains the most likely silent difference in real libraries. It is a documented deviation.
- **Performance:** see [Performance](#performance). Experimental dynamic-`Any` modules
  compile 25–37% slower than at the CI perf reference, since the #858 identity series.
  Programs that do not opt in are not affected.
- **New coverage:** two CPython 3.13.16 test adaptations were added to the corpus:
  23 `test_shlex` methods and the str halves of eight `test_posixpath` methods.
  See the [core-sweep guide](../../tests/upstream/core-sweep.md).

## Provenance

| Input | Value |
|---|---|
| Main | `2eb0f36ec3de4632b6fa378884bcf36d68de8e3c` (#968), with last release `v0.1.0-alpha.3` = `f5a09d42` |
| Native compiler | Three-stage fixed point, 748,732 compiler IR lines, SHA-256 `29db3a81c9d99e7378370e7720e544cd1cebd5111b72f749508fe9087cfa4c84` |
| Toolchain | LLVM/clang 18.1.3, Linux x86-64, 4 shared vCPUs |
| CPython oracle | Ubuntu CPython **3.13.17** for probes and sweeps. New recordings used CPython **3.13.16** (python-build-standalone via uv 0.13.4), as `.python-version` requires. |
| Isolation | Private `PYSTACHY_CACHE` per sweep, at most two concurrent jobs. Timing ran alone afterwards. |

The 3.13.17 oracle is a disclosed difference from the pinned interpreter. Checked-in
`.out` recordings remain the 3.13.16 reference, and `tests/run.sh` compared against them.
`make port-check` refuses any interpreter except 3.13.16 by design.

## Standard library

The native import sweep ran `tools/import_sweep.py -j 2` over the Ubuntu 3.13.17 stdlib
in 52 s with no timeouts. **150/459 modules compile.** The last measured baseline was
144/470 at `53c17bad` (2026-10-19). The denominators differ: eight modules now ship in
`lib/` and are excluded (60 instead of 52), and the Ubuntu inventory lacks four
`ctypes.macholib` files and adds `sitecustomize`. Nine of the 518 shared module sources
differ between 3.13.16 and 3.13.17.

| Result | Modules |
|---|---|
| Baseline successes kept | 143/144; `_weakrefset` is now supplied by `lib/` and excluded |
| Newly compiling | `argparse`, `traceback`, `reprlib`, `email.charset`, `_pyrepl._threading_handler`, `wsgiref.validate` |
| Lost | None |
| First error changed | 144 modules; 63 now stop earlier at `_imp`/`_ast`/`_opcode` because `92cb532b` (in alpha.3) removed those stand-ins on purpose |

The 55-name selection from the [22 October expansion](stdlib-expansion-2026-10-22.md)
still compiles 43/55 with the native compiler. All 12 rejected names stop at the same
first blocker as before. The ten rejected functional probes keep their documented
blockers. Of 15 new release-user API probes, 11 compile and match CPython. The other
four are `copy.copy`, `copy.deepcopy`, `enum.Enum` and `json.dumps(indent=2)`.

The stub-assisted sweep was stopped at about 147 of 459 programs to fit the time and CPU
bounds. The 146/470 stub-assisted figure from 2026-10-19 is therefore not refreshed.

## CPython test suite

| Check | Result |
|---|---|
| `tests/programs/upstream/*.py`, JIT and AOT | 127 cases, **254 passed**, 0 failed |
| Same corpus, JIT, `PYSTACHY_GC_STRESS_PROGRAM=1` | **127 passed**, 0 failed (AOT under stress not run) |
| Real CPython 3.13.16 `Lib/test` files compiled whole (`pystachy ir`) | 1/76, a helper module (`test_tomllib/burntsushi.py`) |
| Test methods extracted from 12 modules, JIT and AOT | 6 modules match CPython (shlex, posixpath, getopt, `string.Template`, colorsys, struct); 6 still rejected at compile time with known gaps |

Whole CPython test files stop on their test infrastructure first: `unittest` in 21
files, `test.support` in 17, then `copy` in 9. Counting every import rather than only the
first blocker, `test.*` appears in 64 files, `unittest` in 57, `copy` in 19, `pickle` in 18,
and `doctest`, `gc`, `inspect` and `unittest.mock` in 11 each. Native execution of real
CPython test files therefore needs `unittest` and a bounded `test.support` before library
gaps matter. Until then, coverage grows through adapted methods.
The two adaptations that needed no compiler change are now in the corpus. The `test_html`
unescape table (about 350 assertions) needs only run-time `%` formats. The `bisect`,
`heapq` and `urljoin` tables need small typing splits.

## Ports and packages

| Check | Result |
|---|---|
| Port acceptance unit tests | 15/15 |
| Hosted upstream suites (relaxed to 3.13.17 in a scratch copy) | `fnmatch` 17/17, `textwrap` 66/66 |
| Native port programs (14 ports, 33 cases), JIT and AOT | **66 passed**, 0 failed; also 70/70 under per-allocation GC |
| json_repair replay | Port on CPython 645/645. Native AOT, JIT and both under GC stress each **644/645**. |
| Package probes, compile-only | 23/27 run, every archive hash verified. 2 compile (sgp4, and now jdcal), 4 first errors advanced, 17 unchanged, **0 regressed** |

The CPython-hosted alpha.3 compiler gives the same 23 first errors as main, so the
package advances predate alpha.3. The only json_repair mismatch is still case 59,
`12345678901234567890`, beyond signed 64 bits. Promoting ints cannot reach it yet: the
port opts into dynamic `Any`, and a module cannot opt into both, as the
[python-int contract](../python-int.md) states.

json_repair 0.64.2 on PyPI differs from the ported 0.64.1 only in schema-guided repair
(`prefixItems`, two files, +6/−1 lines). The port excludes schema mode, so no port change
is needed. The prepared upstream `skip_to_character` change is still absent upstream and
has not been submitted.

## Performance

PENDING

## Pull requests and issues

- Closed as superseded, with comments naming where the change lives: #848 and #852
  (both heads are ancestors of main via #964/#966) and #659 (replaced by #735).
- The three Dependabot tool pins conflict pairwise. This sweep's change combines uv
  0.13.4, setuptools 84.1.0 and ruff 0.17.1, so CI runs once. ruff 0.17.1 reports no
  findings on this main.
- #911 is the only open compiler fix and the strongest release candidate. It needs main
  merged in, one CI run and readiness review once #949–#951 land.
- #882 (support-surface docs) needs its json_repair, #773 and manifest-count statements
  refreshed before merge. #743 is an 8.3 MB audit through #842, 319 commits behind main.
  Research drafts #784, #796 and #816 stay unmerged.

## Ranked expansion targets

The ranking weighs each target by how many users and packages it would unblock, using
what the probes and import sweep showed:

1. **`enum`**: user `Enum` subclasses and `import enum` fail. This blocks `http`, `uuid`,
   wcwidth and click ([#7](https://github.com/den-run-ai/pystachy/issues/7), [#610](https://github.com/den-run-ai/pystachy/issues/610)).
2. **`copy`**: `copyreg`'s type-keyed dispatch dictionary blocks `copy`, `pickle`,
   `shelve` and five more modules, plus 19 CPython test files ([#805](https://github.com/den-run-ai/pystachy/issues/805)).
3. **`json.dumps(indent=...)`** and typed (non-`JSONValue`) containers in `json.dumps`.
4. **`_thread.RLock` as a value**: blocks `logging`, `hashlib`, `queue`, `threading` and `sched`.
   `logging` is also urllib3's and therefore requests' next blocker.
5. **`os.O_RDONLY` in `glob`**, which blocks `pathlib`. **`email.charset.Charset`
   field inference** blocks 15 `email` modules.
6. **`unittest`**, the first blocker for native CPython test files.
7. Small language gaps found by packages:
   - `isinstance` with a tuple of types held in a variable, which blocks unchanged tomli-w ([#748](https://github.com/den-run-ai/pystachy/issues/748) is the reverse shape);
   - `**kwargs` on dunder methods, which blocks packaging's `Version` ([#263](https://github.com/den-run-ai/pystachy/issues/263));
   - `dict(key=value)`, `zip(strict=True)`, `\N{...}` escapes ([#672](https://github.com/den-run-ai/pystachy/pull/672)) and `tuple(set)`.
8. **`statistics.mean`/`stdev`** ([#746](https://github.com/den-run-ai/pystachy/issues/746)),
   and `argparse.ArgumentParser`, which now imports but needs multiple inheritance.

## Reproduction

From a bootstrapped checkout with `PYSTACHY_LLVM=/usr/lib/llvm-18/bin` and a private
`PYSTACHY_CACHE`:

```sh
python3.13 tools/import_sweep.py -j 2 --metadata build/import-meta.json ./pystachy /usr/lib/python3.13 build/import-sweep.json
PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/*.py
PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_JOBS=1 tests/run.sh ./pystachy jit tests/programs/upstream/*.py
make port-check PY=python3.13   # requires CPython 3.13.16
```

The json_repair replay follows [its README](../../tests/upstream/json_repair/README.md).
The package probes reuse the archive URLs, hashes and probe sources in
[the 17 October package report](compatibility-2026-10-17-packages.json).
