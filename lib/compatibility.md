# Library compatibility

This reference describes compiled behavior. The adapted sources may expose more
APIs when CPython runs them, because optional imports select CPython's C modules
and dynamic features. Differential cases live in `tests/lib_*.py`; deliberate
differences live in `tests/deviations/`, and rejected inputs in `tests/errors/`.

Pystachy uses 64-bit integers, homogeneous containers and UTF-8 byte strings.
Unless a module explicitly decodes characters, lengths and positions count bytes.
See [language compatibility](../docs/language/compatibility.md).

## Operator

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

## Path modules

`posixpath` supports string constants, `normcase`, `isabs`, `join`, `split`,
`splitext`, `splitdrive`, `splitroot`, `basename`, `dirname` and `normpath`.
`genericpath` supplies their helpers. `abspath`, `relpath`, `commonpath`,
`commonprefix`, `expanduser`, `expandvars`, `realpath` and filesystem tests are
outside this supported API set. Builtin `os.path` has its own documented APIs.

`stat` supports constants, `S_IS*`, `S_IMODE` and `S_IFMT`, but not `filemode`.
`curses.ascii` supports ASCII characters; byte strings are not Unicode character
sequences.

## CPython-only code

Ports keep code that only CPython can run, as CPython's sources have it, under
`if sys.implementation.name == "cpython":`. Pystachy decides that test at compile time, as its
`sys.implementation.name` is `"pystachy"`, and drops the block (see
[compile-time branches](../docs/language/modules.md#compile-time-branches)): `urllib.parse`'s
imports of `warnings` and `ipaddress`, its docstrings of the result fields and its
byte tables, and `statistics`' import of `random` and table of kernels.

## Pure-Python accelerators

`bisect`, `heapq`, `operator` and `stat` execute their Python implementations
when the C accelerators cannot import. Consequently, edge behavior can differ
from CPython's accelerated modules:

- `heappop([])` reports `pop from empty list`, rather than `index out of range`.
- Some keyword arguments rejected by C functions are accepted by Python functions.
- `bisect` treats `hi=-1` as a bound; `_bisect` treats it as `len(a)`.
- `stat` tests use the module's constants rather than `_stat`'s separate constants.
- For more than 2,500 items, `heapify` compares in a different order from `_heapq`'s
  cache-friendly loop, with the same result.
- `operator.__doc__` is the Python module's docstring, which CPython replaces with
  `_operator`'s.

## Module docstrings

A module's `__doc__` is its docstring, as in CPython, but for the modules written for
Pystachy: `collections`, `curses`, `functools` and `io` have docstrings of their own.

## Html and HTMLParser

`html.escape`, `html.unescape` and the HTML4/HTML5 entity mappings reuse the
adaptations merged in [#378](https://github.com/den-run-ai/pystachy/pull/378). Numeric references
are bounded before checked-int conversion and named references use the upstream HTML5 table.

`html.parser.HTMLParser` retains CPython 3.13.16's incremental parser and uses
ordinary single inheritance. Typed subclasses can override the start/end tag,
data, comment, declaration, processing-instruction and reference callbacks.
`feed`, `close`, `reset`, `getpos`, `get_starttag_text`, `convert_charrefs` and
`scripting` are exercised by the probe tests, including RAWTEXT and RCDATA.
Attribute records use `list[tuple[str, str | None]]`; missing values remain None.

Native column offsets count UTF-8 bytes, and tag/attribute name case conversion
uses ASCII-only `str.lower`. Unicode text and entity output remain supported,
but these behaviors differ from CPython for non-ASCII columns and uppercase
names. User subclass constructors and callback signatures need compatible
annotations. Multiple inheritance and dynamic attributes remain unavailable.

`_markupbase` is an internal implementation detail. Its abstract-construction
guard is omitted and its field layout is declared in `__init__`. Its legacy SGML
helpers remain in the source but are outside the compiled surface tested here.
See [the probe record](../docs/html-parser-probe.md) for provenance and commands.

## Difflib

`SequenceMatcher` accepts strings or lists of strings, including `isjunk` and
`autojunk`. It provides sequence setters, longest-match and matching-block
queries, opcodes, and the three ratio methods. `get_close_matches`, `Match`,
`IS_CHARACTER_JUNK` and `IS_LINE_JUNK` also work.

Items of other types are rejected. Generator APIs are unavailable:
`get_grouped_opcodes`, `unified_diff`, `context_diff`, `ndiff`, `restore`,
`Differ.compare`, and `HtmlDiff` tables. The linediff example groups opcodes itself.

## Getopt

`getopt` and `gnu_getopt` support short and long options, unique long-option
prefixes, GNU option interleaving, a leading `+`, and `POSIXLY_CORRECT` through
`os.getenv`. `GetoptError` exposes `msg`, `opt` and the legacy `error` alias.

`longopts` must be `list[str]`; CPython also accepts one string. Messages are
untranslated. Error messages and parsing otherwise follow the upstream code.

## Heapq

Heap operations, including `_max` variants, and `nlargest`/`nsmallest` work.
The top-k functions accept lists and supported iterables: tuples, strings,
dicts, sets, `dict.items()`, and objects with `__iter__`, with or without
`__len__`. `key=` accepts supported functions, builtins and bound methods.
Ties preserve input order.

Lists are read in place. Other inputs are first materialized by a comprehension;
therefore a key/comparison that changes a dict or set being read does not raise
CPython's iterator-mutation `RuntimeError`. A `__len__` that raises `TypeError`
is handled as in CPython. Apart from the large-heap comparison order above,
the algorithm preserves comparison and key-call order for list inputs.

`merge` is a generator and does not compile. Pass `file.readlines()` rather than
an open file directly. Materialize a generator expression with a supported
consumer before passing it to a top-k function.

## Html

`escape`, `unescape` and the HTML4/HTML5 entity mappings follow CPython 3.13.16.
Numeric references produce Unicode text, including Latin-1 characters, and named
references use the upstream HTML5 table. Oversized references are replaced according
to HTML rules without requiring arbitrary-precision integers. Decimal conversion
keeps the default 4,300-digit limit; changing that limit with `sys` is unavailable.
Caller indexing, slicing and lengths retain Pystachy's UTF-8 byte semantics.

## Keyword

`kwlist`, `softkwlist`, `iskeyword` and `issoftkeyword` use CPython 3.13.16's
keyword sets. Predicates accept positional strings or `None`; other input types
fail compilation. Membership uses frozen snapshots, so changing the public lists
does not change the predicates.

## Collections

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

## Shlex

`split`, `quote`, `join` and the lexer support POSIX/compatibility modes, comments,
quotes, escapes, whitespace splitting, punctuation, token pushback and source
stacking. Input text is read through `StringIO`; Unicode characters are read whole.

Files are read eagerly. Pushed files are closed on push rather than on source
pop; constructor files remain the caller's responsibility. Iteration and `next()` read
one token at a time from a shared position. `punctuation_chars` is writable;
its constructor accepts bools or strings, while lists fail compilation. Lexer
subclasses and arbitrary stream types are outside the compiled surface.

## Io

`StringIO` supports construction with `initial_value` and `newline`, reading and
writing, `readlines`/`writelines`, iteration, `getvalue`, positioning and
truncation, closing and stream capability queries. It exposes `closed`,
`encoding`, `errors`, `line_buffering` and seek constants. `print(..., file=buf)`
works. Newline translation, NUL padding after seeking past the end, and closed
stream errors follow CPython's implementation.

- Sizes and positions count bytes rather than Unicode characters.
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

## Csv

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

## Re

String patterns support CPython 3.13 syntax: character classes, repeats (greedy,
lazy and possessive), groups and backreferences, lookarounds, conditionals,
atomic groups, scoped flags, escapes and Unicode character classes/case folding.
The module and `Pattern` expose matching, searching, splitting, substitution,
escaping and cache purging. `Match` supports group queries (up to five groups
per `group` call), runtime-length `groups(default=None)` tuples, indexing,
dictionaries, positions, spans and expansion.

- Matches decode code points, but positions (`pos`, `endpos`, group spans and
  pattern-error positions) are byte indices. A byte that `ord()` reads as no
  character's part (a truncated, overlong or above-U+10FFFF sequence) is its own
  character, as `chr()` made it.
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
Active operations retain their decoded input, so callbacks can safely purge;
existing patterns and matches remain usable. ASCII character-class tables belong
to their pattern and preserve scoped case folding and Unicode fallback.

## Fnmatch

`fnmatch`, `fnmatchcase`, `filter` and `translate` accept strings. Translation
follows CPython's regular expressions, including Unicode ranges. Matching uses
`lib/re`'s code-point handling, and `_compile_pattern` uses a 32,768-entry typed
LRU cache with CPython-compatible statistics. Case normalization is POSIX's
identity operation. Bytes patterns are unsupported.

## Functools

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

## Textwrap

`TextWrapper` and `wrap`, `fill`, `shorten`, `dedent`, `indent` support upstream
options, mutable wrapper options and overridable class attributes. Regex work
uses `lib/re`.

Widths count bytes. Breaking a long non-ASCII word may divide its UTF-8 bytes
across lines. `unicode_whitespace_trans` must map ints to ints, with no string
or `None` replacements; custom tables are looked up byte by byte. Mutated and
custom tables retain their semantics when whitespace fast paths do not apply.
`TextWrapper` subclasses are unsupported.

## String

Constants, `capwords` and `Template` work. Templates support mapping inputs
(dicts or objects with `__getitem__`), keyword arguments or both; keywords take
precedence. `substitute`, `safe_substitute`, `is_valid` and `get_identifiers`,
plus the template and pattern attributes, are available.

Template subclasses are unsupported. Keyword values of different types, as in
`substitute(name="Ann", count=3)`, are looked up as values of their union type.
`Template.flags` is an int, invalid-placeholder columns count bytes, and
`capwords` capitalizes ASCII letters only.

`Formatter` supports `format`, `vformat`, `parse`, `get_field`, `get_value`,
`check_unused_args`, `format_field` and `convert_field`, and subclasses that
override them. `lib/_pystachy_string.py` implements the parsers of CPython's
`_string`, with its errors; `parse()` returns a list, so a malformed format string
raises before its first field is looked up. Automatic and manual numbering,
conversions, nested format specs and recursion limits follow CPython.
Positional arguments may have different types (as may keyword ones): a field's
value has their union type, which formats as its value does. When a call has
both, their types must agree, so `format("{0} {x}", 1, x="s")` is rejected.
`vformat` takes a tuple and a dict, or a `**kwargs` record; type an empty dict.

Field names with attributes or indexes (`{0.x}`, `{0[1]}`) raise `ValueError`, but
`Formatter().format()` of the base class with a constant template whose fields read
attributes, and positional arguments only, formats as `str.format()` of that template does,
which reads the attributes ([reflection](../docs/language/semantics.md#reflection)); a
loop over a constant list of such templates unrolls. `check_unused_args` receives the keys used as a list in first-use order
rather than a set. Overrides compile for every call's argument types in the
program; an override, like other functions, must return one type for each.
Field names count UTF-8 bytes, so only ASCII digits make positional ones.

## Statistics

Supported APIs are `fmean` (including weights), `geometric_mean`, `median`,
`median_low`, `median_high`, `median_grouped`, `quantiles`, `mode`, `multimode` and
`covariance` for the compatible sequence types, and `correlation` (linear and ranked) of
floats. Weighted `fmean` uses the port of CPython's
`math.sumprod` algorithm; unsupported iterators are materialized first.

- `median` and `quantiles` require floats: integer/bool inputs can produce
  different return types in CPython. `median_low` and `median_high` retain the
  item type. `median` of strings is unsupported.
- `mode` and `multimode` cannot use float keys. String inputs iterate bytes.
- Integer products in weighted `fmean` can raise `OverflowError` beyond 64 bits;
  CPython's integers continue growing.
- The port's `sumprod` returns a float, including `11.0` for integer inputs and
  `0.0` for empty inputs, where CPython can return an integer.
- `correlation` of ints is a compile-time error: it rebinds its list-of-int parameters to
  the float deviations or ranks ([error test](../tests/errors/lib_statistics_correlation.py)).
  Its ranks for `method='ranked'` come from itertools' `count()` and `groupby()`, in a list
  that starts as floats, where CPython's starts as ints and holds the same float ranks.

Unsupported APIs are `mean`, `harmonic_mean`, variance/stdev and their population
variants, `linear_regression`, `kde`, `kde_random`,
and `NormalDist`. These depend on exact fractions, decimal/long integers,
iterators, properties or other features beyond the port's compiled paths. Only
CPython runs the module's import of `random`, which `kde_random` and
`NormalDist.samples` use ([CPython-only code](#cpython-only-code)).

## Random

`Random` objects and the module's functions, which share a hidden instance, give
CPython's values for int, bool and float seeds: `seed`, `random`, `getrandbits`,
`getstate`/`setstate`, `randrange`, `randint`, `choice`, `shuffle`, `sample`
(including `counts=`), `choices` (weights or cumulative weights) and the `uniform`,
`triangular`, `normalvariate`, `gauss`, `lognormvariate`, `expovariate`,
`vonmisesvariate`, `gammavariate`, `betavariate`, `paretovariate`, `weibullvariate`
and `binomialvariate` distributions. `_pyrandom` is the Mersenne Twister of
`_random.Random` in the subset, which CPython builds in, so no `_random.py` can
replace it. `binomialvariate` uses a port of CPython's `math.lgamma` algorithm,
as Pystachy's `math` has none.

- `seed()`, `seed(None)` and `Random()` use the time, process id and monotonic
  clock, CPython's fallback when it cannot read `os.urandom()`.
- A float seeds with its hash, as in CPython; a NaN's hash is 0 rather than
  CPython's object-dependent value.
- `getrandbits(k)` takes at most 63 bits and raises `OverflowError` for more,
  before drawing. `randrange` and `randint` raise `OverflowError` where the width,
  `b + 1` or the width plus the step leaves 64 bits (`randint(a, 2**63 - 1)`).
- Populations are lists, strings and runtime-length tuples; a `range` is not a
  value, so pass `list(range(n))`. Strings are sequences of bytes past ASCII.
  Weights and counts share one numeric type. `sample` raises `TypeError` for a
  `deque`, which `isinstance` does not find a `Sequence`, and takes a dict view,
  which is a list.
- Of the module functions, only `random` and `getrandbits` convert to a typed
  `Callable`; the others are unannotated upstream methods, which unannotated
  parameters or a lambda can take.
- `randrange` and `randint` take ints or bools, and `triangular` floats: with int
  bounds, its `low == high` case would return an int.

Seeds of `str`, `bytes` or `bytearray` (SHA-512 into a long integer), `randbytes`,
`SystemRandom` (absent from `__all__`), subclasses of `Random` (its
`__init_subclass__` chooses how they draw integers) and pickling are unsupported.
An integer passed as `choices`' weights is a compile error rather than CPython's
hint to pass `k=`.

## Urllib.parse

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


## Datetime

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
- Strings are UTF-8 bytes: `fromisoformat()` rejects a non-ASCII separator, and its length
  checks count bytes, as `_datetime`'s parser does.

## Binascii

`binascii` is `_pystachy_binascii`, a port of CPython's C module (`Modules/binascii.c`) to the
subset. Pystachy loads it for `import binascii`, where CPython imports its C module; as for the
other modules that Debian's CPython builds in, a `binascii.py` on the module path is never
imported. All twelve functions are there,
with the C module's signatures, results and errors (`binascii.Error`, a `ValueError`, with its
messages): `hexlify` and `b2a_hex` with `sep` and `bytes_per_sep`, `unhexlify` and `a2b_hex`,
`b2a_base64` and `a2b_base64` (with `strict_mode`), `b2a_uu` and `a2b_uu` (with `backtick`),
`b2a_qp` and `a2b_qp` (with `quotetabs`, `istext` and `header`), `crc32` and `crc_hqx`.
`binascii.Incomplete` exists, as in CPython, where no function raises it.

- Binary data is `bytes`, as Pystachy has no `bytearray`, `memoryview` or `array`. The `a2b_*()`
  functions also take a `str` of ASCII characters, as CPython's do. Another type of argument
  is a compile-time error, where CPython raises `TypeError`.
- `hexlify(data, None)` and `b2a_hex(data, None, n)` separate nothing, as without a `sep`, where
  CPython raises `TypeError` ([deviation](../tests/deviations/lib_binascii_sep_none.py)).
- The functions are Python functions, whose reprs are `<function hexlify at ...>`, not
  `<built-in function hexlify>`. `a2b_base64.__doc__` is CPython's docstring without the
  indentation of its option's description, which CPython 3.13 removes from a Python function's
  docstring.

## Codecs

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

## Atexit

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

## Abc

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

## Struct

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
  compiles are compile-time errors ([error test](../tests/errors/lib_struct_dynamic.py)), and so
  are the methods of a `Struct` made of one, and `Struct()` of a `bytes` format.
- What CPython checks as `pack()` runs, the number of values for the format and the type of a
  value for its code (a `str` for `s`, a `float` for an integer code), is checked as the program
  compiles, with CPython's message ([error test](../tests/errors/lib_struct_arity.py),
  [another](../tests/errors/lib_struct_str.py)), and a value that may be `None` is a compile-time
  error but for `?`. So is a format CPython rejects in `unpack()`, `unpack_from()` and
  `iter_unpack()`; `pack()` and `calcsize()` of one raise CPython's `struct.error` as the
  program runs.
- `iter_unpack()` gives a list of the tuples, where CPython gives an iterator of them
  ([deviation](../tests/deviations/lib_struct_iter_unpack.py)); a `for` loop and `list()` see the
  same tuples.
- An unsigned 8-byte value from 2\*\*63 on (`Q`, and the native `L`, `N` and `P`) raises
  `OverflowError: integer result does not fit in 64 bits` as it is unpacked, since Pystachy's ints
  are 64-bit ([deviation](../tests/deviations/lib_struct_unsigned64.py)).
- Buffers are `bytes`: Pystachy has no `bytearray`, `memoryview` or `array`, and `pack_into()`,
  which writes into one, raises `NotImplementedError`.
- A format of more than nine values gives a tuple of more than nine items, which can be unpacked
  into names and indexed, but not printed, compared or hashed
  ([tuples](../docs/language/typing.md)).
- A NaN's payload is not kept: unpacking a NaN gives a NaN of its sign, which packs as the quiet
  NaN, where CPython keeps the bits of a NaN it unpacks with `f` or `d`.
- `struct.pack` and the module's other functions as values (`f = struct.pack`) raise
  `NotImplementedError` when called, as the compiler makes the calls by their names. A `Struct`'s
  methods are values, as `Struct("!I").pack` is.

## Thread

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

## Types

`types` is Pystachy's own module for CPython's `Lib/types.py`, of which it has `TracebackType`,
the class of the object a `with` statement passes to `__exit__()` (see [Contextlib](#contextlib)),
and `GenericAlias` for CPython's idiom for a generic class: `__class_getitem__ = classmethod(GenericAlias)` (or
`classmethod(types.GenericAlias)`) in a class body defines nothing in Pystachy, so the class
compiles as it does without it ([test](../tests/types_generic_alias.py)). Its subscripts in
annotations are what they are for any class, and at run time, where CPython makes them
`types.GenericAlias` objects, they are a compile-time error
([error test](../tests/errors/types_generic_alias_subscript.py)).

- Any other use of `GenericAlias`, such as calling it, is a compile-time error
  ([error test](../tests/errors/types_generic_alias_call.py)).
- The module's other names, CPython's (`MappingProxyType`, `SimpleNamespace`, `FunctionType`,
  `MethodType`, `ModuleType`, `NoneType`, `new_class()`, `coroutine()`, ...), import as in
  CPython, also in an optional import, but any use of one is a compile-time error
  ([error test](../tests/errors/types_unsupported_name.py)): Pystachy has no such objects, or
  none that behave exactly as CPython's.

## Contextlib

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
- `suppress()` takes exception classes, named, as a `with` statement's item, which is compiled
  as an `except` clause that catches them (exception classes are no values of the subset);
  `with suppress(...) as x`, and a `suppress` object elsewhere, are compile-time errors.
- `nullcontext(enter_result)` takes it positionally, and not `None` alone (`nullcontext(None)`
  is `nullcontext()`); `nullcontext` is a function that makes one of two classes' objects, and
  the managers are no subclasses of `AbstractContextManager` (class templates have no bases).
- `__doc__`, `__name__` (no `functools.wraps()`) and `gen` of a `_GeneratorContextManager` are
  not available, and its `__exit__` called with a class but no exception returns `False` (CPython
  makes the exception, `typ()`; a class is no value).
- A function that a manager decorates and that calls itself is rejected (the decorator's `inner()`
  calls itself before its return type is inferred): use the manager inside it instead.
- `ExitStack`, `redirect_stdout`, `redirect_stderr`, `chdir` and the async managers
  (`asynccontextmanager`, `aclosing`, `AsyncExitStack`, `AbstractAsyncContextManager`) are not
  ported: the subset has no list of managers of different classes, no assignable `sys.stdout`,
  no `os.getcwd()` and no `async def`.

## Unicodedata

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
point that its `str` argument's UTF-8 encodes, and the strs it gives hold the code points' UTF-8
(their `len()` counts bytes, as for any Pystachy str: see the [language
reference](../docs/language/compatibility.md#text-and-file-positions)).

- Iterating a str gives its bytes, so `[c for c in s if unicodedata.combining(c) == 0]` raises
  `TypeError` for a character of more than one byte
  ([deviation](../tests/deviations/lib_unicodedata_bytes.py)): `re.findall("(?s).", s)` gives
  the characters, as in CPython ([test](../tests/lib_unicodedata_chars.py)).
- `lookup()` takes a `str`; `bytes`, which CPython's also takes, is a compile-time error.
- `unicodedata._ucnhash_CAPI`, the capsule through which CPython's `\N{...}` escapes find
  names, is not there.
- The tables, about 850 KB of source, are compiled into each program that imports
  `unicodedata`: they add about 1 MB of IR and 0.4 s to a `pystachy run`. A function decodes
  the table it reads the first time it reads it, into a few lists of ints.

## Itertools

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
([tests](../tests/lib_itertools_terminating.py), [ranges](../tests/lib_itertools_range.py),
[generators](../tests/lib_itertools_generators.py),
[upstream](../tests/upstream_itertools.py)).

- The iterators are generators (`Generator[T]`), which yield items of one type: `chain()` of
  iterables of different item types ([error test](../tests/errors/lib_itertools_chain_mixed.py)),
  an `accumulate()` function that returns another type than the items'
  ([error test](../tests/errors/lib_itertools_accumulate_type.py)) and a `zip_longest()`
  `fillvalue` of another type than an iterable's items
  ([error test](../tests/errors/lib_itertools_zip_longest_fillvalue.py)) are compile-time
  errors, as is an `accumulate()` `initial` of another type than its sums, such as `initial=0`
  of floats, where CPython yields the int `0` and then floats (`initial=0.0` is not an error)
  ([error test](../tests/errors/lib_itertools_accumulate_initial.py)). `accumulate()` of bools
  gives a bool and then ints, as in CPython, and `zip_longest()` without `fillvalue` gives
  optional items.
- `batched()`, `permutations()`, `combinations()`, `combinations_with_replacement()` and
  `product(..., repeat=n)` yield tuples whose length the program knows only as it runs, whose
  items must be ints, floats, bools, strs or their optional types
  ([tuples](../docs/language/typing.md)): of tuples, lists or objects, they are compile-time
  errors ([error test](../tests/errors/lib_itertools_combinations_objects.py),
  [another](../tests/errors/lib_itertools_batched_tuples.py)), and `product()` with `repeat`
  needs one item type across its iterables
  ([error test](../tests/errors/lib_itertools_product_repeat_mixed.py)). `product()` without
  `repeat` and `zip_longest()` yield a tuple with an item of each iterable, of its type.
- A list unpacked into the iterables of `chain()`, `zip_longest()` or `product()` is a number of
  arguments known only as the program runs, a compile-time error
  ([error test](../tests/errors/lib_itertools_star_list.py)); `chain.from_iterable()` takes a
  list of iterables. `starmap()` takes tuples of arguments, not lists
  ([error test](../tests/errors/lib_itertools_starmap_list.py)).
- `tee(iterable, n)` gives a list of the `n` iterators, where CPython gives a tuple
  ([deviation](../tests/deviations/lib_itertools_tee_list.py)); `tee(iterable)` gives a tuple of
  two. Unpacking, indexing, `len()` and loops see the same iterators.
- `groupby()`'s key of `None` groups by the items themselves; a key function that is an object
  in a variable may be `None`, so its keys must have the items' type unless it is made in the
  call ([error test](../tests/errors/lib_itertools_groupby_key_object.py)). Its groups are
  generators that share the `groupby()`'s iterator, as the C type's do: advancing the
  `groupby()` ends the group before it ([test](../tests/lib_itertools_groupby.py)). A key that
  is not equal to itself (a NaN) still makes a group of its item, as in CPython; but a float
  has no identity, so the same NaN object twice makes two groups, where CPython makes one
  ([deviation](../tests/deviations/lib_itertools_groupby_nan.py)).
- An argument whose type the C function rejects (`permutations()`' `r` of another type than
  `int`, `count()` of something other than a number) and `islice()` or `tee()` with too few or
  too many arguments raise CPython's `TypeError` as the program runs
  ([test](../tests/lib_itertools_argtypes.py)); other wrong numbers of arguments, keywords a
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
  ([error test](../tests/errors/lib_itertools_isinstance.py)), as are the other functions as
  classes. The iterators do not print (CPython prints `count(5)`), and their type's name,
  pickling, `copy.copy()` (but for `tee()`'s `__copy__()`), `__reduce__()`, `__setstate__()`
  and `__length_hint__()` are not there
  ([error test](../tests/errors/lib_itertools_print.py),
  [another](../tests/errors/lib_itertools_type_name.py)).
- `zip()`, `map()`, `filter()`, `enumerate()` and `reversed()` are not values, so an itertools
  function cannot take one ([error test](../tests/errors/lib_itertools_zip_argument.py)); it can
  take a generator expression over them. Ints are 64-bit: `count()` past `2**63 - 1` raises
  `OverflowError`, where CPython's ints grow.
