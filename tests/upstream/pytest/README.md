# Selected original unittest parity

`tools/pytest_native_upstream.py` closes the extraction-oracle gap for a bounded
selection of real upstream methods. For each suite it runs this sequence:

1. Import the unchanged, hash-pinned upstream file in isolated CPython and run
   the selected methods through real `unittest.TestSuite`/`TestCase`.
2. Export those methods using `tools/cpython_test_methods.py`, preserving an
   explicit original-method to adapted-pytest-ID mapping.
3. Run the adapted suite in ordinary CPython pytest and the generated runner in
   CPython. Require exactly the selected IDs and every setup/call/teardown phase
   to pass.
4. Run the same adapted suite in native JIT and AOT and compare its collection
   and phase outcomes with real pytest.

An original failure, error, runtime skip, expected failure, unexpected success,
missing case, changed inventory or source hash prevents qualification. The tool
does not infer original correctness from adapted tests. Its tests deliberately
break an original assertion, a subtest, setup and cleanup, and also inject an
incorrect extraction while the original passes.

## Pinned scope

The [manifest](manifest.json) preserves every original case ID in these source
files, the explicit selected methods, source hashes and known exclusions.

| Suite | Selected methods | Original inventory | Source |
|---|---:|---:|---|
| fnmatch | 3 | 17 | CPython 3.13.16 `Lib/test/test_fnmatch.py` |
| textwrap | 6 | 66 | CPython 3.13.16 `Lib/test/test_textwrap.py` |
| statistics | 2 | 401 | CPython 3.13.16 `Lib/test/test_statistics.py` |
| mypyc NameGenerator | 5 | 5 | mypy `mypyc/test/test_namegen.py` |

The CPython pin is `cbc944f4bc59639a444dd971c737788ba2283a91`; the mypy pin is
`1231cf158a9cab0c41f613f3d8070c1332632f29`. NameGenerator's implementation and all
five original upstream methods are unchanged. This qualifies that component,
not the complete mypy/mypyc package or its build pipeline.

The statistics inventory includes doctests added by its real `load_tests`
hook. The tool records those IDs and excludes them from its explicit method
selection. The exporter accepts that hook only through the explicit
`selected_methods_only=True` API; its usual CLI still rejects custom collection.
Module/class setup and teardown restrictions are unchanged. Subtests retain
their assertions but become ordinary statements after extraction, so a failed
adapted subtest stops that method. Exact subtest IDs, failure aggregation,
messages and traceback formatting are outside this contract.

`TestFMean.test_weights` is an observed exclusion: original unittest and adapted
CPython pass, but alpha.3 native compilation rejects its local exception-class
alias (`StatisticsError = statistics.StatisticsError`) in an `except` clause.
A second observed exclusion, `TestLinearRegression.test_proportional`, passes
original/adapted CPython but native compilation rejects its unchanged integer
inputs (`expected int, got float` in `lib/statistics.py:1542`). The original
source and full 401-case inventory remain pinned. Other unselected
methods are explicitly listed in the report as outside this bounded
qualification; this is not a claim that each one is unsupported.

## Reproduce

Use the pinned development interpreter/pytest and LLVM setup in
[installation](../../../docs/install.md). fnmatch/textwrap sources and their
license already exist in the repository and can run offline:

```sh
python3 tools/pytest_native_upstream.py --suite fnmatch --suite textwrap \
  --compiler ./pystachy --json build/pytest-upstream-bundled.json
```

Fetch optional sources once, then qualify all four suites. `--fetch` only
downloads missing files whose exact URLs and hashes are in the manifest; a
mismatched existing file is an error. Real CPython `test.support` sources are
included for statistics. No support stubs replace upstream code.

```sh
python3 tools/pytest_native_upstream.py --fetch --compiler ./pystachy \
  --json build/pytest-upstream-all.json
python3 tools/pytest_native_upstream.py --compiler ./pystachy \
  --json build/pytest-upstream-all-offline.json
```

The default source cache is `build/pytest-upstream-sources`; `--source-cache`
selects another verified cache. Each run imports a fresh snapshot containing
only pinned files, so extra `.py`, bytecode and extension modules in the cache
cannot shadow them. It also verifies the loaded original library module's path
and source hash; a preloaded or installed copy cannot stand in for the pin.
`--mode python` checks original, adapted and generated
CPython without native execution. Repeating `--mode` selects JIT/AOT; generated
CPython always runs first. No compilation or timing fallback is permitted.

Reports retain original outcomes and subtest counts, the full source inventory,
every excluded case, source hashes, adapted-source hashes and all runner phase
reports. Existing stdlib differential, broader upstream, GC and sanitizer checks
remain separate acceptance gates. These results measure compatibility, not
pytest throughput.

Downloaded CPython material retains its exact PSF license; downloaded mypy
material retains its exact MIT license. Both license files are hash-pinned,
downloaded with the corresponding sources and included in each source snapshot.
Generated extracts carry the upstream filename/hash and preservation reminder.
