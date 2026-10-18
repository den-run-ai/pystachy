# Package compatibility, 17 October 2026

Measured at main **`d3fbfc6f5f6d5650f25ffc0d97be93b512f41a6f`**, with
CPython 3.13.16 and LLVM 18.1.3 on Linux x86-64. Native checks used the
bootstrapped `./pystachy`; rejection discovery used the same source under the
CPython-hosted compiler. Three installed-wheel reference programs additionally
used CPython 3.12.14, explicitly identified below.

**All 15 shipped ports still pass their 31 selected differential programs in
both native JIT and AOT: 62 passed, zero failed.** These are useful adapted
library subsets, not 15 unchanged PyPI packages. All 31 programs also match their
recordings on CPython with the edited ports. With the exact upstream distributions,
30 match; `port_pyaes_cipher.py` requires the documented list-key-to-bytes driver
adaptation before it can call upstream AES.

The [machine-readable results](compatibility-2026-10-17-packages.json) retain
package versions, archive URLs and SHA-256 hashes, exact probe source, diagnostics,
selected reference output, adaptations and validation counts. All 15 upstream
archives matched the existing `PORT_REFERENCE.md` pins. The additional packages
were deliberately selected; the success/failure totals are not an ecosystem-wide
compatibility percentage.

## Shipped ports: what works and how much is adapted

"Minor" describes localized source edits for the stated API. It does not promise
full dynamic argument handling, Unicode character semantics or unbounded integers.
"Major" includes substantial package/API narrowing even when the retained algorithm
has few source edits. Marker counts are `tools/port_edits.py`'s historical-edit
heuristic, not changed lines or currently necessary compiler workarounds.

| Port / pinned release | Adaptation | Fresh compiled evidence and retained boundary |
|---|---|---|
| jdcal 1.4.1 | Minor; 2 markers | Calendar conversions; float-local initialization and boolean `is_leap`; extreme values remain limited by 64-bit arithmetic. |
| iniconfig 2.3.1 | Minor; 4 | INI parsing/access/conversions; named escape spelling, typed defaults and materialized iteration. |
| pylev 1.4.0 | Minor; 5 | Five distance functions/aliases and tested typed sequences; Python 2 shims removed, memo annotated; strings count UTF-8 bytes. |
| roman 5.2 | Minor; 3 | Conversion, validation and errors; argparse CLI outside compiled coverage. |
| sqids 0.5.2 | Minor; 2 | Integer-list IDs and blocklists; tuple/set and prefix/suffix adaptations; ASCII alphabets and 64-bit limits. |
| convertdate 2.5.1 | Major package narrowing; 29 | Arithmetic calendars and selected holidays; omits astronomical PyMeeus calendars and convenience APIs. |
| pyaes 1.6.1 | Major API narrowing; 36 | AES block cipher with integer-list keys/data; no compiled modes, padding or streaming API. |
| pyfiglet 1.0.4 | Major packaging/API narrowing; 40 | Rendering with three embedded fonts; no font discovery/installation, transforms or CLI. |
| qrcode 8.2 | Major adaptation; 59 | Matrix/text QR encoding; no image factories or CLI; string inputs; field validation differs from upstream setters. |
| sgp4 2.27 | Major package narrowing; 23 | Scalar pure-Python orbit propagation; no C++/NumPy API, OMM or export convenience layer. |
| snowballstemmer 3.1.1 | Major package narrowing; 17 | English Porter2 and Porter only; no other 34 languages or dynamic factory. |
| ordered-set 4.1.0 | Major type/API narrowing; 46 | String items and list operands; no general ABC, fancy indexing or pickling surface. |
| sortedcontainers 2.4.0 | Major type/API narrowing; 58 | Integer SortedList only; no keyed lists/dicts/sets; snapshot iteration and list-valued ranges. |
| tomli-w 1.2.0 | Major type/API narrowing; 26 | Homogeneous typed documents; no mixed documents, datetime/Decimal or binary dump; inline-table cache omitted. |
| wcwidth 0.9.2 | Major package narrowing; 36 | Width functions and selected Unicode tables with a UTF-8 adapter; excludes terminal discovery/wrapping and native extension. |

The total is **386 markers**, matching the current tracking comment in
[#262](https://github.com/den-run-ai/pystachy/issues/262); its older 581/421-marker
body describes earlier snapshots. Each port's [guide](../../ports/README.md)
defines the tested API more precisely.

## Unmodified upstream source: measured first blockers

Each program was first run successfully on CPython with the upstream source.
For compiler rejection, `pystachy ir` checks semantic compilation; it does not
execute a JIT program or build an executable. A first diagnostic is an observed
barrier, not proof that fixing it makes the package work.

These package probes used the upstream package roots plus isolated third-party
dependencies on `PYSTACHY_PATH`, with Pystachy's shipped `lib/` fallback. They did
**not** add a full CPython standard-library overlay. Thus missing `warnings`,
`importlib`, `calendar` and similar errors describe this normal shipped-library
configuration; they are not claims that each module still fails unchanged under
the broader overlay used by the separate stdlib/benchmark audits.

| Upstream source | Selected use | Result on this baseline |
|---|---|---|
| sgp4 2.27 | `sgp4.functions.jday(2000, 1, 1, 0, 0, 0.0)` | **Unchanged JIT and AOT agree with CPython:** `(2451544.5, 0.0)`. This helper is not full orbit propagation. |
| jdcal 1.4.1 | Gregorian and Julian conversion | `jcal2jd`: `expected int, got float` at the changing local. |
| iniconfig 2.3.1 | Parse and access an INI value | `\N{...} escapes are not supported`. |
| pylev 1.4.0 | Levenshtein and Damerau distance | Python 2 shim: `name 'xrange' is not defined`. |
| roman 5.2 | To/from Roman numerals | Missing `argparse` imported for the CLI. |
| sqids 0.5.2 | Encode/decode `[1, 2, 3]` | `tuple() of set[str] is not supported`. |
| ordered-set 4.1.0 | Construct and iterate strings | `unsupported call slice(None)`. |
| sortedcontainers 2.4.0 | Construct integer SortedList | Missing `traceback`. |
| pyaes 1.6.1 | AES block with a bytes key | Missing `copy`. |
| pyfiglet 1.0.4 | Render `Hi` | Missing `importlib`. |
| qrcode 8.2 | Make a QR matrix | Eager import reaches missing `PIL`, although this use needs no image. |
| convertdate 2.5.1 | Gregorian-to-Julian day | Missing `calendar`; PyMeeus is present for the CPython reference. |
| snowballstemmer 3.1.1 | English stemming | Package import reaches Arabic `Among()` class-table inference. |
| tomli-w 1.2.0 | Serialize `{"n": 1}` | `types.MappingProxyType is not supported`. |
| wcwidth 0.9.2 | ASCII string width | Package import reaches missing `enum`. |
| cachetools 7.2.2 | LRUCache lookup | `_HashedTuple` subclasses builtin tuple, an unsupported base class. |
| packaging 26.3 | Compare Versions | Missing `warnings`. |
| boltons 26.2.0 | `iterutils.chunked` | `make_sentinel` defines a class inside a function. |
| attrs 26.1.0 | `@attrs.define` class | Missing `inspect`. |
| six 1.17.0 | Read `PY3` | Missing `importlib`. |
| more-itertools 11.2.1 | `chunked` | Missing `functools.cached_property`. |
| requests 2.34.2 | Import/version | Missing `warnings`; no network request made. |
| pytest 9.1.1 | Import/version | Missing `ast`; this is the runner, not evidence about compiling a selected test function. |
| NumPy 2.3.5 | `arange(4).sum()` | Missing `warnings`. Reference: installed wheel, CPython 3.12.14. |
| Pandas 2.2.3 | `Series([1, 2, 3]).sum()` | Missing `warnings`. Reference: installed wheel, CPython 3.12.14. |
| Pydantic 2.13.5 | Construct BaseModel | Missing `importlib`. Reference: installed wheel, CPython 3.12.14. |
| Click 8.5.0 | Style text | Missing `enum`. Reference: installed wheel, CPython 3.13.16. |

NumPy/Pandas/Pydantic remain **major compatibility targets** beyond these first
errors: their installed distributions depend on native extensions, and their
Python-facing object/dynamic APIs exceed the standalone subset. Adding warnings
or importlib does not provide those runtimes. Pystachy's
[packaging rules](../packages.md) explicitly do not make arbitrary C extensions
importable; the ndarray example is not NumPy compatibility. Likewise,
[#259](https://github.com/den-run-ai/pystachy/issues/259) and
[#263](https://github.com/den-run-ai/pystachy/issues/263) remain cachetools and
packaging targets, not landed ports.

## Small adaptations checked from exact upstream source

These experiments copied the hashed upstream source and changed only the listed
text. They were separate from the shipped port checks.

| Experiment | JIT/AOT result |
|---|---|
| jdcal: `jd = float(367 * year)` in `jcal2jd` | Both conversion calls match CPython. Full `is_leap` behavior is not established by this sample. |
| pylev: delete the two `if PY2: range = xrange` branches | Both iterative distance calls match CPython. Merely assigning `PY2 = False` still fails; removing the branches is necessary for this probe. Recursive memo adaptation remains outside this sample. |
| iniconfig: spell `\N{BYTE ORDER MARK}` as `\ufeff` | Simple parse/access and the full existing parser differential program pass in JIT/AOT. |
| Same minimally edited iniconfig, full existing API driver | Both modes reject `SectionWrapper.__iter__.lineof`: helper declared `int` returns `int | None`. A successful simple example does not cover iteration. |

The iniconfig result makes a useful next small target: preserve upstream iterator
behavior while addressing its optional-return typing, then rerun both drivers.
It would be inaccurate to say nested functions, `key=` or generators are simply
unimplemented based on old port comments.

## Upstream test suites versus compiled tests

Fresh, unedited upstream suites were also run **on CPython 3.13.16 against the
edited port**, with the selected module's source path checked before execution
and its module identity checked afterward:

| Suite | Hosted result | Compiled claim |
|---|---:|---|
| jdcal 1.4.1 `test_jdcal.py` | 9 passed, 1 skipped (`astropy._erfa` absent) | Only the separate differential drivers ran compiled. |
| roman 5.2 `src/tests.py::TestRoman` | All 8 methods passed | Includes CPython-only CLI paths; does not make argparse compile. |
| iniconfig 2.3.1 `testing/test_iniconfig.py` | All 54 tests passed | Does not count as 54 compiled upstream tests. |

The package suite inventory is still incomplete. The exact hashed, per-case
acceptance manifest covers **fnmatch/textwrap**, not these 15 packages.
Examples of retained package limits: sgp4's committed selection keeps 5/33
satellites and 16/700 published verification lines; sqids uses 40 fixed
property inputs instead of running Hypothesis; pyaes uses selected cipher
vectors, not its PyCrypto-dependent randomized suite. See [porting](../porting.md)
and the individual port references before expanding a count into a broader claim.

## Source-wheel packaging works

`tools/package_smoke.py --compiler ./pystachy --no-build-isolation` passed using
CPython 3.13.16, setuptools 84.0.0, wheel 0.48.0 and uv. It built sdists/wheels for
all port sources and the dependent example, verified licenses/provenance, resolved
and installed a hashed dependency lock without an index, and matched CPython
library/module/CLI, JIT and AOT output. The AOT programs still ran after deleting
the installed Python sources and clearing runtime paths. Incompatible dependency
constraints and a wheel modified after locking were both rejected. This validates
source-package distribution and resolution; arbitrary native-extension imports
remain outside that result.

## Bugs, semantics and performance priorities

No new failure appeared in the 62 shipped port checks. These important existing
limits remain observable and should not be hidden by that result:

- UTF-8 byte string semantics affect distances, normalization, stemmer cursors and
  caller-supplied width limits: [#120](https://github.com/den-run-ai/pystachy/issues/120).
- OrderedSet retains upstream 4.1.0's stale stored indices after an interior
  `pop(i)`; this is an upstream behavior preserved by the port, not a new compiler regression.
- SortedList snapshot iteration/list-valued ranges and qrcode's delayed property
  validation are documented port deviations, not unchanged upstream semantics.
- `Any` template work is separate from runtime heterogeneous storage. This baseline
  predates #607 and its follow-up stack; see
  [#616](https://github.com/den-run-ai/pystachy/issues/616). Full `cache`/`lru_cache`
  signatures still need annotations ([#620](https://github.com/den-run-ai/pystachy/issues/620)).
- Large table initialization and regex import/compilation remain performance
  investigation targets, especially pyaes, wcwidth, roman and pyfiglet. Historical
  port speedup/build/RSS numbers were **not rerun as benchmarks here**. The JSON's
  single smoke timings are concurrent-run diagnostics and do not establish speedups.
- The old tomli-w quadratic string-concatenation measurement predates the owned-local
  append optimization. Do not relabel it a current regression without a fresh paired run.
  Removed inline-table caching and materialized iterators remain concrete sources of extra work.

Re-baseline port comments before choosing more adaptations:
[#521](https://github.com/den-run-ai/pystachy/issues/521),
[#530](https://github.com/den-run-ai/pystachy/issues/530) and #262 already own this.
Examples now worth re-probing include datetime helpers in sgp4/convertdate,
struct-based pyaes decoding, qrcode property setters and wcwidth's omitted legacy
cache. A currently available feature does not prove that its exact upstream use
works. `tools/census.py` still labels many shipped features as blockers, including
sets, generators, try statements and lambdas; use it for source discovery, not
current coverage percentages ([#261](https://github.com/den-run-ai/pystachy/issues/261)).

## Reproduction

For the committed ports, after a verified compiler build:

```sh
PYSTACHY_JOBS=4 tests/run.sh ./pystachy 'jit aot' tests/port_*.py
PYTHONPATH=ports python3.13 tests/port_iniconfig_api.py
```

For the 23 sdist probes, use the JSON's exact release archive URL and verify
`sha256` before extracting. The four installed-wheel probes have no retained
archive URL: install their exact listed release into the indicated interpreter
environment, then verify the recorded `module_init_sha256` against its
`__init__.py`; that hash verifies only this source file, not the entire wheel. Put its package root (usually the archive root or
`src/`) on `PYSTACHY_PATH`, save `program` as `probe_<package>.py` **outside** the
package directory, and run:

```sh
PYTHONPATH="$upstream_root:$dependencies" python3.13 probe_package.py
PYSTACHY_PATH="$upstream_root:$dependencies" ./pystachy ir probe_package.py
PYSTACHY_PATH="$upstream_root:$dependencies" ./pystachy run probe_package.py
PYSTACHY_PATH="$upstream_root:$dependencies" ./pystachy build probe_package.py -o probe_package
./probe_package
```

Do not name the probe `package.py`, which shadows the tested import. For packages
rejected by `ir`, the last three commands were not run and provide no execution
claim. Install the listed releases and their normal dependencies into an isolated
target for the reference interpreter. The 3.12 wheel cases should use CPython
3.12 rather than loading their binary dependencies in 3.13. Each minimal-adaptation
record specifies the exact file and before/after replacement.
