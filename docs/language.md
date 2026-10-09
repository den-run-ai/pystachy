# The Pystachy language

Pystachy is Python with the types made static and the dynamic machinery removed. This page is
the complete reference: what compiles, how types are decided, how modules are imported, and
every known way a compiled program can differ from CPython. The [README](../README.md) has the
short version.

The contract: **a program that Pystachy compiles prints what CPython prints**, apart from the
[deviations](#deviations-from-cpython) listed below. A program that CPython would run but
Pystachy cannot run the same way is [rejected at compile time](#rejected-rather-than-miscompiled)
with a `file:line: error:`, never miscompiled.

| | in short |
|---|---|
| [Types](#types) | `int` (64-bit, overflow-checked), `float`, `bool`, `str`, `list[T]`, `dict[K, V]`, `tuple[...]`, classes and dataclasses, `Optional` of a class |
| [Typing rules](#typing-rules) | annotated functions have their declared types; an unannotated module-level function is a *template*, compiled once per list of argument types |
| [Modules](#modules) | your own modules and packages, the builtin modules `sys`, `os`, `math`, `time`, ..., and unmodified standard library modules from `lib/` |
| [Removed on purpose](#removed-on-purpose) | exceptions (`try`), generators, lambdas and closures, inheritance, sets, `bytes`, big integers, `async`, ... |
| [Syntax errors](#syntax-errors) | every `SyntaxError` CPython reports before running a file, at CPython's line and almost always with its message |

Contents: [Types](#types) · [Typing rules](#typing-rules) · [Statements](#statements) ·
[Modules](#modules) · [Expressions](#expressions) ·
[Builtins and library modules](#builtins-and-library-modules) ·
[Removed on purpose](#removed-on-purpose) · [Syntax errors](#syntax-errors) ·
[Deviations from CPython](#deviations-from-cpython) ·
[Rejected rather than miscompiled](#rejected-rather-than-miscompiled)

## Types

`int` (64-bit), `float` (IEEE double), `bool`, `str`, `list[T]`, `dict[K, V]`
(keys `int` or `str`), `tuple[A, B, ...]` (up to 9 elements, indexed by integer
constants), user classes, `Optional[C]` / `C | None` for class types, and `None` as a
return type. The `typing`
spellings (`List`, `Dict`, `Tuple`, `Optional`, `TextIO`) work when imported from `typing`,
and string forward references work (also inside `list["Node"]`), as does `typing_extensions` in place of `typing`.

### When annotations are evaluated

As in CPython 3.13, the annotations of a def's parameters and return, of a class body and of
module-level code are evaluated when the statement runs, also in an imported module whether
or not the program uses the def: one that raises there is a compile-time error with CPython's
exception (a name not bound yet, `"C" | None`, `C[int]` of a class, `Optional[A, B]`, an
attribute a module does not have). Such an annotation must also read only names that are
surely bound by then (not bound only in an `if` branch or a loop, nor deleted), and be a
type: a class or `typing`'s name, subscripts of those and of the builtin generics, `|` of
them, literals, or a variable as the whole annotation (an alias, an error where the
annotation is used). What may run code of the program there is rejected: a call, an operator
other than `|`, a variable as an operand or subscripted, a subscript of one of the program's
classes (`__class_getitem__`), an attribute of a builtin module other than `typing`. A string
annotation is not evaluated, and neither is any annotation in a module that imports
`annotations` from `__future__`.

## Typing rules

- A function whose parameters are annotated has those types; a missing return annotation
  means `-> None`. Methods' parameters must be annotated.
- A module-level function with an unannotated parameter is a **template**: each call
  compiles it, once per list of argument types, for those types (an annotated parameter
  keeps its type), and its first `return` with a value decides what it returns. It is
  compiled only when a call needs it, so what Pystachy cannot compile in it is an error only
  then. In it, `isinstance(x, T)` (also with a tuple of types or `T | U`), `hasattr(x, "a")`
  (the builtin types have CPython 3.13's attributes) and `x is None`, when `x`'s type decides
  them, are constants: only the branch that runs is compiled (in `if`, `while`, `assert`,
  `and`/`or` and conditional expressions), and nothing after a `return`. A parameter whose
  argument is `None` reads as `None`, and outside if branches and loops may get a value of
  another type (`if hi is None: hi = len(a)`, `if acc is None: acc = []`). A template that
  returns objects returns `None` where it ends without a `return`, as CPython does. A
  function with `*args` is a template too: each call arity compiles it with `args` a tuple
  of the extra arguments' types (iterating it needs one item type; `()` is the empty
  tuple), and in `def f[T](x: T) -> T` (PEP 695) what mentions a type parameter is
  unannotated. In a template's function, an empty list or dict that nothing fills where the
  argument types let code run (a loop over the empty tuple of `*args`, a branch an
  `isinstance` test removes) may be returned before anything shows its type: the first use
  of it further on that does (a call it is passed to, a store, another `return` of a list or
  dict) decides what the function returns. If none does, each call gives the container the
  type its context expects (an annotated variable or parameter, `str.join()`, a declared
  return type), else `list[int]` or `dict[int, int]`; a type error that such a guess causes
  says where it came from.
- Each variable has one type for its lifetime, fixed by its annotation or first assignment.
- Empty `[]` and `{}` take their type from context: an annotation, a parameter, a field,
  or the variable being assigned. A variable without a type that is assigned `[]` or `{}`
  takes it from its first use that shows what the container holds: `append`, `insert`,
  `extend`, `+=`, `xs[i] = v`, `d[k] = v`, `setdefault` (also `d.setdefault(k, []).append(v)`
  and `d.setdefault(k, {})[k2] = v`), `get(k, default)` or a reassignment (until then only
  `len()`, `bool()` and truth tests may read it; a read before that use, in the function's
  source, is typed by it when its item expression can be; in a template's function only code
  that runs for the argument types counts, and a fill under a test that a type not known at
  the read would decide leaves the container without a type). A local that nothing in its
  function fills takes the type expected where it is read. A module global's first use may
  be in a function (also a method, or a function of another module): a read that needs the
  type before that function is compiled compiles the function first; the same goes for a
  global that only functions assign (`global x; x = ...`). After `from m import X` (or
  `Y = X` at module level) of such a container, the two names hold one container, typed by
  the first use of either. `None` in a display takes the type of its neighbours.
- No silent `int` → `float` conversion when assigning or passing arguments: CPython would
  keep an `int`, so `x: float = 1` is rejected (write `1.0`). Arithmetic mixes freely.
- Python scoping: a name assigned in a function is local to it; `global` opts out.
- Class fields come from class-body annotations or from `self.x = ...` in `__init__`,
  typed by annotation, parameter, literal, constructor, method or function call (not a call
  of a template, whose result type is known only once it is compiled, nor of a function that
  returns `None`: annotate the field).

## Statements

assignment (chained, tuple and list unpacking, swaps), annotated and
augmented assignment (`+=` on lists extends in place; `__iadd__` & co are honoured),
`if`/`elif`/`else`, `while`, `for` (both with `else`) over `range`, lists, strings, dicts,
files, tuples of one item type, `.items()`/`.keys()`/`.values()`, `enumerate` (with `start`), `zip` and
`reversed` (also of a `range`), stepping each sequence as its CPython iterator does (a dict
that changes size raises `RuntimeError`), `break`, `continue`, `return`, `pass`, `global`,
`del` of a list item or a dict key, `assert`, `with open(...) as f:` (also several items, in
parentheses or not), `raise` of a builtin exception (`from` allowed; it ends the program
with CPython's message and status, `SystemExit` and `KeyboardInterrupt` included), `def`,
`class`, `@dataclass`, docstrings, `del` of a variable (later reads raise `NameError` or
`UnboundLocalError`; not of a global in a function), `import`/`from` of the builtin modules
`sys`, `os`, `os.path`, `math`, `time`, `errno`, `tempfile`, `typing`, `dataclasses`, `builtins`
and `__future__`, and of Python modules (below), with keyword-only (`*`) and positional-only
(`/`) parameters.

## Modules

### Finding and running modules

`import NAME` finds the package `NAME/__init__.py` or the file `NAME.py` in the
directory of the main program's real file (symbolic links resolved, as for CPython's
`sys.path[0]`), on `PYSTACHY_PATH` (directories separated by `:`), or in `lib/` beside the
compiler. Packages (also namespace packages), submodules, `import a.b as x`, `from ... import`,
relative imports, `from m import *` and circular imports work. A module's top-level code runs
once, when the first import of it runs, as in CPython, and `__name__` (also `m.__name__`)
is the module's name; `__debug__` is `True`, while `__file__`, `__doc__`, `__spec__` and the
other attributes CPython gives a module are not supported, and an imported module may not
bind `__name__`.

### Module scope

A module sees its own names and the builtins, never the main
program's: a program that defines its own `len` does not change `bisect`'s. An import in a
function binds its names in that function only. `from m import x` of a variable copies its
value, as CPython binds it; of a function or class it names the same one. `from m import *`
takes the names `__all__` lists (also after `+=`, `append` and `extend`), else the public
names bound when the module's code ends; a name a package binds itself (`from .parse import
parse`) wins over its submodule of that name. A module-level `name = function` makes an
alias. A global that its module's code may leave unbound (assigned in an `if`, or only after
an import that can call back into the module) is checked where functions and other modules
read it, raising CPython's `NameError` or `AttributeError`. A template's function compiled
before its module's code assigns a global it reads (first called in a branch that does not
run) takes the global's type from its first binding in the branches of that code that run:
an annotation, an assignment whose value can be typed there, or an empty container that the
code fills; the read is checked as above.

### Decided at compile time, as CPython decides it at import time

What CPython decides at import time is decided at compile time. An imported module's
`if __name__ == "__main__":` block is dropped, and so are `if typing.TYPE_CHECKING:` blocks
(also where `TYPE_CHECKING` is imported in a `try` whose `except ImportError:` clause sets it
to `False`). Tests of `sys.platform` against Windows (`==`, `!=`, `startswith()`, `in` a tuple
or list of Windows names) and of `os.name` are decided for POSIX, these and the `__main__`
test also inside `not`/`and`/`or`, where the other operands still run in CPython's order (`if effect() and
os.name == "nt":` calls `effect()`). These names are recognized only where they name what
the module imported: a parameter, local, loop variable or other import of the same name
hides them, and a name a function binds only in code dropped this way (also by `:=`, a `match` capture or
a `type` statement) is still its local.

### Optional imports

An optional import, `try: <imports> / except ImportError:` (the standard library's optional
C accelerators), runs its imports in order until one fails: its module is not found, its
module's code surely raises `ImportError` at its top level (`if sys.platform != "win32":
raise ImportError(...)`), or a from-import names what its module has not bound by then and does not have as a
submodule (a module still being imported has bound only what its code has run so far; a
`del`, also in a branch or loop, may unbind). The imports before it run their code and bind their names, a failing module's
code runs up to its raise, and then the handler runs; a module that failed is not imported,
so a later import runs its code again.

An import inside a function of an imported module
that the program's module-level imports do not load is an error only where that function is
compiled. `import pkg.util as u` binds `u` to the attribute `util` of `pkg`, as CPython
does: the submodule, unless the package binds `util` itself after its own code imported the
submodule (`from .util import util`).

### Code Pystachy cannot compile in an imported module

A class or function of an
imported module that Pystachy cannot compile (inheritance, unannotated methods, an annotation
it does not support such as `Iterable[int]`, `int | None` or `dict[float, X]`, a `bytes` or
`**kwargs` parameter, a field whose type cannot be inferred, ...) is an error only where the
program uses it, and the message names it (`m.total() is not supported: parameter 'xs':
unsupported type annotation`), but its `def` or `class` statement still runs where the
module's code reaches it, as in CPython. Pystachy evaluates there the default values it can
compile, and the parts it can compile of the others (the items of a display). What it leaves
uncompiled (decorators, default values, bases, a class body) must run no code of the
program: it may read names, compute with literals and builtin values (`2 ** 31 - 1`,
`TABLE.get(k)`, `sorted(xs, key=len)`, `math.sqrt(2.0)`, `typing.Optional[int]`), bind and
delete names in a class body, use `if`, and apply `staticmethod`, `classmethod`, `property`,
`@dataclass`, `typing`'s `overload`, `final`, `override`, `no_type_check` and
`runtime_checkable`, and `object.__new__`. A variable or function of the module that such
code reads and that may still be unbound raises CPython's `NameError` when the statement
runs; its annotations are checked as under *Types*, and a base that raises (`C[int]` of a
class without bases) is CPython's error. `class C(object)` is a class without bases only
where `object` is surely still the builtin when the statement runs. A method that Pystachy
cannot compile or call (such as `def __len__(self):` without `-> int`) is an error only
where the program calls it, also implicitly (`len(x)`, or comparing, sorting or printing
objects inside containers).

### The vendored standard library

`lib/` holds unmodified
CPython 3.13 modules that compile this way ([`lib/README.md`](../lib/README.md)): `bisect`, `colorsys`, `heapq`,
`operator`, `stat`, `posixpath` and `genericpath` (the path string functions), `this` and
`curses.ascii`.

## Expressions

literals (decimal, hex, octal, binary and `_`-separated numbers; strings
with every escape except `\N{...}`, raw and triple-quoted strings, implicit
concatenation), f-strings with `!r`, `!s`, `!a`, `=`, nested format specs and CPython's
complete format-spec mini-language, `%` formatting with a constant format string
(`"%-5s %05.2f" % (a, b)`: the conversions `s r a d i u x X o e E f F g G c` with their flags,
widths and precisions, but not `%(name)s`, `*` or a precision on integers), arithmetic with Python semantics (`//` and `%` floor,
`/` is correctly rounded true division, exact int/float comparison), bitwise ops,
chained comparisons, `in`/`not in`, `is`/`is not` (not on numbers and bools), `and`/`or`
returning operands, `not`, conditional expressions, keyword and default arguments, negative
indices, slicing, list/dict/tuple displays, list comprehensions, generator expressions and
`range()`/`reversed()`/`enumerate()`/`zip()` as the argument of `list()`, `sorted()`,
`sum()`, `min()`, `max()`, `any()`, `all()`, `str.join()` or `list.extend()` (`any()` and
`all()` stop at the deciding item, as they do over files), `x in range(...)`, and operator
overloading resolved statically:
`__add__` & co, the in-place forms, `__eq__`, rich comparisons with CPython's reflection
rules (`a < b` tries `b.__gt__(a)`), `__len__`, `__bool__`, `__str__`, `__repr__` and
`__format__`. Objects inside lists, dicts and tuples compare, sort and print through
their own methods, as CPython calls them: lists and tuples compare their items with `==`
before ordering them, `list.sort`, `sorted` and `min` use `<` (`__lt__`, else the reflected
`__gt__`), and `max` uses `>`. Unary `-`, `+` and `~` on objects are not supported.

## Builtins and library modules

`print` (with `sep`, `end`, `file`, `flush`), `len`, `str`, `repr`, `ascii`,
`int`, `float`, `bool`, `ord`, `chr`, `abs`, `min`, `max`, `sum`, `sorted` (and
`list.sort`, with `reverse=`), `list`, `dict`, `round`, `divmod`, `pow` (also modular,
with inverses), `any`, `all`, `input`; the common `str`, `list` and `dict` methods
(`find`/`index`/`count` with start and end, `split`/`rsplit`, `partition`/`rpartition`,
`splitlines`, `removeprefix`/`removesuffix`, `center`/`ljust`/`rjust` with a fill character,
`zfill`, `expandtabs`, `capitalize`/`title`/`swapcase`, `dict.pop` with a default); `open()` with
CPython's modes, errors, `buffering=`, `newline=` translation and positions for `"+"`
modes, and files' `read`/`readline`/
`readlines`/`write`/`writelines`/`flush`/`close`, iteration and `closed`/`name`/`mode`;
`sys.argv/exit/stdin/stdout/stderr/maxsize/platform/setrecursionlimit/getrecursionlimit` (the streams
are files), `os.system/getpid/getenv/remove/rmdir/fspath/path.exists/path.realpath` and `os.name/sep/curdir/pardir/extsep/pathsep/linesep/
devnull`, `tempfile.mkdtemp`, `time.time/time_ns/monotonic/perf_counter/process_time` (and
their `_ns` forms) and `time.sleep`, the `errno` constants, and the `math` functions and
constants, which raise CPython's domain and range errors.

## Removed on purpose

Each of these would require a dynamic runtime or a large compiler
feature: exception handling (`try`; `with` works for files), generator functions
(`yield`), generator expressions other than the consumer arguments above, lambdas and
closures, inheritance (so user exception classes), `**kwargs` and `*args` in methods, sets, dict and
multi-clause comprehensions, slice steps, first-class functions (`map`, `key=`),
`isinstance`/`hasattr` other than the static cases above, `getattr`/`eval`, `bytes` (literals
are rejected; a binary mode computed at run time raises `NotImplementedError`) and binary
files, complex numbers, arbitrary-precision integers, `async`, `match` and `:=`. The parser
accepts all of them, and the compiler rejects each where it compiles it, so an imported
module may use them in code the program never runs. Misusing them as CPython forbids (an
`await` outside an async def, a `nonlocal` without a binding, `yield` in a comprehension,
`:=` outside brackets) is a syntax error wherever it is (below).

## Syntax errors

Every `SyntaxError` CPython reports before it runs a file is a
compile-time error with CPython's message and line, wherever it is: in a template or a
function of an imported module that is never compiled, in a class, and in code the loader
drops (an imported module's `__main__` block, a platform branch). That covers the file
(bytes that are not UTF-8 without a coding declaration, NUL bytes, coding declarations, at line 0 where CPython reports one there);
CPython's tokenizer (brackets never closed, mismatched, or more than 200 deep; more than 99
levels of indentation; unterminated strings; number literals; invalid characters; f-string
fields); its parser (targets that cannot be assigned or deleted, with its "Maybe you meant
'=='" variants; `try` without `except` or `finally`; parameter lists, also a lambda's;
keyword and `**` arguments; `:=`, `yield` and `*x` where its grammar has no place for them;
escapes in str and bytes literals); its symbol table (`global` and `nonlocal` after a use or
of a parameter or without a binding; `yield` and `:=` in comprehensions, and a later `for` clause that rebinds a `:=` target;
`import *` in a
function); and its compiler (`break`, `continue`, `return`, `yield`, `await` and `async` out
of place; a bare `except:` that is not last; starred targets and more than 255 targets
before one; `__debug__`; a late `from __future__` import; more than 21 statically nested
blocks, counted as CPython's compiler counts them, at the line where it first finds them),
also in a type parameter's bound or default and a `type` statement's value, which it compiles
though they are evaluated lazily. When a file has several errors, Pystachy reports the one CPython
reports: the parser's first, a tokenizer error only where the parser reaches it, then the
symbol table's, then the compiler's. Where CPython's parser has a specific message for some
malformed code (the statement an indented block is missing after, parenthesized
parameters), Pystachy may say just "invalid syntax", and patterns in `match` statements are
not checked. `tools/syntax_sweep.py` compares `pystachy check` with CPython's `compile()`.

## Deviations from CPython

In these cases the program compiles but can behave differently from CPython:

- `int` is 64-bit. Where CPython would produce a bigger int, including an intermediate
  result or `int()` of a long string, Pystachy raises `OverflowError` instead of
  wrapping. `int ** negative int` is a `ValueError` (the result type would be dynamic;
  `0 ** -1` raises CPython's `ZeroDivisionError`), and so is a negative float to a
  fractional power (CPython returns a complex).
- `str` is a byte string holding UTF-8: `len`, indexing, slicing, iteration, `find`/`index`
  and `write()`'s result count bytes, case mapping, the `is*()` tests and `split()` know
  only ASCII, and `chr(i)` for `i < 256` is that byte (above, its UTF-8; `"%c" % i` is the character's
  UTF-8 for every `i`).
  ASCII behaves exactly like CPython; escapes such as `\xe9` and `€` produce UTF-8, and
  format widths, `center`/`ljust`/`rjust`/`zfill`, `repr()`'s escapes, `read(n)` and
  `ord()` count characters. Files hold the
  same bytes, read as UTF-8 or Latin-1; any other `encoding=` raises `NotImplementedError`
  when the file opens. A surrogate (`chr(0xD800)` to `chr(0xDFFF)`) is held in its
  three-byte form and printed or written as it is, where CPython raises
  `UnicodeEncodeError`; its `repr()`, `ascii()` and `ord()` match CPython's.
- `dict.keys()`, `.values()` and `.items()` return list snapshots, so `enumerate()`, `zip()`
  and `reversed()` of them do not notice a dict that changes size (a plain `for` over
  `d.items()` steps the dict itself and does).
- A runtime error prints only the last line of CPython's traceback (without `NameError`'s
  "Did you mean" hints) and exits with status 1 after flushing stdout; CPython's
  compile-time `SyntaxWarning`s are not printed. Recursion is limited only by the native
  stack: it goes past CPython's limit of 1,000 calls (`sys.setrecursionlimit()` checks its
  argument as CPython does and records it for `sys.getrecursionlimit()`, but bounds nothing and
  is not compared with the current depth),
  and where CPython raises `RecursionError` the program dies with `SIGSEGV` (status 139, losing buffered output) or,
  for a tail call in an AOT build, loops forever. `==` between two cyclic dataclass objects
  recurses like that too.
- Floats are unboxed, so a NaN has no identity: `nan in [nan]` is `False`, and lists or
  tuples holding the same NaN object compare, and sort, as if they held different ones. The
  sum of an empty `list[float]` is `0.0` (`sum(xs, 1)`: `1.0`), where CPython returns the int
  start.
- An import of a builtin module binds its names for the whole program, wherever it appears
  (an import of a Python module in a function binds its names in that function only, as in
  CPython, also where the name is a builtin module it re-exports: `from helper import os`). A program that reads a module's attribute before the import of the module has
  run reads its zero value instead of raising `NameError`.
- A function declared or inferred to return a value that ends without a `return` raises
  `RuntimeError` there, where CPython returns `None` (a template that returns objects
  returns `None`, as CPython does).
- The `lib/` modules behave as their pure-Python code, which CPython replaces with C
  accelerators: errors can be worded differently, the functions accept keyword arguments the
  C versions reject, `bisect`'s `hi=-1` is not `len(a)`, assigning to a `stat` constant
  changes the `S_IS*` tests, and `heapify` of more than 2,500 items compares in another
  order. A program file named like a module CPython imports at startup (`stat.py`,
  `posixpath.py`) replaces it, where CPython keeps its own.
- A class of an imported module that Pystachy leaves uncompiled (above) is not created when
  the module is imported, so the errors CPython raises while creating it are not reported:
  `typing`'s checks of `NamedTuple`, `TypedDict`, `Protocol` and `Generic` classes, `__slots__`
  conflicts, `@dataclass`'s field order and mutable defaults, a base that is not a class or
  cannot be subscripted (but a subscript of a class without bases, above), and an exception
  that a builtin operation in its body raises. A template's code is compiled per argument
  types, so a type error in code a program never calls is not reported (syntax errors are), and its
  variables keep one type, so code that rebinds one to another type (`a /= b` on ints) is
  rejected when it is compiled.
- An optional import of a module that Pystachy does not find runs its handler, also where
  CPython would find the module (a standard library module Pystachy lacks, or a package
  installed for CPython); a handler that may end the program is rejected instead (below). A
  module whose code raises `ImportError` at its top level keeps the globals that code set
  before the raise, where CPython discards the half-run module; a later import runs the
  code again over them.
- A global (a function or class included) that its module's code has not bound when it is
  read (assigned in a branch that did not run, or read while the module is still being
  imported: a circular import) raises `AttributeError: module 'm' has no attribute 'x'`, read
  as `m.x` or taken by a `from m import x` that is not an optional import. CPython 3.13 raises
  `ImportError: cannot import name 'x' from 'm' (FILE)` for the from-import, and its
  `AttributeError` says the module is partially initialized or suggests renaming its file.
- Memory is reclaimed by a conservative collector, not reference counting: garbage is
  freed in batches and there are no finalizers (`__del__` never runs). A file the program
  drops without closing is closed when a collection finds it unreachable, or at exit, not at
  once as in CPython. A file used in one expression (`open(p).read()`,
  `print(..., file=open(p, "w"))`) is closed right after it, and opening a file that has a
  writer open runs a collection first; but the stack scan is conservative, so a writer that a
  function dropped a moment ago can still look reachable. Its data can then be missing when
  the file is read back, and appends through several dropped writers can land out of order.
- In `"+"` modes, a write after reads goes where CPython's text layer stopped reading ahead,
  which Pystachy models in 8 KiB chunks. After `read(n)` for an `n` above that, CPython has
  read ahead by about `n` characters instead; and when a `for` loop over the file stops
  early, CPython 3.13 keeps its read-ahead across a write, so the next `read()` returns the
  text from before the write.

## Rejected rather than miscompiled

CPython would run these programs, but Pystachy rejects them at compile time, with a
`file:line: error:`, rather than compile them into something that behaves differently:

### Names and scopes

- a function, class, method or import name bound twice, or a name that is both a variable and a
  function, class or import
- a class-body default that names an earlier class attribute (Pystachy has no class scope), also
  one named like a builtin or `__name__`, also in an imported module
- a local read textually before its first assignment (declare it first: `x: int`), where a name
  that a function deletes, defines with `def` or `class`, or binds with `:=`, a `match` capture
  or a `type` statement is its local too
- a read of a function's local that only code dropped at compile time binds
- calling a builtin whose name the module also binds as a variable (`sum = 0` ... `sum(xs)`,
  which CPython would reject at run time)

### Modules and imports

- a read in a function of a name that its import of a Python module binds, where Pystachy cannot
  tell that the import has run (after a loop that imports it, say)
- a read of a global that only a template's function assigns, compiled before a call compiles
  that function (declare it at module level: `x: T`)
- `from m import x` of a global that only m's functions assign (read it as `m.x`, or declare it
  in m.py)
- a global read before its module's code assigns it whose first binding there is a `for` or
  `with` target or a value whose type is not known yet at that point
- another module's global, other than a constant (a literal, also a negative number), read while
  that module is still being imported
- an imported module that binds `__name__`
- a syntax error in a module that one of the program's import statements names, also where that
  import never runs
- an optional import (`try: import m / except ImportError:`) in which what runs in the `try` may
  raise `ImportError` other than by a module's top-level raise reached for sure, whose handler
  names (`as e`) or re-raises the exception, whose handler may end the program where the module
  is not found, or whose failing module imports the module of the `try` back
- an optional `from m import x` where Pystachy cannot tell whether m has bound x when it runs (m
  binds it in a branch, deletes it, only annotates it, binds it in a function or by a star
  import)
- a name a package binds itself that is also the name of a submodule the program imports, read
  as `pkg.util`, with `from pkg import util` or in the package's functions, when which of the
  two it is depends on when the submodule is first imported
- an alias (`f = g`) that module-level code uses before its assignment
- `__all__` changed other than by `+=`, `append` and `extend`, for `import *`
- `del` of another module's attribute
- in an imported module, uncompiled code (above) that may run code of the program when its `def`
  or `class` statement runs (a call of a function or class; a callable of the program given to a
  builtin, such as `sorted(xs, key=C.m)`; any other decorator; a metaclass; a base that defines
  `__init_subclass__` or `__class_getitem__`; a value that may hold objects of the program's
  classes used as a class attribute, set item, dict key, operand or argument; a read of a class
  attribute that may be such an object; an assignment to an attribute or item; a comprehension,
  or a class-body statement other than an assignment, `del`, `if`, `def`, `class` or a
  docstring), a name such code reads that is not bound by then or that an import or class binds
  only on some path, a decorator that is not a dotted name or a call of one (PEP 614), an
  evaluated annotation that is not a type as above, a class attribute whose class defines
  `__set_name__`, and `class C(object)` or a builtin decorator where the module may have rebound
  the name by then
- an imported module whose functions, lambdas, classes and tuple displays nest past CPython's
  marshal limit

### Templates and empty containers

- an empty container whose first use stores an empty `[]` or `{}` into it (`d[k] = []`)
- an empty list or dict that a template's function returns empty, used where the `list[int]` /
  `dict[int, int]` guess does not fit and the context gives no type (`xs: list[str] = collect()`
  gives one)
- a template whose returns have different types (or `None` and a type other than a class), or
  that calls itself before a return statement decides its type
- a parameter whose argument is `None` given a value of another type in an if branch or loop, or
  bound as a `for` target

### Objects and operators

- comparison dunders that do not return `bool`, `__str__`/`__repr__` that do not return `str`,
  methods without `self`
- an `==` or `!=` between objects of different classes, which CPython would reflect to the right
  operand's `__eq__`
- comparing or sorting objects in a container when the `__eq__` or ordering method the operation
  calls is annotated to take another class, which CPython calls anyway
- `raise` of anything but a builtin exception

### Builtins

- `range()`, `enumerate()`, `zip()` or `reversed()` nested inside `enumerate()`, `zip()` or
  `reversed()` in a `for` loop, and `zip(strict=...)`
- a keyword argument Pystachy does not take (`os.path.realpath(p, strict=True)`)
- `os.getenv()` without a default (its result would be `str` or `None`)

### Source text

- f-strings that reuse their own quote inside a field (PEP 701), `\N{...}` escapes, non-ASCII
  identifiers and tabs in indentation
- a source file whose coding declaration names an encoding other than UTF-8, Latin-1 and ASCII
- source nested more than 5,000 levels deep (expressions, statements and `elif` branches; a `**`
  or `lambda` counts twice), and source whose nesting would overflow CPython's parser stack of
  6,000 levels of its grammar rules (a MemoryError in CPython), counted as measured on CPython
  3.13 (a bracket 24 to 33 levels, a block 7, a comparison's operand 3, ...) so that Pystachy
  stops at most a few dozen levels before CPython does
