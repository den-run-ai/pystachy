# Library compatibility

This reference describes compiled behavior. The adapted sources may expose more
APIs when CPython runs them, because optional imports select CPython's C modules
and dynamic features. Differential cases live in `tests/programs/library/lib_*.py`; deliberate
differences live in `tests/deviations/`, and rejected inputs in `tests/errors/`.

For shared numeric, container, Unicode and resource-lifetime limits, see
[language compatibility](../docs/language/compatibility.md).

Sections follow the areas of the [library support table](../docs/stdlib.md#library-support-at-a-glance);
the [module guide](README.md#module-guide) summarizes what each module supports.

| Area | Modules |
|---|---|
| [Across modules](#across-modules) | [CPython-only code](#cpython-only-code), [Pure-Python accelerators](#pure-python-accelerators), [Module docstrings](#module-docstrings) |
| [Text](#text) | [`textwrap`](#textwrap), [`unicodedata`](#unicodedata), [`shlex`](#shlex), [`keyword`](#keyword), [`curses.ascii`](#cursesascii), [`string`](#string), [`difflib`](#difflib), [`gettext`](#gettext) |
| [Regular expressions](#regular-expressions) | [`re`](#re), [`fnmatch`](#fnmatch) |
| [Data formats and markup](#data-formats-and-markup) | [`json`](#json), [`tomllib`](#tomllib), [`csv`](#csv), [`html` and `html.parser`](#html-and-htmlparser), [`urllib.parse`](#urllibparse) |
| [Binary data and encodings](#binary-data-and-encodings) | [`struct`](#struct), [`binascii`](#binascii), [`codecs`](#codecs) |
| [Collections and functional tools](#collections-and-functional-tools) | [`collections`](#collections), [`copy`](#copy), [`enum`](#enum), [`heapq`](#heapq), [`itertools`](#itertools), [`functools`](#functools), [`operator`](#operator), [`contextlib`](#contextlib) |
| [Numbers and randomness](#numbers-and-randomness) | [`random`](#random), [`statistics`](#statistics), [`mpz`](#mpz) |
| [Dates and times](#dates-and-times) | [`datetime`](#datetime) |
| [Files, OS and command line](#files-os-and-command-line) | [`io`](#io), [Binary files](#binary-files), [Path modules](#path-modules), [`pathlib`](#pathlib), [`glob`](#glob), [`shutil`](#shutil), [`argparse`](#argparse), [`getopt`](#getopt) |
| [Processes and threads](#processes-and-threads) | [`_thread`](#_thread), [`threading`](#threading), [`atexit`](#atexit) |
| [Runtime services](#runtime-services) | [`abc`](#abc), [`types`](#types), [`warnings`](#warnings), [`logging`](#logging), [`traceback`](#traceback), [`weakref` and `_weakref` (prototype)](#weakref-and-_weakref-prototype) |
| [Native interoperability](#native-interoperability) | [`ctypes`](#ctypes) |
| [Removed modules](#removed-modules) | `_imp`, `_ast`, `opcode` |

## Across modules

### CPython-only code

Ports keep code that only CPython can run, as CPython's sources have it, under
`if sys.implementation.name == "cpython":`. Pystachy decides that test at compile time, as its
`sys.implementation.name` is `"pystachy"`, and drops the block (see
[compile-time branches](../docs/language/modules.md#compile-time-branches)): `urllib.parse`'s
imports of `warnings` and `ipaddress`, its docstrings of the result fields and its
byte tables, and `statistics`' import of `random` and table of kernels.

### Pure-Python accelerators

`bisect`, `heapq`, `operator` and `stat` execute their Python implementations
when the C accelerators cannot import; `heapq`'s heap functions follow `_heapq`'s
C code instead ([below](#heapq)). Consequently, edge behavior can differ
from CPython's accelerated modules:

- Some keyword arguments rejected by C functions are accepted by Python functions.
- `bisect` treats `hi=-1` as a bound; `_bisect` treats it as `len(a)`.
- `stat` tests use the module's constants rather than `_stat`'s separate constants.
- `operator.__doc__` is the Python module's docstring, which CPython replaces with
  `_operator`'s.

### Module docstrings

A module's `__doc__` is its docstring, as in CPython, but for the modules written for
Pystachy: `collections`, `curses`, `functools` and `io` have docstrings of their own.

## Text

### `textwrap`

`TextWrapper` and `wrap`, `fill`, `shorten`, `dedent`, `indent` support upstream
options, mutable wrapper options and overridable class attributes. Regex work
uses `lib/re`.

Widths, long-word splitting and tab expansion count Unicode code points.
`unicode_whitespace_trans` must map ints to ints,
with no string or `None` replacements; custom tables are looked up by code point. Mutated and
custom tables retain their semantics when whitespace fast paths do not apply.
`TextWrapper` subclasses are unsupported.

### `unicodedata`

`unicodedata` is `_pystachy_unicodedata`, a port of CPython's C module `unicodedata`
(`Modules/unicodedata.c`) that Pystachy loads for `import unicodedata`, on CPython 3.13.16's
tables of Unicode 15.1.0, which `tools/unicodedata_tables.py` takes from CPython's module and
writes into `_pystachy_unicodedata_db.py` and `_pystachy_unicodedata_names.py`. Every function
works as CPython's does, with its errors and messages: `category()`, `bidirectional()`,
`combining()`, `mirrored()`, `east_asian_width()`, `decomposition()`, `decimal()`, `digit()` and
`numeric()` (with or without a default), `name()`, `lookup()`, which also takes the aliases,
named sequences and derived names (Hangul syllables, CJK and Tangut ideographs) in any case,
`normalize()` and `is_normalized()` in the four forms, and `ucd_3_2_0`, the database of
Unicode 3.2.0 that `stringprep` and the IDNA codec read. A function's character is the one code
point that its `str` argument's UTF-8 encodes, and its results use the same UTF-8 storage.
String lengths and iteration count code points (see the [language
reference](../docs/language/compatibility.md#text-and-file-positions)).

- `lookup()` takes a `str`; `bytes`, which CPython's also takes, is a compile-time error.
- `unicodedata._ucnhash_CAPI`, the capsule through which CPython's `\N{...}` escapes find
  names, is not there.
- The tables, about 850 KB of source, are compiled into each program that imports
  `unicodedata`: they add about 1 MB of IR and 0.4 s to a `pystachy run`. A function decodes
  the table it reads the first time it reads it, into a few lists of ints.

### `shlex`

`split`, `quote`, `join` and the lexer support POSIX/compatibility modes, comments,
quotes, escapes, whitespace splitting, punctuation, token pushback and source
stacking. Input text is read through `StringIO`; Unicode characters are read whole.

Files are read eagerly. Pushed files are closed on push rather than on source
pop; constructor files remain the caller's responsibility. Iteration and `next()` read
one token at a time from a shared position. `punctuation_chars` is writable;
its constructor accepts bools or strings, while lists fail compilation. Lexer
subclasses and arbitrary stream types are outside the compiled surface.

### `keyword`

`kwlist`, `softkwlist`, `iskeyword` and `issoftkeyword` use CPython 3.13.16's
keyword sets. Predicates accept positional strings or `None`; other input types
fail compilation. Membership uses frozen snapshots, so changing the public lists
does not change the predicates.

### `curses.ascii`

`curses.ascii` supports its ASCII character predicates and conversions. `curses` itself is a
Pystachy stand-in for the package that imports `_curses`; it does not provide terminal control.

### `string`

Constants, `capwords` and `Template` work. Templates support mapping inputs
(dicts or objects with `__getitem__`), keyword arguments or both; keywords take
precedence. `substitute`, `safe_substitute`, `is_valid` and `get_identifiers`,
plus the template and pattern attributes, are available.

Template subclasses are unsupported. Keyword values of different types, as in
`substitute(name="Ann", count=3)`, are looked up as values of their union type.
`Template.flags` is an int, and `capwords` capitalizes ASCII letters only.

`Formatter` supports `format`, `vformat`, `parse`, `get_field`, `get_value`,
`check_unused_args`, `format_field` and `convert_field`, and subclasses that
override them. `lib/_pystachy_string.py` implements the parsers of CPython's
`_string`, with its errors; `parse()` returns a list, so a malformed format string
raises before its first field is looked up. Automatic and manual numbering,
conversions, nested format specs and recursion limits follow CPython.
Positional arguments may have different types (as may keyword ones): a field's
value has their union type, which formats as its value does, also where a call has
both: `format("{0} {x}", 1, x="s")` gives `'1 s'`.
`vformat` takes a tuple and a dict, or a `**kwargs` record; type an empty dict.

Field names with attributes or indexes (`{0.x}`, `{0[1]}`) raise `ValueError`, but
`Formatter().format()` of the base class with a constant template whose fields read
attributes, and positional arguments only, formats as `str.format()` of that template does,
which reads the attributes ([reflection](../docs/language/semantics.md#reflection)); a
loop over a constant list of such templates unrolls. `check_unused_args` receives the keys used as a list in first-use order
rather than a set. Overrides compile for every call's argument types in the
program; an override, like other functions, must return one type for each.
Only ASCII digits make positional field names; the field parser does not recognize
Unicode decimal digits.

### `difflib`

`SequenceMatcher` accepts strings or lists of strings, including `isjunk` and
`autojunk`. It provides sequence setters, longest-match and matching-block
queries, opcodes, and the three ratio methods. `get_close_matches`, `Match`,
`IS_CHARACTER_JUNK` and `IS_LINE_JUNK` also work.

Items of other types are rejected. The generators `get_grouped_opcodes()`, `unified_diff()`,
`context_diff()` (with file names, dates, `n` and `lineterm`) and `restore()` work.
`context_diff()` uses a dictionary literal for its fixed prefix table instead of `dict()`
keyword arguments; the upstream generator and grouping algorithm are unchanged.
`tests/programs/upstream/upstream_difflib_context.py` checks selected CPython output-format
assertions and empty, insertion, deletion, replacement, grouping and Unicode cases.
`ndiff()` and `Differ.compare()` still fail because their recursive `_fancy_helper()`
generator yields a type the compiler cannot infer; `HtmlDiff`'s class attribute types
also remain unsupported.

### `gettext`

CPython's `gettext`, with marked edits. Its table of the plural forms' operators is the dict that
CPython makes of a tuple bound to the same name first, as a module global has one type here. Its default locale directory
is made of `sys.base_prefix` (the Pystachy home, see
[sys](../docs/language/compatibility.md#modules-and-libraries)). `NullTranslations` and its
methods `gettext()`, `pgettext()`, `add_fallback()`, `info()` and `charset()`, `textdomain()` and
`bindtextdomain()` work. `optparse` still stops here, as it calls `gettext()` while it is imported.

Its other edits are annotations: the types of `NullTranslations`' fields, which it fills none of,
and the return types of its methods that a fallback's own call answers.

Not supported, as compile-time errors:
- The functions that look up a catalog: `gettext()`, `dgettext()`, `ngettext()`, `translation()`,
  `install()` and the like. `_localedirs` has a type only where `bindtextdomain()` fills it.
  `translation()` imports `locale`, which does not compile, and keys its cache by the
  translations' class, which is not a value here (#7).
- `NullTranslations.ngettext()` and `npgettext()`. They take the count through `operator.index()`,
  which `lib/operator.py` does not apply to an `int`, and for a count of another type find the
  frame to warn from with `sys._getframe()`, which is not supported.
- `GNUTranslations` of a catalog with a plural form, which calls `c2py()`: it needs `exec()`.
- A subclass of `NullTranslations`, such as a translation class to add as a fallback.
  `__init__`'s `fp`, a catalog file, has no concrete type here, so `NullTranslations` is a
  template class, which a class cannot derive from. `add_fallback()` takes another
  `NullTranslations`, which answers as the identity.

## Regular expressions

### `re`

String patterns support CPython 3.13 syntax: character classes, repeats (greedy,
lazy and possessive), groups and backreferences, lookarounds, conditionals,
atomic groups, scoped flags, escapes and Unicode character classes/case folding.
The module and `Pattern` expose matching, searching, splitting, substitution,
escaping and cache purging. `Match` supports group queries (up to five groups
per `group` call), runtime-length `groups(default=None)` tuples, indexing,
dictionaries, positions, spans and expansion. `re.Pattern[str]` and `re.Match[str]` annotate
patterns and matches, as CPython's generic `_sre` types do
([test](../tests/programs/library/lib_re_annotations.py)).

- Matches, bounds (`pos`, `endpos`), group spans and pattern-error positions count
  Unicode code points. Invalid UTF-8 input retains the runtime's permissive behavior;
  strict decoding remains outside this guarantee.
- `findall` with two or more groups still raises `NotImplementedError`; its
  ported result contract remains `list[str]`. `Match.regs` remains unsupported
  because its runtime-length tuple contains tuple elements.
- `split` returns `list[str]` and raises `NotImplementedError` if an unmatched
  capturing group would add `None`.
- `finditer` eagerly returns a list of matches.
- `\N{...}` is a pattern error; character-name lookup is unavailable.
- Flags are ints, `groupindex` is a dict, and `re.error` is the base of
  `PatternError` rather than the same class. Replacement callbacks must return
  strings. Bytes patterns, warnings, `DEBUG` output, `Scanner` and `__index__`
  group numbers are unavailable.

`purge` clears pattern, replacement-template and last-input decoding caches.
An input whose every byte is a code point (ASCII, or raw bytes) is read in place, as
CPython's `_sre` reads a 1-byte string: it is not decoded or cached. Another input's
decoded code points stay cached for the next call on it, but
`findall`, `finditer`, `split`, `sub` and `subn` drop a decoding they made of an
input longer than 1,048,576 code points once they return. Bounded `findall` and `finditer` calls
whose `endpos` precedes the input's end keep it, as do caches that `match` or
`search` made, so loops over advancing windows reuse their decoded prefixes.
Active operations retain their decoded input, so callbacks can safely purge;
existing patterns and matches remain usable. Character-class tables and search
strategies belong to their pattern and preserve scoped case folding and Unicode fallback.

### `fnmatch`

`fnmatch`, `fnmatchcase`, `filter` and `translate` accept strings. Translation
follows CPython's regular expressions, including Unicode ranges. Matching uses
`lib/re`'s code-point handling, and `_compile_pattern` uses a 32,768-entry typed
LRU cache with CPython-compatible statistics. Case normalization is POSIX's
identity operation. Bytes patterns are unsupported.

## Data formats and markup

### `json`

The native prototype implements `loads(s: str) -> JSONValue` and
`dumps(obj: JSONValue, *, ensure_ascii=True, allow_nan=True, sort_keys=False,
separators=None) -> str`. `JSONValue` is the closed recursive union of `None`,
bool, int, float, str, lists of itself and string-keyed dicts of itself.
`separators` is a two-string tuple when supplied. This is native recursive
storage, not general runtime `Any` or a CPython bridge.

The codec supports mixed nested values, Unicode escapes and surrogate pairs,
lone surrogates, last-key-wins duplicate keys and CPython's default nonfinite
float forms (`NaN`, `Infinity`, `-Infinity`). `allow_nan=False` rejects those
values when encoding. `JSONDecodeError` derives from `ValueError` and exposes
`msg`, `doc`, `pos`, `lineno` and `colno`; positions count Unicode characters.
Narrowing parsed lists/dicts preserves identity and shared mutation. Encoding
checks active ancestors for cycles and raises `ValueError` for them; repeated
references without a cycle serialize normally.
The existing unboxed-NaN identity deviation also applies: separately decoded
`[NaN]` lists compare unequal, whereas CPython's cached NaN can make them equal.

The typed `JSONValue` path and public `JSONDecoder` methods reject integer tokens
outside signed 64-bit range with `OverflowError`. Dynamic `Any` decoding promotes
larger tokens, with a 4,300-digit conversion limit that raises `ValueError`. Nested
containers count against `sys.setrecursionlimit()` and stop at 2,000 under a raised limit,
beyond which the codec raises `RecursionError`; CPython's C codec accepts 9,998 at any limit
([deviation](../tests/deviations/json_limits.py)).
Text that Pystachy reads from a file, `input()` or `sys.argv` can hold bytes that
are not UTF-8, which CPython rejects or escapes as it reads them. `loads()` counts
each byte that starts no UTF-8 sequence as one character, as `str` does, in values
and error positions ([deviation](../tests/deviations/json_invalid_utf8.py)).
The default `JSONDecoder.decode()` and `raw_decode()` are supported with typed
`JSONValue` storage. Bytes input, file APIs, configured decoder constructors,
encoder classes, hooks, `strict` and indentation remain unsupported. Typed
`JSONValue` excludes non-string object keys, tuples, `default`, `skipkeys` and
`check_circular`; the dynamic `Any` encoder supports those. Existing typed containers are not implicitly converted to
recursive mutable storage. `ensure_ascii=False` returns non-ASCII and surrogate
characters unchanged; writing that string follows the runtime's text-encoding
rules. See the [native JSON API and representation](../docs/json.md).

### `tomllib`

`tomllib` is CPython 3.13.16's `Lib/tomllib` with the edits below, each marked `Pystachy port:`.
Its modules opt in to [dynamic `Any`](../docs/dynamic-any.md), so `loads(s, *, parse_float=float)`
returns a dict of dynamic values, of the types CPython's `tomllib` gives them: tables are dicts,
arrays are lists, and strings, ints, floats, bools and `datetime`, `date` and `time` objects keep
their types. A program that does not opt in reads them as such values: indexing, iteration,
comparisons, arithmetic and printing work, and `isinstance()` or an annotation
(`name: str = doc["project"]["name"]`) gives typed code a concrete value
([test](../tests/programs/library/lib_tomllib.py)). `TOMLDecodeError` has CPython's messages, and an
uncaught one's line names it `tomllib.TOMLDecodeError`
([test](../tests/programs/library/lib_tomllib_uncaught.py)). The 62 documents of CPython's
`Lib/test/test_tomllib/data`, and the assertions of its `test_error.py` and `test_misc.py` that
need no binary file, `decimal`, `copy` or `test.support`, are in the differential suite
([data](../tests/programs/upstream/upstream_tomllib_data.py),
[errors and limits](../tests/programs/upstream/upstream_tomllib_misc.py)).

- `load(fp)` reads a binary file, whose `BinaryIO` annotation is a compile-time error (a
  [binary file](#binary-files) of `open()` has no `typing` type here). Read the file as text and
  call `loads(f.read())`, which CPython runs too.
- The values have dynamic `Any`'s [deviations](../docs/dynamic-any.md#deviations): an
  annotation that receives a value of another type raises `TypeError`, and `keys()`, `values()`
  and `items()` give lists.
- `parse_float` is a function of one `str`, whose result is the value. One that returns a typed
  `dict` or `list` is a compile-time error (a typed container cannot become an `Any` value); one
  that returns an `Any` dict or list raises CPython's `ValueError`.

The edits: the three modules that use `Any` hold the comment `# pystachy: dynamic-any`.
`_parser.py` annotates tables `dict[Any, Any]` where CPython writes `dict[str, Any]`, and makes an
empty table with a function, `_new_table()`, where CPython writes `{}`, as a typed or empty dict
does not become an `Any` value yet ([#777](https://github.com/den-run-ai/pystachy/issues/777));
keeps `Flags`'s private tree in typed `_FlagEntry` nodes with `set[int]` flags and
`dict[str, _FlagEntry]` children, instead of dynamic dictionaries with known field names.
Pending flags remain in a list, as a set's tuples do not hold a runtime-length tuple yet
([#783](https://github.com/den-run-ai/pystachy/issues/783)); and declares the variable that
`parse_basic_str()` gives one of two functions,
`Callable[[str, Pos], tuple[Pos, str]]`, as each function is a type of its own. `_re.py` asserts that
an offset's hour and minute groups matched, which its pattern ensures, and passes
`str(match.group())` to `parse_float`, as a group is a `str | None`.

The typed flag tree preserves recursive freezing, duplicate pending flags and
array-of-tables subtree resets. It changes private storage, not returned tables
or callback values. The [public flags regression](../tests/programs/library/lib_tomllib_flags.py)
and [callback/alias regression](../tests/programs/library/lib_tomllib_boundary.py)
cover those boundaries. Module-wide numeric identity tracking still follows the
existing import policy; typed state alone does not make the parser identity-free.

### `csv`

The module provides `reader`, `writer`, `DictReader`, `DictWriter`, `Dialect`,
the six `QUOTE_*` constants, `Error`, dialect registration and lookup, and
`field_size_limit`. Default dialect objects are `excel`, `excel_tab` and
`unix_dialect`, registered as `excel`, `excel-tab` and `unix`. `Sniffer` is absent.
Readers accept supported iterables of strings, including files and stdin;
writers accept objects with `write`. Format parameters follow CPython:
`delimiter`, `quotechar`, `escapechar`, `doublequote`, `skipinitialspace`,
`lineterminator`, `quoting` and `strict`.

Writer fields may be strings, integers, floats, booleans, `None`, or objects
converted with `str`. A tuple row may mix types; a list row must be homogeneous.
`writerow` returns the result of the output object's `write`.

- A reader and `next(reader)` parse one record at a time, update `line_num` as input
  is consumed, and retain their position after an early loop exit.
- Reader rows are `list[str]`. `QUOTE_NONNUMERIC` and `QUOTE_STRINGS` raise
  `NotImplementedError` at construction; `QUOTE_NOTNULL` raises it when a row
  would contain `None`. Writers support all six quoting styles.
- `DictReader` rows are `dict[str, str]`. Extra fields and missing fields with
  `restval=None` raise `NotImplementedError`. It reads data and the header at
  construction, so errors are immediate and `line_num` initially names the
  header. Later `fieldnames` assignments rename rows after the header.
  `fieldnames` is `list[str] | None`; `restkey` and `restval` are `str | None`.
- A `DictWriter`'s `restval` is `str | None`. Its error for extra keys lists
  them in dict order, rather than CPython's set order.
- Dialects are objects, rather than classes. Use registered names or keyword
  settings instead of dialect subclasses. Dialect fields are writable: writers
  snapshot settings at construction; readers use settings when each record starts.
  `dialect=` accepts a registered name, `Dialect`, or `None`.
- Uncaught errors name `csv.Error`, rather than `_csv.Error`. A missing `write`,
  a format parameter of a user class, an unsupported iterable row type, or a
  NamedTuple row fails compilation. Integers, floats, bools and `None` passed
  as rows instead raise `csv.Error`. For `QUOTE_NONNUMERIC`, user objects are
  nonnumeric even if they define numeric conversion methods.

Dialect characters may be non-ASCII. Parsing decodes characters where required,
and `field_size_limit` counts characters, as CPython does.

<a id="html"></a>

### `html` and `html.parser`

`escape`, `unescape` and the HTML4/HTML5 entity mappings follow CPython 3.13.16, with the
adaptations merged in [#378](https://github.com/den-run-ai/pystachy/pull/378). Numeric references
produce Unicode text, including Latin-1 characters: they are bounded before checked-int
conversion, and oversized references are replaced according to HTML rules without requiring
arbitrary-precision integers. Named references use the upstream HTML5 table. Decimal conversion
keeps the default 4,300-digit limit; changing that limit with `sys` is unavailable. Caller
indexing, slicing and lengths count Unicode code points.

`html.parser.HTMLParser` retains CPython 3.13.16's incremental parser and uses
ordinary single inheritance. Typed subclasses can override the start/end tag,
data, comment, declaration, processing-instruction and reference callbacks.
`feed`, `close`, `reset`, `getpos`, `get_starttag_text`, `convert_charrefs` and
`scripting` are exercised by the probe tests, including RAWTEXT and RCDATA.
Attribute records use `list[tuple[str, str | None]]`; missing values remain None.

Column offsets count Unicode code points. Tag/attribute name case conversion uses
ASCII-only `str.lower`, so non-ASCII uppercase names can differ from CPython. User subclass
constructors and callback signatures need compatible annotations. Multiple inheritance
and dynamic attributes remain unavailable.

`_markupbase` is an internal implementation detail. Its abstract-construction
guard is omitted and its field layout is declared in `__init__`. Its legacy SGML
helpers remain in the source but are outside the compiled surface tested here.
See [the probe record](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/html-parser-probe.md) for provenance and commands.

### `urllib.parse`

String APIs include `quote`, `quote_plus`, `unquote`, `unquote_plus`, `parse_qs`,
`parse_qsl`, `urlencode`, `urlsplit`, `urlparse`, `urlunsplit`, `urlunparse`,
`urljoin`, `urldefrag` and `unwrap`. Query parsing supports blank values, strict
parsing, maximum field count and custom separators. Encoding accepts mappings
or list/tuple pairs, `doseq`, and a supported `quote_via` function.

Supported codecs are UTF-8, Latin-1 and ASCII, including their codec aliases.
Error modes are `strict`, `ignore`, `replace`, `backslashreplace`,
`xmlcharrefreplace`, `surrogateescape` and `surrogatepass`, where CPython permits
them. Decoding rejects `xmlcharrefreplace` and `namereplace` with `TypeError`;
encoding with `namereplace` raises `NotImplementedError`. Unknown handlers retain
CPython's `LookupError`. Other codecs raise `NotImplementedError`.

`SplitResult`, `ParseResult` and `DefragResult` are NamedTuples with fields,
indexing, unpacking, tuple equality, repr, `_replace` and `geturl`. Invalid IPv6
and bracketed hosts and netloc characters whose NFKC form contains `/?#@:` are
validated. Quoting/unquoting also accepts `str | None`, raising the corresponding
CPython error for `None`.

- Strict codec failures raise `UnicodeError` with the upstream message, rather
  than its `UnicodeEncodeError`/`UnicodeDecodeError` subclasses.
- A Pystachy string can contain invalid UTF-8 bytes. These are quoted byte for
  byte; Latin-1/ASCII treat a byte that begins no character as its numeric value.
- `urlsplit` uses the upstream 128-entry typed LRU cache, including default and
  keyword calls, `cache_info` and `cache_clear`. `clear_cache` also clears the
  adapted string-quote tables. Byte APIs remain unavailable.
- Result properties `username`, `password`, `hostname`, `port`, and `encode`
  are unavailable. Bytes inputs/results, `quote_from_bytes` and
  `unquote_to_bytes` are unsupported.
- `urlencode` needs a mapping or sequence; `doseq` sequences must be homogeneous.
  Sets use Pystachy's iteration order. `allow_fragments` must be a bool.
- Deprecated splitting functions, `to_bytes` and `Quoter` are unsupported.

## Binary data and encodings

### `struct`

`struct` is CPython 3.13.16's `Lib/struct.py`, unchanged, on `_pystachy_struct`, a port of the C
module `_struct` (`Modules/_struct.c`) that Pystachy loads for `import _struct`. The types of the
values `unpack()` gives depend on its format, so the compiler parses a format it knows as the
program compiles: a literal (a `str` or a `bytes`), a module's global bound once to a `str`
literal, as `zipfile`'s `structCentralDir` is, or the format of a `Struct` made of a literal. A
call of `pack()`, `unpack()`, `unpack_from()`, `iter_unpack()` or `calcsize()` with such a
format, by its name (`struct.pack(...)`, `pack(...)` after `from struct import pack`) or through a
`Struct`'s method, packs or unpacks each item with the port's functions. Every code of the native
and standard tables works, with the byte orders `@`, `=`, `<`, `>` and `!`, repeat counts,
whitespace, pad bytes and native alignment, and the values have the items' types: `int` for the
integer codes, `float` for `e`, `f` and `d`, `bool` for `?` and `bytes` for `c`, `s` and `p`. The
bytes, the values and the errors are the C module's on x86-64 Linux: `struct.error` with its
messages for a value out of its code's range, a buffer of the wrong size or an offset out of its
range, and `OverflowError` for a float too large for `e` or `f`. `calcsize()` and `Struct()`
also take a `str` the program makes as it runs, raising CPython's `struct.error` for an invalid
format.

- `pack()`, `unpack()`, `unpack_from()` and `iter_unpack()` of a format not known as the program
  compiles are compile-time errors ([error test](../tests/errors/library/lib_struct_dynamic.py)), and so
  are the methods of a `Struct` made of one, and `Struct()` of a `bytes` format.
- What CPython checks as `pack()` runs, the number of values for the format and the type of a
  value for its code (a `str` for `s`, a `float` for an integer code), is checked as the program
  compiles, with CPython's message ([error test](../tests/errors/library/lib_struct_arity.py),
  [another](../tests/errors/library/lib_struct_str.py)), and a value that may be `None` is a compile-time
  error but for `?`. So is a format CPython rejects in `unpack()`, `unpack_from()` and
  `iter_unpack()`; `pack()` and `calcsize()` of one raise CPython's `struct.error` as the
  program runs.
- `iter_unpack()` gives a list of the tuples, where CPython gives an iterator of them
  ([deviation](../tests/deviations/lib_struct_iter_unpack.py)); a `for` loop and `list()` see the
  same tuples.
- An unsigned 8-byte value from 2\*\*63 on (`Q`, and the native `L`, `N` and `P`) raises
  `OverflowError: integer result does not fit in 64 bits` as it is unpacked, since Pystachy's ints
  are 64-bit ([deviation](../tests/deviations/lib_struct_unsigned64.py)).
- Buffers are `bytes`: these functions take no `bytearray`, and Pystachy has no `memoryview` or `array`, and `pack_into()`,
  which writes into one, raises `NotImplementedError`.
- A format of more than nine values gives a tuple of more than nine items, which can be unpacked
  into names and indexed, but not printed, compared or hashed
  ([tuples](../docs/language/typing.md)).
- A NaN's payload is not kept: unpacking a NaN gives a NaN of its sign, which packs as the quiet
  NaN, where CPython keeps the bits of a NaN it unpacks with `f` or `d`.
- `struct.pack` and the module's other functions as values (`f = struct.pack`) raise
  `NotImplementedError` when called, as the compiler makes the calls by their names. A `Struct`'s
  methods are values, as `Struct("!I").pack` is.

### `binascii`

`binascii` is `_pystachy_binascii`, a port of CPython's C module (`Modules/binascii.c`) to the
subset. Pystachy loads it for `import binascii`, where CPython imports its C module; as for the
other modules that Debian's CPython builds in, a `binascii.py` on the module path is never
imported. All twelve functions are there,
with the C module's signatures, results and errors (`binascii.Error`, a `ValueError`, with its
messages): `hexlify` and `b2a_hex` with `sep` and `bytes_per_sep`, `unhexlify` and `a2b_hex`,
`b2a_base64` and `a2b_base64` (with `strict_mode`), `b2a_uu` and `a2b_uu` (with `backtick`),
`b2a_qp` and `a2b_qp` (with `quotetabs`, `istext` and `header`), `crc32` and `crc_hqx`.
`binascii.Incomplete` exists, as in CPython, where no function raises it.

- Binary data is `bytes`: these functions take no `bytearray`, and Pystachy has no `memoryview` or `array`. The `a2b_*()`
  functions also take a `str` of ASCII characters, as CPython's do. Another type of argument
  is a compile-time error, where CPython raises `TypeError`.
- `hexlify(data, None)` and `b2a_hex(data, None, n)` separate nothing, as without a `sep`, where
  CPython raises `TypeError` ([deviation](../tests/deviations/lib_binascii_sep_none.py)).
- The functions are Python functions, whose reprs are `<function hexlify at ...>`, not
  `<built-in function hexlify>`. `a2b_base64.__doc__` is CPython's docstring without the
  indentation of its option's description, which CPython 3.13 removes from a Python function's
  docstring.

### `codecs`

`codecs` is CPython 3.13.16's `Lib/codecs.py` with three marked edits, on `_pystachy_codecs`,
a subset port of the C module `_codecs` that Pystachy loads for `import _codecs`. The BOM
constants, `encode()`, `decode()`, `lookup_error()`, `register_error()`, `strict_errors()` and
the incremental classes (derived from with methods) work as in CPython, and so do the codec
functions of UTF-8, Latin-1, ASCII and charmap (`utf_8_encode()`, `utf_8_decode()` that is not
final, `charmap_build()`, `charmap_encode()`, `charmap_decode()`, ...) with every builtin error
handler but `namereplace`, raising CPython's `UnicodeDecodeError` and `UnicodeEncodeError` with
its messages.

- Encoding with `namereplace`, which needs the characters' names, raises `LookupError: unknown
  error handler name 'namereplace'`, as `str.encode()` does
  ([language reference](../docs/language/compatibility.md)), where CPython writes `\N{...}`.
- `codecs.lookup()`, which Pystachy has no codec registry for, raises `NotImplementedError`
  ([deviation](../tests/deviations/lib_codecs_lookup.py)); reading its result's attributes, as
  `getencoder()` and the other functions built on it do, is a compile-time error. `register()`
  and `unregister()` do nothing.
- The UTF-16, UTF-32, UTF-7 and escape codec functions raise `NotImplementedError`, and so do the
  error handler functions but `strict_errors()` (`ignore_errors()`, ...), which read attributes
  that Pystachy's `UnicodeError` does not have. A handler `register_error()` registers is one that
  `lookup_error()` gives; `str.encode()`, `bytes.decode()` and the charmap codec take only the
  builtin handlers' names.
- `charmap_build()` gives a dict of code points to bytes, where CPython's is an `EncodingMap`
  object (but a dict where the table does not start with U+0000 or leaves the BMP), and
  `charmap_decode()` takes a decoding table, a str, not a dict.
- A class attribute that binds a function of a subclass's codec (`_buffer_decode =
  codecs.utf_8_decode`, as the `encodings` modules bind them) over a method of its base is not
  supported: define the method with `def`.
- `codecs.strict_errors.__name__` and the other handlers' are unsupported: the handlers are
  `Callable` values.

The edits: the error handlers are bound without the `except LookupError` clause for builds
without them, which binds them to `None`; the four incremental classes' `errors` parameters
are annotated, so that the classes are no templates; and the `import encodings`, which never
runs, is left out.

## Collections and functional tools

### `collections`

The shipped module provides `deque`, `defaultdict`, `OrderedDict` and `Counter`, and
`namedtuple()` (below). Each of the four is a generic class whose item types (`deque[T]`, `Counter[T]`,
`defaultdict[K, V]`, `OrderedDict[K, V]`) come from supported constructor
arguments, an annotation (`q: deque[int] = deque()`,
`d: defaultdict[str, list[int]] = defaultdict(list)`) or an explicit constructor
(`Counter[str]()`). Parameters, returns and fields can name them. The compiled
types are fixed; a deque's items may be an explicitly supported union such as
`int | str`, and mapping keys are the supported dict key types. The package binds `abc` to
the builtin `collections.abc`, as CPython's binds it to `_collections_abc`, which is that builtin
module too, and its `__doc__` is its own docstring.

`deque` supports both ends, optional `maxlen`, extension, rotation,
insertion/removal, indexing, containment/search, copies, comparisons, repetition
and `reversed()`. Iteration reads live items and rejects endpoint mutations, while
`reversed()` iterates over a snapshot; `maxlen` is writable. Rich comparisons use
snapshots when item comparison callbacks mutate a queue. Searches (`count`, `index`,
containment and `remove`) read live items and detect structural mutations with
CPython's operation-specific errors; same-size replacements are preserved.

The mappings hold dicts rather than derive from `dict`, so `isinstance(x, dict)`
and `isinstance(x, collections.abc.Mapping)` are false. They support indexing,
assignment, `del`, `in`, `len`, iteration,
`reversed()`, `keys()`, `values()`, `items()`, `get`, `pop`, `popitem`,
`setdefault`, `clear`, `update`, `copy` and equality with each other and with a
dict on the right; any other operand, such as `None`, is unequal, as CPython's
identity fallback finds. An empty display operand (`d == {}`) has no type: test
`not d`. Views are lists, as a dict's are here, and iteration is a snapshot
rather than CPython's iterator that raises when the mapping changes size.
Constructors and `update` take a dict, a list, tuple or set of pairs, or another
of these mappings (a `Counter` types only the keys of an `OrderedDict` or
`defaultdict`: the `int` values need an annotation); other iterable objects of
pairs need `list(...)` first, and a generator expression a list comprehension.
Keyword arguments are accepted by `update` and `subtract`, not by constructors.
Calling `__init__` again updates the items, as CPython's does (`Counter` adds
the counts; a `defaultdict`'s also replaces `default_factory`).
`dict(m)` of a mapping is not supported: `{k: v for k, v in m.items()}` copies it.

- `defaultdict(factory)` accepts builtin classes such as `int`, `list`, `set`,
  `str`, `float` and `dict`, functions, lambdas and `None`. A factory types
  nothing unless it is a function with a return annotation, so the key and value
  types come from an annotation or explicit types (`defaultdict[str, int](int)`)
  where no mapping argument gives them; a factory that makes another mapping
  (`defaultdict(lambda: defaultdict(int))`) takes the value type from them. Only
  indexing calls the factory, keeping a value the factory itself stored for the
  key. `__missing__`, a writable `default_factory`, `copy`, `|` and `|=` follow
  the C type: `|` takes a dict or another of these mappings, raising CPython's
  `TypeError` for `None` and builtin values that are not, and `|=` also pairs.
  The repr names a builtin class given to the constructor as CPython does, and
  other factories, and a class assigned to `default_factory` later, as
  `<function>`.
- `OrderedDict` supports `move_to_end(key, last=True)`, `popitem(last=True)`,
  `fromkeys(iterable, value)` with a value that types the items, `|` and `|=` (as
  defaultdict's), and order-sensitive equality between OrderedDicts. Two dicts
  hold its items, the first ones in reverse order, so that operations at either
  end take amortized constant time, as with CPython's linked list. Moving a key
  reinserts the key object given.
- `Counter` counts with ints. It supports missing counts of zero, `update` and
  `subtract` from iterables and mappings, `most_common(n)`, `elements()`,
  `total()`, `+ - | &`, unary `+` and `-`, their in-place forms, and the 3.10
  comparisons, which raise CPython's `TypeError` for a `None` operand.
  `elements()` returns a list rather than an iterator, and an empty `Counter()`
  operand on the left of an operator needs its type.

A deque compares with deques: `==` with `None` is false and `<` raises CPython's
`TypeError`. Its reflected multiplication and comparisons with other containers,
pickling, `ChainMap` and the `User*` classes are unavailable. A `deque` is
not a `collections.abc.Sequence` to `isinstance`.

`namedtuple()` is carried out by the compiler: a module's top-level
`NAME = namedtuple(typename, field_names, *, rename=False, defaults=None, module=None)` with
literal arguments is a class statement, a NamedTuple whose fields each call that makes an object
types (a class template). Construction by position and keyword, defaults, field access,
indexing, unpacking, iteration, `len()`, comparisons, `hash()`, `repr()`, `str()`, `_make()`,
`_asdict()` (of fields of one type), `_replace()`, `_fields`, `_field_defaults` and
`type(x).__name__` and `__module__` behave as CPython's, and CPython's errors for invalid
names and too many defaults are compile errors. Assigning the class's or a field's `__doc__` a
string literal is accepted; reading it, other uses of the function, subclassing and a field
given `None` are rejected (see
[compatibility](../docs/language/compatibility.md#classes-dataclasses-and-namedtuples)).

### `copy`

`copy` is Pystachy's own subset (`lib/copy.py`) of CPython 3.13.16's module. CPython's module
dispatches on `type(x)` and copies other objects through the pickling protocol (`__reduce_ex__`,
`copyreg`, `__dict__` updates), none of which a compiled program has at run time. Here the
static type of the value selects its copy as the program compiles, with CPython's results
([test](../tests/programs/library/lib_copy.py)):

- A number, a str, bytes, `None`, a range and a function are their own copies; so is a tuple or
  a frozenset for `copy()`, and a tuple of such values for `deepcopy()`. A list, a dict and a set
  are copied item by item (`copy()` gives `x.copy()`), a deep copy of a frozenset is a new one, and
  a deep copy of a tuple is a new tuple of its items' copies, or the tuple itself where no item
  changed.
- An object of a class of the program is copied through its `__copy__()` or `__deepcopy__(memo)`
  where its class defines one; otherwise the copy is a new object of its exact class (no
  `__init__()` call) whose fields hold the original's values, or their deep copies, and a field
  that `__init__()` left unassigned stays so. A field of a base class's type copies the object of
  the subclass that it holds, frozen dataclasses and `NamedTuple` classes included. The copy's
  numbers are the original's objects, as CPython's are: through `Any`, `copy.n is x.n`
  ([test](../tests/programs/library/lib_copy_identity.py)).
- Where the deep copy of an object's fields may run code that sees or changes the object (a
  `__deepcopy__()`, or the `__hash__()` or `__eq__()` of a dict's keys or a set's items, also of
  their tuples' items: [test](../tests/programs/library/lib_copy_deep_tuple_key.py)), it
  follows CPython's order and reads: an object with a `__dict__` has its attributes copied in the
  `__dict__`'s order, each read as the copy reaches it, so that a hook that changes a later
  attribute gives the copy the new value, and one that adds an attribute raises CPython's
  `RuntimeError` ([test](../tests/programs/library/lib_copy_deep_live.py)); an object of
  `__slots__` only has the slots' values as they were when its copy began, the derived class's
  first, as `copyreg` gives them ([test](../tests/programs/library/lib_copy_deep_slots.py)). Such
  a copy of an object whose `__dict__` order is not known as the program compiles (as for
  `vars()`: an attribute assigned in a branch, for one) is a compile-time error
  ([test](../tests/errors/library/lib_copy_deep_order.py)). The copy has its attributes while it
  is made, where CPython's gets them at the end, which only code that a cycle leads back to the
  copy sees.
- A deep copy keeps a memo, as CPython's does, so that objects shared within the value stay
  shared in the copy and cycles are copied as cycles; the memo that `__deepcopy__(memo)` gets is
  an opaque object that it can pass to `deepcopy()`. A dict cannot be given as `deepcopy()`'s
  memo.
- In a module compiled with [dynamic `Any`](../docs/dynamic-any.md), an `Any` value that holds a
  number, a str, `None`, a list, a dict or a tuple is copied as above
  ([test](../tests/programs/library/lib_copy_any.py)); one that holds an object, an iterator or
  (for `deepcopy()`) a function raises `TypeError`, where CPython copies it
  ([deviation](../tests/deviations/lib_copy_any_object.py)).
- These are compile-time errors: copies of exceptions, of objects of the library's classes
  (`StringIO`, `deque` and the others, which stand in for C types) and of classes that derive from
  one with fields, of classes that define `__reduce__`, `__reduce_ex__`, `__getstate__`,
  `__setstate__`, `__getnewargs__` or `__getnewargs_ex__`, of a union of classes, of iterators,
  generators and files, and deep copies of bound methods and `Callable` values, which may hold a
  bound method that CPython's deep copy binds to a copy of its object.
- `copy.replace()` (new in CPython 3.13) is not provided; `dataclasses.replace()` and a
  `NamedTuple`'s `_replace()` are.

### `enum`

`enum` is Pystachy's own subset (`lib/enum.py`) of CPython 3.13.16's module. CPython makes an
enum class with its metaclass, `EnumType`, whose `__prepare__`, `__new__` and `__call__` have no
form in a compiled program, so the compiler makes the class from its class statement instead,
as it makes dataclasses and `NamedTuple` classes ([test](../tests/programs/library/lib_enum.py)):

- A class statement of a module's body that derives from `Enum`, `IntEnum`, `StrEnum`, `Flag` or
  `IntFlag` (as the body's import statements name them: `from enum import Enum`, or
  `import enum`), from `str` or `int` and `Enum`, or from an enum class of its own module
  without members, makes an enum class. Its members are its body's
  `NAME = value` statements, whose values are literals (numbers, strs, bytes, `True`, `False`,
  `None` and tuples of them) of one type, or `auto()`, which gives CPython's values: one more
  than the greatest value before (from 1), or a `StrEnum` member's name in lower case. An int
  or a str value may also be an expression that the class body computes, with `int`'s operators
  and `str`'s `+` and `*`, of literals, of the members before it and of the module's constants
  (names bound once, before the class statement): `B = 1 << 3`, `C = A | B`, `D = BASE + 1`,
  within the 64-bit int range ([test](../tests/programs/library/lib_enum_values.py)). A member
  whose value an earlier one has is its alias; `@unique` reports aliases as an error.
- Members are objects of the class, with `name`, `value`, `_name_` and `_value_`, CPython's
  `repr()`, `str()`, `format()` and `hash()`, identity equality, and copies that are the member
  itself; the class's methods, properties and class methods work on them as on other objects.
- The class as a value is an object of `EnumType`: `C(value)` finds the member with that value
  (or returns a member it is given, also one held through a base class's type, such as `Enum` or
  `Flag`: [test](../tests/programs/library/lib_enum_base_lookup.py),
  [flags](../tests/programs/library/lib_flag_base_lookup.py)) and raises CPython's `ValueError` for another value,
  `C[name]` raises `KeyError`, iteration and `list(C)` give the members without aliases in
  definition order, and `len(C)`, `x in C` (a member, or a member's value), `C.__members__` (a
  read-only mapping, aliases included) and `repr(C)` are CPython's. Enum classes of other modules
  work where they are imported ([test](../tests/programs/library/lib_enum_import.py)), and so
  do members in `Any` values ([test](../tests/programs/library/lib_enum_any.py)).
- An `IntEnum` member is no `int` here, nor a `StrEnum` member a `str`: each is an object of its
  class with `int`'s comparisons, arithmetic, `bool()` and `hash()`, or `str`'s comparisons,
  `+`, `in`, `len()` and `upper()`, `lower()`, `startswith()`, `endswith()` and `encode()`,
  whose results are ints and strs, and with CPython's `TypeError` for an operand of another
  type. Compared with an object of another class, a member lets that object's reflected method
  decide, or identity where it has none, as `int`'s and `str`'s methods return `NotImplemented`
  ([test](../tests/programs/library/lib_enum_reflected.py)). One cannot be passed where an `int`
  or `str` is typed, `int(member)` is not supported, and these are compile-time errors, as
  CPython's member is an `int` or a `str`: `isinstance()` of one and `int` or `str`, also of a
  value of a base class, such as `Enum`, that may hold one
  ([test](../tests/errors/library/lib_enum_isinstance_base.py)), and a member as an `Any` value,
  whose `isinstance()` would find no `int` or `str`
  ([test](../tests/errors/library/lib_enum_any_strenum.py)): its `.value` can be one.
- `sys.exit()` and `SystemExit` take the member of an `IntEnum` or `IntFlag` class, or of a class
  of `int` and `Enum`, as CPython takes its `int`: the value is the exit status, and nothing is
  written to stderr ([test](../tests/programs/exceptions/exit_enum_member_caught.py)).
  The status uses the integer stored when the member was created, ignoring `__index__()` and
  `__int__()` overrides and later changes to `_value_`. Exception argument formatting retains
  the [documented construction-time behavior](../docs/language/compatibility.md#exception-contents).
- An enum class of `str` and `Enum`, or of `int` and `Enum` (`class C(str, Enum)`), is made as a
  `StrEnum` or an `IntEnum` class with `Enum`'s `str()` and `format()` (`C.A`, where a
  `StrEnum` member's is its value), as CPython 3.12 gives a mixed-in class
  ([test](../tests/programs/library/lib_enum_mixin.py)). Its members follow the rules above, and
  `isinstance()` of one and `IntEnum`, `StrEnum` or `ReprEnum`, which CPython answers `False`, is
  a compile-time error ([test](../tests/errors/library/lib_enum_mixin_isinstance.py)), as is
  `auto()` in a class of `str` and `Enum`, whose CPython value is the str of `Enum`'s next int.
- A class method `_missing_(cls, value)` is called where a lookup by value finds no member, as
  CPython's `EnumType` calls it: the lookup gives the member it returns, raises CPython's
  `ValueError` where it returns `None`, and passes on what it raises
  ([test](../tests/programs/library/lib_enum_missing.py)). One whose result may be of another
  type, for which CPython raises `TypeError`, is a compile-time error
  ([test](../tests/errors/library/lib_enum_missing_result.py)).
- A `Flag` class's members have int values of 0 or more (`auto()` gives the power of two past the
  greatest value before). Iterating over the class, and `len()` of it, give its single-bit
  members; `|`, `&`, `^` and `~` give members, or pseudo-members made once for each value (their
  names, `R|X`, are CPython's), with CPython's `ValueError` for bits that no member has (the
  boundary `STRICT`); a flag's `in`, iteration, `len()`, `bool()`, `repr()` (`<P.R|X: 5>`,
  `<P: 0>`), `str()`, `format()` and `hash()`, and a member of value 0, are CPython's, and the
  name of a pseudo-member without members is `None`
  ([test](../tests/programs/library/lib_enum_flag.py)). Lookup also accepts a non-int value
  equal to a declared member's value, or an already cached pseudo-member's value, as CPython's
  value map does; class containment tests declared values for non-ints
  ([test](../tests/programs/library/lib_enum_flag_numeric_lookup.py)). An `IntFlag` member has `int`'s
  operations, `str()` and `format()`, as an `IntEnum` member does, and `|`, `&` and `^` with an
  int keep its class, whose boundary `KEEP` keeps the bits no member has (`<I: 12>`,
  `<I.A|12: 13>`); its members follow the int-like members' rules above, and `isinstance()` of
  one and `ReprEnum`, which CPython's `IntFlag` derives from, is a compile-time error too
  ([test](../tests/programs/library/lib_enum_intflag.py)). Bits that occur only in composite
  members are supported when the single-bit members are declared in increasing value order.
  Iteration looks up each bit as it advances: an unnamed bit yields `None` until a lookup of
  that value has created a pseudo-member ([test](../tests/programs/library/lib_enum_flag_bits.py)).
  Such bits with out-of-order single-bit members or a custom (including inherited)
  `_iter_member_()` remain a compile-time error, as do a
  `boundary=` keyword, a flag class's own `_missing_()`, and an int on the left of a flag's `|`, `&` or `^`, as reflected operator methods are not
  supported.
- These are compile-time errors: `ReprEnum` as a base; other mixin types
  (`class C(float, Enum)`) and keywords; members of other values or types, `_ignore_`, `_order_`
  and private names; `__new__`, `__init__` and `_generate_next_value_`; an enum
  class that derives from an enum class of another module, or from one with members (CPython's
  `TypeError`); a class statement in an `if` or `try` statement, or whose base is imported in
  one ([test](../tests/errors/library/lib_enum_conditional.py),
  [test](../tests/errors/library/lib_enum_try_import.py)); the functional API (`Enum("Color", "RED GREEN")`); reassigning a member
  (CPython's `AttributeError`); `reversed()` of an enum class, and an enum class without
  members as a value. `enum.property`, `member`, `nonmember`, `verify`, `global_enum` and the
  other helpers are not provided.

### `heapq`

Heap operations, including `_max` variants, and `nlargest`/`nsmallest` work.
The top-k functions accept lists and supported iterables: tuples, strings,
dicts, sets, `dict.items()`, and objects with `__iter__`, with or without
`__len__`. `key=` accepts supported functions, builtins and bound methods.
Ties preserve input order.

Lists are read in place. Other inputs are first materialized by a comprehension;
therefore a key/comparison that changes a dict or set being read does not raise
CPython's iterator-mutation `RuntimeError`. A `__len__` that raises `TypeError`
is handled as in CPython. The algorithm preserves comparison and key-call order
for list inputs.

The heap functions and their `_max` variants follow `Modules/_heapqmodule.c` of
CPython 3.13.16, which CPython imports over `heapq.py`'s: a sifted item trades
places with each item it passes, so a comparison that changes the heap finds all
of its items there, and one that changes its size raises `RuntimeError: list
changed size during iteration`. An empty heap raises `IndexError: index out of
range`, and `heapify()` of more than 2,500 items compares in the C module's
cache-friendly order.

`merge` does not compile: its heap entries are lists that mix an item, an int and the
iterator's `__next__` method, and a list's items share one type. Pass `file.readlines()`
rather than an open file directly. Materialize a generator expression with a supported
consumer before passing it to a top-k function.

### `itertools`

`itertools` is `_pystachy_itertools`, which Pystachy loads for `import itertools`, where CPython
imports its C module (`Modules/itertoolsmodule.c`). It has all of the module's functions:
`count`, `cycle`, `repeat`, `accumulate` (with `func` and `initial`), `batched` (with `strict`),
`chain` and `chain.from_iterable`, `compress`, `dropwhile`, `filterfalse`, `groupby`, `islice`,
`pairwise`, `starmap`, `takewhile`, `tee`, `zip_longest`, `product` (with `repeat`),
`permutations`, `combinations` and `combinations_with_replacement`. Each iterates as the
pure-Python equivalent that CPython's documentation gives for it (`Doc/library/itertools.rst`),
on generators, with the C module's argument checks and messages when it is called and the C
types' order of reads: an iterator reads its input one item at a time, as it is iterated, so
infinite inputs (`count()`, `cycle()`, generators) end where `islice()`, `zip()`, `takewhile()`
or `break` stop reading, and `islice()` reads no item past its stop. As in CPython, `cycle()`
keeps the items it has read, `tee()` keeps the items its slowest iterator has not read (in
shared links of 57), and `product()`, `permutations()`, `combinations()` and
`combinations_with_replacement()` read the whole of their iterables when they are called. The
functions are templates: each call's argument types make its code
([tests](../tests/programs/library/lib_itertools_terminating.py), [ranges](../tests/programs/library/lib_itertools_range.py),
[generators](../tests/programs/library/lib_itertools_generators.py),
[upstream](../tests/programs/upstream/upstream_itertools.py)).

- The iterators are generators (`Generator[T]`), which yield items of one type: `chain()` of
  iterables of different item types ([error test](../tests/errors/library/lib_itertools_chain_mixed.py)),
  an `accumulate()` function that returns another type than the items'
  ([error test](../tests/errors/library/lib_itertools_accumulate_type.py)) are compile-time
  errors, as is an `accumulate()` `initial` of another type than its sums, such as `initial=0`
  of floats, where CPython yields the int `0` and then floats (`initial=0.0` is not an error)
  ([error test](../tests/errors/library/lib_itertools_accumulate_initial.py)). `accumulate()` of bools
  gives a bool and then ints, as in CPython, and `zip_longest()` without `fillvalue` gives
  optional items. A `zip_longest()` `fillvalue` of another scalar type than an iterable's items
  gives items of their union ([test](../tests/programs/library/lib_itertools_zip_longest_fillvalue.py)).
- `batched()`, `permutations()`, `combinations()`, `combinations_with_replacement()` and
  `product(..., repeat=n)` yield tuples whose length the program knows only as it runs, whose
  items must be ints, floats, bools, strs or their optional types
  ([tuples](../docs/language/typing.md)): of tuples, lists or objects, they are compile-time
  errors ([error test](../tests/errors/library/lib_itertools_combinations_objects.py),
  [another](../tests/errors/library/lib_itertools_batched_tuples.py)), and `product()` with `repeat`
  needs one item type across its iterables
  ([error test](../tests/errors/library/lib_itertools_product_repeat_mixed.py)). `product()` without
  `repeat` and `zip_longest()` yield a tuple with an item of each iterable, of its type.
- A list unpacked into the iterables of `chain()`, `zip_longest()` or `product()` is a number of
  arguments known only as the program runs, a compile-time error
  ([error test](../tests/errors/library/lib_itertools_star_list.py)); `chain.from_iterable()` takes a
  list of iterables. `starmap()` takes tuples of arguments, not lists
  ([error test](../tests/errors/library/lib_itertools_starmap_list.py)).
- `tee(iterable, n)` gives a list of the `n` iterators, where CPython gives a tuple
  ([deviation](../tests/deviations/lib_itertools_tee_list.py)); `tee(iterable)` gives a tuple of
  two. Unpacking, indexing, `len()` and loops see the same iterators.
- `groupby()`'s key of `None` groups by the items themselves; a key function that is an object
  in a variable may be `None`, so its keys must have the items' type unless it is made in the
  call ([error test](../tests/errors/library/lib_itertools_groupby_key_object.py)). Its groups are
  generators that share the `groupby()`'s iterator, as the C type's do: advancing the
  `groupby()` ends the group before it ([test](../tests/programs/library/lib_itertools_groupby.py)). A key that
  is not equal to itself (a NaN) still makes a group of its item, as in CPython; but a float
  has no identity, so the same NaN object twice makes two groups, where CPython makes one
  ([deviation](../tests/deviations/lib_itertools_groupby_nan.py)).
- An argument whose type the C function rejects (`permutations()`' `r` of another type than
  `int`, `count()` of something other than a number) and `islice()` or `tee()` with too few or
  too many arguments raise CPython's `TypeError` as the program runs
  ([test](../tests/programs/library/lib_itertools_argtypes.py)); other wrong numbers of arguments, keywords a
  function has not, and non-iterables are compile-time errors.
- An iterator that an exception has left (from its function, predicate or key, or from its
  input) is finished, as a generator is, where CPython's C iterators can go on
  ([deviation](../tests/deviations/lib_itertools_exception.py)). So is an iterator whose input
  has ended: called again, it reads no input, where CPython's `accumulate()`, `compress()`,
  `dropwhile()`, `filterfalse()`, `groupby()`, `starmap()` and `takewhile()` read their inputs
  again, which an input that yields again after its end, or `compress()`'s data, which it reads
  before it finds its selectors' end, shows
  ([deviation](../tests/deviations/lib_itertools_ended.py)). An iterator that its own input
  resumes raises `ValueError: generator already executing`, where CPython's go on
  ([deviation](../tests/deviations/lib_itertools_reenter.py)); `tee()` raises CPython's
  `RuntimeError`.
- An input generator is not closed when the iterator reading it is dropped, as a generator the
  program drops is not ([deviation](../tests/deviations/lib_itertools_close.py)). As generators,
  the iterators have the generator's attributes for `hasattr()` (`send`, `close`, `gi_frame`,
  ...), which CPython's have not
  ([deviation](../tests/deviations/lib_itertools_hasattr.py)), and `send()`, `throw()` and
  `close()` work on them where CPython raises `AttributeError`
  ([deviation](../tests/deviations/lib_itertools_protocol.py)).
- `chain` is an object whose calls make generators, with `from_iterable()` as a method and the C
  type's repr, not a class: `isinstance(x, itertools.chain)` is a compile-time error
  ([error test](../tests/errors/library/lib_itertools_isinstance.py)), as are the other functions as
  classes. The iterators do not print (CPython prints `count(5)`), and their type's name,
  pickling, `copy.copy()` (but for `tee()`'s `__copy__()`), `__reduce__()`, `__setstate__()`
  and `__length_hint__()` are not there
  ([error test](../tests/errors/library/lib_itertools_print.py),
  [another](../tests/errors/library/lib_itertools_type_name.py)).
- `zip()`, `map()`, `filter()`, `enumerate()` and `reversed()` are not values, so an itertools
  function cannot take one ([error test](../tests/errors/library/lib_itertools_zip_argument.py)); it can
  take a generator expression over them. Ints are 64-bit: `count()` past `2**63 - 1` raises
  `OverflowError`, where CPython's ints grow.

### `functools`

`cache` and `lru_cache` wrap annotated `def` functions. The default `maxsize` is
128; `None` is unbounded, zero disables storage, and negative values become zero.
Bare `@lru_cache` works. Wrappers expose `cache_info`, `cache_clear`, `__wrapped__`,
`__name__` and `__qualname__`. `CacheInfo` contains `hits`, `misses`, `maxsize` and
`currsize`. Clearing resets entries and statistics.

Each wrapper specializes its argument and result types. Accepted key types are
`int`, `bool`, `str`, `str | None`, objects, and tuples of supported key types. An
object argument is keyed by identity, or by its class's `__hash__` and `__eq__`, which
a call may run more than once where CPython's hashes the key once. Defaults
and keyword arguments bind against the original signature, evaluate arguments
in source order, and retain defaults evaluated when the function was defined,
including closure defaults. Functions with nine parameters are supported.

Call spelling remains significant, as in CPython: `f(1)`, `f(1, 2)`, `f(1, b=2)`,
`f(a=1, b=2)` and `f(b=2, a=1)` use distinct entries. Full positional calls use
tuple keys; other forms also record positional count and ordered keyword names.
They share one LRU, capacity, statistics and clearing. Aliases and bound
`__call__` calls use the same keys as direct calls.

Misses count before execution; exceptions are not cached. Recursive insertion of
the same key keeps the existing cache entry, while the outer call returns what
it computed. Hits update recency; eviction removes the least-recently-used
entry. Cached results retain object identity, including falsy results and optional
`None` values.

Unsupported cases are unannotated parameters/results, a result annotated solely
`-> None`, float and NamedTuple keys, variadic functions, builtin/method/lambda targets,
and decorators on class-body methods. Required keyword-only parameters and
explicit keyword-only arguments are unsupported; a keyword-only default may be
omitted. `cache_parameters` is unavailable.

`typed=True` is accepted, but static parameter types already separate the calls
it would distinguish. Programs run on one thread; caches need no lock.
The module uses CPython's C wrapper when CPython imports it.

`reduce(function, iterable[, initial])` folds supported iterables once, including
files and `StringIO`. The callback and accumulator must retain the types inferred
for this call. Omitted initial values, explicit `None`, empty inputs and callback
exceptions follow CPython; integer results retain checked 64-bit arithmetic.

`cmp_to_key(comparator)` returns a key function for `sorted` and list sorting.
The comparator accepts two values of one supported type and returns an int.
Key objects expose writable `obj` and the five comparison methods. `hash()` of one
raises CPython's `TypeError: unhashable type: 'functools.KeyWrapper'`, also where it is
used as a dict key or set element. The factory is a function rather than CPython's
`KeyWrapper`, so factory attributes, reflection and pickling are unavailable.

`partial(func, *args, **keywords)` stores a function, bound method, builtin,
closure or callable object with positional and keyword arguments. A call passes
the stored positional arguments first, and its own keywords replace stored ones.
A partial of a partial is flattened, as in CPython: `func`, `args` (a tuple) and
`keywords` (printing as a dict) hold the merged values. A first argument that is
not callable raises CPython's `TypeError`. Each call is checked against the
function's signature where it is compiled, so a wrong call fails compilation
rather than raising `TypeError`. The attributes can be assigned, unlike C's
read-only ones. `repr()` gives the default `<functools.partial object at ...>`
rather than CPython's call form; pickling, `__dict__` and `partialmethod` are
unsupported.

`@wraps(wrapped)` on a def, and `update_wrapper(wrapper, wrapped)` of a function a def or
lambda makes in a function (or a decorated def), give the wrapper the wrapped function's
`__name__` and `__qualname__`, as CPython's do, with `assigned` naming either (a tuple or
list of str constants, or a module's name that one assignment binds to such a tuple, as
`WRAPPER_ASSIGNMENTS`). The compiler applies them, where CPython's code sets the attributes:
a wrapped function's names must be known as it compiles, so a wrapped `Callable` value makes
the wrapper's names a compile-time error to read, and a wrapped object without them (a
callable object, a `partial`) leaves the wrapper its own, as in CPython. `__wrapped__`,
`__doc__`, `__module__` and `__dict__` are not a function's attributes in Pystachy, and
`wraps(f)` as a value, not a decorator, is a compile-time error. `total_ordering` remains
unsupported: class decorators are not compiled.

### `operator`

Arithmetic, comparison, logical, sequence and bitwise operator functions compile
for supported operand types. `call()` forwards a supported callable's arguments.
In-place functions require a result that keeps its input type: `itruediv(1.0, 2.0)`
works; rebinding an integer to a float does not.

`itemgetter`, `attrgetter` and `methodcaller` are callable objects: call them
directly, store them, or pass them as `key=` to `sorted`, `min`, `max`, `list.sort`
and the library's key parameters. A getter specializes on its literal arguments,
so `itemgetter(1)` reads a fixed tuple's or NamedTuple's item with its static type
and `attrgetter("name")` reads `o.name`; each literal value makes a getter type of
its own, so `itemgetter(0)` and `itemgetter(1)` cannot share a list or variable.
`itemgetter(i)` of a variable `i` indexes lists, strings and dicts, and a fixed
tuple at run time with the union of its items' types. Dotted names, several
items or names (a tuple result) and `methodcaller` arguments work as in CPython,
and reprs match C's. A literal getter's constants cannot be assigned.

Attribute and method names must be string literals: a missing attribute and a
name that is not a string fail compilation, rather than raising `AttributeError`
or `TypeError` when the getter runs (a single non-string literal still raises
CPython's `TypeError` when the getter is made). Pickling is unsupported.
`length_hint` and `index` are not general substitutes for CPython's versions:
for example, `length_hint([1, 2])` and `index(2)` fail compilation.

### `contextlib`

Ported from CPython 3.13's `Lib/contextlib.py`, each change marked `Pystachy port`.
`@contextmanager` keeps `_GeneratorContextManager`'s `__enter__` and `__exit__`: "generator
didn't yield", "generator didn't stop" and "generator didn't stop after throw()" are its
`RuntimeError`s, an exception of the block is thrown into the generator where it is suspended and
suppressed where the generator swallows it, and a `StopIteration` or `GeneratorExit` of the block,
or a `RuntimeError` that PEP 479 or the generator made of the `StopIteration`, goes on as itself.
A manager it makes also decorates a function (`@cm()`, `ContextDecorator`), and both take keyword
arguments. `closing(thing)`, `nullcontext()`, `nullcontext(value)`, `suppress(A, B)` and
`AbstractContextManager` (to derive from) are the others.

- `@contextmanager` (or `@contextlib.contextmanager`, as the module imports it) on a method, its
  only decorator, makes the generator method `_pys_cm_NAME` and a method `NAME(self, /, *args,
  **kwds)` that returns what `contextmanager(self._pys_cm_NAME)(*args, **kwds)` returns (the
  subset has no other decorated methods): `dir()` and `vars()` of the class show the first, and
  those of the module `_pys_cm_GCM`, the name it imports `_GeneratorContextManager` as. Subclasses
  inherit and override such a method, and `super().NAME()` runs the base class's generator, but a
  manager that `super().NAME()` makes and that decorates a function makes its generator for each
  call with the method of the object's class; an override of a method of a class of another module is
  rejected as the program compiles (the managers' types differ).
- `suppress()` as a `with` statement's item, with exception classes named, is compiled as an
  `except` clause that catches them; one kept as a value, or given exception classes held as
  values, is CPython's (its `__exit__` tests them with `issubclass()`). `with suppress(...) as x`
  is a compile-time error.
- `nullcontext(enter_result)` takes it positionally, and not `None` alone (`nullcontext(None)`
  is `nullcontext()`); `nullcontext` is a function that makes one of two classes' objects, and
  the managers are no subclasses of `AbstractContextManager` (class templates have no bases).
- `__doc__`, `__name__` (no `functools.wraps()`) and `gen` of a `_GeneratorContextManager` are
  not available, and its `__exit__` called with a class but no exception returns `False` (CPython
  makes the exception, `typ()`, which the port leaves out: a `with` statement passes the
  exception).
- A function that a manager decorates and that calls itself is rejected (the decorator's `inner()`
  calls itself before its return type is inferred): use the manager inside it instead.
- `ExitStack`, `redirect_stdout`, `redirect_stderr`, `chdir` and the async managers
  (`asynccontextmanager`, `aclosing`, `AsyncExitStack`, `AbstractAsyncContextManager`) are not
  ported: the subset has no list of managers of different classes, no assignable `sys.stdout`,
  no `os.getcwd()` and no `async def`.

## Numbers and randomness

### `random`

`Random` objects and the module's functions, which share a hidden instance, give
CPython's values for int, bool and float seeds: `seed`, `random`, `getrandbits`,
`getstate`/`setstate`, `randrange`, `randint`, `choice`, `shuffle`, `sample`
(including `counts=`), `choices` (weights or cumulative weights) and the `uniform`,
`triangular`, `normalvariate`, `gauss`, `lognormvariate`, `expovariate`,
`vonmisesvariate`, `gammavariate`, `betavariate`, `paretovariate`, `weibullvariate`
and `binomialvariate` distributions. `_pyrandom` is the Mersenne Twister of
`_random.Random` in the subset, which CPython builds in, so no `_random.py` can
replace it. `binomialvariate` calls `math.lgamma`, provided by the native runtime.

- `seed()`, `seed(None)` and `Random()` use the time, process id and monotonic
  clock, CPython's fallback when it cannot read `os.urandom()`.
- A float seeds with its hash, as in CPython; a NaN's hash is 0 rather than
  CPython's object-dependent value.
- `getrandbits(k)` takes at most 63 bits and raises `OverflowError` for more,
  before drawing. `randrange` and `randint` raise `OverflowError` where the width,
  `b + 1` or the width plus the step leaves 64 bits (`randint(a, 2**63 - 1)`).
- Populations are lists, strings, ranges and runtime-length tuples
  ([test](../tests/programs/containers/range_value.py)). String populations are
  sequences of code points.
  Weights and counts share one numeric type. `sample` raises `TypeError` for a
  `deque`, which `isinstance` does not find a `Sequence`, and takes a dict view,
  which is a list.
- Of the module functions, only `random` and `getrandbits` convert to a typed
  `Callable`; the others are unannotated upstream methods, which unannotated
  parameters or a lambda can take.
- `randrange` and `randint` take ints or bools. `triangular` of int bounds returns an
  `int | float`: its low bound where the mode's fraction of the range divides by zero, as in
  CPython, and a float otherwise.

Seeds of `str`, `bytes` or `bytearray` (SHA-512 into a long integer), `randbytes`,
`SystemRandom` (absent from `__all__`), subclasses of `Random` (its
`__init_subclass__` chooses how they draw integers) and pickling are unsupported.
An integer passed as `choices`' weights is a compile error rather than CPython's
hint to pass `k=`.

### `statistics`

Supported APIs are `fmean` (including weights), `geometric_mean`, `median`,
`median_low`, `median_high`, `median_grouped`, `quantiles`, `mode`, `multimode`,
`covariance` and `linear_regression` for the compatible sequence types, and `correlation`
(linear and ranked) of floats. Weighted `fmean` and `linear_regression` use the port of
CPython's `math.sumprod` algorithm; unsupported iterators are materialized first.

- `median` of ints or bools returns their union with `float`, as CPython returns the middle
  item of an odd number of them and the mean of the two middle ones otherwise. `quantiles`
  requires floats: of ints CPython returns `n - 1` copies of a single data point, ints, and
  floats otherwise ([error test](../tests/errors/library/lib_statistics_quantiles_int.py)).
  `median_low` and `median_high` retain the item type. `median` of strings is unsupported.
- `mode` and `multimode` cannot use float keys. String inputs iterate code points.
- Integer products in weighted `fmean` and in `linear_regression(..., proportional=True)`
  can raise `OverflowError` beyond 64 bits; CPython's integers continue growing.
- The port's `sumprod` returns a float, including `11.0` for integer inputs and
  `0.0` for empty inputs, where CPython can return an integer.
- `correlation` of ints is a compile-time error: it rebinds its list-of-int parameters to
  the float deviations or ranks ([error test](../tests/errors/library/lib_statistics_correlation.py)).
  Its ranks for `method='ranked'` come from itertools' `count()` and `groupby()`, in a list
  that starts as floats, where CPython's starts as ints and holds the same float ranks.

Unsupported APIs are `mean`, `harmonic_mean`, variance/stdev and their population
variants, `kde`, `kde_random` and `NormalDist`. These depend on exact fractions, decimal/long integers,
iterators, properties or other features beyond the port's compiled paths. Only
CPython runs the module's import of `random`, which `kde_random` and
`NormalDist.samples` use ([CPython-only code](#cpython-only-code)). Bounded pattern
matching now lowers `kde`'s kernel selection, but its distinct lambda values cannot
share one inferred native function slot; function `__doc__` writes also remain unsupported.

### `mpz`

The experimental non-stdlib `mpz.mpz` type is an explicit arbitrary-precision
integer class. Its [API, representation and compatibility limits](../docs/mpz.md)
are separate from the checked 64-bit builtin `int` contract.

## Dates and times

### `datetime`

`timedelta`, `date`, `time`, `datetime`, `timezone`, `tzinfo` subclasses, `MINYEAR`,
`MAXYEAR` and `UTC` are supported. The module is CPython's `_pydatetime`; where CPython's
`_datetime` accelerator behaves differently, the port follows it: error messages, float
`timedelta` arguments (each unit added exactly, fractions rounded once), exact `timedelta`
products and quotients with floats, ISO 8601 parsing, aware `time` comparisons, `repr()` with
`fold` and the `strftime()` format scan.

Supported operations include construction with keywords and range checks; `+`, `-`, unary
operators, `abs()`, `*` and `/` by ints and floats, `//`, `%` and `divmod()` of timedeltas;
comparisons, sorting, `min()` and `max()`; `str()`, `repr()` and `format()`;
`total_seconds()`, `toordinal()`, `fromordinal()`, `weekday()`, `isoweekday()`,
`isocalendar()`, `fromisocalendar()`, `fromisoformat()`, `isoformat()` with `sep` and
`timespec`, `ctime()`, `replace()`, `combine()`, `date()`, `time()`, `timetz()`,
`timetuple()`, `utctimetuple()`, `utcoffset()`, `tzname()` and `dst()`. Aware datetimes
support `timestamp()`, `astimezone(tz)`, `fromtimestamp(t, tz)` and `now(tz)`.
`strftime()` gives CPython's result on Linux: glibc's C-locale directives with flags, widths
and `E`/`O` modifiers, and datetime's `%f`, `%z`, `%:z` and `%Z`. A `tzinfo` subclass
overrides `utcoffset()`, `dst()` and `tzname()`, whose `dt` is a `datetime` or `None`, and
can use the inherited `fromutc()`.

- Pystachy's `time` module has no `localtime()` or `mktime()`. `date.today()`,
  `date.fromtimestamp()`, `datetime.today()`, `now()` and `fromtimestamp()` without a time
  zone, `timestamp()` of a naive datetime, `astimezone()` of a naive datetime or without a
  time zone, `strftime("%s")`, and a `%Z` with flags or a width where `dst()` is not `None`,
  raise `NotImplementedError`.
- `strptime()`, the deprecated `utcnow()` and `utcfromtimestamp()`, pickling and
  `copy.replace()` are unsupported. `hash()` of these objects hashes the fields that
  `_getstate()` packs into bytes upstream (Pystachy has none), so they are dict keys and set
  elements, equal objects hashing alike; the values differ from CPython's.
- `timetuple()` returns a NamedTuple with `time.struct_time`'s nine fields and repr, without
  `tm_zone` and `tm_gmtoff`. `isocalendar()`'s result is a NamedTuple: index or unpack it, as
  `tuple()` of it is unsupported.
- Reflected operators are unsupported: write `timedelta * 2` and `date + timedelta`, not
  `2 * timedelta` or `timedelta + date`.
- `datetime.min` and `datetime.max` are typed `date` (a subclass's class attribute keeps its
  base's type). `fromisoformat()` and `fromtimestamp()` must be called through their class,
  not a `date` object.
- Integers are 64-bit: `total_seconds()`, division, `%` and `divmod()` raise `OverflowError`
  beyond about 106,751,991 days, as does a float count of microseconds of `2**63` or more.
- `timezone(timedelta(0))` is a new object equal to `timezone.utc`, and a `name` of `None`
  means no name. Subclasses of `timezone` are rejected.
- The Python fallback's replacement sentinels remain: an explicit `None` for a numeric
  field in `date.replace()`, `time.replace()` or `datetime.replace()` preserves that field;
  explicit `tzinfo=True` in `time.replace()`, `datetime.replace()` or `datetime.combine()`
  preserves the original time zone. CPython's C implementations reject those explicit
  values with `TypeError`; `tzinfo=None` still removes the time zone.
- Objects of subclasses of `date`, `time` and `datetime` print as their base class, and
  arithmetic and `replace()` return objects of the base class.
- Ordering a `date` with a `datetime` raises the `TypeError` of the reflected comparison.

## Files, OS and command line

### `io`

`StringIO` supports construction with `initial_value` and `newline`, reading and
writing, `readlines`/`writelines`, iteration, `getvalue`, positioning and
truncation, closing and stream capability queries. It exposes `closed`,
`encoding`, `errors`, `line_buffering` and seek constants. `print(..., file=buf)`
works. Newline translation, NUL padding after seeking past the end, and closed
stream errors follow CPython's implementation.

- Sizes and positions count Unicode code points.
- Iteration and `next()` read one line at a time from the shared stream position.
- `with StringIO() as f:` closes it as the block is left (`__enter__` raises CPython's
  `ValueError` for a closed one).
- `newlines`, `detach`, `fileno` and pickling are unavailable.
- Invalid argument types such as `StringIO(5)` are compile-time errors.

`BytesIO` supports construction with `initial_bytes` (bytes or `None`, also by keyword, and
`__init__` called again), `read`, `read1`, `readline`, `readlines` (whose size bound stops the
lines once their total reaches it, as the C type's does), iteration, `write`, `writelines` (of
any iterable of bytes), `getvalue`, `seek`, `tell` and `truncate` with CPython's `whence` rules,
clamping and errors, `close`, the read-only `closed`, `with`, and `readable`, `writable`,
`seekable`, `isatty` and `flush`. NUL bytes pad a write past the end, and a closed one raises
CPython's `ValueError` for every method but `close()` (`iter()` returns it, and `next()`
raises). Positions and sizes count bytes, as in CPython.

- `getbuffer()` (a `memoryview` of the buffer), `readinto()` and `readinto1()` (into a writable
  buffer, such as a `bytearray`) are unavailable, as Pystachy has no `memoryview`, `bytearray`
  or `array`; so are `detach()` and `fileno()` (which raise `io.UnsupportedOperation`) and
  pickling. A call of any is a compile-time error.
- Invalid argument types such as `BytesIO("x")`, `write("x")` (and so `print(..., file=)` to a
  `BytesIO`) are compile-time errors, as are attributes of the program's own on one.
- `writelines([])` needs the empty list typed (`lines: list[bytes] = []`).

`TextIOWrapper` is the text layer over a binary stream. Its buffer is any object with the
methods CPython's calls: `readable()`, `writable()`, `seekable()` and `closed`; `read1()` or
`read()` to read; `write()`, `flush()` and `close()`; and `tell()` for a seekable, writable
buffer. Each buffer class gets its own specialization of the class.

What it supports:
- construction with `buffer`, `encoding`, `errors`, `newline`, `line_buffering` and
  `write_through`;
- `read`, `readline`, `readlines` and iteration; `write`, `writelines`, `flush` and `close`;
  `with`, and `print(..., file=t)`;
- the `encoding`, `errors`, `newlines`, `buffer`, `line_buffering`, `write_through`, `closed`
  and `name` attributes, `repr()`, and the `readable`, `writable`, `seekable`, `isatty` and
  `fileno` queries.

It reads and writes the buffer as CPython's does: the same calls, in chunks of 8192 bytes. It has
CPython's universal-newline decoding, newline translation and line buffering, and its codec
errors. It raises CPython's errors for a closed stream or an unsupported operation.
`io.UnsupportedOperation` is caught as `OSError` or `ValueError`: a program cannot name it.
`read(n)`, `readline(n)`, `readlines(hint)` and `write()`'s result count characters, as in
CPython.

- The encodings are UTF-8, Latin-1 and ASCII, by any of their names. Another raises
  `NotImplementedError` when the wrapper is made: CPython would use its codec, or raise
  `LookupError` for a name it does not know.
- Without `encoding=`, the encoding follows a file's rule, the runtime's form of CPython's
  `locale.getpreferredencoding(False)`: `"utf-8"` in the C or POSIX locale (UTF-8 mode), and
  otherwise the locale's codeset. `encoding="locale"` gives `locale.getencoding()`'s codeset,
  with the C locale coerced to C.UTF-8 as CPython coerces it. The `PYTHONUTF8` and
  `PYTHONCOERCECLOCALE` settings are not read.
- `newlines` is `None` or the one kind of newline read. Once two or more kinds have been read,
  CPython gives a tuple of them; Pystachy raises `NotImplementedError` instead.
- `seek`, `tell`, `truncate`, `detach`, `reconfigure` and `_CHUNK_SIZE` are compile-time errors,
  as are attributes the program adds (`t.mode = "r"`) and subclasses.
- CPython's finalizer flushes and closes a wrapper the program drops; Pystachy's does not. Close
  the wrapper, or leave its `with` block, to write what is waiting.
- Where a buffer class has `read1()`, its `read()` must take a size. A subclass's `read1()`,
  `write()` or `tell()` must also be its base class's.

`IncrementalNewlineDecoder` is the C type's universal-newline decoder (`Modules/_io/textio.c`),
for `decoder=None`: `decode()` takes `str` input, holds a final `\r` back until the next call or a
final one, records the kinds of newline it decodes and, with `translate` true, makes `\r\n` and
`\r` `\n`. `getstate()`, `setstate()`, `reset()`, `newlines` and the truth tests of `translate`
and `final` are CPython's ([test](../tests/programs/library/lib_io_newline_decoder.py)). `text_encoding()` gives its
argument, or for `None` `"utf-8"` in UTF-8 mode, which the runtime's rule above turns on in the C
and POSIX locales, and `"locale"` otherwise; Pystachy reads no `PYTHONWARNDEFAULTENCODING`, so it
never warns. `open` and `BlockingIOError` are the builtins, and `DEFAULT_BUFFER_SIZE` is 8192.

- A decoder object, which CPython's decodes `bytes` input with first, raises
  `NotImplementedError` ([deviation](../tests/deviations/lib_io_newline_decoder_object.py)), and
  `bytes` input, for which CPython raises `TypeError`, is a compile-time error
  ([error test](../tests/errors/library/lib_io_newline_decoder_bytes.py)).
- `newlines` raises `NotImplementedError` once more than one kind of newline has been decoded,
  where CPython's is a tuple of them, as `TextIOWrapper`'s does
  ([deviation](../tests/deviations/lib_io_newline_decoder_tuple.py)).

`_io` is `_pystachy__io`, which Pystachy loads for `import _io`, where CPython imports the C module
that its `io` is a layer over. It has CPython's docstring and `io`'s `StringIO`, `BytesIO`,
`TextIOWrapper`, `IncrementalNewlineDecoder`, `text_encoding()`, `open`, `BlockingIOError` and
`DEFAULT_BUFFER_SIZE` ([test](../tests/programs/library/lib_io_cmodule.py)). Its classes are `io`'s, and their module
is `_io`, as CPython's are, through either module: `type(x).__module__` and an object's default
`repr()` name `_io` ([test](../tests/programs/library/lib_io_type_module.py)). `FileIO`, the `Buffered*` classes and
`open_code()` are not names of either: the [binary files](#binary-files) that `open()` makes are of
classes of their own, which are not constructed by name; the `_IOBase` classes, from which
`io`'s do not derive, and `UnsupportedOperation` are not there either. A use of any is a
compile-time error ([error test](../tests/errors/library/lib_io_open_code.py),
[another](../tests/errors/library/lib_io_fileio.py)). With `_io`, `importlib` stops next at the missing
`_warnings`, and then needs `marshal` and CPython's runtime import machinery.

### Binary files

`open()` of a mode with `b` makes the object CPython 3.13.16's makes: a `BufferedReader`,
`BufferedWriter` or `BufferedRandom`, or with `buffering=0` a `FileIO` (`lib/_pystachy_bfile.py`, over
the runtime's files) ([test](../tests/programs/io/bfile_basic.py),
[modes](../tests/programs/io/bfile_modes.py)). Their bytes are read and written as they are, without
decoding or newline translation:

- They have `read()`, `readline()`, `readlines()`, a `FileIO`'s `readall()`, iteration over their
  lines, `write()`, `writelines()`, `seek()` (with Linux's `SEEK_DATA` and `SEEK_HOLE`), `tell()`,
  `truncate()`, `flush()`, `close()`, `fileno()`, `isatty()`, `readable()`, `writable()`,
  `seekable()`, `name`, `mode` (as `FileIO` names it: `w+b` is `rb+`), `closed` and `with`, and
  `type()` and `repr()` name `_io`'s classes.
  `readlines(hint)` includes the line that takes the total byte count above a positive hint;
  reaching it exactly does not stop reading ([test](../tests/programs/io/bfile_readlines_hint.py)).
- Errors are CPython's, in its order: `open()`'s checks of the mode, and of `encoding`, `errors`
  and `newline`, which a binary mode refuses; the OS's errors; and each class's messages for an
  operation on a closed file or one its mode does not have (`io.UnsupportedOperation`)
  ([test](../tests/programs/io/bfile_errors.py)).
- A buffered file's writes reach the OS when CPython's do (its buffer has `st_blksize` bytes, or
  those of `buffering=`), and its reads and writes are at its position. `truncate()` discards
  read-ahead and cached position state, so reads see the file as it now is, including after a
  seek into a partial final buffer. A failed seek preserves the logical position
  ([truncate test](../tests/programs/io/bfile_truncate_read.py),
  [position test](../tests/programs/io/bfile_stdio_sync.py)).
  A `FileIO`'s `read(n)` is one read of the OS, which a pipe or a terminal may end short
  ([test](../tests/programs/io/bfile_fifo_raw.py)), and a read error raises CPython's `OSError`
  ([test](../tests/programs/io/bfile_read_error.py)). Its `write()` likewise makes one OS write
  and returns the number of bytes accepted, which can be less than the input length
  ([file-layer probe](../tools/fileprobe.c)).
- A file used in one expression (`open(p, "wb").write(data)`) is closed right after it, as
  CPython's finalizer closes it ([test](../tests/programs/io/bfile_temp.py)), unless that call
  returns the file, as `__iter__()` and `__enter__()` do
  ([test](../tests/programs/io/bfile_temp_escape.py)); one dropped otherwise is closed as a
  text file is ([lifetime](../docs/language/compatibility.md#memory-and-resource-lifetime)).
- Every binary file has one type, of a class the four derive from, so that one name holds files
  of different modes, as in CPython.

These are compile-time errors: `open()` of a binary mode in a module where `open` is bound
otherwise (a parameter, a `def`, an import or an assignment of that name), or called as
`io.open()` ([test](../tests/errors/io/bfile_open_bound.py)); `buffering=1`, for which CPython
warns that line buffering isn't supported in binary mode, and a `buffering=` that is not a
literal int, since the class depends on it ([test](../tests/errors/io/bfile_buffering_var.py));
`closefd=` and `opener=` (these where the program reaches them: in code that is never compiled, such
as an `if False:` block, they compile, [test](../tests/programs/io/bfile_open_dead.py)); a `str`
for `write()`, which CPython rejects with `TypeError`
([test](../tests/errors/io/bfile_write_str.py)), and other buffer objects; `read1()`, `peek()`,
`readinto()`, `detach()` and `raw`; and the classes as names (`io.FileIO`, `io.BufferedReader`)
and `typing.BinaryIO`. Deviations:

- `open()` of a binary mode that the program computes (`open(p, mode)`) makes a text file here,
  whose open raises `NotImplementedError`, as the file's class must be known as the program
  compiles ([test](../tests/deviations/bfile_mode_computed.py)).
- In a file opened `a+b`, a write is at the file's end at once, as the OS appends it, so `tell()`
  and reads before the next flush show the file as it will be. CPython's `BufferedRandom` keeps
  the write in its buffer at the position where it was made until it flushes it
  ([test](../tests/deviations/bfile_append_buffer.py)).

### Path modules

`posixpath` supports string constants, `normcase`, `isabs`, `join`, `split`,
`splitext`, `splitdrive`, `splitroot`, `basename`, `dirname` and `normpath`.
`genericpath` supplies their helpers. `abspath`, `relpath`, `commonpath`,
`commonprefix`, `expanduser`, `expandvars`, `realpath` and filesystem tests are
outside this supported API set. Builtin `os.path` has its
[own documented APIs](../docs/language/modules.md#builtin-modules-and-files), which
include `abspath`, `relpath`, `expanduser` and `commonprefix`.

`stat` supports constants, `S_IS*`, `S_IMODE` and `S_IFMT`, but not `filemode`.

### `pathlib`

`pathlib` is Pystachy's own subset (`lib/pathlib.py`) of CPython 3.13.16's package, for POSIX: its
`PurePosixPath` and `PosixPath` classes, which `PurePath` and `Path` name, as CPython's
`PurePath(...)` and `Path(...)` make them on POSIX, with CPython's code for their methods
([test](../tests/programs/library/lib_pathlib.py)):

- Pure paths: construction from strs and paths, `/` and `joinpath()`, `str()`, `repr()`,
  `as_posix()`, `parts`, `drive`, `root`, `anchor`, `parent`, `parents` (indexing, `len()`,
  `in`, iteration), `name`, `suffix`, `suffixes`, `stem`, `with_name()`, `with_stem()`,
  `with_suffix()`, `relative_to()` (also `walk_up`), `is_relative_to()`, `is_absolute()`,
  `match()`, equality, hashing and ordering, with CPython's errors.
- Concrete paths: `exists()`, `is_dir()`, `is_file()`, `is_symlink()` (CPython's errors for
  what they do not ignore), `open()`, `read_text()`, `write_text()`, `iterdir()`, `glob()` and
  `rglob()` (CPython 3.13's selectors and order, hidden files included; given `case_sensitive`,
  literal parts too match the directory's entries:
  [test](../tests/programs/library/lib_pathlib_glob_case.py)), `mkdir()` (also
  `parents` and `exist_ok`), `touch()`, `unlink()`, `rmdir()`, `rename()`, `replace()`,
  `absolute()`, `resolve()`, `expanduser()`, `cwd()` and `home()`.
- A path's constructor takes at most eight segments, as parameters, so that subclasses can
  derive from the classes, and unpacking a list into it (`Path(*parts)`) is not supported; a
  tuple's items are. Iterating over a `Path`'s `parents` gives its parents typed as `PurePath`
  objects (indexing one gives a `Path`), so a `Path` method of an iterated parent is a
  compile-time error.
- Pystachy has no `os.PathLike` objects: `open()` and the `os` functions take `str(path)`,
  and passing a path is a compile-time error; `path.open()` opens one.
- `expanduser()` of `~user`, and `open()` with `buffering`, `errors` or `newline`, raise
  `UnsupportedOperation` ([deviation](../tests/deviations/lib_pathlib_unsupported.py)).
  Windows paths, `stat()`, `lstat()`, binary I/O (`read_bytes()`, `write_bytes()`), `walk()`,
  `samefile()`, links, owners, `chmod()`, `as_uri()` and `full_match()` are not provided; a
  subclass's derived paths are `PurePath` or `Path` objects.

### `glob`

`glob` is Pystachy's own subset (`lib/glob.py`) of CPython 3.13.16's module: `glob()` and
`iglob()` with `root_dir`, `recursive` and `include_hidden`, `escape()` and `has_magic()`,
with CPython's functions for them and their order of results
([test](../tests/programs/library/lib_glob.py)). On POSIX, `escape()` and `has_magic()`
accept both `str` and `bytes`. With no metacharacters, `escape()` returns its input by
identity. `glob()` and `iglob()` take text paths
([CPython-derived cases](../tests/programs/upstream/upstream_glob_escape.py)). Directories are listed with `os.listdir()`
and tested with `os.path.isdir()`, as CPython's `os.scandir()` entries would be. `dir_fd`
raises `NotImplementedError`, and `translate()` is not provided.

### `shutil`

`shutil` is Pystachy's own subset (`lib/shutil.py`) of CPython 3.13.16's module, for str paths:
`copyfileobj()`, `copyfile()`, `copymode()`, `copy()`, `move()` and `rmtree()`, with `Error`,
`SameFileError` and `SpecialFileError` and CPython's checks and messages
([test](../tests/programs/library/lib_shutil.py)). `copyfile()` copies a file's bytes through
the runtime; it opens and checks the source before it truncates the destination, as CPython does
([test](../tests/programs/library/lib_shutil_copyfile_dir.py)).
`rmtree()` is CPython 3.13's Linux `_rmtree_safe_fd`, in the runtime: it walks the tree through
directory descriptors, and finds each directory by the device and inode that `lstat()` found,
so a directory replaced by a link during the walk is not followed. Its steps, their order and
its errors are CPython's, a link's included (`OSError: [Errno None] None: 'path'`), and
`ignore_errors` passes over each ([test](../tests/programs/library/lib_shutil_rmtree.py)).
`rmtree.avoids_symlink_attacks` is not provided. `rmtree()`'s `onerror`, `onexc` and `dir_fd`,
and `copyfile()` of a link with `follow_symlinks=False`, raise `NotImplementedError`
([deviation](../tests/deviations/lib_shutil_unsupported.py)). `move()` of a file to another
file system copies it with `copy()` (CPython uses `copy2()`, which also copies its times), and
of a directory raises the rename's `OSError`. `copytree()`, `copy2()`, `copystat()`, `which()`,
`disk_usage()`, `get_terminal_size()` and the archive functions are not provided.

### `argparse`

Create a parser in the module body or a top-level function. Assign it to one
name, then call `add_argument()` directly in the same block before parsing.
The compiler gives each destination a field on a fresh Namespace. An optional
integer without a default has type `int | None`. A required one has type `int`.

```python
import argparse

parser = argparse.ArgumentParser(prog="scale")
parser.add_argument("filename")
parser.add_argument("-n", "--repeat", type=int, default=1)
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()
print(args.filename, args.repeat, args.verbose)
```

| Form | Supported behavior |
|---|---|
| Declarations | Literal `prog`, `description`, `add_help`, and `allow_abbrev`. Positional names, short and long options, aliases, `dest`, `required`, `metavar`, and help text. |
| Values | Builtin `str`, `int`, and `float`; homogeneous literal choices; scalar defaults of the result type or `None`; `store_true` and `store_false`. |
| Positionals | One value, `nargs="?"`, or a final `"*"` / `"+"` positional. Repeated values form a typed list. |
| Parsing | `parse_args()` and `parse_known_args()` take process arguments or an explicit `list[str]`. Each call returns independent values. Known-argument parsing also returns the remaining strings in order. |
| Output | Help and options declared with `action="version", version="%(prog)s 1.0"` print to stdout and exit 0. Argument errors write usage and a diagnostic to stderr and exit 2. The English formatter uses `COLUMNS` or 80 columns. |

Results support field access, identity, representation, equality and
`isinstance(result, argparse.Namespace)`. Each schema has its own native class,
so `type(result) is argparse.Namespace` is false and its name is compiler-generated.
Equality compares declared fields. A foreign operand returns false without
reflected comparison. Distinct results sharing a NaN field can compare unequal
under the native float identity rules.

Code can raise and catch `argparse.ArgumentTypeError` when validating values.
Parser declarations must stay in their owning scope. Runtime-defined schemas,
groups, subparsers and custom actions or converters are outside this subset.
The [JSON repair command](../ports/json_repair/PORT.md#file-and-pipe-command)
uses an optional filename, boolean switches and a named output file.

### `getopt`

`getopt` and `gnu_getopt` support short and long options, unique long-option
prefixes, GNU option interleaving, a leading `+`, and `POSIXLY_CORRECT` through
`os.getenv`. `GetoptError` exposes `msg`, `opt` and the legacy `error` alias.

`longopts` must be `list[str]`; CPython also accepts one string. Messages are
untranslated. Error messages and parsing otherwise follow the upstream code.

## Processes and threads

<a id="thread"></a>

### `_thread`

`_thread` is `_pystachy_thread`, a port of the C module `_thread` (`Modules/_threadmodule.c`)
that Pystachy loads for `import _thread`, for the one thread that a Pystachy program runs, as
CPython's builds without threads had `_dummy_thread` until 3.8. Locks (`allocate_lock()` and
`LockType`, also through the obsolete `allocate()`, `acquire_lock()`, `release_lock()` and
`locked_lock()`) and reentrant locks (`RLock`, with the `_is_owned()`, `_recursion_count()`,
`_release_save()` and `_acquire_restore()` of `threading.Condition`) work as CPython's do in one
thread: `acquire()` of an unlocked lock takes it, `acquire(False)` of a locked one gives `False`,
and an `acquire()` with a timeout gives `False` once the timeout has passed. `acquire()` checks
its arguments as CPython's does, with its `ValueError` and `OverflowError`, and `release()` of a
lock that is not held raises CPython's `RuntimeError`. `_count()`, `stack_size()`,
`interrupt_main()`, whose SIGINT raises `KeyboardInterrupt`, `exit()`, `daemon_threads_allowed()`,
`TIMEOUT_MAX` and `error`, which is `RuntimeError`, work as in CPython, and `_local` is a base
class whose subclasses' `__init__` binds their fields.

- `start_new_thread()`, the obsolete `start_new()` and `start_joinable_thread()` raise
  `NotImplementedError` ([deviation](../tests/deviations/lib_thread_start.py)).
- An `acquire()` of a locked lock that would wait for ever (without a timeout) raises
  `RuntimeError: deadlock: ...`, where CPython waits for another thread to release the lock, and
  so do `_acquire_restore()` of a reentrant lock that is held and `join()` of a thread handle that
  is not done ([deviation](../tests/deviations/lib_thread_deadlock.py)).
- `with lock:` acquires the lock and releases it as the block is left, for both kinds of lock.
- `get_ident()` is the process's id, and so is `get_native_id()`, as Linux gives a process's main
  thread the process's id; CPython's `get_ident()` is the thread's `pthread_t`.
- `interrupt_main()` of another signal than SIGINT does nothing, as CPython's default handlers do
  (Linux's signal numbers: those from 65 on are out of range).
- `_excepthook()`, which reports an exception that a thread's `run()` raises, raises
  `NotImplementedError`: no thread but the main one runs.

### `threading`

CPython's `threading.py` on the one-thread `_thread` above, with marked edits, compiled with
[dynamic `Any`](../docs/dynamic-any.md) for a thread's target, its arguments and its name. Locks,
reentrant locks (`RLock()` is `_thread`'s; the Python `_RLock` works too), `Condition` (of either
lock, or of an object with `acquire()` and `release()`), `Semaphore`, `BoundedSemaphore`, `Event`,
`Barrier`, `Timer`, `local`, `current_thread()`, `main_thread()`, `enumerate()`,
`active_count()`, `get_ident()`, `get_native_id()`, `stack_size()`, `TIMEOUT_MAX` and the main
thread's `Thread` object (`MainThread`) work as in CPython where no other thread runs, and so do
`Thread` subclasses and their objects, but for starting them
([test](../tests/programs/library/lib_threading.py)).

- `Thread.start()` (also of a `Timer`) raises `_thread`'s `NotImplementedError`, where CPython
  runs the thread ([deviation](../tests/deviations/threading_start.py)); a wait that only another
  thread could end raises `_thread`'s `RuntimeError: deadlock: ...`.
- `run()` of a `Thread` (or a `Timer`) called directly calls its target without arguments, and
  raises `NotImplementedError` where it has `args` or `kwargs` (an `Any` value is not unpacked
  into a call's arguments). The target, its arguments and the name are `Any` values, so a list or
  dict of typed items cannot be one of the arguments.
- `Condition` calls its lock's `acquire()` and `release()`, which CPython binds as the condition's
  own attributes, and its `__exit__()` releases the lock. `_release_save()`, `_acquire_restore()`
  and `_is_owned()` are the lock's own where it is a reentrant lock; of any other lock they are
  `Condition`'s.
- A `Thread` keeps no copy of `sys.stderr` and no `_invoke_excepthook` (no started thread reports
  an exception); `_dangling` is a set, which keeps its threads (no weak containers), and
  `current_thread()` never makes a `_DummyThread`. There is no `register_at_fork()` (no
  `os.fork()`), and the module does not `del _thread` (#612).

### `atexit`

`atexit` is `_pystachy_atexit`, a port of the C module `atexit` that Pystachy loads for
`import atexit`. `register(func, *args, **kwargs)` (also as a decorator) records a callback
that calls `func` with those arguments, and the end of the program runs the callbacks, the last
registered first, as CPython's finalization does: after the program's code, and also where it
ends with `sys.exit()` or with an exception that nothing catches, whose message is shown first.
A callback that raises, also `SystemExit`, is reported on stderr and the next one runs; the exit
status stays the program's. `_run_exitfuncs()`, `_clear()` and `_ncallbacks()` work as in
CPython.

- `atexit.unregister()` raises `NotImplementedError`
  ([deviation](../tests/deviations/lib_atexit_unregister.py)): a callback is a closure that calls
  the function, and Pystachy cannot compare it with another function.
- The report of a callback that raises is `Exception ignored in atexit callback:` and the
  exception's last line, where CPython names the function and shows the traceback.
- In an extension module (`pystachy ext`), `register()` records callbacks that never run:
  CPython's own finalization does not know of them.

## Runtime services

### `abc`

`abc` is `_pystachy_abc`, which Pystachy loads for `import abc`, as CPython has imported its
own `abc` before a program runs. A class that derives from `ABC`, or whose class statement
passes `metaclass=ABCMeta`, has abstract methods: those its body decorates with
`@abstractmethod` (also under `@property`, `@classmethod` and `@staticmethod`, and through the
deprecated `abstractproperty`, `abstractclassmethod` and `abstractstaticmethod`), and those of
its base it does not define again. Making an object of a class that has one evaluates the
arguments and raises CPython's `TypeError: Can't instantiate abstract class C without an
implementation for abstract methods 'a', 'b'`. Abstract methods can have bodies, which
`super()` calls; `isinstance()` of an ABC is decided by the class statements, as for any class.

- `register()`, which makes a virtual subclass, and reading `__abstractmethods__` are
  compile-time errors, and so is defining `__subclasshook__`, the class method through which
  CPython's `isinstance()` asks a class.
- An abstract method is implemented by a `def` (a class attribute that shadows a method of the
  base is not supported).
- `update_abstractmethods()` is not supported: class decorators are not compiled.

### `types`

`types` is Pystachy's own module for CPython's `Lib/types.py`, of which it has `TracebackType`,
the class of the object a `with` statement passes to `__exit__()` (see [Contextlib](#contextlib)),
`MappingProxyType` and `GenericAlias`. `GenericAlias` is for CPython's idiom for a generic class:
`__class_getitem__ = classmethod(GenericAlias)` (or `classmethod(types.GenericAlias)`) in a class
body defines nothing in Pystachy, so the class compiles as it does without it
([test](../tests/programs/reflection/types_generic_alias.py)). Its subscripts in annotations, evaluated or
not, name the class, as CPython does not check their arguments: types, or number, `None`,
`True`, `False` and `...` constants (`C[1]`, `C[int, ...]`). A string argument is a forward
reference, as elsewhere in an annotation, and any other argument must still be an annotation
([test](../tests/programs/reflection/types_generic_alias_subscripts.py),
[constants](../tests/programs/reflection/types_generic_alias_constants.py)); `re.Pattern` and `re.Match` follow
the idiom, as CPython's `_sre` types are generic. At run time, where CPython makes them
`types.GenericAlias` objects, they are a compile-time error
([error test](../tests/errors/reflection/types_generic_alias_subscript.py)).

`MappingProxyType(d)` is a read-only view of dict `d`, CPython's `mappingproxy`
(`lib/_pystachy_mappingproxy.py`): indexing, `in`, `len()`, iteration (which fails as the dict's
iterator does where the dict changes size), `reversed()`, `get()`, `keys()`, `values()`, `items()`,
`copy()`, `==` and `!=` with a dict or another view, `|` (a new dict), `str()` and `repr()` give
CPython's results, from the dict's items as they are when the view is read; `|=` and `hash()` raise
CPython's `TypeError` ([test](../tests/programs/library/lib_types_mappingproxy.py)). Item assignment and
deletion are compile-time errors, where CPython raises `TypeError`
([error test](../tests/errors/library/lib_types_mappingproxy_setitem.py)). A view has no
attributes of its own, as CPython's has none, so code given only the view cannot reach its dict:
`hasattr()` of its fields or of `__dict__` is false, `__init__` leaves it viewing its dict, and
`type(view).__module__` is `builtins` ([test](../tests/programs/library/lib_types_mappingproxy_opaque.py));
reading or assigning a field is a compile-time error, where CPython raises `AttributeError`
([error test](../tests/errors/library/lib_types_mappingproxy_field.py)).

- It takes a dict, whose key and value types are the view's (`MappingProxyType[str, int]`);
  CPython's takes any mapping. `keys()`, `values()` and `items()` give lists, as a dict's do, and
  `dict(view)` and `dict | view` are compile-time errors, as for other mapping objects.
- A view is equal only to a dict or a view of an equal dict: compared with an object of another
  class it is unequal, where CPython compares its dict with the object, whose own `__eq__`, given
  the dict, may decide ([deviation](../tests/deviations/lib_types_mappingproxy_eq_other.py)).
  Comparing a dict with such an object is a compile-time error.
- Through a dynamic `Any` value, a view is an object like others: it is not iterable, and its
  `keys()`, `values()` and `items()`, typed lists, are compile-time errors (dynamic `Any`'s
  [deviations](../docs/dynamic-any.md#deviations)).

- Any other use of `GenericAlias`, such as calling it, is a compile-time error
  ([error test](../tests/errors/reflection/types_generic_alias_call.py)).
- The module's other names, CPython's (`SimpleNamespace`, `FunctionType`,
  `MethodType`, `ModuleType`, `NoneType`, `new_class()`, `coroutine()`, ...), import as in
  CPython, also in an optional import, but any use of one is a compile-time error
  ([error test](../tests/errors/reflection/types_unsupported_name.py)): Pystachy has no such objects, or
  none that behave exactly as CPython's.

### `warnings`

CPython's `warnings.py`, with marked edits, which decide as CPython's C module `_warnings` does
(`Python/_warnings.c`), as CPython runs that one: the registries, `warn()`'s checks of its
arguments and the types of `warn_explicit()`'s file and line. `warn()` and `warn_explicit()` of a
`str` or of a warning (also of a class of the program), the filters (`simplefilter()`,
`filterwarnings()` by message, category, module and line, `resetwarnings()` and
`sys.warnoptions`, read as the module is imported) and their actions, `catch_warnings()` (also
`record=True` and `action=...`), `formatwarning()`, `showwarning()` to a file and `_deprecated()`
work. The module imports `re`, which its default filters need, and `string`'s `Formatter`, which
formats `_deprecated()`'s message.

- `warn()` shows a warning at `<sys>`, line 0, as Pystachy has no frames (`sys._getframe()`):
  CPython gives that location where the stack is shallower than `stacklevel`, and otherwise the
  file and line of the code that warns, with its source line. Every warning is the main
  program's: its module is `__main__`, so that the default filters show a `DeprecationWarning`
  as CPython shows one that the main program's code causes, and its registry is the main
  program's, so that the `default` action shows a text and category once in the program, where
  CPython shows it once per location
  ([deviation](../tests/deviations/lib_warnings_location.py)).
- No warning shows a source line, as there is no `linecache`: CPython shows the line of a file
  that `warn_explicit()` names where the file exists. `module_globals` is not read.
- A registry's keys are `(text, category, lineno)` tuples, as a dict's keys have one type:
  CPython's `(text, category)` key has a line number that no C int is, and so has the key of the
  filters version, `version` in CPython; a value is 1 for `True`. The default filter's module is
  the pattern `re.compile('__main__\\Z')`, which matches the module name `__main__` alone, as the
  str `'__main__'` that CPython's C module keeps does
  ([test](../tests/programs/library/lib_warnings_main_filter.py)); `warnings.filters` shows the pattern (same
  deviation test).
- A message that is neither a `str` nor a warning raises `TypeError`, where CPython takes the
  object itself as the warning's text; `showwarning()` and `formatwarning()` given a `str` make a
  warning of its category of it, which a recorded message holds, where CPython keeps the `str`
  ([deviation](../tests/deviations/lib_warnings_message_type.py)).
- `sys.warnoptions` names the builtin warning categories (also as `builtins.NAME`): another name
  is an unknown category, and a dotted one names a module, which is not imported by name, so it
  is an invalid module name.

Not supported, as compile-time errors:
- Replacing `showwarning()` or `formatwarning()`, as a module's function is bound once
  ([error test](../tests/errors/library/lib_warnings_showwarning.py)), and `catch_warnings(module=...)`,
  as a module is not a value.
- A recorded message's `file` and `source`
  ([error test](../tests/errors/library/lib_warnings_message_file.py)).
- A filter of a tuple of categories, which CPython's `issubclass()` takes
  ([error test](../tests/errors/library/lib_warnings_category_tuple.py)).
- A `skip_file_prefixes` tuple of a `str` and an item of another type, as `warn()` checks its
  items one by one ([error test](../tests/errors/library/lib_warnings_skip_prefixes_mixed.py)): CPython
  raises `TypeError` for it where the call runs, as for a tuple of other items alone
  ([test](../tests/programs/library/lib_warnings_skip_prefixes.py)).
- `deprecated`, which sets the attribute `__deprecated__` of the function it decorates and wraps
  it with `functools.wraps()` ([error test](../tests/errors/library/lib_warnings_deprecated.py)).

<a id="_weakref-prototype"></a>

### `logging`

CPython's `logging/__init__.py` (the package's own module: no `logging.config` or
`logging.handlers`), with marked edits, compiled with [dynamic `Any`](../docs/dynamic-any.md): a
record's message, its arguments, a level's name and the values that a format interpolates are
`Any` values. Loggers and their hierarchy (`getLogger()`, `getChild()`, `getChildren()`,
`propagate`, `disabled`), levels (`setLevel()` of a level or a name, `getLevelName()`,
`addLevelName()`, `getLevelNamesMapping()`, `disable()`), the module's functions and `basicConfig()`,
`Formatter` in its `%`, `{}` and `$` styles (also with `defaults`), `extra`, `exc_info` and
`exception()`, `Filter` and filter functions, `Handler`, `StreamHandler`, `FileHandler`,
`NullHandler`, the last resort handler, `Handler.handleError()`, `makeLogRecord()` (whose dict's
keys that name a record's attributes, `exc_text` and `stack_info` among them, set them:
[test](../tests/programs/library/lib_logging_make_record.py)), `shutdown()` at exit and the
handlers' locks work
([tests](../tests/programs/library/lib_logging.py), [configuration](../tests/programs/library/lib_logging_config.py),
[stderr](../tests/programs/library/lib_logging_stderr.py)). `%`-style messages and formats are
formatted by `_pystachy_percent` (`fmt % args` of a format string that only the run time knows),
and `%(asctime)s` by `_pystachy_time`, as `time.strftime()` of `time.localtime()` formats it.

- There are no frames: a record's caller is the one CPython gives where it has none,
  `(unknown file)`, line 0, `(unknown function)` (`pathname`, `filename`, `module`, `lineno`,
  `funcName`), and `stack_info` and `stacklevel` add nothing. `Handler.handleError()` shows
  `Logged from file (unknown file), line 0` where CPython shows the caller's frames.
- There are no tracebacks: a record's `exc_info` is `(type(e), e, None)`, and its text is the
  exception's [traceback lines](#traceback), its causes' and its own last line, without CPython's
  `Traceback (most recent call last):` and frames. `exc_info=True` (also `exception()`) outside
  an `except` clause adds no text, where CPython's adds `NoneType: None`; a `(type, value,
  traceback)` tuple is not supported, and `makeLogRecord()` of a dict whose `exc_info` is not
  `None` raises `NotImplementedError` (as `SocketHandler`'s and `QueueHandler`'s dicts have it,
  `None` works) ([test](../tests/deviations/lib_logging_exc_info.py)).
- A message's arguments are `Any` values, so a list, dict or set of typed items cannot be one
  (the compiler says so where it is passed: pass `str(x)`, or format the message first); a
  mapping argument (`%(name)s` of a dict) is a `dict` of `Any` values. `extra` is a
  `dict[str, Any]` (a dict display, at the call); its items are the record's for the formats,
  which read them by name, but not attributes of the record (`record.user`).
- The keyword arguments of the logging calls and of `basicConfig()` are parameters: an unknown
  one is a compile-time error, where CPython raises `ValueError`; `stream` and `filename` count
  as given where they are not `None`, and a `format` of `None` is the style's default. A stream
  is a file or an `io.StringIO` (a [reference union](../docs/language/typing.md#native-reference-unions)),
  and `StreamHandler`'s repr shows no stream name. `FileHandler` writes UTF-8: another encoding
  raises `NotImplementedError`, and `errors` is not passed on.
- `setLoggerClass()`, `getLoggerClass()`, `setLogRecordFactory()` and `getLogRecordFactory()`
  raise `NotImplementedError` (a class is not a value): `Logger` makes the loggers and
  `LogRecord` the records. `Formatter.converter` is not supported (times are local), nor is
  `LoggerAdapter`, whose methods pass `**kwargs` of values of different types; `captureWarnings()`
  needs `warnings.showwarning` to be replaceable, which [warnings](#warnings) does not support.
- A filter that is an object of `Filter` or a subclass is asked through its `filter()`; any other
  filter is called, so an object of another class with a `filter()` method raises `TypeError`.
  `Filterer.filter()` gives `False` or the record, as in CPython.
- Named handlers are kept in a dict (no weak containers), so that one stays registered until it
  is closed, where CPython drops it once nothing else refers to it.
- A record's `threadName` is `MainThread`, `processName` `MainProcess` and `taskName` `None`, as
  for CPython's main thread outside asyncio; the module does not `del StrFormatter` (#612).

### `traceback`

`traceback` is Pystachy's own subset (`lib/traceback.py`) of CPython 3.13.16's module. Pystachy keeps
no tracebacks and has no frames, so an exception formats as CPython formats one whose
`__traceback__` is `None`: `format_exception()`, `print_exception()`, `format_exc()` and
`print_exc()` give the exception-only lines of the exception's causes (`raise ... from`), each
followed by CPython's `The above exception was the direct cause of the following exception:`,
and then its own; `format_exception_only()` gives its last line, `Type: message` (or `Type` where
the message is empty, `module.Type` for a class outside `__main__` and `builtins`). The legacy
`(type, value, tb)` arguments work too ([test](../tests/programs/library/lib_traceback.py)). These
are the lines whose last one an uncaught exception's report shows.

- An exception that was raised shows no `Traceback (most recent call last):` and frames, and one
  that another exception's handling caused (`__context__`) shows no `During handling of the above
  exception, another exception occurred:` and earlier exception
  ([deviation](../tests/deviations/lib_traceback_context.py)); `__notes__` and a `SyntaxError`'s
  location are not shown.
- The stack functions (`extract_stack()`, `format_stack()`, `print_stack()`, `extract_tb()`,
  `format_tb()`, `print_tb()`, `format_list()`) give and print nothing. `TracebackException`,
  `StackSummary`, `FrameSummary`, `walk_stack()`, `walk_tb()` and `print_last()` are not provided.
- The legacy form with a value of `None` (`print_exception(ValueError, None, None)`) raises
  `TypeError`, where CPython shows `NoneType: None`.

### `weakref` and `_weakref` (prototype)

The [weak-reference contract](../docs/weakref.md) covers `ref` and
`ReferenceType`, one class, to ordinary class instances: calling a reference
returns its referent, or `None` once the collector has reclaimed it. While both
referents live, `==`, `!=` and `hash()` are the referents'; a dead reference
equals only itself and keeps a hash computed before. Referents die when the
collector finds them unreachable, not when CPython's last counted reference
goes, so a reference to a temporary still compares by its referent until a
collection clears it. `repr()` is CPython's, without the ` (NAME)` suffix CPython
adds for a referent whose class defines `__name__`. A reference has no attributes
of its own: reading, assigning, reflecting over or `hasattr()` of its fields,
which are the module's, is rejected or false, and `r.__init__(obj)` leaves it
unchanged. A callback, `ref(obj, callback)`, runs once with the reference after
the collection that finds the referent dead, where the program next makes or
calls a reference, rather than when CPython's last counted reference goes: a
referent's callbacks newest reference first, none of a reference that is itself
dead, and an exception one raises reported as CPython reports one it ignores. A
callback must be a function or `None`. `__callback__`, proxies,
`getweakrefcount()`, `getweakrefs()`, weak containers and the reuse of one
reference per referent (`ref(x) is ref(x)`) are absent.

`weakref` is CPython's module, adapted ([test](../tests/programs/library/lib_weakref_module.py)): its `ref`
and `ReferenceType` are `_weakref`'s, also through from-imports and `import *`.
`_weakrefset` is CPython's file, unchanged.

- `WeakSet`, `WeakValueDictionary`, `WeakKeyDictionary` and `WeakMethod` keep
  CPython's code, which is a compile-time error where a program uses them: `WeakSet`
  binds a method under another name (`__sub__ = difference`), the dictionaries derive
  from `_collections_abc.MutableMapping`, and `WeakMethod` from the generic
  `ReferenceType` ([error tests](../tests/errors/library/lib_weakref_weakset.py)).
- `proxy`, `ProxyType`, `CallableProxyType`, `ProxyTypes`, `getweakrefcount()`,
  `getweakrefs()` and `finalize` are absent, and `__all__` leaves them out
  ([deviation](../tests/deviations/lib_weakref_all.py)); `getweakrefcount()` would need
  CPython's one reference per referent, and `finalize` takes `*args` and `**kwargs`.
- `WeakSet` is not registered as a `MutableSet`: a class is not a value here
  ([#7](https://github.com/den-run-ai/pystachy/issues/7)).
- `_remove_dead_weakref()`, `_weakref`'s in CPython, is `weakref`'s own here.

## Native interoperability

### `ctypes`

Only [static declarations](../docs/ffi.md#static-ctypes-declarations) are supported:
literal module-level `CDLL`, complete immutable `argtypes`/`restype` pairs, and
direct fixed-arity calls. The FFI guide lists accepted scalar types, bytes,
pointer cells and rejected dynamic features. The adapted llvmlite example verifies
real parsing, verification and ownership; it is not whole-package support.

Pointer integers are restricted to `[0, 2**63)`. Negative inputs or high-bit results
raise `OverflowError`, including output-cell reads; CPython instead exposes
unsigned pointer-sized integers. `string_at(NULL, 0)` returns empty bytes;
other NULL reads and lengths below `-1` raise `ValueError`. Invalid non-NULL
addresses and mismatched C declarations remain the caller's responsibility.

<a id="_imp-prototype"></a>
<a id="_ast-prototype"></a>
<a id="opcode"></a>

## Removed modules

These modules were shipped earlier and have been removed; see the
[library scope](../docs/stdlib.md#library-scope).

- `_imp`: the former lock/capability prototype. Pystachy resolves imports while compiling
  and has no CPython runtime importer.
- `_ast` and `ast`: the former constructor-only prototype. Pystachy does not expose source
  parsing or AST compilation through these APIs.
- `opcode`, `_opcode` and their CPython bytecode tables. Pystachy compiles native code and
  does not execute CPython bytecode or expose code objects; `dis` remains unavailable. This is
  an intentional compatibility reduction, not a claim that the former table operations were
  incorrect.
