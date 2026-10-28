# json_repair native port and upstream contribution

The port supplies in-memory, schema-free `repair_json()` and `loads()` with
native mutable `Any` values, valid-JSON decoding, logging and serialized returns.
It is included in the `pystachy-ports` wheel with all subpackages, license and
source notes. File, CLI, schema/Pydantic and arbitrary `json.dumps` options remain
outside this API; see [the contract](../../ports/json_repair/PORT.md).

## Compiler and runtime work

The JSON additions are approximately 60 net library lines and three compiler
condition changes. `JSONDecoder.decode/raw_decode` retains its public class and
recursive `JSONValue` storage. The explicit native `_raw_decode` adapter follows
the existing dynamic-JSON dispatch route to produce `Any` containers. The port
uses a guarded CPython fallback at its two prefix-decoding sites. No runtime
object layout, integer semantics or garbage-collector change was needed.

The final port types its internal lookahead cache as
`dict[str, tuple[int, int | None]]`. Recursive repaired values and logs remain
`Any`; changing log storage required a rejected typed/dynamic boundary conversion,
so it was not adopted. Cache typing reduced the mixed benchmark's executable
text by 3.3%, with no established throughput gain on the shared host.

The parity corpus now retains the actual upstream API and options, including
serialization defaults, Unicode, logging, strict/streaming modes and long-string
cases. Literal loops and small helper calls yield 645 distinct combinations.
The checker fails on missing cases, duplicate IDs, wrong types, altered Unicode,
key order, logs, serialized text and error messages.

At port-source revision `89a7e05f` (the published source-equivalent follow-up), pristine and adapted CPython 3.13.16 replayed
645/645; native JIT, AOT and both GC-stressed modes replayed 644/645. Case 59,
`12345678901234567890`, raises `OverflowError` because native integers are signed
64-bit. This failure remains in the corpus and the checker exits nonzero; it is
not silently excluded. The native JSON codec's 256-container bound also remains.
Full integer parity needs general arbitrary-precision storage and operations,
not conversion to a different JSON type. The [language roadmap](https://github.com/den-run-ai/pystachy/issues/12)
tracks the wider integer and API limits.

The four focused regressions passed JIT/AOT normally and under GC stress (8
executions per configuration). The 19 JSON loader/corpus-checker unit tests
passed. Installed-wheel checks passed CPython, JIT and source-free AOT, including
mutable results. Compiler/runtime bootstrap reached a three-stage fixed point.
Main's stdlib/port cleanup was subsequently merged, preserving its removals;
`docs/stdlib.md` retains both the cleanup and the new decoder description.
The [pull request](https://github.com/den-run-ai/pystachy/pull/847) records final
integration checks, full-corpus IR comparison and current CI status separately.

## Performance findings

See [samples, source identities and reproduction](../../bench/json_repair/PROFILING.md).
The original repeated ten-record workload showed 2.33x AOT versus upstream
CPython, but larger payloads expose limits that this small mixture misses.

| Finding | Evidence | Next step |
|---|---|---|
| Escape-heavy malformed strings rescan accumulated text quadratically | Doubling 1,000 to 2,000 escaped newlines increases original AOT from 30 to 115 ms; CPython from 102 to 370 ms | Replace full-prefix brace-state rebuilding with an incremental update, with delimiter/escape regressions |
| `_rebuild_unmatched_opening_braces` is the main CPython hotspot on that case | 85% of instrumented time; native scaling agrees, but native instruction attribution was not collected | Profile native instructions/allocations before changing the runtime |
| Typed cache reduces generated code, not proven elapsed time | 3.3% smaller native text; overlapping timing distributions | Retain the clearer internal type; keep JSON results dynamic |
| String accumulation and character access remain candidates | `_scan_string_body`, `get_char_at` and `_append_string_content` lead the small mixed CPython profile | Measure native copying/allocation cost before changing accumulation |
| GC is not the leading cost in the measured mixed case | Five collections, 34.1 MiB peak, about 1.6–1.7 ms collection time | Prioritize parser work before collector tuning |

The single-character scanner now uses `str.find`, counting preceding escapes
only at potential matches. Its fallback handles multiple targets, negative
positions and backslash targets. A differential native regression compares
1,850 scans. Ordinary mixed throughput is inconclusive; the useful upstream
case is a malformed object with a missing opening brace and a long quoted key.

## Small upstream PR first

The prepared upstream candidate changes only `JSONParser.skip_to_character`
and adds focused tests: 21 net implementation lines and 38 test lines. It
preserves schema, file and CLI APIs, typing and dependencies. On upstream
v0.64.1, 429 tests passed with 17 expected timing-test skips under `CI=1`;
mypy, ty and Ruff passed. A 100 KB missing-opening-brace key took median
0.171857 s versus 0.006972 s per 20 repairs across seven interleaved CPython
samples (24.65x); this is a targeted case, not a general library speed claim.

Suggested title: **Use string search for in-memory single-character lookahead**.
Recheck upstream main, apply the small patch on a fork branch, rerun its tests,
include the reproducible case and disclose AI assistance. The candidate is
prepared separately; no upstream PR has been submitted.

Do not submit the entire downstream port as an upstream replacement: it removes
working APIs and adds compiler-specific adaptations. A later optional native
build PR can be small only after Pystachy handles more of the original source:

- Upstream recursive value aliases and runtime-length tuple keys across dynamic
  storage, removing explicit `Any` replacements and the `repr` cache key.
- The context enum and `ExitStack` pattern, plus bound-method replacement.
- Public decoder methods that preserve identity while selecting dynamic result
  storage, removing the private native adapter.
- Arbitrary-precision integers and separate file/schema/CLI validation for a
  full-package compatibility claim.

Keep the escape-rescanning fix as its own semantic/performance PR. Passing the
original string and index to `raw_decode` could separately remove a suffix copy;
that candidate has not been implemented or measured here.
