# lib/: standard library modules for Pystachy

A program's `import NAME` finds `NAME.py` or `NAME/__init__.py` next to the program, then on
`PYSTACHY_PATH`, then here (Pystachy's builtin modules, `sys`, `os`, `math` and the others
listed in [docs/language.md](../docs/language.md#builtins-and-library-modules), come first). The modules here are **unmodified** copies of CPython
3.13.16's pure-Python standard library modules that Pystachy compiles as they are: their
unannotated functions are templates, compiled for the argument types of each call, and the
code they never run (CPython's C accelerators, generators) is never compiled. `tests/lib_*.py`
checks each against CPython.

| module | from CPython 3.13.16 | SHA-256 | what works |
|---|---|---|---|
| `bisect` | `Lib/bisect.py` | `f1cf7b85fc36b5da249813fc5ab97d9464f8cc1bc817f7146206fa2713e35999` | everything, `key=` too (a function of the program or a builtin, compiled into each call) |
| `colorsys` | `Lib/colorsys.py` | `65e3dfbf7bad61d4d7d7731a69dd7e75a347fd350d91327a51010a94e6fd2f1d` | everything |
| `operator` | `Lib/operator.py` | `c048f8a6852832d5fa750d6ae772d7658c52c3511d261cb902f7edfd262e9127` | the operator functions; not `attrgetter`, `itemgetter`, `methodcaller` (class templates whose `_call` field holds a closure of `__init__`, which a field's type cannot be inferred from), `call`, `length_hint`, `index`; the in-place functions only where the result keeps its type (`itruediv(1, 2)` would rebind an int to a float) |
| `stat` | `Lib/stat.py` | `07217986d9b2172b509dab3578d18ac05ba768b418e1f1e8c90e38a8f7c2b3c6` | the constants and `S_IS*()`, `S_IMODE`, `S_IFMT`; not `filemode` (it iterates a tuple of tuples of different lengths) |
| `this` | `Lib/this.py` | `481d0cb3de511eae0b5713dad18542b07eafd9c013bb7690f7497bad49923a71` | everything (it prints the Zen of Python) |
| `posixpath` | `Lib/posixpath.py` | `69acb9e294987cd6056a2237048373cf8d6201faf1e43a49c38889b47d2fb28e` | the constants and `normcase`, `isabs`, `split`, `splitext`, `splitdrive`, `splitroot`, `basename`, `dirname`, `normpath` on `str` paths; not `join`, `relpath`, `commonpath`, `abspath`, `expanduser`, `expandvars`, `realpath`, `exists` and the other file tests (`try`, `*args`, `map`, `os.environ`, `re`) |
| `genericpath` | `Lib/genericpath.py` | `cdac5a68dd738051e0d66fc81d5947d6a1776248fc6fe862253477608d870ec4` | what `posixpath` uses of it; not `commonprefix` (`map`) or the file tests (`try`) |
| `curses.ascii` | `Lib/curses/ascii.py` | `780dd8bbaf0ee7e832f164c1772953e694a9cd1031d1ab1471af65344d3645e6` | everything, for ASCII characters (strings are byte strings) |
| `urllib` | `Lib/urllib/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | the package, which is empty; its `parse` is a port (below) |

`curses/__init__.py` is Pystachy's own stand-in: CPython's wraps the C extension `_curses`, and
so is `functools.py` (below).

## `difflib`, a port of CPython's

`difflib.py` is CPython 3.13.16's `Lib/difflib.py` (SHA-256
`1593ae08143632f4f81fea3beeeb279d803f8a9be922b12fe79664d78bba879d`) edited in 12 places, each
marked `# Pystachy port:`. It has `SequenceMatcher` (`set_seqs()`, `set_seq1()`, `set_seq2()`,
`find_longest_match()`, `get_matching_blocks()`, `get_opcodes()`, `ratio()`, `quick_ratio()`,
`real_quick_ratio()`, with `isjunk` and `autojunk`), `get_close_matches()`, `Match`,
`IS_CHARACTER_JUNK()` and `IS_LINE_JUNK()`, as CPython's code. A sequence is a str or a list of
strs (lines, words): the matcher's tables are typed for str items.

- `Match` is a `typing.NamedTuple` class, where CPython makes it with `collections.namedtuple()`;
  `SequenceMatcher` has no `__class_getitem__` (`types.GenericAlias`).
- `SequenceMatcher.__init__` types the fields, sets `a` and `b`, and builds `b`'s tables, as
  `set_seqs(a, b)` does, where CPython sets `a` and `b` to `None` first and then calls it: a class
  template's field takes the type of its first value. `isjunk` is a `Callable[[str], bool] | None`
  (a def, a lambda or one of the module's junk functions), the caches are `... | None`, and the
  tables are `dict[str, ...]` and `set[str]`.
- `find_longest_match()` and `quick_ratio()` test `x in set` and call `dict.get()` where CPython
  binds `set.__contains__` and `dict.get` to locals first: a builtin's method is no value in
  Pystachy. Their empty dicts and list are annotated.
- `get_matching_blocks()`, `get_opcodes()` and `quick_ratio()` read their cache field into a local
  and test that (a test narrows no field), so they return lists, never `None`;
  `get_matching_blocks()` makes each `Match` with `Match(*t)` where CPython maps `Match._make`.
- `get_close_matches()` keeps its best `n` with `sorted(result, reverse=True)[:n]`, the documented
  equivalent of the `heapq.nlargest()` CPython calls (which needs iterators); the module's final
  `del re` is gone (a module-level `del` is not supported).

Not compiled, because they are generators: `get_grouped_opcodes()`, `unified_diff()`,
`context_diff()`, `ndiff()`, `restore()`, `Differ.compare()` and `HtmlDiff`'s tables
(`examples/linediff` groups opcodes into a unified diff itself). A sequence of items other than
strs is a compile-time error (`tests/errors/lib_difflib_int_items.py`).

`tests/lib_difflib.py` compares it with CPython's on the cases of CPython's
`Lib/test/test_difflib.py` and the module's doctests that use these. Run by CPython, the edited
module passes that file's 57 tests. Two applications use it:
[`examples/linediff`](../examples/linediff/README.md), unified and word diffs of two files, at
about twice CPython's speed (the `SequenceMatcher` of two texts of 50,000 lines takes 39 ms,
against CPython's 124 ms), and [`examples/suggest`](../examples/suggest/README.md), spelling
suggestions from a vocabulary, where each `get_close_matches()` of 20,000 words takes 3.9 ms, against
CPython's 23 ms.

## `getopt`, a port of CPython's

`getopt.py` is CPython 3.13.16's `Lib/getopt.py` (SHA-256
`0ce875700c8798193b8e2748f7a27fc542cc4d525a1e6fc403767450ec92be99`) edited in 15 places, each
marked `# Pystachy port:` but for the six messages, which the comment that replaces the `gettext`
import describes. It has the whole module, as CPython's code: `getopt()` and `gnu_getopt()` (also
with a leading `+` in the short options, or `POSIXLY_CORRECT` set), with unique prefixes of long
options, `GetoptError` (with `msg`, `opt` and the old name `error`) and its messages.

- CPython's messages go through `gettext`'s `_()`, but `gettext` reads `sys.base_prefix`, which
  Pystachy does not have, and `%` formatting takes only a literal format string. So each message
  is `%` formatted as it is, untranslated (CPython ships no translation of them either).
- `GetoptError.__init__`'s parameters and `__str__`'s return are annotated `str`: an exception
  class is no class template, and a method without a return annotation returns `None`.
- `longopts` is annotated `list[str]` in `getopt()` and `gnu_getopt()`, since its default `[]`
  has no type otherwise. CPython also takes one str (`'alpha='`); here that is a compile-time
  error (`tests/errors/lib_getopt_longopts_str.py`).
- `opts` is annotated `list[tuple[str, str]]`: `do_longs()` and `do_shorts()`, which fill it, are
  templates, and an empty list is not typed through them.
- `do_longs()` declares `optarg: str | None` first: it is `None` or a str, set in the two arms of
  a `try`.
- `gnu_getopt()` reads `POSIXLY_CORRECT` with `os.getenv()` where CPython calls
  `os.environ.get()`: Pystachy has no `os.environ`.

`tests/lib_getopt.py` compares it with CPython's on the cases of CPython's
`Lib/test/test_getopt.py`. Run by CPython, the edited module passes that file's 8 tests and its
doctest (not the test of the translation catalogs, which needs CPython's `Tools/`).
[`examples/cut`](../examples/cut/README.md), a `cut` with GNU's options, is an application of it.

## `heapq`, with `nlargest()` and `nsmallest()` ported

`heapq.py` is CPython 3.13.16's `Lib/heapq.py` (SHA-256
`6d43277e5c76fc0f073cd388fcff852d14d068f6bb6d4886c340f8b75a1229a9`) with `nsmallest()` and
`nlargest()` edited, each edit marked `# Pystachy port:`; the rest of the file is CPython's byte for
byte. It has `heappush`, `heappop`, `heapify`, `heapreplace`, `heappushpop` and the `_max`
variants, as CPython's code, and `nlargest()` and `nsmallest()`, with and without `key=`, of a list
or of another iterable the subset passes (a tuple, a str, a dict, a set, `d.items()`, an object
with `__iter__`, with or without `__len__`), as CPython's algorithm: the same heap operations, so
the same comparisons and calls of `key` in the same order, and the same ties, as the
`(elem, order)` and `(key, order, elem)` tuples keep the input's order among equal items.

The edits, the same in both functions:

- `it = iter(iterable)` is `iterable` itself for a list, else a list of its items: the subset has
  no iterators. The list is a comprehension, `[elem for elem in iterable]`: `list(iterable)` would
  call an object's `__len__` (its length hint), which `iter()` does not.
- For n of 1, `min(it, default=sentinel, key=key)` with an `object()` sentinel is
  `[min(it, key=key)] if it else []`: the subset has neither `object()` nor `default=`.
- In `try: size = len(iterable)`, the `TypeError` of an iterable without `__len__` is raised before
  `len()`, under `if not hasattr(iterable, '__len__')`, which the argument's type decides: `len()`
  of an object without `__len__` is a compile-time error. A `__len__` that raises `TypeError` is
  caught, as in CPython.
- `zip(range(n), it)` (`range(0, -n, -1)` in `nlargest()`), which takes the first n items, is a
  comprehension over `range(min(n, len(it)))` that indexes `it`, and with a `key` a loop that reads
  each item once, before its key is called, as `zip()`'s iterator reads it (a key may change the
  list): `range()` cannot be nested in `zip()`. The loop over the other items, which goes on with `zip()`'s iterator in CPython, is
  `for i, elem in enumerate(it)`, which skips the first n: a list is read in place, as CPython's
  iterator reads it, with no copy.
- An empty `result` returns `[]`, not `result`: its tuples are not of the items' type, which the
  function returns elsewhere.

Where it differs from CPython:

- The items of an iterable other than a list are taken into a list first, so a `key` or a
  comparison that changes the dict or set being read does not raise CPython's `RuntimeError`.
- For an n above 2,500 that is less than the length, `heapify()` of the decorated items compares
  in another order than CPython's `_heapq` does (see the end of this page), with the same result.

`merge()` is an error where a program calls it: it is a generator. So is an open file as the
iterable of `nlargest()` or `nsmallest()`, as `hasattr()` of a file is not supported (its
`readlines()` is an argument), and a generator expression, which the subset has only as the
argument of `list()`, `sorted()`, `sum()` and the like (`list()` of it is an argument).

`tests/lib_heapq_topk.py` compares them with CPython's on ints, floats, strs and tuples, n of -1,
0, 1, 2, the length and around it, empty input, `key=` (a lambda, a function, a builtin,
`str.lower`, a bound method), ties, the iterables above, and objects whose `__lt__`, `__eq__`,
`__iter__` and `__len__` log their calls, so that the comparisons are CPython's, in its order. Run
by CPython, the edited module passes CPython's `Lib/test/test_heapq.py` (51 tests), and its
`nlargest()` and `nsmallest()` make the same comparisons and calls of `key`, with the same results,
as CPython's own in 36,000 calls on random inputs with many ties (lists, tuples and an object
without `__len__`, n from -2 to past the length, with and without `key`).

In an AOT executable, `nlargest(10, xs)` and `nsmallest(10, xs)` of 100,000 ints take 45 and
47 µs, against CPython's 1,970 and 1,936 µs: most items are only compared with the heap's top, an
int comparison in the compiled loop, where CPython steps an iterator and calls a rich comparison
for each; `nlargest(10, pairs, key=second)` of 100,000 `(str, int)` tuples takes 108 µs (CPython:
4,263 µs). Where the heap does more of the work the gain is smaller: `nsmallest(1000, xs)` takes
867 µs (CPython: 3,363 µs), most of it replacing and sifting `(elem, order)` tuples, and
`nlargest(1, xs)`, `max()` of the list, 234 µs (CPython: 590 µs). The `sorted()` that an n at or
past the length takes is slower than CPython's: 38 µs for 1,000 ints (CPython: 27 µs), whose sort
compares ints with a function of their own, where Pystachy's compares through a descriptor of the
items' type. (Medians of 3
runs, each the median of 5 rounds of 20 calls, 2,000 for 1,000 ints, on items from a linear
congruential generator.) [`examples/topk`](../examples/topk/README.md) picks the most frequent
words of a text with them.

## `io`, Pystachy's own

CPython's `io` is the C module `_io` (`Modules/_io/`); its pure-Python twin `Lib/_pyio.py` makes
`StringIO` a `TextIOWrapper` over a `BytesIO`, and neither compiles. `io.py` here has `StringIO`,
written after CPython 3.13.16's `Modules/_io/stringio.c` and keeping its docstrings, and
`SEEK_SET`, `SEEK_CUR` and `SEEK_END`:

- `StringIO(initial_value='', newline='\n')`, `read(size)`, `readline(size)`,
  `readlines(hint)`, iteration, `write(s)` (which returns `len(s)`), `writelines()`,
  `getvalue()`, `seek(pos, whence)`, `tell()`, `truncate(pos)`, `close()` and `closed`, `flush()`,
  `readable()`, `writable()`, `seekable()`, `isatty()`, `encoding`, `errors` and
  `line_buffering`.
- It does what `stringio.c` does. The newline modes translate what is written (`None`: `\r\n` and
  `\r` become `\n`; `"\r"` and `"\r\n"`: `\n` becomes them) and end the lines that are read (`""`:
  at `\n`, `\r` and `\r\n`). A write past the end pads the gap with NULs. `seek()` takes a nonzero
  offset only from the start. Its errors, `truncate()`'s and those of a closed stream are
  CPython's, word for word, with or without the full stop as each method has it.
- Writes at the end gather in a list that is joined when the text is read, so a text built from
  many writes takes linear time.
- `print(..., file=buf)` writes into it: the compiler passes each piece of a `print()` to the
  `write()` method of an object of the program's classes, a call each, as CPython does
  (`tests/print_file_object.py`).

Where it differs from CPython (`tests/deviations/lib_io.py`):

- Sizes and positions (`read(n)`, `readline(n)`, `tell()`, `seek()`, `truncate()`, what `write()`
  returns) count a str's bytes past ASCII, as `len()` and slicing do; CPython's count characters.
- A `for` loop over it reads the lines left when it starts: an iterator class, which would read
  each line as the loop asks for it, is not supported.
- `with io.StringIO() as f:` is a compile-time error: Pystachy's `with` takes files only
  (`tests/errors/lib_io_with.py`).
- There is no `newlines` (a str, a tuple or `None`), `detach()`, `fileno()` (CPython raises
  `UnsupportedOperation`) or pickling, and `StringIO(5)` is a compile-time type error where CPython
  raises `TypeError`.

`tests/lib_io.py` compares it with CPython's `StringIO`. Run by CPython in place of its own, it
passes 29 of the 39 `StringIO` tests of CPython's `Lib/test/test_memoryio.py` (with its `IntLike`
an int: Pystachy has no `__index__`); the others test pickling, `detach()`, `newlines`, an
iterator that is the stream itself, and the `TypeError` of an argument of another type, which
Pystachy reports at compile time. In an AOT executable, a `write()` at the end
costs 37 ns and a `readline()` 22 ns, the loop included, against 42 and 142 ns with CPython's C
`StringIO` (best of 5 runs over a million lines). [`examples/column`](../examples/column/README.md),
a `column -t` that builds its table in a `StringIO`, is an application of it.

## `csv`, Pystachy's own

`csv.py` is no copy: CPython's `csv` is `Lib/csv.py` over the C module `_csv` (`Modules/_csv.c`),
and Pystachy has no C modules. It is Pystachy's own module, written after CPython 3.13.16's
`_csv.c` and `Lib/csv.py`: a reader runs `_csv.c`'s state machine (`parse_process_char`, from
`START_RECORD` to `AFTER_ESCAPED_CRNL`) over the characters of each line, a writer escapes, doubles
and quotes as `join_append_data` does, and a dialect is checked as `dialect_new` checks it, in its
order, so that what `csv` reads, writes and rejects is CPython's, with CPython's `csv.Error`
messages, and its `TypeError` and `ValueError` messages for a bad setting. The characters the state
machine adds to a field one by one are taken as slices of the line, each run of them found with
`str.find()`.

It has `reader()` and `writer()`, with a dialect and the format parameters `delimiter`,
`quotechar`, `escapechar`, `doublequote`, `skipinitialspace`, `lineterminator`, `quoting` and
`strict`; a reader's `line_num` and `dialect`, and a writer's `writerow()`, `writerows()` and
`dialect`; the six `QUOTE_*` constants, `Error`, `Dialect`, the dialects `excel`, `excel_tab` and
`unix_dialect` (registered as `"excel"`, `"excel-tab"` and `"unix"`), `register_dialect()`,
`get_dialect()`, `unregister_dialect()`, `list_dialects()` and `field_size_limit()`; and
`DictReader` and `DictWriter`. It has no `Sniffer`. A reader reads any iterable of strs (a file,
`sys.stdin`, a list of lines, an object whose `__iter__` steps through a list), and a writer writes
to any object with a `write()` method (a file, `sys.stdout`, an object of the program's class), and
returns what `write()` returns. `writerow()` is a template: a row is a list or a tuple (or a str or
a dict, as in CPython) of strs, ints, floats, bools, `None`s or objects of the program's classes,
each field `str()`-ed as CPython does; a tuple's items may have different types
(`writerow((name, 3, 1.5))`), a list's cannot. Where it differs from CPython
(`tests/deviations/lib_csv.py`):

- A reader parses all of its input when its iteration starts, where CPython's reader is an iterator
  that parses a row at each step: an error in the data is raised before the loop sees a row,
  `line_num` is the last line's throughout the loop, the rows are all held in a list (the memory a
  file takes grows with it), and the reader has no rows left for a second iteration, also where the
  first one stopped early. `next(reader)` does not compile, as the subset has no `next()`: take the
  rows with `list()`, or the header with a `DictReader`.
- A row is a `list[str]`: a reader whose quoting is `QUOTE_NONNUMERIC` or `QUOTE_STRINGS`, which
  make floats of the unquoted fields, raises `NotImplementedError` when it is made, and one of
  `QUOTE_NOTNULL`, which makes `None` of an empty unquoted field, raises it where the row holding
  one ends. A writer quotes with each of the six quoting styles as CPython's does.
- A `DictReader`'s row is a `dict[str, str]`: a row longer than `fieldnames` (whose other fields
  CPython puts in a list under `restkey`), and a shorter one where `restval` is `None`, raise
  `NotImplementedError`; `fieldnames` is a `list[str]` or `None`, `restkey` and `restval` a str or
  `None`. A `DictReader` reads its rows, and the header, when it is made, where CPython's reads the
  header when its `fieldnames` property is first read: `line_num` is then the header's, `fieldnames`
  assigned afterwards names the fields of the rows after the header, and an error in the data is
  raised by the constructor. A `DictWriter`'s `restval` is a str or `None`, and its `ValueError` for
  the keys of a row that are not in `fieldnames` lists them in the dict's order (CPython's, in a
  set's, which varies from run to run for strs).
- `excel`, `excel_tab` and `unix_dialect` are `Dialect` objects, where CPython's are classes: a
  class is no value in the subset, and there is no inheritance to derive a dialect from
  `csv.Dialect` with, so a dialect of the program's is a registered name
  (`register_dialect("pipes", delimiter="|")`) or keyword arguments. `Dialect` is the type CPython
  calls `_csv.Dialect` (what `get_dialect()` returns, and a reader's or writer's `dialect`), whose
  fields can be assigned (CPython's are read-only): a writer writes with the settings its dialect
  had when it was made, and a reader reads with those it has when its iteration starts.
  `dialect=` is a registered name, a `Dialect` or `None`.
- An uncaught error is reported as `csv.Error` (CPython's class is `_csv.Error`). A writer of an
  object without `write()` (`tests/errors/lib_csv_no_write.py`), a format parameter that is an object
  of the program's class, a row that cannot be iterated (but an int, float, bool or `None`, which
  raise CPython's `csv.Error`; `tests/errors/lib_csv_row_not_iterable.py`) and a NamedTuple row
  (`tests/errors/lib_csv_namedtuple_row.py`) are compile-time errors, where CPython raises `TypeError` or writes the
  NamedTuple's fields; for `QUOTE_NONNUMERIC`, an object of the program's class is no number, also
  where its class defines `__float__`, `__int__` or `__index__`.

A str holds UTF-8 in Pystachy: where the dialect's characters are ASCII, the state machine reads a
line byte by byte, which reads it character by character, as no byte of a character past ASCII is a
delimiter, quote, escape, space or line break; where one of them is past ASCII, it reads the line
character by character. A field's length, which `field_size_limit()` bounds, counts characters, as
CPython's does.

`tests/lib_csv.py` compares it with CPython's `csv`: the cases of CPython 3.13's
`Lib/test/test_csv.py` that do not use `next()` or classes as dialects (line ends, NUL, escapes,
quoting, `skipinitialspace`, quoted line breaks, the end of the data, `strict`, each error with its
message, the writer's quoting, escaping and empty fields, line terminators, dialects and the
registry, `field_size_limit()`, `DictReader` and `DictWriter`), round trips through files,
characters past ASCII in fields and as the dialect's characters, and 300 random rows written and
read back and 300 random sets of lines read, with random dialects. Beyond the tests, run by
CPython in place of its own `csv`, it read 200,000 random sets of lines and wrote 200,000 random
rows as CPython's does, with random dialects (raising `NotImplementedError` only where a row would
hold a float or `None`), and its `DictReader` made CPython's dicts, `fieldnames` and `line_num` for
50,000 random files (raising `NotImplementedError` exactly where a dict would hold a `None` or a
list); compiled, it printed what it prints under CPython for 120,000 random reads and writes.
`examples/csvstat` is an application of it.

For a file of 200,000 generated orders (16.1 MB, 10 fields a row; `examples/csvstat/rwbench.py`
on a 4-core x86-64 VM, the medians of 11 runs, CPython's and the executable's in turn), compiled AOT
it reads the file in 0.850 µs a row (CPython 3.13.16: 1.333 µs), parses the file's lines already in
memory in 0.713 µs (1.221 µs), and writes the rows to a file in 0.755 µs (1.207 µs).

## `re`, a port of CPython's

`re/` is no copy: CPython's `re` is a pure-Python parser and compiler (`Lib/re/_parser.py` and
`_compiler.py`) over the C matching engine `_sre` (`Modules/_sre/`), and neither compiles as it
is (the parser's tuples of mixed types, and C). `re/__init__.py` ports CPython 3.13.16's
`Lib/re/__init__.py`, `_parser.py` and `_compiler.py` to the subset, and `re/_sre.py` ports the
engine of `sre_lib.h` and `sre.c` op for op, with its explicit stack of match contexts. They make
CPython's code of a pattern and run it as CPython's engine does, so a pattern matches, splits
and substitutes as in CPython, and raises CPython's errors, with their messages and positions.
`re/_constants.py` holds `Lib/re/_constants.py`'s numbers, and `re/_unicode.py`, which
`tools/re_tables.py` generates from CPython's own Unicode functions, the tables `_sre` reads
(`\w`, `\d`, `\s`, line breaks, the case mappings and `_casefix.py`'s extra cases), and the
identifier characters a group name may have.

It has `compile`, `match`, `fullmatch`, `search`, `findall`, `finditer`, `split`, `sub` and
`subn` (with a template or a function as the replacement), `escape`, `purge`, the flags, and
`error` with `msg`, `pos`, `lineno` and `colno`; `Pattern`'s methods, also with `pos` and
`endpos`, its `pattern`, `flags`, `groups` and `groupindex`, and `==`; `Match`'s `group()` (of up
to 5 groups at once), `m[g]`, `groupdict()`, `start()`, `end()`, `span()`, `expand()`, `pos`,
`endpos`, `lastindex`, `lastgroup`, `re` and `string`; and the reprs. It has all of 3.13's syntax:
classes, greedy, lazy and possessive repeats, named groups, backreferences, lookahead and
lookbehind, conditional and atomic groups, inline and scoped flags, the `\x`, `\u`, `\U` and
octal escapes, and Unicode's `\w`, `\d`, `\s`, `\b` and case folding. A string is matched
character by character (code point by code point). Where it differs from CPython
(`tests/deviations/lib_re.py`):

- A position (`pos`, `endpos`, `start()`, `end()`, `span()`, an error's `pos`) is an index into
  the str, which holds UTF-8, as slicing and `find()` count it: past ASCII, it counts bytes.
- `findall()` of a pattern with 2 groups or more raises `NotImplementedError`, and
  `Match.groups()` and `Match.regs` are errors where the program uses them: their tuples are as
  long as the pattern's group count, which runtime-length tuples (M4) would type.
- `split()` returns a `list[str]`, so it raises `NotImplementedError` for a pattern with a group
  that takes no part in a match, where CPython's list holds `None`. That is the signature's
  choice: a `list[str | None]` would hold it.
- `finditer()` returns a list of the matches, found before it returns.
- `\N{...}` is a pattern error: Pystachy has no table of the characters' names.
- An inline flag that is no flag, `(?iⅠ)` or `(?-Ⅰ:x)`, is an "unknown flag" where the character
  may begin an identifier, else "missing -, : or )" or "missing flag": CPython asks
  `str.isalpha()`, which differs for 262 characters such as U+2160 ROMAN NUMERAL ONE (`Ⅰ`).
- The flags are ints, not `RegexFlag` members; `groupindex` is a dict; `re.error` is the base class
  of the `PatternError` the module raises (CPython 3.13 has one class); a replacement function
  must return a str (CPython's may return `None`); and there is no `DEBUG` output, `Scanner`,
  `__index__` group number, warning or `bytes` pattern.

`tests/lib_re.py` compares it with CPython's `re`, and `tests/upstream_re_*.py` with CPython
3.13.16's own tests of it, JIT and AOT, against what CPython's `re` printed: the 403 cases of
`Lib/test/re_tests.py` (each also searched with IGNORECASE, with UNICODE and within its match,
as `test_re_tests` does) and its benchmarks, and some 1,200 cases of `Lib/test/test_re.py`, the
ones that apply to str patterns: matches and the groups backtracking restores, atomic groups and
possessive repeats, lookaround, backreferences and conditionals, flags and case folding, escapes
and Unicode classes, `sub()` and its templates, `split()`, `findall()` and `finditer()` past
empty matches, and the errors, with their messages and positions. Their headers list what they
leave out and why: the deviations above, bytes patterns, warnings, CPython's internals
(`re._compiler`, `DEBUG`) and its C types' own behaviour (immutable objects, `copy`, pickling,
the `TypeError` of a non-str argument), str subclasses, and the cases too big for `make
verify`'s run with a collection at every allocation, which run there on smaller inputs.
`tools/re_fuzz.py` (`make re-fuzz`, a step of `make verify`) runs the port on CPython against
CPython's `re`, deterministically: 2,000 random patterns must compile to the same code (or raise
the same error), and match, split and substitute 19 strings each as CPython's `re` does, every
other pattern on strs that hold UTF-8 as Pystachy's do; and the test cases too big for the
compiled tests run there at upstream's size (`make re-fuzz RE_FUZZ="20000 2"` runs 20,000
patterns of seed 2). With it, unmodified roman 5.2 prints what CPython prints. It is about 3
times slower than `_sre`.

`tools/re_probe.py` (`make re-probe`, a step of `make verify`) runs the port on CPython for
textwrap's patterns, on 20 paragraphs and 20 blocks `tools/re_bench.py` generates: each result must
be CPython's `re`'s, and the matcher's entries and the contexts it makes must stay within fixed
limits, deterministic counts that a change making the matcher do more exceeds. `tools/re_bench.py`
times the same operations, compiled and under CPython (`make re-probe RE_PROBE="--time
./pystachy"`).

One search is not `_sre`'s: a pattern that begins with `^` of `MULTILINE` (after groups' marks)
enters the matcher only where a line begins, at the string's start or after a `\n`, where `_sre`
enters it at every position and fails at once at all the others (`tests/lib_re_lines.py`). For a
block of 15 lines, `dedent()`'s `^[ \t]+$` substitution enters the matcher 16 times instead of 313,
and takes 4.2 µs compiled, against 10.9 µs before and CPython's 2.1 µs. And the matcher keeps its
contexts for reuse, the state's for all its matches (`tests/lib_re_reuse.py`), where `_sre` pushes a
new one for each nested match: they are made as deep as it goes, 7 for `wordsep_re`'s split of a
paragraph instead of 3,110, which takes about 6% less time compiled, and `wordsep_simple_re`'s 15%
less. A branch skips an alternative, and a search a position, where the alternative or the pattern
begins with a literal or a class repeated at least once (after groups' marks, for a search) and the
character there is not that one, without the nested match that would fail at once
(`tests/lib_re_first.py`): `wordsep_simple_re`'s split of a paragraph enters the matcher 79 times
instead of 468, and takes 30% less time compiled.

Each `Pattern` also keeps a 128-entry ASCII membership table for each character class it uses,
built on that class's first ASCII test and shared by later matches, searches and substitutions.
The table is indexed by the class's position in the bytecode; integer offsets into flattened
tables keep the warm path on inline `list[int]` reads. Case folding remains at the opcode that
requests the test, including scoped flags, and non-ASCII characters still use the original
`charset()` evaluator. The bytecode stays CPython's. The tables belong to the pattern, so evicting
it from `re`'s or `fnmatch`'s caches can release them; repeated matching adds no global cache.
`tests/lib_re_charset.py` checks all ASCII characters, Unicode fallback and case folding, scoped
flags, repeated use, nested substitutions and a pattern retained across `purge()`.

## `fnmatch`, a port of CPython's

`fnmatch.py` is CPython 3.13.16's `Lib/fnmatch.py` (SHA-256
`95391dac2ce9f60084d65eba2f4b9d9735e28136d55b684e1fde7d6342555963`) with 8 regions edited,
each marked `# Pystachy port:`. Its functions are CPython's: `fnmatch()`, `fnmatchcase()`,
`filter()` and `translate()` translate a shell pattern into CPython's regular expression, character
for character, and match it with `lib/re`; `_compile_pattern()` keeps the compiled patterns in an
`lru_cache(maxsize=32768, typed=True)`, so its `cache_info()` counts what CPython's does.

- `_compile_pattern(pat: str) -> Callable[[str], re.Match | None]`, with `from typing import
  Callable`: `lib/functools` types a cache from its function's annotations. A pattern is a `str`
  (CPython's also takes `bytes`, which Pystachy has not), and the matcher is the bound method
  `re.compile(...).match` as a `Callable`.
- `translate()`'s sentinel `STAR = object()` is `None` (#251): `_translate()` and
  `_join_translated_parts()` annotate their lists `list[str | None]` and test `is STAR` as before.
- `_join_translated_parts()` binds `fixed` and `res` to a list and then to the str it joins
  (#248): the lists are `pieces` and `res`, the strs `fixed` and `joined`.
- `filter()` tests `os.name == 'posix'` where CPython tests `os.path is posixpath`: a module is no
  value in Pystachy. `os.path.normcase()` is Pystachy's builtin, posixpath's: a str as it is.

`tests/lib_fnmatch.py` compares `translate()` of 45 patterns (classes, negated, reversed and
dashed ranges, `[]]`, an unclosed `[`, `&&`, `~` and `|` in a class, regex metacharacters,
non-ASCII) and the names each matches with CPython's, and the cache's statistics. A pattern
matches by code point, as `lib/re` does, so a non-ASCII name matches as in CPython.

In an AOT executable, `fnmatchcase()` of 2,000 names against 10 patterns takes 428 ns a match
with the cache and 1,236 ns compiling the pattern each time (CPython: 286 and 3,269 ns): `lib/re`
compiles a pattern about 3.6 times faster than CPython's `re`, whose parser and compiler are
Python, and matches about 1.6 times slower than its C engine `_sre`, so the cache saves Pystachy
less than it saves CPython, but still nearly two thirds of the time.

## `functools`, Pystachy's own

CPython's `Lib/functools.py` does not compile (it imports `abc`, `collections`, `reprlib` and
`_thread`, and its pure-Python `lru_cache` keeps its links in lists of mixed types and sets
attributes on a function), and its `lru_cache()` is C: `_functools._lru_cache_wrapper`
(`Modules/_functoolsmodule.c`). `functools.py` here has `cache()` and `lru_cache()` in the subset,
written after that C code, with `lru_cache`'s docstring:

- `lru_cache(maxsize)` (128 by default, `@lru_cache` bare too; a negative `maxsize` is 0) keeps the
  results of the `maxsize` most recently used calls, `lru_cache(maxsize=None)` and `cache()` every
  result, and `maxsize=0` none. The wrapper has `cache_info()`, a `CacheInfo` named tuple of
  `hits`, `misses`, `maxsize` and `currsize`, `cache_clear()`, which empties the cache and zeroes
  the statistics, `__wrapped__` and the function's `__name__` and `__qualname__`.
- It counts and updates as C does, so what a program sees of it is CPython's: a hit makes the
  call the most recently used, a miss counts before the function runs (a call that raises is
  counted, and its exception is not cached), a call that added its own key while it ran (a
  recursive call with the same arguments) returns what it computed and leaves the cache as it is,
  and a full cache gives the least recently used entry to the new result. A result is the object
  the function returned, also a falsy one or `None`.
- A dict of Pystachy holds keys of one type and values of another, so each decorated function
  has a cache of its own types: `_lru_cache_wrapper` is a generic class, `Generic[*_Ts, _R]`,
  whose `__init__` takes the function as a `Callable[[*_Ts], _R]`, so each wrapper binds `_Ts` to
  the function's parameter types and `_R` to its return type ([`docs/language.md`](../docs/language.md),
  *Typing rules*). The key of a call is the tuple of its arguments, a `tuple[*_Ts]`, which
  `__call__(self, *args: *_Ts)` takes by position (CPython's key for one `int` or `str` argument
  is the argument itself).

What it does not have, each a compile-time error (`tests/errors/lib_functools_*.py`):

- a function whose parameters or return are not annotated, that returns `None` (`-> None`: its
  results would be a `list[None]`), that takes `*args` or `**kwargs`, or whose parameter is of a
  type Pystachy's dicts cannot key (a `float`, an object; CPython hashes those): the parameters are
  `int`, `bool`, `str`, `str | None` and tuples of those;
- `lru_cache()` of a builtin, a method or a lambda (it caches a def's results, of the program or
  of a function), and of a method in a class body, where Pystachy applies no decorator;
- a call through the cache that passes a keyword argument or leaves out one that has a default
  value: `__call__(self, *args: *_Ts)` takes each of the function's positional parameters, by
  position (CPython caches each form of a call apart, `f(1)`, `f(1, 2)` and `f(1, b=2)` being three
  entries);
- `cache_parameters()`, whose dict mixes `int | None` and `bool` values.

`typed=True` is accepted and keeps no calls apart: a parameter has one type, so the calls it
would keep apart (`f(1)` and `f(1.0)`) cannot both compile. The cache needs no lock, as a
Pystachy program has one thread. `tests/lib_functools.py` and `tests/lib_functools_mod.py`
compare it with CPython's C wrapper.

In an AOT executable, a cache hit costs 24 ns (unbounded) to 31 ns (bounded) for an `int`
argument, 26 ns for a `str` one and 36 ns for a `(str, int)` pair, whose key tuple is made and
hashed for each call; CPython's C wrapper takes 60 to 61, 61 and 84 ns, a loop's step included
(medians of 3 runs over 1,000 warm keys). A miss that evicts takes 68 ns, against 104 ns.

## `textwrap`, a port of CPython's

`textwrap.py` is CPython 3.13.16's `Lib/textwrap.py` (SHA-256
`30f3d833950d53e168cc021961574b553f56aed84458712b2eb29c6495843d46`) edited in 7 places, each
marked `# Pystachy port:`. It has the whole module, as CPython's code: `wrap()`, `fill()`,
`shorten()`, `dedent()`, `indent()` and `TextWrapper`, with each of its options (also changed on
a wrapper after it is made) and its class attributes (which a wrapper can override with its own).
Its regular expressions are `lib/re`'s.

- `TextWrapper`'s class body makes the patterns `word_punct`, `letter`, `whitespace` and
  `nowhitespace`, builds `wordsep_re` and `wordsep_simple_re` of them, and then `del`s them: a
  class body can neither read its own attributes (#126) nor `del`. They are the module's
  `_word_punct`, `_letter`, `_whitespace_class` and `_nowhitespace`, which the class body reads.
- The four class attributes, each a call's result, are annotated (`dict[int, int]`,
  `re.Pattern`), and `unicode_whitespace_trans` is `dict.fromkeys()` of a list comprehension
  where CPython's is of `map(ord, ...)`, which Pystachy takes only where its items are taken at
  once.
- `wordsep_re`'s pattern is `%` of a mapping (`%(wp)s`), which Pystachy does not support:
  `str.replace()` of each name makes the same pattern.
- `max_lines=None` is annotated `int | None`: a field that a class template gives `None` needs
  its type.
- `_munge_whitespace()` replaces each character through `unicode_whitespace_trans` with
  `''.join([chr(trans.get(ord(c), ord(c))) for c in text])`: Pystachy has no `str.translate()`.
- `dedent()` enumerates `list(zip(margin, indent))`: `zip()` nested in `enumerate()` is not
  supported.

Where it differs from CPython (`tests/deviations/lib_textwrap.py`):

- A width counts a str's bytes, as `len()` does in Pystachy: past ASCII, fewer characters fit
  on a line, and a word longer than the width (`break_long_words`) is broken after that many
  bytes, which can fall inside a character, whose bytes two lines then hold apart.
- `unicode_whitespace_trans` maps code points to code points, an int each, the type of its default:
  a table with a str or `None` value, which `str.translate()` takes to replace a character with
  several or to delete it, is a compile-time type error (`tests/errors/lib_textwrap_trans_str.py`).
  It is looked up byte by byte: a table that a wrapper is given maps the bytes of a character past
  ASCII, not the character (CPython's table maps only ASCII whitespace).
- A subclass of `TextWrapper` is an error: only an exception class may have a base (#7).

`tests/lib_textwrap.py` compares it with CPython's on the cases of CPython's
`Lib/test/test_textwrap.py`, and on a wrapper's own options and class attributes. Run by
CPython, the edited module passes that file's 66 tests.

In an AOT executable, `wrap()` of a 500-character paragraph of 79 words takes 137 µs, `fill()`
136 µs and `shorten()` 134 µs, against CPython's 64, 66 and 54 µs; `dedent()` of a 15-line
block takes 45 µs (CPython: 11 µs) and `indent()` 1.2 µs (CPython: 2.3 µs). Most of the time
is `lib/re`'s: `wordsep_re.split()` takes 122 µs of `wrap()`'s 137 (CPython's `_sre`: 38 of 64),
and the lookups that stand in for `str.translate()` 10 µs (CPython: 2.7 µs), while the rest of
`wrap()`, the wrapping itself, takes 6 µs, against CPython's 17 µs. `dedent()`'s three regular
expressions take 20, 14 and 13 µs (CPython: 3 µs each). (Medians of 3 runs, each the median of
5 rounds over 200 generated ASCII paragraphs or blocks.)

## `string`, a port of CPython's

`string.py` is CPython 3.13.16's `Lib/string.py` (SHA-256
`c000d9c4340c910b869399f0f0acc1b70e39391ad9344c4e08d8d0f80210a916`) edited in 16 places, each
marked `# Pystachy port:`. It has the constants, `capwords()` and `Template`, as CPython's code:
`substitute()` and `safe_substitute()` with a mapping (a dict, or an object with `__getitem__`),
keyword arguments or both, `is_valid()`, `get_identifiers()`, the `template` attribute, the class
attributes `delimiter`, `idpattern`, `braceidpattern`, `flags` and `pattern`, and the `ValueError`
of an invalid placeholder, with its line and column. Its regular expression is `lib/re`'s.
`Formatter` stays in the file, uncompiled: a program that uses it is an error where it does (it
needs CPython's C module `_string`, whose import is optional here, and sets of mixed items;
`tests/errors/lib_string_formatter.py`).

- `import _string` is an optional import (`try:` ... `except ImportError: pass`): Pystachy has no
  `_string`, which only `Formatter` uses, and runs the handler; CPython imports it, and its
  `Formatter` works.
- `from collections import ChainMap` is gone (no `collections` here), and so is its one use: where
  `substitute()` and `safe_substitute()` are given no mapping, CPython binds `mapping` to `kws`,
  and where they are given both, to `ChainMap(kws, mapping)`, which a variable of one type cannot
  hold. Their `convert()` looks a name up in `kws` first, then in `mapping`,
  `str(kws[named]) if kws and named in kws else str(mapping[named])`, where an empty `kws` (a
  `**kwargs` record, which the call decides) is not looked in; with no mapping, `mapping` is the
  empty `_sentinel_dict`, whose `KeyError` names the key as CPython's does.
- `_sentinel_dict = {}`, `mapping`'s default, is annotated `dict[str, str]`, as nothing fills it.
- In `Template`'s class body, `braceidpattern` and `flags` are annotated (`str | None`, `int`):
  `None` and another module's variable (`re.IGNORECASE`) give a class attribute no type. `pattern`
  is bound, to `None`, so that the module's code may assign it.
- The module's `Template.__init_subclass__()`, which computes `pattern`, is
  `Template.pattern = _template_pattern()`, a function of `__init_subclass__()`'s lines with
  `Template` for `cls`: Pystachy compiles no `__init_subclass__()`, which calls `super()` and reads
  `cls.__dict__`. CPython still calls it for a subclass.
- `__init__` annotates its parameter (`template: str`), and so `is_valid()` and
  `get_identifiers()` annotate their returns (`-> bool`, `-> list[str]`): with an unannotated
  `__init__`, `Template` is a class template, whose objects compile its special methods,
  `__init_subclass__()` too; with an annotated one, a method without unannotated parameters
  returns `None` unless it says otherwise.
- `capwords()` annotates `sep` as `str | None`: `s.split(sep)` of a template's parameter whose
  argument is `None` is an error, and of an optional `str` it is CPython's default.
- `safe_substitute()`'s `convert()` returns `mo.group() or ''`, a `str` (group 0 is never `None`),
  where `lib/re`'s `group()` is a `str | None`, and `_invalid()` passes `splitlines()` its
  `keepends` by position, as Pystachy takes it.

Where it differs from CPython (`tests/deviations/lib_string.py`):

- `Template.flags` is an int, `2`, where CPython's is `re.IGNORECASE` (`lib/re`'s flags are ints).
- The column of an invalid placeholder counts the str's bytes past ASCII, as `lib/re`'s positions
  do, and `capwords()` capitalizes ASCII letters alone, as `str.capitalize()` does.

A subclass of `Template` (another `delimiter`, `idpattern`, `braceidpattern`, `flags` or
`pattern`) is an error: only an exception class may have a base (#7;
`tests/errors/lib_string_subclass.py`). So are keyword arguments whose values have different types
(`substitute(name="Ann", count=3)`), as a dict of them would be: Pystachy reads a `**kwargs` record
by a name computed as the code runs only where its values share a type
(`tests/errors/lib_string_kwargs_types.py`).

`tests/lib_string.py` compares it with CPython's on the cases of CPython's
`Lib/test/test_string.py` that need no subclass of `Template`, and on the class attributes, the
pattern and keyword arguments with a mapping. Run by CPython, the edited module passes that file's
39 tests, also the 25 of `Template`, those that subclass it among them, as `__init_subclass__()`
is CPython's, and those of `Formatter`, as CPython imports `_string`.

In an AOT executable, `substitute()` of a 430-character template with 14 placeholders takes 5.8 µs
with a dict (CPython: 4.6 µs) and 6.1 µs with a dict and two keyword arguments (CPython: 7.3 µs,
which makes a `ChainMap` at each call); `safe_substitute()` 5.7 µs (4.8), `get_identifiers()`
5.3 µs (4.2) and `is_valid()` 5.2 µs (3.8): most of each is `lib/re`'s scan of the template, which
CPython's `_sre` does faster. `substitute()` of `"$who likes $what"` takes 0.78 µs (0.81), and
`capwords()` of 18 words 0.48 µs (1.35). (Medians of 3 runs, each the median of 5 rounds of 2,000
calls, 20,000 for the short ones.) [`examples/mailmerge`](../examples/mailmerge/README.md)
renders a message for each record of a data file with it.

## `statistics`, a port of CPython's

`statistics.py` is CPython 3.13.16's `Lib/statistics.py` (SHA-256
`80b677e786418c299ced99993f4a89804d4532e0b5e26971286713a6de538c18`) edited in 20 places, each
marked `# Pystachy port:`. It has `fmean()`, with and without `weights`, `median()`,
`median_low()`, `median_high()`, `median_grouped()`, `quantiles()`, `geometric_mean()`, `mode()`,
`multimode()` and `StatisticsError` (a `ValueError`), as CPython's code computes them, with its
results bit for bit and its exceptions and their messages: of lists, tuples, sets, dicts, strs and
objects with `__iter__` (with `__len__` or not), of floats, and of ints and bools where the result
has one type (below); of strs and tuples too for `median_low()` and `median_high()`, and of ints,
strs and tuples of them for `mode()` and `multimode()`. The weights of `fmean()` go through
`math.sumprod()`, which Pystachy's `math` does not have: `_sumprod()` ports its C code. The other
functions stay in the file, uncompiled, as CPython wrote them: a program that uses one is an error
where it does (below).

The edits, which replace 52 of the file's 1,817 lines with 195 (88 of them `_sumprod()`, 62 of
those code), and need no change to the compiler or the runtime:

- The imports of `numbers`, `random`, `fractions`, `decimal`, `itertools`, `functools.reduce` and
  `collections` are optional (`try:` ... `except ImportError: pass`), as Pystachy has none of them
  (its `functools` has no `reduce`) and only functions that it leaves uncompiled use them;
  `_random = random` moves into the `try` of `random`. `_decimal_sqrt_of_frac()`'s return
  annotation is quoted, `'Decimal'`: CPython 3.13 evaluates it where the `def` runs.
- `sumprod` is imported from `math` where `math` has it (CPython), in an optional import after
  `_sumprod()`, which is the module's `sumprod` where it does not. `_sumprod()` is
  `math_sumprod_impl()` of CPython 3.13.16's `Modules/mathmodule.c` for the subset's sequences of
  ints, bools and floats, the C code's operations in its order: the products of ints and bools are
  added as ints, and those of floats, or of floats and ints or bools, in triple length with
  `math.fma()` (`tl_fma()`, `dl_mul()` and `dl_sum()`, written out in its loop: as functions that
  return tuples, they made a weighted `fmean()` three times as slow), until a product or a sum is
  not finite, then as floats. It returns `float(math.sumprod(p, q))`, the float that `fmean()`
  divides. An input without `__len__`, or whose `len()` raises `TypeError`, is read into a list
  first, as C iterates it.
- `fmean()` counts the items of an iterable without `__len__` (an object with `__iter__` alone, as
  `hasattr()` tells), or whose `len()` raises `TypeError`, in a list of them, where CPython counts
  them with a generator, `count()`, that it gives `fsum()`: the subset has no generators. Its return
  is annotated `float`, as it may call itself before it returns. It passes weights that are no list
  or tuple to a call of itself as a list of them, where CPython makes `weights` that list: a
  variable has one type.
- `geometric_mean()`'s generator `count_positive()` is a loop that keeps what it would give in a
  list, which `fsum(map(log, ...))` takes.
- `median()`, `median_low()`, `median_high()`, `median_grouped()` and `quantiles()` call
  themselves with `list(data)` where `data` is no list, as `data = sorted(data)` makes it a list.
  `median_grouped()` converts `interval` and the middle value to floats in variables of their own,
  `interval_f` and `x_f`, as they may be ints.
- `mode()` and `multimode()` count the items in a dict, as `Counter(iter(data))` does
  (`_count_elements()`): `mode()` takes the pair of `most_common(1)` with `max()` of the dict's
  items by count, as `heapq.nlargest(1, ...)` does, the first of the highest count, and
  `multimode()` returns `list(counts)` for no data, the `[]` of the dict's keys' type.
- `LinearRegression` (a `collections.namedtuple`) and `kde_random()`'s table of kernels are made in
  the `try` of an optional import of `collections` and of `random`, which Pystachy does not have:
  the table, a dict of different functions, the first of them a method of a `NormalDist`, would not
  compile.

Where it differs from CPython (`tests/deviations/lib_statistics.py`):

- Pystachy's ints are 64-bit: `fmean()` with weights adds the products of ints as ints, as
  `math.sumprod()` does, and raises `OverflowError` where their sum leaves 64 bits (CPython goes on
  with longer ints). Without weights, `fsum()` adds them as floats, as in CPython.
- The module's `sumprod`, `math.sumprod` in CPython, is `_sumprod()`, which returns a float:
  `sumprod([1, 2], [3, 4])` is `11.0`, and of no items `0.0`, where CPython's are ints.
- The items of a str (for `mode()`, `multimode()`, `median_low()` and `median_high()`) are its
  bytes past ASCII, as iterating it gives them.

What it does not have, each a compile-time error (`tests/errors/lib_statistics_*.py`):

- `median()` and `quantiles()` of ints or bools: CPython's `median()` of an odd number of ints is
  the middle int, of an even number a float, and its `quantiles()` of one data point are ints, of
  more floats, where a function has one return type (`median_low()` and `median_high()` return an
  item, and `median([float(x) for x in xs])` a float). So is `median()` of strs: CPython returns
  the middle one of an odd number of them, and raises `TypeError` for an even number, whose two
  middle ones it divides.
- `mode()` and `multimode()` of floats: a dict of Pystachy has no float keys.
- `mean()`, `harmonic_mean()`, `variance()`, `pvariance()`, `stdev()` and `pstdev()`: they add
  exactly, as `fractions.Fraction`s keyed by denominator, keep the data's classes in a set, convert
  to `Decimal` and take square roots of fractions of long ints; Pystachy has no `Fraction`,
  `Decimal` or long int, and `fsum()` and a division round twice where they round once.
  `harmonic_mean()` also asks whether `iter(data) is data`.
- `covariance()` and `linear_regression()` (generator expressions given to `sumprod()`, and a
  `collections.namedtuple`), and `correlation()` (`itertools`' `count()` and `groupby()`).
- `kde()` (a `match` statement), `kde_random()` (`random.Random`) and `NormalDist` (properties,
  reflected operators, a `__slots__` dict; `random` for `samples()`).

`tests/lib_statistics.py` compares it with CPython's on the cases of CPython's
`Lib/test/test_statistics.py` and of the docstrings for these functions that the subset types
(floats in place of the ints they give `median()` and `quantiles()`, no `Fraction`, `Decimal` or
iterator), on lists, tuples, sets, dicts, strs and objects with `__iter__` (and `__len__`, whose
calls it prints), empty data, NaNs, infinities and signed zeros, the errors and their messages, 240
weighted means of generated data with infinities, NaNs, overflows and cancellations, and the
medians and quantiles of generated data of every length from 1 to 40. Run by CPython, the edited
module passes CPython 3.13.16's `Lib/test/test_statistics.py`: all its 401 tests (372 test
methods of 43 classes, the 24 doctests of the module's docstrings and 5 of the test's helpers), as
the unmodified module does, also with its `sumprod` replaced by `_sumprod()`, which `fmean()`,
`covariance()`, `correlation()` and `linear_regression()` then use. Compiled, `_sumprod()` gives
what CPython's C `math.sumprod()` gives, repr for repr, for 1,464,607 generated pairs of sequences
of floats, and of floats and ints or bools, with infinities, NaNs, subnormals, overflows and
cancellations (and `0.0` for 36,016 empty ones, where C gives `0`).

In an AOT executable, on 100,000 items from a linear congruential generator, `fmean()` takes
297 µs (CPython: 352 µs), and with weights 717 µs for floats (896), 952 µs for int weights (1,308)
and 570 µs for ints (1,374): `_sumprod()`'s loop reads unboxed items, where C's `math.sumprod()`
reads each item's object. `median()`, `median_low()` and `quantiles(n=100)` of floats take 8.3 to
8.9 ms (12.9 to 13.1 ms), most of it the sort, `median_high()` and `median_grouped()` of ints 6.3
and 6.5 ms (10.6), `geometric_mean()` 2.4 ms (6.4: a `log()` per item, which CPython calls through
`map()`), and `mode()` and `multimode()` of ints 1.0 ms (3.1). (Medians of 3 runs, each the median
of 5 rounds of 10 to 50 calls.) [`examples/latency`](../examples/latency/README.md) reports the
latencies of each endpoint of an access log with it.

## `urllib.parse`, a port of CPython's

`urllib/parse.py` is CPython 3.13.16's `Lib/urllib/parse.py` (SHA-256
`491b233e8d87a2ab73964afff029717177d53ad8def328ed9b00575db983da27`) with 27 edits, each marked
`# Pystachy port:`, and `urllib/__init__.py` is CPython's, which is empty. Of CPython's 1,264 lines,
1,156 are as they are; the edits change or remove 108 and add 576. The budget: 257 of the lines
added are the codecs that stand in for `str.encode()` and `bytes.decode()` (Pystachy has no bytes),
87 test bracketed hosts and NFKC forms where CPython calls `ipaddress` and `unicodedata`, 23 quote a
str of bytes, and the other 209 are the result classes, the blocks that only CPython runs, and the
lines and comments of the smaller edits.

What works, on strs, as CPython's code does it:

- `quote()`, `quote_plus()`, `unquote()` and `unquote_plus()`, with `safe`, `encoding` and `errors`.
  A str holds UTF-8 in Pystachy, so `quote()` quotes its bytes as CPython quotes the bytes of
  `str.encode()`, and `unquote()` decodes the bytes of the percent-escapes of each ASCII run as UTF-8
  (with `errors='replace'` by default), each sequence that is no UTF-8 replaced as CPython's decoder
  replaces it (`unquote('%F0%9F%98')` is one U+FFFD, `unquote('%ED%A0%80')` three). The codecs are
  UTF-8, Latin-1 and ASCII, under any of the names `codecs.lookup()` finds them by (`'utf8'`,
  `'ISO-8859-1'`, `'us-ascii'`, `'l1'`, ...), with the error handlers `strict`, `ignore`, `replace`,
  `backslashreplace`, `xmlcharrefreplace`, `surrogateescape` and `surrogatepass` (a surrogate is held
  as Pystachy holds one, its three bytes), CPython's `LookupError` for a handler it does not know and
  `TypeError` for `xmlcharrefreplace` and `namereplace` in `unquote()`, and its messages.
- `parse_qs()` and `parse_qsl()`, with `keep_blank_values`, `strict_parsing`, `encoding`, `errors`,
  `max_num_fields` and `separator` (also of several characters), and their `ValueError`s.
- `urlencode()` of a dict, or of a list or tuple of pairs, with `doseq` (a value that is a list,
  tuple or set is a sequence, an int or `None` is not), `safe`, `encoding`, `errors` and `quote_via`
  (`quote`, `quote_plus` or a function of the program); keys and values that are no strs are
  `str()`-ed, as in CPython.
- `urlsplit()`, `urlparse()`, `urlunsplit()`, `urlunparse()`, `urljoin()`, `urldefrag()` and
  `unwrap()`, with the `ValueError`s of an invalid IPv6 URL or bracketed host and of a netloc whose
  NFKC form holds `/?#@:`, and `uses_relative` and the other lists. `SplitResult`, `ParseResult` and
  `DefragResult` are NamedTuples: their fields, indexing, unpacking, `==` with tuples, `repr()`,
  `_replace()` and `geturl()`.
- A `str | None` for the string of `quote()`, `quote_plus()`, `unquote()` and `unquote_plus()`,
  which raise CPython's `TypeError` or `AttributeError` for `None`.

The edits:

- The imports: `typing.NamedTuple` for `collections.namedtuple`, and `types`, `warnings` and
  `ipaddress` optional (`try:` ... `except ImportError: pass`), as Pystachy has none of them.
- What only CPython runs is in blocks that begin `try: import types`: Pystachy decides an optional
  import as it compiles, and where an import fails it drops the rest of the `try` block
  ([`docs/language.md`](../docs/language.md#optional-imports)). They make the result classes for strs
  again as classes that derive from their NamedTuples and their mixins
  (`type('SplitResult', (SplitResult, _NetlocResultMixinStr), {'__slots__': ()})`), set
  `__class_getitem__`, the fields' docstrings and the result pairs (`_fix_result_transcoding()`),
  make `_ALWAYS_SAFE` and `_ALWAYS_SAFE_BYTES`, which are bytes, and wrap `urlsplit()` and
  `_byte_quoter_factory()` in `functools.lru_cache`, which CPython's decorators did. So CPython,
  running the edited module, has CPython's result classes, bytes paths and caches.
- `DefragResult`, `SplitResult` and `ParseResult` are `typing.NamedTuple` classes, the bases that
  `namedtuple()` made, with the docstrings they were given and `geturl() -> str`: only an exception
  class has a base in Pystachy, so a class has no mixin, and the mixins' properties (`username`,
  `password`, `hostname`, `port`) and `encode()` are CPython's only; `_DefragResultBase` and the
  others name them, for the bytes classes, which stay CPython's.
- `_coerce_args()` names its first argument, as Pystachy decides `isinstance()` of a name as it
  compiles, and puts the return of bytes in an `else` block, which it then leaves out for strs; its
  loop takes all the arguments, as Pystachy slices no tuple. `urlunsplit()` and `urlunparse()`
  unpack their components before they pass them, as Pystachy unpacks only a tuple's items into
  arguments, not a NamedTuple's.
- `urljoin()` makes a new list of the segments, as Pystachy assigns to no slice and has `filter()`
  only as the argument of a consumer.
- `_checknetloc()` replaces each of the 19 characters whose NFKC form holds one of `/?#@:` with that
  form (`_NFKC_DELIMITERS`, from CPython 3.13's Unicode 15.1), for `unicodedata.normalize()`: no
  composition takes one of these five characters in, so that is all NFKC changes of what the test
  reads. `_check_bracketed_host()` calls `_ip_version()`, whose `_is_ipv4()` and `_is_ipv6()` test a
  str as `ipaddress.ip_address()`'s constructors parse it, scope IDs and IPv4 suffixes included, and
  raise its `ValueError`.
- `quote()` returns `_quote_str(_encode(string, encoding, errors), safe)` for `string.encode()` and
  `quote_from_bytes()`; `_encode()` makes the str of the bytes, which holds byte b as `chr(b)` (a
  str's byte in Pystachy, a code point below 256 in CPython), and takes an `encoding` and `errors`
  of `None` as `'utf-8'` and `'strict'`; `_quote_str()` quotes it as `quote_from_bytes()` quotes
  bytes, with the quoted forms of the 256 bytes made once for each `safe`.
- `unquote()`'s `_generate_unquoted_parts()` returns a list of the parts (Pystachy has no
  generators), unquotes an ASCII string at once (`lib/re`'s `finditer()` is slower than `_sre`'s), and
  calls `_unquote_str()` and `_decode()` for `_unquote_impl()` and `bytes.decode()`.
- The codecs (`_codec()`, `_encode()`, `_encode_error()`, `_decode()`, `_utf8_char()`,
  `_decode_error()`) are those of CPython's `unicodeobject.c` and `stringlib/codecs.h` and the
  handlers of `codecs.c`: the same runs of characters an encoder cannot encode, the same ranges of
  bytes the UTF-8 decoder gives its handler (an invalid start byte, an invalid continuation byte,
  the unexpected end of the data), the same replacements and positions. `_UTF8` (a str's length of
  `'\xe9'`) tells Pystachy's strs from CPython's code points, so the module runs under CPython too.
- `urlencode()` names the pairs `pairs` (a dict stays a dict) and the quoted key, value and element
  `qk`, `qv` and `qelt` (a key or value that is no str keeps its type), and an `elif` takes a value
  without `__len__` as no sequence, as `len()` of it, and looping over it, would be compile-time
  errors where CPython's `len()` raises `TypeError`.
- `parse_qsl()` and `_generate_unquoted_parts()` annotate their returns, which their first return,
  of `[]`, would type, and `_typeprog`, `_hostprog` and `_portprog` are annotated, as only a
  function gives them a value other than `None`.

Where it differs from CPython (`tests/deviations/lib_urllib_parse.py`):

- Where CPython's codecs raise `UnicodeEncodeError` or `UnicodeDecodeError` (`errors='strict'`, the
  default of `quote()`), the port raises `UnicodeError` with their message, as Pystachy raises
  neither: an `except` clause that names them does not catch it.
- An encoding other than UTF-8, Latin-1 and ASCII raises `NotImplementedError`, where CPython
  encodes and decodes (or raises `LookupError` for a name it has no codec for), and so does the
  error handler `namereplace` in `quote()`, which needs the names of the characters.
- A str that holds bytes that are no UTF-8, which no CPython str is (`chr(233)` is the byte 0xE9 in
  Pystachy, docs/language.md), is quoted byte for byte; for Latin-1 and ASCII, a byte that begins no
  character is the character of its value, as `lib/re` reads it.
- `urlsplit()` caches nothing, which only its speed shows (and `cache_info()`, an error below); a
  `doseq` value that is a set of strs gives its items in the order of a Pystachy set, which differs
  from CPython's ([`docs/language.md`](../docs/language.md#deviations-from-cpython)).

Each of these is a compile-time error (`tests/errors/lib_urllib_parse_*.py`):

- `username`, `password`, `hostname` and `port` of a `SplitResult` or `ParseResult`, which are
  properties of CPython's mixins (`@property` is not supported; `_hostname.py`), and `encode()` of a
  result (`_encode.py`).
- Bytes: `quote_from_bytes()`, `unquote_to_bytes()` (`_unquote_to_bytes.py`), a bytes argument and
  the bytes result classes.
- `urlsplit.cache_info()`, `cache_clear()` and `clear_cache()` (`_cache.py`).
- `urlencode()` of something other than a mapping or a sequence (`_not_sequence.py`; CPython raises
  `TypeError`), and with `doseq`, a value that is a sequence of items of different types
  (`_doseq_mixed.py`).
- An `allow_fragments` that is an int, not a bool (`_allow_fragments_int.py`): `urlsplit()` rebinds
  it to `bool(allow_fragments)`, and a variable has one type.
- The deprecated `splittype()` and the other split functions, `to_bytes()` and `Quoter`, which warn
  with `warnings` (`_deprecated.py`).

`tests/lib_urllib_parse.py` compares it with CPython's `urllib.parse`: the str cases of CPython's
`Lib/test/test_urlparse.py` and of `test_urllib.py`'s `QuotingTests`, `UnquotingTests` and
`urlencode_Tests`, every codec name and error handler on characters past U+00FF and on surrogates,
then `unquote()` of every one-byte escape and of two to four bytes drawn from each class of bytes
CPython's UTF-8 decoder tells apart, and `quote()` of code points at the ends of each length of
UTF-8, summed up by a digest of their `ascii()`. Run by CPython in place of its own, the edited
module passes all 77 tests of CPython 3.13.16's `test_urlparse.py` (5 subtests skip, as with
CPython's own: they are about non-ASCII bytes) and 28 of the 29 tests of `test_urllib.py`'s
`QuotingTests`, `UnquotingTests` and `urlencode_Tests`: `test_quote_with_unicode` stops at its
`assertRaises(UnicodeEncodeError, ...)`, the deviation above, and passes with `UnicodeError` in its
place; the whole of `test_urllib.py`, 109 tests, gives what it gives with CPython's own module but
for that one. Beyond the
tests, compiled, it gave what CPython gives for `unquote()` of all 65,536 two-byte escapes in 7
codec and handler combinations, of three bytes from 25 values and four from 13, for `quote()` of
all 1,114,112 code points in 4 combinations and back, and for 200,000 random strings of URL
pieces through each function, about 30 calls each.

In an AOT executable (medians of 3 runs, each the median of 5 rounds of 20,000 calls after one that
warms up), `quote()` of `'café crème/menu'` takes 252 ns (CPython 3.13.16: 865 ns), `quote_plus()`
of four ASCII words 134 ns (488), `unquote()` of `'caf%C3%A9%20cr%C3%A8me%2Fmenu'` 418 ns (2,209),
`parse_qsl()` of a query of 7 fields 1.04 µs (8.99) and `parse_qs()` 1.16 µs (9.68), `urlencode()`
of 4 pairs 652 ns (4,583), `urlsplit()` of 1,000 URLs in turn 338 ns (2,061) and `urljoin()` 812 ns
(3,743); `urlsplit()` of one URL again and again takes 338 ns, where CPython's cache gives its result
in 91 ns. [`examples/urlstats`](../examples/urlstats/README.md) reads an access log with it, 5.4 to
5.9 times as fast as CPython.

These modules behave as their pure-Python code, which CPython replaces with C accelerators that
differ at the edges: errors can be worded differently (`heappop([])` raises `IndexError: pop
from empty list` here, `index out of range` from CPython's `_heapq`), keyword arguments the C
functions reject are accepted, `bisect`'s `hi=-1` is a plain bound (`len(a)` for `_bisect`),
`stat`'s tests read the module's constants (`_stat` has its own), and `heapify` of more than
2,500 items calls `__lt__` in another order (`_heapq` switches to a cache-friendly loop).

These files are part of Python and are used under the PSF License Version 2; see
`THIRD_PARTY_NOTICES`. `tools/import_sweep.py` tries every module of a CPython standard library
this way, with the modules here in place of the library's own; [`docs/stdlib.md`](../docs/stdlib.md)
reports which import and why the others do not.
