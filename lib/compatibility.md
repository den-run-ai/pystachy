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

`attrgetter`, `itemgetter` and `methodcaller` are not supported. `length_hint`
and `index` are not general substitutes for CPython's versions: for example,
`length_hint([1, 2])` and `index(2)` fail compilation.

## Path modules

`posixpath` supports string constants, `normcase`, `isabs`, `join`, `split`,
`splitext`, `splitdrive`, `splitroot`, `basename`, `dirname` and `normpath`.
`genericpath` supplies their helpers. `abspath`, `relpath`, `commonpath`,
`commonprefix`, `expanduser`, `expandvars`, `realpath` and filesystem tests are
outside this supported API set. Builtin `os.path` has its own documented APIs.

`stat` supports constants, `S_IS*`, `S_IMODE` and `S_IFMT`, but not `filemode`.
`curses.ascii` supports ASCII characters; byte strings are not Unicode character
sequences.

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

The shipped module provides `deque` only. It supports both ends, optional `maxlen`,
extension, rotation, insertion/removal, indexing, containment/search, copies,
comparisons and repetition. Compiled construction needs a typed list, including
an explicitly typed empty list; materialize other supported iterables with `list()`.
Named generic subscriptions such as `deque[int]` remain unsupported.

Iteration is a snapshot, and `maxlen` is writable. Rich comparisons also use
snapshots when item comparison callbacks mutate a queue. Searches (`count`,
`index`, containment and `remove`) read live items and detect structural mutations
with CPython's operation-specific errors; same-size replacements are preserved.
`reversed`, reflected multiplication, comparisons with other containers, pickling,
`namedtuple`, `Counter`, `defaultdict` and `OrderedDict` are unavailable.

## Shlex

`split`, `quote`, `join` and the lexer support POSIX/compatibility modes, comments,
quotes, escapes, whitespace splitting, punctuation, token pushback and source
stacking. Input text is read through `StringIO`; Unicode characters are read whole.

Files are read eagerly. Pushed files are closed on push rather than on source
pop; constructor files remain the caller's responsibility. Iteration materializes
remaining tokens. `punctuation_chars` is writable;
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
- Iteration returns the remaining lines as a batch when the loop starts.
- `with StringIO()` is unsupported; `with` handles files only.
- `newlines`, `detach`, `fileno` and pickling are unavailable.
- Invalid argument types such as `StringIO(5)` are compile-time errors.

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

- A reader parses all input when iteration begins. Errors occur before the loop
  receives a row; `line_num` stays at the final line; rows remain in memory.
  A second iteration has no rows, even if the first stopped early. `next(reader)`
  is unsupported; use `list(reader)` or `DictReader` for a header.
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
  snapshot settings at construction; readers use settings at iteration start.
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
per `group` call), indexing, dictionaries, positions, spans and expansion.

- Matches decode code points, but positions (`pos`, `endpos`, group spans and
  pattern-error positions) are byte indices.
- `findall` with two or more groups raises `NotImplementedError`;
  `Match.groups` and `Match.regs` are unsupported variable-length tuples.
- `split` returns `list[str]` and raises `NotImplementedError` if an unmatched
  capturing group would add `None`.
- `finditer` eagerly returns a list of matches.
- `\N{...}` is a pattern error; character-name lookup is unavailable.
- For 262 identifier characters where CPython's `str.isalpha` differs, an invalid
  inline flag can receive a different error message (for example, `(?iⅠ)`).
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
`int`, `bool`, `str`, `str | None`, and tuples of supported key types. Defaults
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
`-> None`, float/object keys, variadic functions, builtin/method/lambda targets,
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
Key objects expose writable `obj` and the five comparison methods. Hashing is
rejected at compile time. The factory is a function rather than CPython's
`KeyWrapper`, so factory attributes, reflection and pickling are unavailable.
`partial`, `wraps`, `update_wrapper` and `total_ordering` remain unsupported.

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

`Formatter` and template subclasses are unsupported. Keyword values accessed by
computed names must share a type, so `substitute(name="Ann", count=3)` is rejected.
`Template.flags` is an int, invalid-placeholder columns count bytes, and
`capwords` capitalizes ASCII letters only.

## Statistics

Supported APIs are `fmean` (including weights), `geometric_mean`, `median`,
`median_low`, `median_high`, `median_grouped`, `quantiles`, `mode` and `multimode`
for the compatible sequence types. Weighted `fmean` uses the port of CPython's
`math.sumprod` algorithm; unsupported iterators are materialized first.

- `median` and `quantiles` require floats: integer/bool inputs can produce
  different return types in CPython. `median_low` and `median_high` retain the
  item type. `median` of strings is unsupported.
- `mode` and `multimode` cannot use float keys. String inputs iterate bytes.
- Integer products in weighted `fmean` can raise `OverflowError` beyond 64 bits;
  CPython's integers continue growing.
- The port's `sumprod` returns a float, including `11.0` for integer inputs and
  `0.0` for empty inputs, where CPython can return an integer.

Unsupported APIs are `mean`, `harmonic_mean`, variance/stdev and their population
variants, `covariance`, `correlation`, `linear_regression`, `kde`, `kde_random`,
and `NormalDist`. These depend on exact fractions, decimal/long integers,
iterators, properties or other features beyond the port's compiled paths.

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
