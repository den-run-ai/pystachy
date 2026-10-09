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
| [Types](#types) | `int` (64-bit, overflow-checked), `float`, `bool`, `str`, `list[T]`, `dict[K, V]`, `tuple[...]`, classes, dataclasses and `NamedTuple`s, `Optional` of any of these |
| [Typing rules](#typing-rules) | annotated functions have their declared types; an unannotated module-level function is a *template*, compiled once per list of argument types |
| [Exceptions](#exceptions) | `try`/`except`/`else`/`finally` and `raise` with CPython 3.13's exception hierarchy, and exception classes of the program |
| [Modules](#modules) | your own modules and packages, the builtin modules `sys`, `os`, `math`, `time`, ..., and unmodified standard library modules from `lib/` |
| [Removed on purpose](#removed-on-purpose) | generators, lambdas and closures, inheritance (but an exception class's), sets, `bytes`, big integers, `async`, ... |
| [Syntax errors](#syntax-errors) | every `SyntaxError` CPython reports before running a file, with CPython's message and line |

Contents: [Types](#types) · [Typing rules](#typing-rules) · [Statements](#statements) ·
[Exceptions](#exceptions) · [Modules](#modules) · [Expressions](#expressions) ·
[Builtins and library modules](#builtins-and-library-modules) ·
[Removed on purpose](#removed-on-purpose) · [Syntax errors](#syntax-errors) ·
[Deviations from CPython](#deviations-from-cpython) ·
[Rejected rather than miscompiled](#rejected-rather-than-miscompiled)

## Types

`int` (64-bit), `float` (IEEE double), `bool`, `str`, `list[T]`, `dict[K, V]` (keys `int`,
`str`, or tuples of `int`, `bool`, `str`, `str | None` and such tuples), `tuple[A, B, ...]` (up
to 9 elements, indexed by integer constants), user classes, `T | None` (also `None | T`,
`Optional[T]` and `Union[T, None]`, whose repeated members collapse as `typing`'s do:
`Union[T, T, None]`, and `Union[T]` is `T`) for a class type or for `str`, `int`, `float`,
`bool`, `list`, `dict` and `tuple` (wherever a type goes, inside containers too), and `None` as
a return type.

The `typing` spellings (`List`, `Dict`, `Tuple`, `Optional`, `Union`, `TextIO`, and `Self` in a
class's methods and fields, which is that class) work when imported from `typing`, and string
forward references work (also inside `list["Node"]`), as does `typing_extensions` in place of
`typing`. `collections.abc` imports as `typing` does (also `from collections import abc`), and
`Mapping[K, V]` and `MutableMapping[K, V]` (from either) are `dict[K, V]`, `Sequence[T]` and
`MutableSequence[T]` are `list[T]` (so they are invariant, and a tuple or `str` is no
`Sequence`); `isinstance(x, Sequence)` and its siblings are decided by `x`'s type. `os.PathLike`
(also `os.PathLike[str]`) in a union with `str` is dropped, as a path of another type cannot
exist in Pystachy: `str | os.PathLike[str]` is `str` (with `None`, `str | None`), and
`os.fspath()` returns the `str` it is given.

`x: Final = v` is `x = v` outside class bodies (in one, a field typed by its constant),
`x: Final[T]` is `x: T`, `x: Final` alone does nothing, and a `def` decorated with `@overload`
(also a method) is the stub CPython replaces with the `def` after it: it is dropped.

### When annotations are evaluated

As in CPython 3.13, the annotations of a def's parameters and return, of a class body and of
module-level code are evaluated when the statement runs, also in an imported module whether or
not the program uses the def: one that raises there is a compile-time error with CPython's
exception (a name not bound yet, such as a class defined further on, `"C" | None`, `C[int]` of a
class, `Optional[A, B]`, an attribute a module does not have). Such an annotation must also read
only names that are surely bound by then (not bound only in an `if` branch or a loop, nor
deleted), and be a type: a class or `typing`'s name (also a module global that only
`T = TypeVar("T")` statements bind, one or more), subscripts of those and of the builtin
generics, `|` of them, literals, or a variable as the whole annotation (an alias, an error where
the annotation is used). What may run code of the program there is rejected: a call, an operator
other than `|`, a variable as an operand or subscripted, a subscript of one of the program's
classes (`__class_getitem__`), an attribute of a builtin module other than `typing` (but
`os.PathLike` and `collections.abc`'s names).

A string annotation (`"Node"`) is not evaluated, and neither is any annotation in a module that
imports `annotations` from `__future__`.

## Typing rules

- A function whose parameters are annotated has those types; a missing return annotation
  means `-> None`. Methods' parameters must be annotated.
- A module-level function with an unannotated parameter is a **template**: each call
  compiles it, once per list of argument types, for those types (an annotated parameter
  keeps its type), and its first `return` with a value decides what it returns. It is
  compiled only when a call needs it, so what Pystachy cannot compile in it is an error only
  then. In it, `isinstance(x, T)` (also with a tuple of types or `T | U`), `hasattr(x, "a")`
  (the builtin types have CPython 3.13's attributes) and `x is None`, when `x`'s type decides
  them (for an object, which may be `None`, when its argument is known not to be: a new object
  or `self`), are constants: only the branch that runs is compiled (in `if`, `while`, `assert`,
  `and`/`or` and conditional expressions), and nothing after a `return`. A parameter whose
  argument is `None` reads as `None`, and outside if branches and loops may get a value of
  another type (`if hi is None: hi = len(a)`, `if acc is None: acc = []`). A template that
  returns objects or `T | None` returns `None` where it ends without a `return`, as CPython
  does, and one that cannot end (it always raises) may be called where a value is expected
  (`return fail("bad")`): the call has the type its context expects. A
  function with `*args` is a template too: each call arity compiles it with `args` a tuple
  of the extra arguments' types (iterating it needs one item type; `()` is the empty
  tuple), and in `def f[T](x: T) -> T` (PEP 695) what mentions a type parameter is
  unannotated, as are a module-level function's parameters and return that mention a
  module-level `T = TypeVar("T")` (from `typing` or `typing_extensions`; a method's may not).
  In a template's function, an empty list or dict that nothing fills where the
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
- Optional values: a `T | None` is a `T`'s pointer, and `None` is null (a class type includes
  `None` already); an `int | None`, `float | None` or `bool | None` is a pointer to an immutable
  box of the value, made where an `int`, `float` or `bool` becomes one.
- A local first assigned `None` is `T | None` for the first other value assigned to it, typed
  where it is assigned (also by unpacking); a read before that, in the order the code is
  compiled, takes the type of the first such value in the function's source whose type is known
  there, or else the type expected where it is read (a return, an argument, an item), and a
  local that only `None` is ever assigned to reads as `None` (until then only comparisons with
  `None` may read it), as does a global that module code only assigns `None` and no function's
  `global` statement binds. So is module code's global for the values module code assigns it,
  where they can be typed at its first assignment.
- `x if c else None` (also nested: `x if c else y if d else None`, and
  `None if x is None else x + 1`), `x or None`, a template that returns `None` and a `T` (in
  either order) and a display that holds `None` among `T` items give `T | None`; `None or x` is
  `x`, and `x or 0` is an `int` for an `int | None` `x`. `d.get(k)` and `os.getenv(name)`
  without a default return `V | None` (also for `int`, `float` and `bool` values) and
  `str | None`, and so do `d.get(k, d)` and `d.pop(k, d)` with a default `d` that may be `None`.
- A `T` or `None` goes where a `T | None` is expected (a tuple item by item). Where only a `T`
  works (a method, `len()`, indexing, iteration, `in`, `+`, `<`, unpacking, a builtin's
  argument) the value is checked when it runs, and `None` raises CPython's error (also `-x`,
  `abs()`, `int()`, `range()`, `%d` and a format spec of an `int | None`); `==`, `is`, truth
  tests, `str()`, `repr()`, f-strings, `%` (a `tuple | None` is its items or one `None`),
  `print()`'s `sep` and `end`, a slice's bounds (`None` is an omitted one) and `sys.exit()`
  treat `None` as CPython does, and so do the repr, comparisons and sorting of containers of
  optional items, also against containers of `T` items (`list[str | None] == list[str]`; `+` of
  the two makes a `list[str | None]`, which `extend()` and `+=` also take a `list[str]` into);
  `join()` and `writelines()` check each `str | None` item.
- A key that may be `None` is in no dict: `in` is `False`, `get()` and `pop()` give their
  default, and `d[k]`, `d.pop(k)`, `del d[k]` and `d[k] op= v` raise `KeyError: None`
  (`d[k] op= v` stores `k` only where `d[k]` has found it, so `k` needs no narrowing there,
  where `d[k] = v` needs it); so is a tuple whose item may be `None` where the dict's keys hold
  a `str` (a `None` item of a tuple key that nothing else types is a `str | None`), and a `bool`
  looks up, pops and deletes the `int` key it equals (`d[True, 2]`), and a `KeyError` names it
  as CPython's does (`KeyError: (True, 2)`); `None in xs` and `xs.count(None)` look for it in a
  list.
- Where CPython would pass the `None` on (an assignment to a `T` variable or field, a `T`
  argument of a user function or of a list method, a return from a function declared to return a
  `T`), the value must be known not to be `None`: a local or parameter is, as mypy narrows it,
  in the body of `if x is not None:`, `if x:` and `while x is not None:` (and the `elif` and
  `else` blocks of the tests that show it), in the right operand of `x is not None and`, in the
  arms of a conditional expression, after `if x is None: return` (or `raise`, `continue`,
  `break`, `sys.exit()`, `assert False`), after `assert x is not None`, after `x = <a T>`, and
  after a loop where it holds at each way out (its test is false, which never happens for
  `while True:`, or a `break`; after a loop with an `else` block: the end of that block, or a
  `break`), until a value that may be `None` is assigned to it (in a loop's body: anywhere in
  it). A comprehension's variables are its own, and do not change what is narrowed outside it.
  Module globals and fields are not narrowed, as a call may change them: copy one to a local,
  and test that.
- No silent `int` → `float` conversion when assigning or passing arguments: CPython would
  keep an `int`, so `x: float = 1` is rejected (write `1.0`). Arithmetic mixes freely, and so
  do `in`, `count()`, `index()` and `remove()` of a list of numbers (`1 in [1.0]`).
- Python scoping: a name assigned in a function is local to it; `global` opts out.
- Class fields come from class-body annotations or from `self.x = ...` in `__init__` (`self`
  being whatever its first parameter is named), typed by annotation, parameter, literal,
  constructor, method or function call, or a list, tuple or dict display of those (by its first
  item), `[x] * n`, `list(range(n))`, `list(xs)` or `sorted(xs)` (not a call of a template,
  whose result type is known only once it is compiled, nor of a function that returns `None`:
  annotate the field). An exception class (below) also has its base's fields, and an object
  of it is an object of its bases too.
- A `typing.NamedTuple` class (annotated fields with defaults, a docstring, methods) is a
  dataclass whose fields only its `__init__` assigns, read like the tuple of them: unpacking
  (also as a `for` target), constant indexing, iteration, `in`, `len()`, `%` formatting,
  `+` and `*` (which make a tuple), `p._replace(f=v)`, `_fields`, `_asdict()` (of fields of
  one type), and `==`, `!=` and ordering as tuple's methods do them (also with plain tuples
  and other NamedTuples), except an operator that its class defines; its `repr()` is a
  dataclass's.
- `C.x` reads the class attribute that a class-body default binds (instances read it until
  they assign `x`), also a `Final` one. `C.x = v` (also `cls.x += 1` in a class method) assigns
  it, which `C.x` and the objects that have not assigned `x` then read. A class-body `x = v`
  without an annotation is `x: T = v`, `T` given by `v` as for a field (but in a dataclass or
  NamedTuple, where it would be no field). An exception class shares the class attributes it
  inherits with its base: `S.x`, `E.x` and the objects of both read one variable, which the
  class body that binds it evaluates once, and `E.x = v` changes it for both; a class body
  that binds `x` again (`x = v`, or `x: T = v` with the base's type `T`) gives the class its
  own. `C.__name__` is the class's name.
- A method decorated with `@staticmethod` or `@classmethod` is called through its class
  (`C.m(...)`) or through an object (`o.m(...)`, `self.m(...)`, which only checks that `o` is
  not `None`). There is no inheritance (but for exception classes), so a class method's `cls`
  is always its own class: `cls(...)` makes one, `cls.x` reads a class attribute and
  `cls.m(...)` calls a static or class method. A class method that uses `cls` and that an
  exception class of the same module inherits is compiled again for that class, so
  `S.make()` makes an `S`.

## Statements

assignment (chained, tuple and list unpacking, swaps), annotated and
augmented assignment (`+=` on lists extends in place; `__iadd__` & co are honoured),
`if`/`elif`/`else`, `while`, `for` (both with `else`) over `range`, lists, strings, dicts,
files, tuples (and NamedTuples) of one item type, objects (below), `.items()`/`.keys()`/`.values()`,
`enumerate` (with `start`), `zip` and
`reversed` (also of a `range`), stepping each sequence as its CPython iterator does (a dict
that changes size raises `RuntimeError`), `break`, `continue`, `return`, `pass` (and `...`), `global`,
`del` of a list item, a dict key or an object's item, `assert`, `with open(...) as f:` (also several items, in
parentheses or not), `try` (below), `raise` of an exception class, a call of one or an
exception, a bare `raise` and `raise ... from ...` (if nothing catches it, it ends the program
with CPython's message and status, `SystemExit` and `KeyboardInterrupt` included), `def`,
`class`, `@dataclass` (also `@dataclass(kw_only=True)`; its `__init__` calls `__post_init__`), `class P(NamedTuple)`, `@staticmethod`, `@classmethod`, docstrings, `del` of a variable (later reads raise `NameError` or
`UnboundLocalError`; not of a global in a function), `import`/`from` of the builtin modules
`sys`, `os`, `os.path`, `math`, `time`, `errno`, `tempfile`, `typing`, `collections.abc`,
`dataclasses`, `builtins` and `__future__`, and of Python modules (below), with keyword-only (`*`) and positional-only
(`/`) parameters.

## Exceptions

`try` with `except` clauses (an exception class, a tuple of them, with `as NAME` or not, or a
bare `except:`; `builtins.ValueError` and `os.error` too, and `A or B` of classes, which is
`A`), `else` and `finally`, in every combination CPython accepts but `except*`. A clause catches
its classes and those deriving from them, in CPython 3.13's hierarchy and the program's
(`except LookupError` catches a `KeyError`, `except Exception` does not catch `SystemExit`;
`IOError` is `OSError`): what a `raise` raises, and what the runtime raises, also in other
functions and modules and in code the runtime calls back (`sort()` with a `__lt__` that raises
leaves the list whole): a missing dict key, an index out of range, `int("x")`, a division by
zero, `open()` of a missing file and the other `OSError` subclasses, unpacking, `sys.exit()` as
`SystemExit`, and the checked arithmetic's `OverflowError`.

A clause's classes are looked up when an exception gets to it (one whose `class` statement has
not run raises `NameError`). The name bound by `as` is unbound after its clause, however the
clause is left, and may be bound to a value of another type before or after it.

A builtin exception, which calling a builtin exception class makes too
(`err = ValueError("x")`), is a value of its own type, which `Exception`, `BaseException` or any
builtin exception class names in annotations (`errors: list[Exception]`;
`OSError(errno, strerror[, filename])` is CPython's `[Errno n] strerror` of the subclass the
errno names, and `ImportError(msg, name=..., path=...)` takes its keywords, as do
`AttributeError`'s and `NameError`'s): print it, `str()`, `repr()` or format it, store it,
compare it (by identity: an exception that raised an object of an exception class is that
object, so `e is x` after `raise x`), `raise` it, test it with `isinstance()` or
`type(e).__name__`; its attributes such as `e.args` are not supported. `raise ... from` a cause
that is not an exception raises CPython's `TypeError`.

`finally` runs on every way out of the statement: at its end, as an exception passes, and at
`return` (whose value is computed first), `break` and `continue`; a `return`, `break` or
`continue` in it drops the exception in flight. A bare `raise` re-raises the exception being
handled, which every way out of an except clause restores, and an exception that leaves a `with`
block closes its file (a close that fails raises its `OSError` in its place, inside the `try`
statement around, as `__exit__` does). A module whose code raises is not imported: the name its
import binds is unbound, and a later import runs its code again.

### Exception classes

A class whose one base is a builtin exception class (also `builtins.ValueError`, `os.error`), or
an exception class of the program, is an exception class: fields, `__init__`, `__str__`,
`__repr__`, other methods, class-body fields with or without defaults and docstrings, as for any
class. Its objects keep the positional arguments of the call that makes them, as CPython's
`args`, for `str()` (`''`, `str(arg)` or the tuple's repr; a `KeyError`'s repr of its argument)
and `repr()` (`E('a', 2)`), and `super().__init__(...)` sets them again; without an `__init__`
of its own or of a base, a class takes any positional arguments.

A subclass has its base's fields and methods and may define `__init__`, `__str__` and `__repr__`
again: `str()`, `repr()`, `print` and an uncaught exception's line always use those of the
object's class, `super().__str__()` and the others those of the base (also written
`Base.__str__(self)` and `super(E, self)`), and `e.__str__()` is `str(e)`; a class method that
uses `cls` is compiled again for each class that inherits it, and class attributes are shared as
above; `==` between objects of classes with a base in common calls that base's `__eq__`.
Deriving from `OSError` or `SystemExit`, a class with an `__init__` of its own (or of a base)
keeps no args, and has the code `None`, until `super().__init__(...)` sets them, as CPython's
do.

`except E as e` binds the object, typed as the nearest class of the program that the clause's
classes derive from (else as a builtin exception, whose `str()` and `repr()` still are the
object's). One that nothing catches prints `module.E: str(e)` (`E` alone in the main program,
without `: ` when `str(e)` is empty) and ends with status 1; one that derives from `SystemExit`
ends the program as its code says, as `SystemExit` does. `except SystemExit` catches those,
`except Exception` does not.

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
`del`, also in a branch or loop, may unbind; of a builtin module, what Pystachy's lacks). The imports before it run their code and bind their names, a failing module's
code runs up to its raise, and then the handler runs; a module that failed is not imported,
so a later import runs its code again. Another `try` around imports (with `finally`, or
clauses naming other classes) imports its modules as any import does: a module that is not
found is an error.

An import inside a function of an imported module
that the program's module-level imports do not load is an error only where that function is
compiled. `import pkg.util as u` binds `u` to the attribute `util` of `pkg`, as CPython
does: the submodule, unless the package binds `util` itself after its own code imported the
submodule (`from .util import util`).

### Code Pystachy cannot compile in an imported module

A class or function of an
imported module that Pystachy cannot compile (inheritance other than an exception class's,
unannotated methods, an annotation it does not support such as `Iterable[int]` or
`dict[float, X]`, a `bytes` or
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
indices, slicing of strings and lists, tuple `+` and `*` by a constant, list/dict/tuple
displays, list comprehensions, generator expressions and
`range()`/`reversed()`/`enumerate()`/`zip()` as the argument of `list()`, `sorted()`,
`sum()`, `min()`, `max()`, `any()`, `all()`, `str.join()` or `list.extend()` (`any()` and
`all()` stop at the deciding item, as they do over files, and `list.extend()` appends each
item of a generator expression as it is made), `x in range(...)`, and operator
overloading resolved statically:
`__add__` & co, the in-place forms, `__eq__`, rich comparisons with CPython's reflection
rules (`a < b` tries `b.__gt__(a)`), `__len__`, `__bool__`, `__str__`, `__repr__` and
`__format__`. Objects inside lists, dicts and tuples compare, sort and print through
their own methods, as CPython calls them: lists and tuples compare their items with `==`
before ordering them, `list.sort`, `sorted` and `min` use `<` (`__lt__`, else the reflected
`__gt__`), and `max` uses `>`. Unary `-`, `+` and `~` on objects are not supported.

The container protocol is resolved statically too: `o[k]` calls `__getitem__`, `o[k] = v`
`__setitem__` (`o[k] += v` both), `del o[k]` `__delitem__`, and `x in o` `__contains__`, whose
result counts as its truth does; without `__contains__`, `x in o` looks for `x` among the items
`__iter__` steps through. An `__iter__` annotated `-> Iterator[T]` (or `Iterable[T]`) that
returns `iter(xs)` of a list, a tuple, a `str` or another such object steps through `xs` as a
list's iterator does, wherever the object is iterated: `for` loops, comprehensions, unpacking,
`enumerate()`, `zip()`, `list()`, `sorted()`, `min()`, `max()`, `sum()`, `any()`, `all()`,
`str.join()` and `list.extend()`; `list()`, `sorted()` and `list.extend()` then call its
`__len__`, if it has one, as CPython's length hint. A method the operation needs and the class
does not define is an error with CPython's message (`'C' object is not subscriptable`), and an
object that is `None` raises CPython's error when it runs.

## Builtins and library modules

`print` (with `sep`, `end`, `file`, `flush`), `len`, `str`, `repr`, `ascii`,
`int`, `float`, `bool`, `ord`, `chr`, `abs`, `min`, `max`, `sum`, `sorted` (and
`list.sort`, with `reverse=`), `list`, `dict`, `round`, `divmod`, `pow` (also modular,
with inverses), `any`, `all`, `input`, `format`; the common `str`, `list` and `dict` methods
(`find`/`index`/`count` with start and end, also `None`, `split`/`rsplit`, `partition`/`rpartition`,
`splitlines`, `removeprefix`/`removesuffix`, `center`/`ljust`/`rjust` with a fill character,
`zfill`, `expandtabs`, `capitalize`/`title`/`swapcase`, `dict.pop` with a default; not
`str.format()`, `dict.update()`, `popitem()` and `fromkeys()`, `dict()` of pairs, or tuple's
`index()` and `count()`); `open()` with CPython's modes, errors, `buffering=`, `newline=`
translation and positions for `"+"` modes, and files' `read`/`readline`/
`readlines`/`write`/`writelines`/`flush`/`close`, iteration and `closed`/`name`/`mode`;
`sys.argv/exit/stdin/stdout/stderr/maxsize/platform/setrecursionlimit/getrecursionlimit` (the streams
are files), `os.system/execv/getpid/getenv/remove/rmdir/fspath/path.exists/path.realpath/path.join` and `os.name/sep/curdir/pardir/extsep/pathsep/linesep/
devnull`, `tempfile.mkdtemp`, `time.time/time_ns/monotonic/perf_counter/process_time` (and
their `_ns` forms) and `time.sleep`, the `errno` constants, and the `math` functions and
constants, which raise CPython's domain and range errors (but `dist`, `fsum`, `gamma`,
`isclose`, `lgamma`, `prod` and `sumprod`, which are rejected).

## Removed on purpose

Each of these would require a dynamic runtime or a large compiler
feature: generator functions (`yield`), generator expressions other than the consumer
arguments above, lambdas and closures, inheritance other than an exception class's, `**kwargs` and
`*args` in methods, star arguments in calls (`f(*xs)`) and starred targets (`a, *rest = xs`),
sets, dict and multi-clause comprehensions, slice steps, first-class
functions (`map`, `key=`), `isinstance`/`hasattr` other than the static cases above, `getattr`/`eval`, `bytes` (literals
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
  and `write()`'s result count bytes, case mapping and the `is*()` tests but `isspace()`
  know only ASCII, and `chr(i)` for `i < 256` is that byte (above, its UTF-8; `"%c" % i` is
  the character's UTF-8 for every `i`).
  ASCII behaves exactly like CPython; escapes such as `\xe9` and `€` produce UTF-8, and
  format widths, `center`/`ljust`/`rjust`/`zfill`, `repr()`'s escapes, `read(n)` and
  `ord()` count characters, as `strip()` (also of given characters), `split()`,
  `rsplit()`, `splitlines()` and `isspace()` read them (CPython's Unicode whitespace and
  line breaks). Files hold the
  same bytes, read as UTF-8 or Latin-1, without checking them (invalid UTF-8 is read as it
  is, where CPython raises `UnicodeDecodeError`); any other `encoding=` computed at run time
  raises `NotImplementedError` when the file opens. A surrogate (`chr(0xD800)` to
  `chr(0xDFFF)`) is held in its three-byte form and printed or written as it is, where
  CPython raises `UnicodeEncodeError` (`sys.stderr`, which an uncaught exception's line and
  `sys.exit()`'s message go to, writes it as `\udcff`, as CPython's does); its `repr()`,
  `ascii()` and `ord()` match CPython's.
- `dict.keys()`, `.values()` and `.items()` return list snapshots, so `enumerate()`, `zip()`
  and `reversed()` of them do not notice a dict that changes size (a plain `for` over
  `d.items()` steps the dict itself and does), and neither do `in`, `min()` and `max()` over
  `d.values()` when an `__eq__` or `__lt__` of the values changes the dict, where CPython
  raises `RuntimeError`; they print as lists and compare equal to lists.
- A type error that CPython raises only when the code runs (`<` between dicts, a constant
  index outside a tuple) is a compile-time error, so the output before it is not printed.
- An exception that nothing catches prints only the last line of CPython's traceback (without
  `NameError`'s "Did you mean" hints) and exits with status 1 after flushing stdout; CPython's
  compile-time `SyntaxWarning`s are not printed. Running out of memory (`MemoryError`), a
  Ctrl-C (`KeyboardInterrupt`) and running out of stack (below) end the program at once: no
  `except` clause catches them, and no `finally` block runs (a `raise KeyboardInterrupt` is
  an exception like the others). Recursion is limited only by the native
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
  run reads its zero value instead of raising `NameError` (but after an import in a `try`
  statement that raised, as CPython does).
- An exception keeps `str()` of its arguments and what `repr()` shows of them as it is made
  (their `__str__` and `__repr__` run then), where CPython computes them from `args` each time:
  an argument changed afterwards (a list) is not seen, and an argument whose `__str__` or
  `__repr__` raises makes the call of the exception class (`raise KeyError(obj)`) raise that
  exception instead, so that an `except KeyError` does not run.
- A function declared or inferred to return a value that ends without a `return` raises
  `RuntimeError` there, where CPython returns `None`, also when it is declared to return
  `C | None` for a class `C` (a dataclass or `NamedTuple` too). A function declared to return
  `T | None` for an `int`, `float`, `bool`, `str`, `list`, `dict` or `tuple` T, and a template
  that returns objects or `T | None`, return `None` there, as CPython does.
- An optional value that is `None`, passed to a builtin method's parameter that has a
  default (`s.split(sep)`, `s.strip(chars)`), means the default, as an explicit `None` does,
  also where CPython raises `TypeError` (the fill character of `ljust()`, `rjust()` and
  `center()`).
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
  installed for CPython), and so does one of a name that a builtin module of Pystachy lacks
  (`from math import fsum`); a handler that may end the program is rejected instead (below). A
  module whose code raises keeps the globals that code set before the raise, where CPython
  discards the half-run module; a later import runs the code again over them.
- A global (a function or class included) that its module's code has not bound when it is
  read (assigned in a branch that did not run, or read while the module is still being
  imported: a circular import) raises `AttributeError: module 'm' has no attribute 'x'`, read
  as `m.x`, where CPython 3.13's says that the module is partially initialized or suggests
  renaming its file. `from m import x` where `x` is unbound (`m`'s code left it so, or has not
  bound it yet) raises CPython's `ImportError: cannot import name 'x' from 'm' (path)`, naming
  the real path of `m`'s file where the program was compiled, where CPython names the file it
  found (and suggests renaming it in a circular import).
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

- a read of a name that nothing binds, and an attribute, operation or format spec that the static
  types rule out (`unicode`, `obj.missing`, `1 + "a"`, `f"{obj:>6}"` of an object without
  `__format__`), where CPython raises `NameError`, `AttributeError` or `TypeError` as it runs, also
  in a `try` whose clause catches it (a feature test such as `try: unicode / except NameError:`)
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
  raise `ImportError` other than by a module's top-level raise reached for sure (also a from-import
  of a name that its module's code may leave unbound), whose handler names (`as e`) or re-raises
  the exception, whose handler may end the program where the module is not found, or whose failing
  module imports the module of the `try` back
- an optional `from m import x` where Pystachy cannot tell whether m has bound x when it runs (m
  binds it in a branch, deletes it, only annotates it, binds it in a function or by a star
  import)
- a `def` or `class` statement inside a block of a module's code (`if`, `try`, a loop), and a class
  body statement other than fields, methods, a docstring, `pass` and `...`
- a name a package binds itself that is also the name of a submodule the program imports, read
  as `pkg.util`, with `from pkg import util` or in the package's functions, when which of the
  two it is depends on when the submodule is first imported
- an alias (`f = g`) that module-level code uses before its assignment
- `__all__` changed other than by `+=`, `append` and `extend`, for `import *`
- `from <builtin module> import *`
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
- an empty `[]` or `{}` that nothing gives a type (`{}["k"]` alone)
- an empty list or dict that a template's function returns empty, used where the `list[int]` /
  `dict[int, int]` guess does not fit and the context gives no type (`xs: list[str] = collect()`
  gives one)
- a template whose returns have different types (or `None` and an empty `[]` or `{}` that it does
  not fill), or that calls itself before a return statement decides its type (or, after a return of
  a `T`, before a return of `None` makes it return `T | None`)
- in a template's function, a use of a parameter whose argument is `None` as a value (`s.upper()`,
  `xs[0]`; `len()`, `int()`, `float()` and `ord()` of it raise CPython's error when they run), also
  in a branch that does not run for that call, and in a `try` whose clause would catch CPython's
  `TypeError`
- a parameter whose argument is `None` given a value of another type in an if branch or loop, or
  bound as a `for` target

### Objects and operators

- a call whose arguments do not fit the function's parameters (CPython raises `TypeError` where it
  runs; also `raise E` of an exception class whose `__init__` needs arguments)
- comparison dunders and `__bool__` that do not return `bool`, `__str__`/`__repr__` that do not
  return `str`, a `__len__` that returns neither an `int` nor a `bool`, methods without `self` (or
  a class method without `cls`)
- an `__iter__` that is a generator, or that returns anything but `iter(xs)` of a list, a tuple, a
  `str` or an object with such an `__iter__` (an iterator class, whose `__iter__` returns an object
  with `__next__`, too; the list it returns as it is is rejected by CPython too:
  `iter() returned non-iterator of type 'list'`; and `iter(d.keys())`, `values()` or `items()`,
  whose iterator raises if the dict changes size: `iter(list(d.keys()))` copies them), and a call
  of it (`o.__iter__()`)
- iterating over an object, or `x in o`, by its `__getitem__` alone (CPython's old sequence
  protocol), and `reversed()` of an object
- an `==` or `!=` between objects of different classes, which CPython would reflect to the right
  operand's `__eq__`, and between values of other types that cannot be equal (`1 == "1"`, or an
  `int | None` and a `str | None`, which CPython finds equal only when both are `None`)
- comparing or sorting objects in a container when the `__eq__` or ordering method the operation
  calls is annotated to take another class, which CPython calls anyway
- a constant tuple index out of range (CPython raises `IndexError` where it runs)

### Classes, dataclasses and NamedTuples

- a class method's `cls` used as a value or assigned, `@staticmethod` or `@classmethod` on a
  special method, a method of objects called through its class (`C.m(o)`), and decorators other
  than these, `@dataclass` and `@overload`
- `@dataclass` arguments other than `kw_only` (`frozen=`, `order=`, ...), and `dataclasses.field()`
  and `KW_ONLY`
- a class attribute without an annotation in a dataclass or NamedTuple, and an assignment through
  its class to a dataclass's or NamedTuple's class attribute, or to one its class body does not
  bind
- a NamedTuple without fields, assigned a field outside its `__init__`, whose class defines
  `__getitem__` or `__iter__`, compared or added through its own operator method with another type,
  given to `hasattr()` of a name it does not define, `_make()`, `_asdict()` of fields of different
  types, the functional `NamedTuple("P", [...])`, slicing a tuple, a NamedTuple or an object (whose
  `__getitem__` would take a slice object), a tuple `*` a number that is not a constant, and
  CPython's class-creation errors of a NamedTuple (a field after a default, an underscored field,
  an overwritten `__init__`) and of a dataclass (a field without a default after one with it)

### Optional values

- `is` between two `int | None` values (an `int` has no identity here), a `list[int]` or
  `dict[K, int]` where a container of `int | None` items is expected, compared or added (also for
  `float` and `bool`: an `int` item is no box; a tuple's items are copied into boxes, so
  `(1, 2) == t` works for a `tuple[int | None, int]`), and `int | None` arguments of the builtins
  other than those above (`divmod()`, `sum()` of a `list[int | None]`)
- a value that may be `None` where CPython would pass it on and that is not narrowed (above), a
  `list[T]` or `dict[K, T]` passed or assigned where a `list[T | None]` or `dict[K, T | None]` is
  expected (as mypy does: the container could then be given a `None` that its other references do
  not expect; mypy takes it for a `Sequence[T | None]` or `Mapping[K, T | None]`, a list and a dict
  here), and an argument that may be `None` of a builtin function other than `len()`, `int()`,
  `float()`, `ord()`, `dict()`, `sum()`, `round()`, `os.system()`, `os.path.exists()` and those
  that take `None` (and `round(x, n)` of a `float` `x` and an `n` that may be `None`, which would
  return an `int` or a `float` by whether `n` is `None`)
- a read that needs the type of a local that only `None` has been assigned so far, where no other
  value assigned to it can be typed yet and the context expects none (annotate it:
  `x: T | None = None`)
- an empty `[]` or `{}` assigned to a local first assigned `None`, a list display of only `None`
  items (`[None] * n`, `print([None])`) or a dict display of only `None` values that no annotation
  or other operand gives a type, and an empty list that `append(None)` fills first (annotate them)
- a module global first assigned `None` whose other values in module code cannot be typed where it
  is first assigned (`for w in ws: last = w`), or that only functions or other modules give another
  value (annotate it at module level: `last: str | None = None`)

### Dict keys and `bool` values

- dict key types that may be `None`, and tuple keys holding other items (a `float`, a `list`, an
  object, a NamedTuple)
- a `bool` where an `int` is stored (`x: int = True`: CPython keeps the `bool`, which prints as
  `True`), also as a dict key or a tuple key's item where the keys hold an `int` (`d[True] = v`,
  `setdefault()`, a display: CPython keeps a key it adds as the `bool`; a lookup, `pop()`, `del`
  and `d[True] op= v` take it, but the last only where `v` runs no code of the program and changes
  no dict, since CPython adds the key as the `bool` where `v` deletes it; `get()` and `in` also
  take a `bool | None`, which other lookups reject)

### Typing forms

- `typing.ClassVar`, `os.PathLike` other than in a union with `str`, a `TypeVar` named other than
  by a module-level function's parameters and return (in a method, a field, a variable's
  annotation, or as a value), a `TypeVar`'s constraints and a bound other than a string, a bare
  `Final` but in an assignment (in a class body, of a constant), an `@overload` stub that the `def`
  implementing it does not follow in its block past other `def`s only (in an imported module, one
  that no `def` of its name follows, also a method, is an error where it is called; also one after
  that `def`: CPython keeps the stub, whose calls raise `NotImplementedError`), and a stub's
  default other than a constant
- typing's names in a function's local variable annotations that are not imported (CPython never
  evaluates those)

### Exceptions and exception classes

- `raise` of anything but an exception
- an `except` clause that names something other than exception classes (a variable), and `except*`
- `except ... as x` in a function where `x` is a global (the end of the clause deletes it, as `del`
  would), and at a module's top level where `x` is a global of another type that a function reads
  (the function would not see the exception)
- `==` between exceptions where an exception class defines `__eq__` or `__ne__` (`is` works), but
  between objects of classes with a base in common
- an exception that may be `None` (`Exception | None`, `ValueError | None`; an object of an
  exception class may be)
- an object of an exception class where a builtin exception is expected (`list[Exception]`:
  annotate it with the class or a base of the program), objects of exception classes with no base
  in common in the program in one list, and a builtin exception where an object of an exception
  class is expected (`except Exception as e: log(e)` where `log` takes an `E`: catch it as
  `except E as e`)
- an exception class with two bases, one deriving from `SyntaxError` and its subclasses, from
  `UnicodeDecodeError`, `UnicodeEncodeError` or `UnicodeTranslateError`, or from an exception
  group, a decorated one, one defining again a method of its base other than `__init__`, `__str__`
  and `__repr__` (methods are not dispatched on the object's class), a class method that uses `cls`
  called through an object of a class that another class derives from (`e.k()`, where `e` may be an
  `S`: `cls` would be the object's static class), or through a class that inherits it where a
  default value of it is evaluated when its `def` runs or the class is in another module, `S.x = v`
  of a class attribute that `S` inherits (CPython would give `S` one of its own) and `C.x = v` of
  one that a class deriving from `C`, or a base of it, binds again in its class body, a field its
  base declares (but a class attribute bound again with its type), or one that would be its builtin
  base's own attribute (`args`, `code` of `SystemExit`, `errno`, `strerror`, `filename` and
  `filename2` of `OSError`, `msg` of `ImportError`), or one that the builtin base's `__init__` sets
  where it may run after the class's code assigns the field (`value` of `StopIteration`, `name` and
  `obj` of `AttributeError`, `name` of `NameError`, `name` and `path` of `ImportError`: assign it
  after `super().__init__(...)`, or give it a default in the class body, which CPython's objects
  keep apart from the base's attribute)
- reading those attributes where the class has no such field (`self.args`, `S(5).value`),
  `BaseException`'s methods other than `__str__` and `__repr__` (`e.add_note()`,
  `e.with_traceback()`), a field of a class deriving from a value's class read after `isinstance()`
  tested the value (`isinstance()` does not change the type of a value), a call `x.__init__(...)`
  on an object of a class that a class deriving from it defines `__init__` again for,
  `Base.method(self, ...)` naming a base other than the class's own, one whose `__init__` may leave
  a field of the base unassigned where the base's code reads it (call `super().__init__()` first),
  keyword arguments where no class of its line has an `__init__` (but those its builtin base's
  takes, such as `ImportError`'s `name` and `path`), more than three arguments for one deriving
  from `OSError` (or for `OSError` itself), and `super()` outside the methods of exception classes

### Builtins

- `range()`, `enumerate()`, `zip()` or `reversed()` nested inside `enumerate()`, `zip()` or
  `reversed()` in a `for` loop, and `zip(strict=...)`
- a keyword argument Pystachy does not take (`os.path.realpath(p, strict=True)`)
- an `encoding=` constant other than UTF-8 and Latin-1

### Source text

- f-strings that reuse their own quote inside a field (PEP 701), `\N{...}` escapes, non-ASCII
  identifiers and tabs in indentation
- a source file whose coding declaration names an encoding other than UTF-8, Latin-1 and ASCII
- source nested more than 5,000 levels deep (expressions, statements and `elif` branches; a `**`
  or `lambda` counts twice), and source whose nesting would overflow CPython's parser stack of
  6,000 levels of its grammar rules (a MemoryError in CPython), counted as measured on CPython
  3.13 (a bracket 24 to 33 levels, a block 7, a comparison's operand 3, ...) so that Pystachy
  stops at most a few dozen levels before CPython does
