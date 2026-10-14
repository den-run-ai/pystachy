# Standard library modules

<a id="lib-standard-library-modules-for-pystachy"></a>

Pystachy reuses CPython library code where it fits the typed subset. This directory
contains unchanged CPython modules, adapted modules with localized
`# Pystachy port:` comments, and subset implementations of APIs backed by C in
CPython. The sources remain valid Python; successful execution under CPython does
not by itself establish that every API compiles with Pystachy.

Imports search builtin modules first, then the program's directory,
`PYSTACHY_PATH`, and `lib/`. See [module rules](../docs/language/modules.md).

## Module guide

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| `bisect`, `colorsys`, `curses.ascii`, `this` | Unchanged CPython | See the pinned-copy table below | Subset string and type rules apply |
| `operator`, `stat`, `posixpath`, `genericpath` | Unchanged CPython | Operator functions, mode tests and string path operations | Partial API coverage |
| `difflib` | Adapted CPython | `SequenceMatcher`, `get_close_matches`, junk predicates and `Match` | String items; generator APIs unavailable |
| `getopt` | Adapted CPython | `getopt`, `gnu_getopt`, `GetoptError` | `longopts` must be `list[str]`; untranslated messages |
| `heapq` | Adapted CPython | Heap operations, `nlargest`, `nsmallest`, `key=` | `merge` unavailable; non-list inputs are materialized |
| `io` | Subset implementation | `StringIO` and seek constants | Byte positions; eager line iteration |
| `csv` | Subset implementation | Reader/writer, dict reader/writer, dialects and registry | Eager reading; reader fields are strings; no `Sniffer` |
| `re` | Subset port of parser/compiler and C engine | String regex syntax and matching, substitution, caches | Byte positions; selected variable-length result APIs unavailable |
| `fnmatch` | Adapted CPython | `fnmatch`, `fnmatchcase`, `filter`, `translate` | String patterns; POSIX case handling |
| `functools` | Typed subset implementation | `cache`, `lru_cache`, statistics and clearing | Annotated functions with supported key types |
| `textwrap` | Adapted CPython | `TextWrapper`, `wrap`, `fill`, `shorten`, `dedent`, `indent` | Byte widths; no subclassing |
| `string` | Adapted CPython | Constants, `capwords`, `Template` | No compiled `Formatter` or `Template` subclasses |
| `statistics` | Adapted CPython | `fmean`, geometric mean, medians, quantiles, mode | Selected numeric types and APIs |
| `urllib.parse` | Adapted CPython | String quoting, query parsing/encoding and URL parsing/joining | Three codecs; no bytes, result properties or URL cache API |

The [compatibility reference](compatibility.md) defines each module's accepted
inputs, unsupported APIs and observable differences from CPython. The
[provenance reference](provenance.md) records upstream files and checks.
The [porting checklist](../docs/porting.md) describes compiled upstream test
coverage and the pinned `make port-check` checks for fnmatch and textwrap.
Builtin modules such as `sys`, `os` and `math` are documented in the
[language guide](../docs/language.md#builtins-and-library-modules).

<!-- Existing section links remain valid. Detailed contracts moved to compatibility.md. -->
<a id="difflib-a-port-of-cpythons"></a>
<a id="getopt-a-port-of-cpythons"></a>
<a id="heapq-with-nlargest-and-nsmallest-ported"></a>
<a id="io-pystachys-own"></a>
<a id="csv-pystachys-own"></a>
<a id="re-a-port-of-cpythons"></a>
<a id="fnmatch-a-port-of-cpythons"></a>
<a id="functools-pystachys-own"></a>
<a id="textwrap-a-port-of-cpythons"></a>
<a id="string-a-port-of-cpythons"></a>
<a id="statistics-a-port-of-cpythons"></a>
<a id="urllibparse-a-port-of-cpythons"></a>

## Unchanged CPython files

These files are byte-for-byte copies from CPython 3.13.16. `tests/record.sh --check`
reads this table and verifies their SHA-256 hashes. API coverage remains limited
to the compiled paths listed here and in the compatibility reference.

| Module | From CPython 3.13.16 | SHA-256 | Tested coverage |
|---|---|---|---|
| `bisect` | `Lib/bisect.py` | `f1cf7b85fc36b5da249813fc5ab97d9464f8cc1bc817f7146206fa2713e35999` | Bisection and insertion, including `key=`. |
| `colorsys` | `Lib/colorsys.py` | `65e3dfbf7bad61d4d7d7731a69dd7e75a347fd350d91327a51010a94e6fd2f1d` | All conversion functions. |
| `operator` | `Lib/operator.py` | `c048f8a6852832d5fa750d6ae772d7658c52c3511d261cb902f7edfd262e9127` | Operator functions and fixed-call `call()`; see [limits](compatibility.md#operator). |
| `stat` | `Lib/stat.py` | `07217986d9b2172b509dab3578d18ac05ba768b418e1f1e8c90e38a8f7c2b3c6` | Constants, `S_IS*()`, `S_IMODE()` and `S_IFMT()`. |
| `this` | `Lib/this.py` | `481d0cb3de511eae0b5713dad18542b07eafd9c013bb7690f7497bad49923a71` | Prints the Zen of Python. |
| `posixpath` | `Lib/posixpath.py` | `69acb9e294987cd6056a2237048373cf8d6201faf1e43a49c38889b47d2fb28e` | String path operations, including `join()`; see [limits](compatibility.md#path-modules). |
| `genericpath` | `Lib/genericpath.py` | `cdac5a68dd738051e0d66fc81d5947d6a1776248fc6fe862253477608d870ec4` | Helpers used by `posixpath`. |
| `curses.ascii` | `Lib/curses/ascii.py` | `780dd8bbaf0ee7e832f164c1772953e694a9cd1031d1ab1471af65344d3645e6` | ASCII character predicates and conversions. |
| `urllib` | `Lib/urllib/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Empty package; `urllib.parse` is adapted separately. |

`curses/__init__.py` is a Pystachy stand-in for the package that normally imports
`_curses`; it does not provide terminal control.

## Examples and measurements

| Example | Library use |
|---|---|
| [Event routing](../examples/route/README.md) | `re`, `fnmatch`, `functools` |
| [CSV reports](../examples/csvstat/README.md) | `csv` |
| [Text and spelling comparisons](../examples/linediff/README.md), [suggestions](../examples/suggest/README.md) | `difflib` |
| [Top words](../examples/topk/README.md) | `heapq` |
| [Aligned tables](../examples/column/README.md) | `io.StringIO` |
| [Field selection](../examples/cut/README.md) | `getopt` |
| [Message rendering](../examples/mailmerge/README.md) | `string.Template` |
| [Latency reports](../examples/latency/README.md) | `statistics` |
| [URL reports](../examples/urlstats/README.md) | `urllib.parse` |

See [performance](../docs/performance.md) for the overall benchmark protocol and
[caching](../docs/caching.md) for recent regex, router and textwrap measurements.
Example tables record particular runs; they are not universal performance claims.

CPython-derived files and code are used under the PSF License Version 2.
See [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES). The
[stdlib coverage guide](../docs/stdlib.md) describes the wider import sweep.
