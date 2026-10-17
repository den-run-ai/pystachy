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
| `stat`, `posixpath`, `genericpath` | Unchanged CPython | Mode tests and string path operations | Partial API coverage |
| `operator` | Adapted CPython | Operator functions, `itemgetter`, `attrgetter`, `methodcaller` | Getters specialize on literal items and names |
| `html`, `html.entities` | Adapted CPython | `escape`, `unescape`, HTML4 and HTML5 entity tables | UTF-8 byte indexing; no configurable integer digit limit |
| `html.parser` | Adapted CPython | Incremental HTMLParser with typed subclass callbacks | Byte columns; ASCII name case conversion; see [probe](../docs/html-parser-probe.md) |
| `difflib` | Adapted CPython | `SequenceMatcher` (also the generator `get_grouped_opcodes()`), `get_close_matches`, junk predicates and `Match` | String items; `unified_diff()` and `context_diff()` still need `type(x).__name__` and `str.format()`, `ndiff()` a `Differ` with `None` junk functions |
| `getopt` | Adapted CPython | `getopt`, `gnu_getopt`, `GetoptError` | `longopts` must be `list[str]`; untranslated messages |
| `heapq` | Adapted CPython | Heap operations, `nlargest`, `nsmallest`, `key=` | `merge` unavailable; non-list inputs are materialized |
| `keyword` | Adapted CPython | Keyword lists, `iskeyword`, `issoftkeyword` | Compiled predicates accept strings and `None` |
| `token` | Adapted CPython | Token constants, `tok_name`, `EXACT_TOKEN_TYPES`, `ISTERMINAL`, `ISNONTERMINAL`, `ISEOF` | `__all__` and `tok_name` written out, with CPython's values and order |
| `collections` | Subset implementation | Typed `deque` (both ends, bounded queues, searches and comparisons), `defaultdict`, `OrderedDict`, `Counter` and `namedtuple()` (a NamedTuple class the compiler makes) | Items share one type; mappings hold dicts; deque iterators check mutation, other iteration is a snapshot; `namedtuple()` only as a module's top-level `NAME = namedtuple(...)` with literal arguments |
| `shlex` | Adapted CPython | `split`, `quote`, `join`, lexer options and source stacking | Files are read eagerly; punctuation field is writable |
| `io` | Subset implementation | `StringIO` and `BytesIO` (also in `with`), seek constants and `TextIOWrapper` over binary buffer objects, with CPython's chunked reads and writes | `StringIO`'s byte positions; lazy line iteration; no `getbuffer()` or `readinto()`; `TextIOWrapper` of UTF-8, Latin-1 and ASCII, without `seek`/`tell`/`detach`/`reconfigure` |
| `csv` | Subset implementation | Reader/writer, dict reader/writer, dialects and registry | Eager reading; reader fields are strings; no `Sniffer` |
| `re` | Subset port of parser/compiler and C engine | String regex syntax and matching, substitution, caches, runtime-length `Match.groups()` | Byte positions; other selected variable-length result APIs unavailable |
| `fnmatch` | Adapted CPython | `fnmatch`, `fnmatchcase`, `filter`, `translate` | String patterns; POSIX case handling |
| `functools` | Typed subset implementation | `cache`, `lru_cache`, statistics, clearing, `reduce`, `cmp_to_key`, `partial`, `wraps`, `update_wrapper` | Typed callables and supported value/key types |
| `textwrap` | Adapted CPython | `TextWrapper`, `wrap`, `fill`, `shorten`, `dedent`, `indent` | Byte widths; no subclassing |
| `string` | Adapted CPython | Constants, `capwords`, `Template`, `Formatter` and its subclasses | No `Template` subclasses; `Formatter` arguments of one union, no attribute or item fields |
| `statistics` | Adapted CPython | `fmean`, geometric mean, medians, quantiles, mode, `covariance`, `correlation` (of floats) | Selected numeric types and APIs |
| `random` | Adapted CPython on a subset `_random` (`_pyrandom`) | Seeded `Random` and module functions, integers, sequences, distributions, state | Int, bool and float seeds; 63-bit `getrandbits`; no subclasses |
| `urllib.parse` | Adapted CPython | String quoting, query parsing/encoding and cached URL parsing/joining | Three codecs; no bytes or result properties |
| `codecs` | Adapted CPython on a subset `_codecs` (`_pystachy_codecs`) | BOM constants, `encode`, `decode`, the UTF-8, Latin-1, ASCII and charmap codec functions, `lookup_error`, `register_error`, the incremental classes | No codec registry (`lookup()`); no UTF-16, UTF-32, UTF-7 or escape codecs |
| `atexit` | Subset port of CPython's C module (`_pystachy_atexit`) | `register` (also as a decorator, with arguments), callbacks run at the end of the program, also after `sys.exit()` or an uncaught exception; `_run_exitfuncs`, `_clear`, `_ncallbacks` | No `unregister`; a failing callback's report shows the exception's last line |
| `abc` | Subset implementation (`_pystachy_abc`) | `ABC`, `metaclass=ABCMeta`, `@abstractmethod` (also under `@property`, `@classmethod`, `@staticmethod`) and the deprecated `abstractproperty`, `abstractclassmethod`, `abstractstaticmethod`, with CPython's `TypeError` for a class with abstract methods; `get_cache_token` | No virtual subclasses (`register()`), `__subclasshook__` or `__abstractmethods__` |
| `_thread` | Subset port of CPython's C module for one thread (`_pystachy_thread`) | `allocate_lock`, `LockType`, `RLock` (with `_is_owned`, `_release_save`, `_acquire_restore`), `get_ident`, `get_native_id`, `stack_size`, `interrupt_main`, `exit`, `TIMEOUT_MAX`, `error`, `_local` as a base class | One thread: `start_new_thread()` raises `NotImplementedError`, and an acquire that would wait for ever raises `RuntimeError` |
| `unicodedata` | Port of CPython's C module (`_pystachy_unicodedata`) on its tables of Unicode 15.1.0 | Every function: the properties, numeric values and decompositions of characters, `normalize()` and `is_normalized()` in the four forms, `name()`, `lookup()` (also of aliases, named sequences and derived names) and `ucd_3_2_0` | `lookup()` takes `str` only; no `_ucnhash_CAPI` |
| `binascii` | Subset port of CPython's C module (`_pystachy_binascii`) | Hex with separators, base64 with strict mode, uu, quoted-printable, `crc32`, `crc_hqx`, `Error` and `Incomplete` | Bytes and ASCII-str arguments only; Python functions, not builtins |
| `struct` | Unchanged CPython on a subset port of the C module `_struct` (`_pystachy_struct`) | `pack`, `unpack`, `unpack_from`, `iter_unpack`, `calcsize` and `Struct` for every code of the native and standard tables, with CPython's bytes, values and errors | The format must be known as the program compiles (`calcsize()` takes any); `bytes` buffers; no `pack_into` |
| `itertools` | Subset implementation of CPython's C module on generators (`_pystachy_itertools`), following the documented pure-Python equivalents | Every function: `count`, `cycle`, `repeat`, `accumulate`, `batched`, `chain` and `chain.from_iterable`, `compress`, `dropwhile`, `filterfalse`, `groupby`, `islice`, `pairwise`, `starmap`, `takewhile`, `tee`, `zip_longest`, `product`, `permutations`, `combinations` and `combinations_with_replacement`, lazy as in CPython, with the C module's argument checks and messages | Iterators are generators of one item type; runtime-length tuples (`batched`, the combinatorics) of scalar items; `tee(it, n)` gives a list; an iterator an exception has left is finished |
| `contextlib` | Adapted CPython | `contextmanager` (also as a decorator), `closing`, `nullcontext`, `suppress` (as a `with` item), `AbstractContextManager`, `ContextDecorator` | No `ExitStack`, `redirect_stdout`, `chdir` or async managers; positional `nullcontext(value)` |
| `types` | Subset implementation (`_pystachy_types`, and the compiler's `_pystachy_typenames`) | `TracebackType`, for `__exit__`'s annotation; `GenericAlias`, for CPython's idiom for a generic class: `__class_getitem__ = classmethod(GenericAlias)` in a class body | Its other names import, but any use of one is a compile-time error; a generic-alias class's subscripts at run time are too |
| `pyobj` | Subset implementation over CPython's stable ABI (`@ffi.extern`), with its twin in `tools/rt_cpython` | Python objects through an embedded CPython, or an extension module's host: `Object`, `import_module`, `of_int`, `of_float`, `of_str`, `of_list` | Needs `PYSTACHY_LIBPYTHON` (CPython 3.12+); scalar conversions only; see [FFI](../docs/ffi.md#calling-cpython) |
| `datetime` | Adapted CPython (`_pydatetime`, following `_datetime`) | `timedelta`, `date`, `time`, `datetime`, fixed-offset `timezone`, `tzinfo` subclasses, ISO 8601, `strftime()` | No local time zone; no `strptime()` or pickling |

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
| `stat` | `Lib/stat.py` | `07217986d9b2172b509dab3578d18ac05ba768b418e1f1e8c90e38a8f7c2b3c6` | Constants, `S_IS*()`, `S_IMODE()` and `S_IFMT()`. |
| `this` | `Lib/this.py` | `481d0cb3de511eae0b5713dad18542b07eafd9c013bb7690f7497bad49923a71` | Prints the Zen of Python. |
| `posixpath` | `Lib/posixpath.py` | `69acb9e294987cd6056a2237048373cf8d6201faf1e43a49c38889b47d2fb28e` | String path operations, including `join()`; see [limits](compatibility.md#path-modules). |
| `genericpath` | `Lib/genericpath.py` | `cdac5a68dd738051e0d66fc81d5947d6a1776248fc6fe862253477608d870ec4` | Helpers used by `posixpath`. |
| `curses.ascii` | `Lib/curses/ascii.py` | `780dd8bbaf0ee7e832f164c1772953e694a9cd1031d1ab1471af65344d3645e6` | ASCII character predicates and conversions. |
| `urllib` | `Lib/urllib/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Empty package; `urllib.parse` is adapted separately. |
| `struct` | `Lib/struct.py` | `9c231f9497caf513a22dee8f790b07f969b0e45854a0bdd6dd84b492e08c2856` | Its names, on `_pystachy_struct`; see [limits](compatibility.md#struct). |

`curses/__init__.py` is a Pystachy stand-in for the package that normally imports
`_curses`; it does not provide terminal control.

`_pystachy_binascii.py` is `binascii`, `_pystachy_codecs.py` is `_codecs`, `_pystachy_atexit.py` is
`atexit`, `_pystachy_struct.py` is `_struct`, `_pystachy_thread.py` is `_thread`,
`_pystachy_unicodedata.py` is `unicodedata` and `_pystachy_itertools.py` is `itertools`, modules
CPython builds into its interpreter: Pystachy loads those files for `import binascii`, `import _codecs`,
`import atexit`, `import _struct`, `import _thread`, `import unicodedata` and `import itertools`,
where CPython imports its C modules.
`tools/unicodedata_tables.py` writes the tables of `unicodedata`, `_pystachy_unicodedata_db.py` and
`_pystachy_unicodedata_names.py`, from CPython's own module.
`_pystachy_abc.py` is `abc`, which CPython imports as it starts, so that a program's own `abc.py`
is never imported there. `types.py` binds `TracebackType` from `_pystachy_types.py` and CPython's
other names of `types` from `_pystachy_typenames`, the compiler's, which only it may import. `_collections_abc` has no file here: it is the compiler's builtin
`collections.abc`, as CPython's `collections` makes it `collections.abc`.

`_pystachy_iterators.py` holds the iterator classes of `iter()` over builtin containers
(`list_iterator`, `dict_keyiterator`, ...). The compiler loads it for a program that calls
`iter()`; programs do not import it. See [iterators](../docs/language/semantics.md#iterators).

`_pystachy_range.py` holds the class of range objects, `range()` as a value. The compiler loads
it for a program that may use one, a read of the builtin `range` other than a `range(...)` that a
loop or a consumer steps through (its methods are compiled where a program calls them); programs
do not import it. See [range objects](../docs/language/semantics.md#range-objects).

## Examples and measurements

| Example | Library use |
|---|---|
| [Maze paths](../examples/mazepath/README.md) | `collections.deque` |
| [Event routing](../examples/route/README.md) | `re`, `fnmatch`, `functools` |
| [CSV reports](../examples/csvstat/README.md) | `csv` |
| [Text and spelling comparisons](../examples/linediff/README.md), [suggestions](../examples/suggest/README.md) | `difflib` |
| [Top words](../examples/topk/README.md) | `heapq` |
| [Aligned tables](../examples/column/README.md) | `io.StringIO` |
| [Field selection](../examples/cut/README.md) | `getopt` |
| [Message rendering](../examples/mailmerge/README.md) | `string.Template` |
| [Latency reports](../examples/latency/README.md) | `statistics` |
| [Monte Carlo estimates](../examples/montecarlo/README.md) | `random`, `statistics` |
| [URL reports](../examples/urlstats/README.md) | `urllib.parse` |

See [performance](../docs/performance.md) for the overall benchmark protocol and
[caching](../docs/caching.md) for recent regex, router and textwrap measurements.
Example tables record particular runs; they are not universal performance claims.

CPython-derived files and code are used under the PSF License Version 2.
See [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES). The
[stdlib coverage guide](../docs/stdlib.md) describes the wider import sweep.

