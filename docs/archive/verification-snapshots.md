# Verification snapshots

These are results recorded in the October 2026 documentation. They preserve the earlier
evidence; use [the testing guide](../testing.md) and a fresh `build/verification.json` for
current coverage and results.

## Differential suite at `b55d4c9`

The documented run reported **2,635 passed, 0 failed**, with both the CPython-hosted and
self-compiled compiler. It included 733 programs and 24 deviations in each mode, 979 rejection
cases, and the parse-only `pystachy check` cases. Pass counts are checks, not unique programs.

## Initial syntax survey

The survey associated with [PR #18](https://github.com/den-run-ai/pystachy/pull/18), merged
9 October 2026, compared `pystachy check` with CPython's `compile()` over 5,701 files from
CPython 3.13's standard library and installed packages. The documentation reported agreement
apart from 19 valid files that Pystachy could not parse, involving tab indentation, named
Unicode escapes or f-string fields reusing the outer quote.

That corpus result does not establish complete syntax compatibility. Later syntax changes
and current restrictions are described in the [execution reference](../language/semantics.md#syntax-errors).
