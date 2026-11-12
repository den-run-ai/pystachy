# Standard library modules

<a id="lib-standard-library-modules-for-pystachy"></a>

Pystachy reuses CPython library code where it fits the typed subset. This directory
contains unchanged CPython modules, adapted modules with localized
`# Pystachy port:` comments, and subset implementations of APIs backed by C in
CPython. The sources remain valid Python; successful execution under CPython does
not by itself establish that every API compiles with Pystachy. The
[library guide](../docs/stdlib.md#library-support-at-a-glance) summarizes support and gaps by
area, and the [compatibility reference](compatibility.md) gives each module's limits.

Imports search builtin modules first, then the program's directory,
`PYSTACHY_PATH`, and `lib/`. See [module rules](../docs/language/modules.md).
Compiler-provided `sys.setrecursionlimit()` bounds recursive native calls with
catchable `RecursionError`; [its depth policy](../docs/language/compatibility.md#errors-and-control-flow)
also applies to compiled library functions. Ports that opt in to
[dynamic `Any`](../docs/dynamic-any.md) rely on its [operation](../docs/dynamic-any.md#operations)
and [iteration](../docs/dynamic-any.md#iteration) contracts, including
[class values, type-keyed registries, generic calls and annotated factories](../docs/dynamic-any.md#class-values-and-type-keyed-registries).
That protocol support alone does not establish whole-module compatibility.

## Module guide

Each area matches a row of the [library support table](../docs/stdlib.md#library-support-at-a-glance):
🟢 the module's public API works, apart from the limitation listed; 🟡 selected APIs or argument
types; 🧪 built on a prototype. Other modules are not shipped, apart from the private helpers
described [below](#unchanged-cpython-files).

### Text

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟢 `textwrap` | Adapted CPython | `TextWrapper`, `wrap`, `fill`, `shorten`, `dedent`, `indent` | No subclassing |
| 🟢 `unicodedata` | Port of CPython's C module (`_pystachy_unicodedata`) on its tables of Unicode 15.1.0 | Every function: the properties, numeric values and decompositions of characters, `normalize()` and `is_normalized()` in the four forms, `name()`, `lookup()` (also of aliases, named sequences and derived names) and `ucd_3_2_0` | `lookup()` takes `str` only; no `_ucnhash_CAPI` |
| 🟢 `shlex` | Adapted CPython | `split`, `quote`, `join`, lexer options and source stacking | Files are read eagerly; punctuation field is writable |
| 🟢 `keyword` | Adapted CPython | Keyword lists, `iskeyword`, `issoftkeyword` | Compiled predicates accept strings and `None` |
| 🟢 `token` | Adapted CPython | Token constants, `tok_name`, `EXACT_TOKEN_TYPES`, `ISTERMINAL`, `ISNONTERMINAL`, `ISEOF` | `__all__` and `tok_name` written out, with CPython's values and order |
| 🟢 `curses.ascii`, `this` | Unchanged CPython | ASCII character predicates and conversions; the Zen of Python | Subset string and type rules apply |
| 🟡 `string` | Adapted CPython | Constants, `capwords`, `Template`, `Formatter` and its subclasses | No `Template` subclasses; `Formatter` arguments of one union, no attribute or item fields |
| 🟡 `difflib` | Adapted CPython | `SequenceMatcher` (also the generator `get_grouped_opcodes()`), `unified_diff()`, `context_diff()`, `restore()`, `get_close_matches`, junk predicates and `Match` | String items; `ndiff()` and `Differ` need the yield type of a recursive generator, and `HtmlDiff` its class attributes' types |
| 🟡 `gettext` | Adapted CPython | `NullTranslations`, `textdomain`, `bindtextdomain` | Catalog lookups (`gettext()`, `translation()`, `install()`) do not compile: they import `locale` and key their cache by a class (#7); no subclass of `NullTranslations`; see [limits](compatibility.md#gettext) |

### Regular expressions

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `re` | Subset port of parser/compiler and C engine; optional matchers generated for a program's own patterns ([prototype](../docs/re-specialization.md)) | String regex syntax and matching, substitution, caches, runtime-length `Match.groups()` | No bytes patterns; `findall()` with two or more groups raises `NotImplementedError`; see [limits](compatibility.md#re) |
| 🟢 `fnmatch` | Adapted CPython | `fnmatch`, `fnmatchcase`, `filter`, `translate` | String patterns; POSIX case handling |

### Data formats and markup

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🧪 `json` | Native recursive-value prototype | `loads(str)`, `dumps(JSONValue)`, default `JSONDecoder.decode/raw_decode`, `JSONDecodeError`; Unicode, mixed arrays/objects, sorting and separators; in modules that opt in to dynamic `Any`, `loads()` into `Any` storage with promoting integer tokens and `dumps()` of `Any` values (tuples, non-`str` keys, `skipkeys`, `check_circular`, `default`) | Typed `JSONValue` integers remain signed 64-bit; nesting within the recursion limit and 2,000 containers, string keys for `JSONValue`; no hooks, indentation or file APIs; see [scope](../docs/json.md) |
| 🧪 `tomllib` | Adapted CPython: typed namespace state and [dynamic payloads/callbacks](../docs/dynamic-any.md#admission-and-containment) | `loads()` (also with `parse_float`) and `TOMLDecodeError`, with CPython's results and messages: tables, arrays, strings, numbers, booleans and datetimes, as dynamic values that a program narrows with `isinstance()` or annotations | No `load()`, which reads a binary file; see [limits](compatibility.md#tomllib) |
| 🟡 `csv` | Subset implementation | Reader/writer, dict reader/writer, dialects and registry | Eager reading; reader fields are strings; no `Sniffer` |
| 🟢 `html`, `html.entities` | Adapted CPython | `escape`, `unescape`, HTML4 and HTML5 entity tables | No configurable integer digit limit |
| 🟢 `html.parser` | Adapted CPython | Incremental HTMLParser with typed subclass callbacks | ASCII name case conversion; see [API scope](compatibility.md#html-and-htmlparser) |
| 🟡 `urllib.parse` | Adapted CPython | String quoting, query parsing/encoding and cached URL parsing/joining | Three codecs; no bytes or result properties |

### Binary data and encodings

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `struct` | Unchanged CPython on a subset port of the C module `_struct` (`_pystachy_struct`) | `pack`, `unpack`, `unpack_from`, `iter_unpack`, `calcsize` and `Struct` for every code of the native and standard tables, with CPython's bytes, values and errors | The format must be known as the program compiles (`calcsize()` takes any); `bytes` buffers; no `pack_into` |
| 🟢 `binascii` | Subset port of CPython's C module (`_pystachy_binascii`) | Hex with separators, base64 with strict mode, uu, quoted-printable, `crc32`, `crc_hqx`, `Error` and `Incomplete` | Bytes and ASCII-str arguments only; Python functions, not builtins |
| 🟡 `codecs` | Adapted CPython on a subset `_codecs` (`_pystachy_codecs`) | BOM constants, `encode`, `decode`, the UTF-8, Latin-1, ASCII and charmap codec functions, `lookup_error`, `register_error`, the incremental classes | No codec registry (`lookup()`); no UTF-16, UTF-32, UTF-7 or escape codecs |

### Collections and functional tools

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `collections` | Subset implementation | Typed `deque` (both ends, bounded queues, searches and comparisons), `defaultdict`, `OrderedDict`, `Counter` and `namedtuple()` (a NamedTuple class the compiler makes); where a module opts in to [promoting ints](../docs/python-int.md), `Counter`'s counts promote, and so do the ints of the classes' type variables | Items share one type; mappings hold dicts; deque iterators check mutation, other iteration is a snapshot; `namedtuple()` only as a module's top-level `NAME = namedtuple(...)` with literal arguments |
| 🟡 `copy` | Subset implementation of CPython's module, by static type (`lib/copy.py`, with `_pystachy_copy` for the memo) | `copy()` and `deepcopy()` of numbers, strs, bytes, `None`, functions, ranges, lists, dicts, sets, frozensets, tuples and objects of the program's classes (field by field, or by their `__copy__()` and `__deepcopy__(memo)`), with CPython's memo: shared objects and cycles copy once; `Error` | An object in an `Any` value raises `TypeError`; exceptions, library classes, pickling methods and a deep copy of a `Callable` are compile-time errors; no `replace()`; see [limits](compatibility.md#copy) |
| 🟡 `enum` | Subset implementation of CPython's module; the compiler makes enum classes from their class statements | `Enum`, `IntEnum`, `StrEnum`, `Flag`, `IntFlag`, classes of `str` or `int` and `Enum`, `auto`, `unique`, `_missing_()`: members and aliases, `name`/`value`, CPython's reprs, lookup by value and by name, flags' composite members, iteration, `len()`, `in`, `__members__`, methods and properties | Member values are literals of one type, or int and str expressions of them and of the module's constants; int- and str-like members are no `int` or `str` where those are typed; no other mixin types, `boundary=` or functional API; see [limits](compatibility.md#enum) |
| 🟡 `heapq` | Adapted CPython | Heap operations, `nlargest`, `nsmallest`, `key=` | `merge` unavailable; non-list inputs are materialized |
| 🟢 `bisect` | Unchanged CPython | Bisection and insertion, including `key=` | Subset string and type rules apply |
| 🟢 `itertools` | Subset implementation of CPython's C module on generators (`_pystachy_itertools`), following the documented pure-Python equivalents | Every function: `count`, `cycle`, `repeat`, `accumulate`, `batched`, `chain` and `chain.from_iterable`, `compress`, `dropwhile`, `filterfalse`, `groupby`, `islice`, `pairwise`, `starmap`, `takewhile`, `tee`, `zip_longest`, `product`, `permutations`, `combinations` and `combinations_with_replacement`, lazy as in CPython, with the C module's argument checks and messages | Iterators are generators of one item type; runtime-length tuples (`batched`, the combinatorics) of scalar items; `tee(it, n)` gives a list; an iterator an exception has left is finished |
| 🟡 `functools` | Typed subset implementation | `cache`, `lru_cache`, statistics, clearing, `reduce`, `cmp_to_key`, `partial`, `wraps`, `update_wrapper` | Typed callables and supported value/key types |
| 🟡 `operator` | Adapted CPython | Operator functions, `itemgetter`, `attrgetter`, `methodcaller` | Getters specialize on literal items and names |
| 🟡 `contextlib` | Adapted CPython | `contextmanager` (also as a decorator), `closing`, `nullcontext`, `suppress`, `AbstractContextManager`, `ContextDecorator` | No `ExitStack`, `redirect_stdout`, `chdir` or async managers; positional `nullcontext(value)` |

### Numbers and randomness

`math` is a compiler builtin; see its
[functions and limits](../docs/language/modules.md#builtin-modules-and-files).

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `random` | Adapted CPython on a subset `_random` (`_pyrandom`) | Seeded `Random` and module functions, integers, sequences, distributions, state | Int, bool and float seeds; 63-bit `getrandbits`; no subclasses |
| 🟡 `statistics` | Adapted CPython | `fmean`, geometric mean, medians, quantiles, mode, `covariance`, `linear_regression`, `correlation` (of floats) | Selected numeric types and APIs; `kde` now passes its `match` dispatch but still needs heterogeneous function storage |
| 🟢 `colorsys` | Unchanged CPython | All conversion functions | Subset string and type rules apply |
| 🧪 `mpz` | Experimental subset wrapper over the shared native bigint core | Explicit arbitrary-precision arithmetic, comparisons, decimal text, hashing and typed containers | Default `int` is checked 64-bit; [promoting ints](../docs/python-int.md) are a separate opt-in. See [API and limits](../docs/mpz.md) |

### Dates and times

The builtin `time` module has `time()`, `monotonic()`, `perf_counter()`, `process_time()`,
their `_ns` forms and `sleep()`.

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `datetime` | Adapted CPython (`_pydatetime`, following `_datetime`) | `timedelta`, `date`, `time`, `datetime`, fixed-offset `timezone`, `tzinfo` subclasses, ISO 8601, `strftime()` | No local time zone; no `strptime()` or pickling |

### Files, OS and command line

`sys`, `os`, `os.path`, `tempfile`, `errno` and `select` are compiler builtins with
[selected APIs](../docs/language/modules.md#builtin-modules-and-files). The
[POSIX select guide](../docs/select.md) describes `select.select()` on integer descriptor lists,
which a file's `fileno()` gives; other `select` APIs remain unsupported.

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `io`, `_io` | Subset implementation; `_io` (`_pystachy__io`) gives its names under the C module's | `StringIO` and `BytesIO` (also in `with`), seek constants and `TextIOWrapper` over binary buffer objects, with CPython's chunked reads and writes; `IncrementalNewlineDecoder` of `str` input, `text_encoding()`, `open`, `BlockingIOError` and `DEFAULT_BUFFER_SIZE` | Lazy line iteration; no `getbuffer()` or `readinto()`; `TextIOWrapper` of UTF-8, Latin-1 and ASCII, without `seek`/`tell`/`detach`/`reconfigure`; `open()`'s [binary files](compatibility.md#binary-files) are `_io`'s `FileIO` and `Buffered*` classes, which are not names of `io`, and there is no `open_code()` |
| 🟡 `stat`, `posixpath`, `genericpath` | Unchanged CPython | Mode tests and string path operations | Partial API coverage |
| 🟡 `argparse` | Subset implementation | `ArgumentParser` with literal declarations, typed result fields, help and errors | Fixed schemas only. See [supported forms](compatibility.md#argparse) |
| 🟢 `getopt` | Adapted CPython | `getopt`, `gnu_getopt`, `GetoptError` | `longopts` must be `list[str]`; untranslated messages |
| 🟡 `pathlib` | Subset implementation of CPython's package, for POSIX | `PurePath`, `PurePosixPath`, `Path` and `PosixPath`: joining, parts, names and suffixes, `with_*()`, `relative_to()`, `match()`, comparisons; `exists()`, `is_dir()`, `is_file()`, `read_text()`, `write_text()`, `open()`, `iterdir()`, `glob()`, `rglob()`, `mkdir()`, `touch()`, `unlink()`, `rmdir()`, `rename()`, `replace()`, `absolute()`, `resolve()`, `expanduser()`, `cwd()`, `home()` | At most eight segments per constructor call; `open()` and `os` take `str(path)`; no Windows paths, `stat()` or binary I/O; see [limits](compatibility.md#pathlib) |
| 🟡 `glob` | POSIX subset | `glob()` and `iglob()` on text paths (`root_dir`, `recursive`, `include_hidden`); `escape()` and `has_magic()` on text and bytes | No `dir_fd` or `translate()`; see [limits](compatibility.md#glob) |
| 🟡 `shutil` | Subset implementation | `copyfileobj()`, `copyfile()`, `copymode()`, `copy()`, `move()`, `rmtree()`, `Error`, `SameFileError` | No `copytree()`, `copy2()`, archives or `which()`; see [limits](compatibility.md#shutil) |

### Processes and threads

`multiprocessing`, `subprocess` and `asyncio` are not shipped; a program runs on one thread,
which `threading` and `_thread` describe.

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `_thread` | Subset port of CPython's C module for one thread (`_pystachy_thread`) | `allocate_lock`, `LockType`, `RLock` (with `_is_owned`, `_release_save`, `_acquire_restore`), `get_ident`, `get_native_id`, `stack_size`, `interrupt_main`, `exit`, `TIMEOUT_MAX`, `error`, `_local` as a base class | One thread: `start_new_thread()` raises `NotImplementedError`, and an acquire that would wait for ever raises `RuntimeError` |
| 🟡 `threading` | Adapted CPython on the one-thread `_thread`, compiled with [dynamic `Any`](../docs/dynamic-any.md) | Locks, reentrant locks, `Condition`, semaphores, `Event`, `Barrier`, `Timer`, `local`, `current_thread()`, `main_thread()`, `enumerate()` and `Thread` objects and subclasses, as in CPython where no other thread runs | `Thread.start()` raises `NotImplementedError`; see [limits](compatibility.md#threading) |
| 🟡 `atexit` | Subset port of CPython's C module (`_pystachy_atexit`) | `register` (also as a decorator, with arguments), callbacks run at the end of the program, also after `sys.exit()` or an uncaught exception; `_run_exitfuncs`, `_clear`, `_ncallbacks` | No `unregister`; a failing callback's report shows the exception's last line |

### Runtime services

`typing`, `dataclasses` and `collections.abc` are compiler support; see
[typing](../docs/language/typing.md).

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🟡 `gc` | Subset port of CPython's C module (`_pystachy_gc`), on the collector's entry for `collect()` | `collect()`, `enable()`, `disable()`, `isenabled()`, `set_threshold()`, `get_threshold()`, `set_debug()`, `get_debug()`, `freeze()`, `unfreeze()` and the `DEBUG_*` flags | The settings are kept and reported, and change nothing: one collector reclaims all memory. `collect()` returns 0. No `get_objects()`, `get_stats()`, `callbacks` or `garbage`; see [limits](compatibility.md#gc) |
| 🟡 `abc` | Subset implementation (`_pystachy_abc`) | `ABC`, `metaclass=ABCMeta`, `@abstractmethod` (also under `@property`, `@classmethod`, `@staticmethod`) and the deprecated `abstractproperty`, `abstractclassmethod`, `abstractstaticmethod`, with CPython's `TypeError` for a class with abstract methods; `get_cache_token` | No virtual subclasses (`register()`), `__subclasshook__` or `__abstractmethods__` |
| 🧪 `logging` | Adapted CPython (`logging/__init__.py`), compiled with dynamic `Any` | Loggers and their hierarchy, levels, the module's functions, `basicConfig()`, `Formatter` (`%`, `{}` and `$` styles, `asctime`), `extra`, `exc_info`, filters, `StreamHandler`, `FileHandler`, `NullHandler`, the last resort handler and `handleError()` | No frames or tracebacks (the caller is unknown); arguments are `Any` values; no `logging.config`, `logging.handlers` or `LoggerAdapter`; see [limits](compatibility.md#logging) |
| 🟡 `traceback` | Subset implementation | `format_exception()`, `print_exception()`, `format_exc()`, `print_exc()`, `format_exception_only()` (also of the legacy `(type, value, tb)`), with causes; empty stacks | No tracebacks or frames: an exception formats as one whose `__traceback__` is `None`; see [limits](compatibility.md#traceback) |
| 🟡 `types` | Subset implementation (`_pystachy_types`, `_pystachy_mappingproxy` and the compiler's `_pystachy_typenames`) | `TracebackType`, for `__exit__`'s annotation; `MappingProxyType`, a read-only live view of a dict (indexing, `in`, `len()`, iteration, `get`, `keys`, `values`, `items`, `copy`, `==`, `\|`, `repr()`); `GenericAlias`, for CPython's idiom for a generic class: `__class_getitem__ = classmethod(GenericAlias)` in a class body, whose subscripts in annotations name the class | Its other names import, but any use of one is a compile-time error; a generic-alias class's subscripts at run time are too; `MappingProxyType` takes a dict |
| 🟡 `warnings` | Adapted CPython | `warn`, `warn_explicit`, the filters (`simplefilter`, `filterwarnings`, `resetwarnings`, `sys.warnoptions`) and their actions, `catch_warnings` (also `record=True`), `formatwarning`, `showwarning`, with the registries of CPython's C module | `warn()` shows a warning at `<sys>:0`, with no source line; `showwarning` cannot be replaced; no `deprecated`; see [limits](compatibility.md#warnings) |
| 🧪 `_weakref` | Experimental collector-backed subset (`_pystachy_weakref`) | `ref`/`ReferenceType` of ordinary class instances: call, `==`, `!=`, `hash()`, `repr()` and callbacks as CPython's, though referents die at collection rather than at the last reference, and callbacks run after it | No `__callback__`, proxies, reference counts or weak containers; see [contract](../docs/weakref.md) |
| 🧪 `weakref` | Adapted CPython, on `_weakref` | `ref` and `ReferenceType`, also by from-imports and `import *` | `WeakSet`, `WeakValueDictionary`, `WeakKeyDictionary` and `WeakMethod` are compile-time errors where used; no `finalize`, proxies, `getweakrefcount()` or `getweakrefs()`; see [limits](compatibility.md#_weakref-prototype) |

### C and CPython interop

`ffi` is the compiler's interface to C; see the [FFI guide](../docs/ffi.md).

| Module | Origin | Supported APIs | Main limitation |
|---|---|---|---|
| 🧪 `ctypes` | Static declaration lowering over `ffi`, with Python pointer-cell helpers | Literal `CDLL`, immutable `argtypes`/`restype`, selected scalar types, bytes, opaque pointers, `byref(c_void_p)`, `string_at` | Fixed positional calls; no structures, callbacks or dynamic signatures. [Contract and llvmlite consumer](../docs/ffi.md#static-ctypes-declarations) |
| 🧪 `pyobj` | Subset implementation over CPython's stable ABI (`@ffi.extern`), with its twin in `tools/rt_cpython` | Python objects through an embedded CPython, or an extension module's host: `Object`, `import_module`, `of_int`, `of_float`, `of_str`, `of_list` | Needs `PYSTACHY_LIBPYTHON` (CPython 3.12+); scalar conversions only; see [FFI](../docs/ffi.md#calling-cpython) |

CPython VM adapters `opcode`, `_opcode`, `_imp` and `_ast` are not shipped; see the
[library scope](../docs/stdlib.md#library-scope).

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
| `tomllib` | `Lib/tomllib/__init__.py` | `71f67036895f4c5acab942618af0cbd3d814451ba61e967f358d0f341a5b8f51` | The package: `loads`, `load` and `TOMLDecodeError`, whose `__module__` it assigns; its other modules are adapted, see [provenance](provenance.md). |
| `struct` | `Lib/struct.py` | `9c231f9497caf513a22dee8f790b07f969b0e45854a0bdd6dd84b492e08c2856` | Its names, on `_pystachy_struct`; see [limits](compatibility.md#struct). |
| `_weakrefset` | `Lib/_weakrefset.py` | `91895a451d06e9f521a1171b31b9b19bc9740f35af00d4fa106338ab7167c9ac` | What `weakref` imports from it; `WeakSet` itself is not supported, see [limits](compatibility.md#_weakref-prototype). |

`curses/__init__.py` is a Pystachy stand-in for the package that normally imports
`_curses`; it does not provide terminal control.

`_pystachy_binascii.py` is `binascii`, `_pystachy_codecs.py` is `_codecs`, `_pystachy_atexit.py` is
`atexit`, `_pystachy_struct.py` is `_struct`, `_pystachy_thread.py` is `_thread`,
`_pystachy_unicodedata.py` is `unicodedata`, `_pystachy_itertools.py` is `itertools`,
`_pystachy__io.py` is `_io`, `_pystachy_gc.py` is `gc`, modules CPython builds into its interpreter: Pystachy loads those
files for `import binascii`, `import _codecs`, `import atexit`, `import _struct`, `import _thread`,
`import unicodedata`, `import itertools`, `import _io` and `import gc`, where CPython imports its C modules.
`tools/unicodedata_tables.py` writes the tables of `unicodedata`, `_pystachy_unicodedata_db.py` and
`_pystachy_unicodedata_names.py`, from CPython's own module.
`_pystachy_abc.py` is `abc`, which CPython imports as it starts, so that a program's own `abc.py`
is never imported there. `_pystachy_bfile.py` holds the binary files that `open()` of a binary mode makes
(the compiler imports it where a module calls `open()` so: loader.py's `binary_opens`). `types.py` binds `TracebackType` from `_pystachy_types.py`, `MappingProxyType`
from `_pystachy_mappingproxy.py` and CPython's other names of `types` from `_pystachy_typenames`, the
compiler's, which only it may import. `_collections_abc` has no file here: it is the compiler's builtin
`collections.abc`, as CPython's `collections` makes it `collections.abc`.

`_pystachy_iterators.py` holds the iterator classes of `iter()` over builtin containers
(`list_iterator`, `dict_keyiterator`, ...). The compiler loads it for a program that calls
`iter()`; programs do not import it. See [iterators](../docs/language/semantics.md#iterators). In
a program where a module opts in to [promoting ints](../docs/python-int.md), its classes read a
container's ints as that module does (`specs.READ_HELPERS`).

`_pystachy_range.py` holds the class of range objects, `range()` as a value. The compiler loads
it for a program that may use one, a read of the builtin `range` other than a `range(...)` that a
loop or a consumer steps through (its methods are compiled where a program calls them); programs
do not import it. See [range objects](../docs/language/semantics.md#range-objects).

`_pystachy_object.py` holds the class of the objects that `object()` makes, sentinels. The compiler
loads it for a program that may call `object()`; programs do not import it. See
[sentinels](../docs/language/semantics.md#sentinels).

`_pystachy_json_any.py` holds `json.loads()` and `json.dumps()` of `Any` values: the decoder builds
`Any`'s containers with `json`'s scanner, and the encoder walks `Any` values as CPython's does. The
compiler loads it for a program that has `json` and a module that opts in to
[dynamic `Any`](../docs/dynamic-any.md), and calls it in such a module where the document is `Any`
values (#779); programs do not import it. Its `_pystachy_json_int.py` helper promotes
overflowing integer tokens without promoting the shared scanner's indices.

`_pystachy_percent.py` is printf-style formatting of a format string that only the run time
knows, `fmt % args` as CPython's `PyUnicode_Format()` formats it, of `Any` values: `logging`
formats its messages and `%`-style formats with it (the compiler formats a literal format string
itself). `_pystachy_time.py` gives `time.strftime()` of `time.localtime()` (or `time.gmtime()`)
of a time, through the C library, for `logging`'s `asctime`; Pystachy's `time` module has no
`localtime()` or `strftime()`. Programs do not import either.

`_pystachy_bytescan.py` provides a bounded byte-span helper for native parsers.
It finds either of two delimiter bytes or a byte below a threshold, returning the
range end on a miss. JSON uses it past the first 32 bytes of a string value in a text
longer than 1 KiB, and for the spans that follow a long run and an escape, for both
recursive typed values and dynamic `Any`. Direct positional
calls of the shipped helper use portable eight-byte scanning; other call forms
and CPython retain its scalar implementation. It adds no method to `bytes` and
does not change decoding, Unicode positions or repair heuristics.

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

