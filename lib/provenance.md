# Library provenance and validation

Upstream-derived modules use CPython 3.13.16. Unchanged copies and their SHA-256
hashes remain in [README.md](README.md#unchanged-cpython-files), where
`tests/record.sh --check` verifies them. The hashes below identify original
upstream files, rather than the adapted file's current contents.

## Adapted Python modules

Each localized adaptation is marked `# Pystachy port:` in source. Common changes
add container/optional annotations, replace iterator-only paths with supported
consumers, and make C-only or dynamic imports optional. Detailed edit history
belongs in the source diff; [compatibility.md](compatibility.md) records the
observable contract.

| Module | Upstream file | Original SHA-256 |
|---|---|---|
| `html` | `Lib/html/__init__.py` | `923d82d821e75e8d235392c10c145ab8587927b3faf9c952bbd48081eebd8522` |
| `html.entities` | `Lib/html/entities.py` | `d9c65fb2828dbc1f3e399058a341d51e9375ec5bca95a8e92599c41bd5b78bde` |
| `html.parser` | `Lib/html/parser.py` | `4274e9112adf3fa57c7f9afa7c9b5c631456b18b7403cc627cc5027d02cdd2ae` |
| `_markupbase` | `Lib/_markupbase.py` | `cb14dd6f2e2439eb70b806cd49d19911363d424c2b6b9f4b73c9c08022d47030` |
| `difflib` | `Lib/difflib.py` | `1593ae08143632f4f81fea3beeeb279d803f8a9be922b12fe79664d78bba879d` |
| `getopt` | `Lib/getopt.py` | `0ce875700c8798193b8e2748f7a27fc542cc4d525a1e6fc403767450ec92be99` |
| `heapq` | `Lib/heapq.py` | `6d43277e5c76fc0f073cd388fcff852d14d068f6bb6d4886c340f8b75a1229a9` |
| `fnmatch` | `Lib/fnmatch.py` | `95391dac2ce9f60084d65eba2f4b9d9735e28136d55b684e1fde7d6342555963` |
| `textwrap` | `Lib/textwrap.py` | `30f3d833950d53e168cc021961574b553f56aed84458712b2eb29c6495843d46` |
| `string` | `Lib/string.py` | `c000d9c4340c910b869399f0f0acc1b70e39391ad9344c4e08d8d0f80210a916` |
| `statistics` | `Lib/statistics.py` | `80b677e786418c299ced99993f4a89804d4532e0b5e26971286713a6de538c18` |
| `urllib.parse` | `Lib/urllib/parse.py` | `491b233e8d87a2ab73964afff029717177d53ad8def328ed9b00575db983da27` |
| `html` | `Lib/html/__init__.py` | `923d82d821e75e8d235392c10c145ab8587927b3faf9c952bbd48081eebd8522` |
| `html.entities` | `Lib/html/entities.py` | `d9c65fb2828dbc1f3e399058a341d51e9375ec5bca95a8e92599c41bd5b78bde` |
| `keyword` | `Lib/keyword.py` | `18c2be738c04ad20ad375f6a71db34b3823c7f40b0340f5294d0e89f3c9b093b` |
| `shlex` | `Lib/shlex.py` | `f927227de5ba5b1b2bdd75e3d9c8cb72b602b3bba3cc8edbf8fb554de0dc1fd7` |

`heapq` adapts its top-k routines while retaining the other upstream code.
`statistics` also ports `math_sumprod_impl` from `Modules/mathmodule.c` for
weighted means. `urllib.parse` includes codec logic corresponding to CPython's
`unicodeobject.c`, `stringlib/codecs.h` and `codecs.c`, plus bracketed-host and
NFKC-delimiter validation. These modules keep CPython-only paths available when
CPython runs the source.

## Subset implementations

| Module | Upstream reference | Implementation |
|---|---|---|
| `io` | `Modules/_io/stringio.c` | Typed `StringIO`, with append chunks joined when read |
| `csv` | `Modules/_csv.c`, `Lib/csv.py` | Reader state machine, writer and dialect APIs |
| `collections.deque` | `Modules/_collectionsmodule.c` | Typed two-list queue with CPython comparison-state checks |
| `functools` | `Modules/_functoolsmodule.c`, `Lib/functools.py` | Generic cache wrapper, plus adapted reduction and comparison-key fallbacks |
| `re` | `Lib/re/`, `Modules/_sre/sre_lib.h`, `sre.c` | Typed parser/compiler and matching engine with an explicit context stack |

`re/_constants.py` retains upstream opcode/flag numbers. `tools/re_tables.py`
generates `re/_unicode.py` from CPython's Unicode functions, including group-name
identifiers, character classes, case mappings and `_casefix.py` exceptions.
These are substantial subset ports, rather than unchanged Python files.

## What the checks establish

`tests/lib_*.py` compares supported compiled paths with CPython through JIT and
AOT. `tests/errors/` checks unsupported inputs; `tests/deviations/` checks
intentional differences. Running an adapted module under CPython separately
checks that it remains compatible Python, including paths Pystachy does not use.

Historical upstream-suite checks recorded with the ports:

| Adapted module | Upstream suite run under CPython | Recorded result |
|---|---|---|
| `difflib` | `test_difflib` | 57 tests passed |
| `getopt` | `test_getopt` | 8 tests and doctest passed; translation-catalog tooling excluded |
| `heapq` | `test_heapq` | 51 tests passed |
| `io.StringIO` | `test_memoryio` StringIO cases | 29 of 39 passed, with `IntLike` replaced by int |
| `textwrap` | `test_textwrap` | 66 tests passed |
| `string` | `test_string` | 39 tests passed, including 25 Template tests |
| `statistics` | `test_statistics` | All 401 tests passed, including a run with the ported `sumprod` |
| `urllib.parse` | `test_urlparse` | All 77 passed, with five upstream subtest skips |
| `urllib.parse` | `test_urllib` quoting/query classes | 28 of 29 passed; strict codec exception subclass differs |
| `html` | `test_html` | Both tests passed |
| `keyword` | `test_keyword` | All 11 tests passed |
| `shlex` | `test_shlex` | 43 of 44 passed; punctuation field is writable |

These counts describe specific recorded checks of the adapted source under
CPython, not the number of APIs or upstream tests executed by the compiled
subset. Current test commands and CI coverage are in
[the testing guide](../docs/testing.md).

The deque reference at the same pinned CPython commit has SHA-256
`02d5bcaea730fc7af1fed5f50f87eacad710022dbebb1efebbbd1737ec940cae`.
`tests/lib_collections.py` and `tests/lib_collections_mutation.py` exercise compiled
queue operations, callback mutation and bounded repetition. Shlex's differential
upstream selection retains its three split/join table methods; HTML retains both
upstream methods, and keyword retains nine methods while excluding dynamic `exec`.
Test headers record source-test hashes and exclusions.

Regex validation also includes `tests/upstream_re_*.py`, deterministic
`tools/re_fuzz.py` comparisons against CPython, and `tools/re_probe.py` checks of
matcher-entry/context counts. Cache, Unicode-range, whitespace and character-class
regressions have dedicated `tests/lib_*` cases. Time measurements are advisory;
see [caching measurements](../docs/caching.md).

CPython-derived code and docstrings are used under the PSF License Version 2.
See [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES).


The HTML parser probe pins CPython commit `cbc944f4bc59639a444dd971c737788ba2283a91`.
`tests/upstream_html_parser.py` retains complete assertion sets from 45 upstream
methods, with helper/type adaptations and excluded methods disclosed in its header.
`tests/lib_html_parser.py` adds RAWTEXT/RCDATA, buffering, lifecycle and inheritance
checks. Native results must be reported separately from CPython-hosted checks;
see [the probe record](../docs/html-parser-probe.md).
