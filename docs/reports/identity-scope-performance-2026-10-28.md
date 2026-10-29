# Identity-scope performance and mixed-policy checks, 28 October 2026

The typed `Counter`/`tomllib` reproducer in [#969](https://github.com/den-run-ai/pystachy/issues/969)
still has a material performance regression on the evaluated main. The identity-scope change
in [#973](https://github.com/den-run-ai/pystachy/pull/973) restores this workload to alpha.3's
measured range. The independent [#974](https://github.com/den-run-ai/pystachy/pull/974) change
recovers much of the cost but remains **1.84x slower than alpha.3** here. These measurements
do not establish that either candidate is ready to merge.

#973's CI also exposes a pre-existing wrong result at the boundary between promoting ints and
dynamic `Any`. It is reproduced below on current main and the candidate's integration tree.
Keep #969 as a release blocker and retain the strict compatibility gate; a passing ordinary
run or a faster benchmark does not clear the failing mixed-policy checks.

## Evaluated sources

| Variant | Source identity |
|---|---|
| alpha.3 | [`f5a09d4223139d7255e31051be97fc509e1ca1fe`](https://github.com/den-run-ai/pystachy/commit/f5a09d4223139d7255e31051be97fc509e1ca1fe), tag `v0.1.0-alpha.3` |
| Main | [`5bd492b33cd6bc32fb464d008d543560a8959486`](https://github.com/den-run-ai/pystachy/commit/5bd492b33cd6bc32fb464d008d543560a8959486) |
| #973 integration | Head [`1cf173f2451396b1c057865de40bf1ca9f8fdf3a`](https://github.com/den-run-ai/pystachy/commit/1cf173f2451396b1c057865de40bf1ca9f8fdf3a) plus main above; tree `93a37730b45151d5097c7df5aba28261c11369f5`, exactly equal to the CI merge `505f8d2a94ed8f3f87ecab4ac4e90f26c076cd68` |
| #974 integration | Published head [`f02150796bc356e2f47572ac147121d0384f919f`](https://github.com/den-run-ai/pystachy/commit/f02150796bc356e2f47572ac147121d0384f919f) plus main above; tested local commit `c33bb19a5459c5f4a26c100cc4d093a08c0036ba`, tree `a5fbdba8564478b347cb83f028ab4213947e9d88`, exactly equal to CI merge `6ff24a07e09bb78be482402b2fd065ea72f2767b` |
| No-import control | The #973 integration tree, with the `tomllib` import and final `tomllib.loads` print removed from the workload |

All timed binaries were built through each revision's **CPython-hosted compiler**, using
CPython **3.13.16**, LLVM/clang **18.1.3**, and that revision's own library and runtime sources.
The benchmark measures native AOT execution; it does not include compilation or the hosted
compiler's startup. Default AOT settings were used. Result-affecting inherited `PYSTACHY_*`
settings were removed, then the matching LLVM directory, source home, one build worker and
a private cache per variant were set explicitly.

The machine was a shared Linux x86-64 host reporting **AMD EPYC 9V74 80-Core Processor**.
Executables were pinned to allowed CPU 0. Results below are medians of **nine interleaved
process elapsed-time samples**, after two warmups. An initial seven-sample round could overlap
light unit tests and is excluded from this table. The reported round was repeated after those
tests completed, with no other session-owned heavy build or timing job running. Host activity
outside this session was not controlled. The final round ran at 22:15:08–22:15:12 UTC.

## Typed-loop result

| Variant | Median, ms | Full observed range, ms | Ratio to alpha.3 |
|---|---:|---:|---:|
| alpha.3 | 22.403 | 21.308–25.016 | 1.000x |
| Main | 215.565 | 204.922–229.867 | 9.622x |
| #973 integration | 22.428 | 21.746–25.234 | 1.001x |
| #974 integration | 41.318 | 39.164–42.946 | 1.844x |
| No-import control | 20.595 | 19.006–28.261 | 0.919x |

#973's small median difference from alpha.3 is inconclusive within the overlapping ranges.
#974 is about **5.2x faster than main**, but its remaining cost versus alpha.3 is well outside
the observed ranges. This one-workload result does not establish JSON throughput, JIT startup,
compile-time, memory or whole-application performance.

Every warmup and measured execution was checked against pinned CPython's output:

```text
449999985000000 30000000
1
```

The no-import control must print the same first line and no second line. No observed run had
unexpected stderr or a nonzero exit status.

The workload is the original #969 shape:

```python
import tomllib

class Counter:
    def __init__(self) -> None:
        self.pos = 0
        self.n = 0

    def step(self, k: int) -> None:
        for i in range(k):
            self.pos = self.pos + i
            self.n += 1

c = Counter()
c.step(30000000)
print(c.pos, c.n)
print(len(tomllib.loads("a = 1")))
```

Its measured source SHA-256 is
`74583cdb90fdf990c6862b4129e8c6573088a2373d9de42e3b4138dfb210781e`.
For each source checkout, build it with `python3.13 pystachy.py build counter.py -o counter`,
verify output first, then run the executable pinned to an allowed CPU. The no-import control
removes only the import and final print.

Deterministic IR inspection supports the performance mechanism. From main to #973, `Counter`
changes from `{i64, i64, ptr, ptr}` to `{i64, i64}`. `Counter.step` has 81 versus 54 IR body
lines and two versus zero `pys_dyn_int_box` calls. The imported TOML implementation still
tracks identity: whole-program calls to that helper fall only from 1,153 to 1,149. The saving
is in the hot typed loop, rather than eliminating the library's identity semantics.

## Mixed promoting-int/Any correctness blocker

The ordinary, non-promoting forms of #973's new fixtures pass. Adding the `python-int` pragma
to their entry modules, as the required compatibility gate does, exposes two existing gaps.

| Fixture | CPython 3.13.16 | Main and #973 integration, JIT and AOT |
|---|---|---|
| `dynany_identity_scope_numbers.py` | `module True True True` and `function True True True` | `module False False True` and `function False False True`, exit 0 |
| `dynany_identity_scope_fields.py` | Both printed field checks complete successfully | Compilation rejects `scopelib.py:29` with `a int value cannot become an Any value` |

The numbers case passes one binding and its alias into an `Any`-accepting helper. Equality
remains true, but the two crossings create distinct objects. This is a silent wrong identity
result, not a timing failure or a newly introduced regression in #973. The promoted numbers
case has byte-identical IR on evaluated main and the original #973 head. Native JIT/AOT
execution on main and native execution produced through the integrated candidate's hosted
front end independently confirm the discrepancy.

The source inputs are pinned here:

- [Numbers fixture](https://github.com/den-run-ai/pystachy/blob/1cf173f2451396b1c057865de40bf1ca9f8fdf3a/tests/programs/inference/dynany_identity_scope_numbers.py)
- [Fields fixture](https://github.com/den-run-ai/pystachy/blob/1cf173f2451396b1c057865de40bf1ca9f8fdf3a/tests/programs/inference/dynany_identity_scope_fields.py)
- [Dynamic helper](https://github.com/den-run-ai/pystachy/blob/1cf173f2451396b1c057865de40bf1ca9f8fdf3a/tests/dynany_scope_support/scopelib.py)

To reproduce from a fresh build of main `5bd492b3`, fetch the PR's fixture commit and copy
only these inputs into temporary files. The tested compiler and its own library/runtime remain
the chosen main revision:

```sh
git fetch origin refs/pull/973/head
probe_dir=$(mktemp -d)
fixture_ref=1cf173f2451396b1c057865de40bf1ca9f8fdf3a
git show "$fixture_ref:tests/dynany_scope_support/scopelib.py" > "$probe_dir/scopelib.py"
for shape in numbers fields; do
    {
        printf '%s\n' '# pystachy: python-int'
        git show "$fixture_ref:tests/programs/inference/dynany_identity_scope_$shape.py"
    } > "$probe_dir/$shape.py"
    PYTHONPATH="$probe_dir" python3.13 "$probe_dir/$shape.py"
    PYSTACHY_PATH="$probe_dir" ./pystachy run "$probe_dir/$shape.py"
    if PYSTACHY_PATH="$probe_dir" ./pystachy build "$probe_dir/$shape.py" -o "$probe_dir/$shape"; then
        "$probe_dir/$shape"
    fi
done
```

The promoted numbers/fields input SHA-256 values are respectively
`373c05a67fcb6a317b830ee4d145e3b0ebefe1e1edbce1b2adcdc21ed14dedcb` and
`1f5f2312c91fed063b52110f9a3cbde210c0a76c5f55e9165c70101aea8d3f83`;
the helper's is `7dfd2375a42d27925ba121d9752dd4841807d92ee8415bceb099ccc13c491b0e`.

Promoting ints have no ordinary numeric-identity companions; narrowing to int64 currently
drops their binding identity before boxing. Merely carrying an existing provenance field
through narrowing cannot repair bindings that never had one. Extending the existing companion
scheme also affects aliases, calls/returns, fields, closures and values beyond int64. Eagerly
narrowing during a copy would incorrectly raise overflow before an actual 64-bit boundary.
That needs a scoped correctness fix with regressions, not a gate exception for wrong output
or a blanket rejection of currently correct value-only programs. Track this under
[#858](https://github.com/den-run-ai/pystachy/issues/858) and
[#907](https://github.com/den-run-ai/pystachy/issues/907).

## Validation scope and remaining gate

[CI run 40764750069](https://github.com/den-run-ai/pystachy/actions/runs/40764750069), on the
#973 integration tree above, fails `python-int-optin-0` and `python-int-optin-1` and therefore
fails the aggregate gate. Other verification groups pass. Installation, Packages, Lint and
Performance smoke workflows on head `1cf173f2` pass; the same-repository DCO workflow is
expected to skip. The failure evidence is in artifacts `12850888853` and `12850973229`.
Neither old-head green checks nor the ordinary fixture passes clear these failures.

The original #973 head was also compared with evaluated main through the hosted IR/diagnostic
oracle on **3,838 corpus inputs**. All 240 differing reports were retained and rerun with a
shared source home after verifying that both revisions' complete library/runtime inputs were
identical. This removed only demonstrated checkout-path differences. The remaining three IR
changes are the scope program, scope IR guard and `upstream_tomllib_data.py`; all reflect the
intended identity-scope reduction. There are **no diagnostic or exit-status differences**.
After integrating main, the three new #911 comparison fixtures also produce identical IR.
This is hosted-front-end evidence, not a claim that a complete local native `make verify`
or native `make irsame` was rerun on the integrated candidate.

Local scope tests (6), compiler-state probe tests (10) and frame-state tests (18) pass; the
scope/state suites were rerun on the integration tree. Direct and indirect callables,
numeric globals, inherited constructors and captured-number callbacks were reviewed for
fallback to full identity tracking. No additional PR-specific defect was found in that
bounded review. No compatibility threshold, exception policy or default mode was changed.

Before merge or release, repair the mixed-policy wrong result, validate the final combined
source, and obtain a complete passing current-tree CI matrix. Recheck the typed-loop and JSON
workloads after the correctness fix. #973 remains blocked; the residual #974-only performance
cost keeps #969 open for the next alpha.
