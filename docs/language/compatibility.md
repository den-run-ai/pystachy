# CPython compatibility

This reference records semantic differences and compilation restrictions. Start with the
[language guide](../language.md) for an overview; use [typing](typing.md),
[modules](modules.md) and [execution rules](semantics.md) for the supported behavior.

- [Programs that compile but differ](#deviations-from-cpython)
- [Programs rejected during compilation](#rejected-rather-than-miscompiled)

Module-specific differences and port scope are recorded in [the library reference](../../lib/README.md).
The inventories here describe known restrictions; they are not a guarantee that every other
Python program compiles. Differential tests and documented deviations are explained in
[testing](../testing.md).

## Deviations from CPython

In these cases a program can compile but behave differently from CPython.

### Numbers

- `int` is 64-bit. Where CPython would produce a bigger int, including an intermediate
  result or `int()` of a long string, Pystachy raises `OverflowError` instead of
  wrapping. `int ** negative int` is a `ValueError` (the result type would be dynamic;
  `0 ** -1` raises CPython's `ZeroDivisionError`), and so is a negative float to a
  fractional power (CPython returns a complex).

- Floats are unboxed, so a NaN has no identity: `nan in [nan]` is `False`, and lists or
  tuples holding the same NaN object compare, and sort, as if they held different ones. The
  sum of an empty `list[float]` is `0.0` (`sum(xs, 1)`: `1.0`), and its `math.prod()` is
  `1.0`, where CPython returns the int start.

### Text and file positions

- `str` is a byte string holding UTF-8: `len`, indexing, slicing, iteration, `find`/`index`
  and `write()`'s result (but a Latin-1 file's) count bytes, case mapping and the `is*()`
  tests but `isspace()` know only ASCII, `replace("", s)`'s gaps are bytes, and `chr(i)` for
  `i < 256` is that byte (above, its UTF-8; `"%c" % i` is the character's UTF-8 for every `i`).
  ASCII behaves exactly like CPython; escapes such as `\xe9` and `€` produce UTF-8, and
  format widths, `center`/`ljust`/`rjust`/`zfill`, `repr()`'s escapes, `read(n)` and
  `ord()` count characters, as `strip()` (also of given characters), `split()`,
  `rsplit()`, `splitlines()` and `isspace()` read them (CPython's Unicode whitespace and
  line breaks). A UTF-8 file holds a str's bytes, read and written without checking them
  (invalid UTF-8 is read as it is, where CPython raises `UnicodeDecodeError`). A Latin-1
  file's bytes are its characters, as in CPython: the str read holds each as UTF-8, as a
  literal does (from U+0080 on, two bytes, which `len()` and indexing count), and a write
  gives each character as its byte (a byte `chr()` makes is one, but `chr()` bytes that
  together are UTF-8, `chr(195) + chr(169)`, are the one character they encode) and returns
  the number of characters, or raises CPython's `UnicodeEncodeError` for one above U+00FF
  before any of the text reaches the file. Any other `encoding=` computed at run time raises
  `NotImplementedError` when the file opens. A surrogate (`chr(0xD800)` to `chr(0xDFFF)`) is
  held in its three-byte form and printed or written to a UTF-8 file as it is, where
  CPython raises `UnicodeEncodeError` (`sys.stderr`, which an uncaught exception's line and
  `sys.exit()`'s message go to, writes it as `\udcff`, as CPython's does); its `repr()`,
  `ascii()` and `ord()` match CPython's. A format width or precision above 10**8, in a format
  spec or a `%` format, raises `ValueError: Too many decimal digits in format string`. CPython
  accepts it up to 2**63 - 1 (2**31 - 1 for a float's precision, above which it raises
  `precision too big`), and its `%` formats report `width too big` or `precision too big`.

- In `"+"` modes, a write after reads goes where CPython's text layer stopped reading ahead,
  which Pystachy models in 8 KiB chunks. After `read(n)` for an `n` above that, CPython has
  read ahead by about `n` characters instead; and when a `for` loop over the file stops
  early, CPython 3.13 keeps its read-ahead across a write, so the next `read()` returns the
  text from before the write.

### Containers and evaluation order

- `dict.keys()`, `.values()` and `.items()` return list snapshots, so `enumerate()`, `zip()`
  and `reversed()` of them do not notice a dict that changes size (a plain `for` over
  `d.items()` steps the dict itself and does), and neither do `in`, `min()` and `max()` over
  `d.values()` when an `__eq__` or `__lt__` of the values changes the dict, where CPython
  raises `RuntimeError`; they print as lists and compare equal to lists. A snapshot is taken
  where the call is evaluated, so a later argument that changes the dict does not change it
  (`sum(d.values(), d.pop(k))`, `e.update(d.items(), k=d.pop(k))`,
  `dict.fromkeys(d.keys(), d.pop(k))`), where CPython's view shows the change.

- A set of strs (or of tuples with str items) iterates and prints in an order of its own: a
  str's hash is the dict's, where CPython's changes from run to run (`PYTHONHASHSEED`), so no
  order of such a set is CPython's on every run (`sorted()` gives one). A display of constants
  equal to an earlier one of its module is made of its own items, where CPython's compiler
  reuses the earlier one's frozenset constant, whose table can differ where elements collide,
  and a module CPython loads from its `.pyc` rebuilds such constants once more. `min()` and
  `max()` of a set take its elements before they call a `key=` function, which so does not see
  the set change (CPython's raises `RuntimeError` where it changes the set's size), and
  `intersection()` and `intersection_update()` take all the items of a generator expression
  before they test them against the set, where CPython tests each as it is made, which differs
  only where the generator's expressions change the set.

- `min()`, `max()` and `math.fsum()` make all the items of a generator expression before they
  compare or add them (or call `key=` on them), so where CPython stops at an item (a `__lt__`
  that raises, or fsum's `OverflowError: intermediate overflow in fsum`), the expressions of the
  later items have run, and an exception that one of them raises comes first.

### Functions and object identity

- `is` between `Callable`s compares the function they hold and its env or bound object, as `==`
  does, so two reads of one bound method (`o.m`) made `Callable`s are the same object, where
  CPython makes a new method object at each read.

- A function declared or inferred to return a value that ends without a `return` raises
  `RuntimeError` there, where CPython returns `None`, also when it is declared to return
  `C | None` for a class `C` (a dataclass or `NamedTuple` too). A function declared to return
  `T | None` for an `int`, `float`, `bool`, `str`, `list`, `dict` or `tuple` T, and a template
  that returns objects or `T | None`, return `None` there, as CPython does.

- A left operand of `+ - * / // % @ & | ^ << >>` (or of their in-place forms) whose class
  defines the operator's method, but which is `None` when the code runs, raises CPython's
  `TypeError` for `None` (`unsupported operand type(s) for |: 'NoneType' and 'B'`), also where
  the right operand's class defines the reflected method, which CPython calls with `None`
  instead (`B.__ror__(b, None)`; reflected methods are not supported, below).

- An optional value that is `None`, passed to a builtin method's parameter that has a
  default (`s.split(sep)`, `s.strip(chars)`), means the default, as an explicit `None` does,
  also where CPython raises `TypeError` (the fill character of `ljust()`, `rjust()` and
  `center()`).

### Errors and control flow

- A type error that CPython raises only when the code runs (`<` between dicts, a constant
  index outside a tuple) is a compile-time error, so the output before it is not printed.

- An exception that nothing catches prints only the last line of CPython's traceback (without
  `NameError`'s "Did you mean" hints) and exits with status 1 after flushing stdout; CPython's
  compile-time `SyntaxWarning`s are not printed. Running out of memory (`MemoryError`), a
  Ctrl-C (`KeyboardInterrupt`) and running out of stack end the program at once: no
  `except` clause catches them, and no `finally` block runs (a `raise KeyboardInterrupt` is
  an exception like the others). Recursion is limited only by the native
  stack: it goes past CPython's limit of 1,000 calls (`sys.setrecursionlimit()` checks its
  argument as CPython does and records it for `sys.getrecursionlimit()`, but bounds nothing and
  is not compared with the current depth),
  and where CPython raises `RecursionError` the program dies with `SIGSEGV` (status 139, losing buffered output) or,
  for a tail call in an AOT build, loops forever. `==` between two cyclic dataclass objects
  recurses like that too.

- An exception keeps `str()` of its arguments and what `repr()` shows of them as it is made,
  once all the arguments of the call are evaluated (their `__str__` and `__repr__` run then),
  where CPython computes them from `args` each time: an argument changed afterwards (a list,
  also by the exception's `__init__`) is not seen, and an argument whose `__str__` or
  `__repr__` raises makes the call of the exception class (`raise KeyError(obj)`) raise that
  exception instead, so that an `except KeyError` does not run.

### Modules and libraries

- An import of a builtin module binds its names for the whole program, wherever it appears.
  An import of a Python module in a function binds its names in that function only, as in
  CPython, including a builtin module it re-exports: `from helper import os`.

- The `lib/` modules behave as their pure-Python code, which CPython replaces with C
  accelerators: errors can be worded differently, the functions accept keyword arguments the
  C versions reject, `bisect`'s `hi=-1` is not `len(a)`, assigning to a `stat` constant
  changes the `S_IS*` tests, and `heapify` of more than 2,500 items compares in another
  order. A program file named like a module CPython imports at startup (`stat.py`,
  `posixpath.py`) replaces it, where CPython keeps its own.

- A class of an imported module that Pystachy leaves uncompiled (see [module rules](modules.md)) is not created when
  the module is imported, so the errors CPython raises while creating it are not reported:
  `typing`'s checks of `NamedTuple`, `TypedDict`, `Protocol` and `Generic` classes, `__slots__`
  conflicts, `@dataclass`'s field order and mutable defaults, a base that is not a class or
  cannot be subscripted (see [uncompiled import-time code](modules.md#unsupported-code-in-imported-modules)), and an exception
  that a builtin operation in its body raises where Pystachy does not evaluate it (see [module rules](modules.md)), as
  `1 // n` of the body's own `n`. A template's code is compiled per argument
  types, so a type error in code a program never calls is not reported (syntax errors are), and its
  variables keep one type, so code that rebinds one to another type (`a /= b` on ints) is
  rejected when it is compiled.

- An optional import of a module that Pystachy does not find runs its handler, also where
  CPython would find the module (a standard library module Pystachy lacks, or a package
  installed for CPython), and so does one of a name that a builtin module of Pystachy lacks
  (`from math import gamma`); a handler that may end the program is rejected instead (see the restrictions below). A
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

### Memory and resource lifetime

- Memory is reclaimed by a conservative collector, not reference counting: garbage is
  freed in batches and there are no finalizers (`__del__` never runs). A file the program
  drops without closing is closed when a collection finds it unreachable (its buffers count
  toward the memory that starts one), or at exit, not at once as in CPython. A file used in
  one expression (`open(p).read()`, `print(..., file=open(p, "w"))`) is closed right after
  it, and opening a file that has a writer open runs a collection first; but the stack scan
  is conservative, so a writer that a function dropped a moment ago can still look reachable.
  Its data can then be missing when the file is read back, and appends through several
  dropped writers can land out of order.

## Rejected rather than miscompiled

CPython can execute these constructs, often raising a runtime error. Pystachy instead rejects
them at compile time with a `file:line: error:`. The lists are grouped by feature; the
[typing](typing.md), [module](modules.md) and [execution](semantics.md) references explain the
supported alternatives.

### Names and scopes

- a read of a name that nothing binds, and an attribute, operation or format spec that the static
  types rule out (`unicode`, `obj.missing`, `1 + "a"`, `f"{obj:>6}"` of an object without
  `__format__`), where CPython raises `NameError`, `AttributeError` or `TypeError` as it runs, also
  in a `try` whose clause catches it (a feature test such as `try: unicode / except NameError:`)
- a function, class, method or import name bound twice, or a name that is both a variable and a
  function, class or import, also in a function: a parameter or local that an import in it binds
  too (`pi = 3.0` ... `from math import pi`), but for a from-import of a Python module's variable,
  which assigns the local
- a class-body default that names an earlier class attribute (Pystachy has no class scope), also
  one named like a builtin or `__name__`, also in an imported module
- a local read textually before its first assignment (declare it first: `x: int`), where a name
  that a function deletes, defines with `def` or `class`, or binds with `:=`, a `match` capture
  or a `type` statement is its local too, also where the name is a class's that the read uses
  (`C.m()`, `C.x`, `C.x = v`, `isinstance(o, C)`, `raise C(...)`)
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
- an alias (`f = g`) that module-level code uses before its assignment, and an alias of a
  from-imported function or class that another module from-imports, in an import cycle, before
  the alias's assignment has run (CPython raises `ImportError`)
- `__all__` changed other than by `+=`, `append` and `extend`, for `import *`
- `from <builtin module> import *`
- `del` of another module's attribute
- an assignment of anything but the literal `False` to `m.TYPE_CHECKING`, or its `del`, where
  module m's `TYPE_CHECKING = False` makes its tests of it decided at compile time: from
  another module, or from m's own code after it imports itself
- in an imported module, uncompiled code that may run code of the program when its `def`
  or `class` statement runs (a call of a function or class; a callable of the program given to a
  builtin, such as `sorted(xs, key=C.m)`; any other decorator of a class or method; a metaclass; a base that defines
  `__init_subclass__` or `__class_getitem__`; a value that may hold objects of the program's
  classes used as a class attribute, set item, dict key, operand or argument; a read of a class
  attribute that may be such an object; an assignment to an attribute or item; a comprehension,
  or a class-body statement other than an assignment, `del`, `if`, `def`, `class` or a
  docstring), a name such code reads that is not bound by then or that an import or class binds
  only on some path, a decorator that is not a dotted name or a call of one (PEP 614), an
  evaluated annotation outside the [supported forms](typing.md#annotations), a class attribute whose class defines
  `__set_name__`, and `class C(object)` or a builtin decorator where the module may have rebound
  the name by then
- an imported module whose functions, lambdas, classes and tuple displays nest past CPython's
  marshal limit

### Templates and empty containers

- types whose serialized representation exceeds 65,536 bytes, a template signature exceeding
  1,048,576 bytes, or active template signatures totaling more than 1,048,576 bytes; these
  compiler resource limits are checked before constructing the oversized strings (including
  tuple repetition), alongside the existing limit of 100 nested template compilations.
  Type-changing recursion is supported when it reaches a finite set of specializations within
  these bounds. Large argument types in diagnostic call contexts are summarized.
- more than 4,096 template specializations in one compilation, across all functions and
  imported modules. Completed specializations still retain their generated code and count
  toward this bound; calls reusing an existing specialization do not. This bounds branching
  over many small type combinations, even when active signatures and nesting remain small.
  Exceeding it reports a source error before allocating the next specialization; annotate
  template parameters or reduce the distinct type combinations.
- more than 16,777,216 bytes of template signatures in one compilation. Each specialization of
  a template function keeps its argument types (its key and its parameters' types), so long
  types could otherwise hold hundreds of MiB under the 4,096 bound. Exceeding it reports a
  source error before allocating the next specialization, naming the template whose
  specializations keep the most.
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
- in a class template: a field given `None` (no specialization types it; another call's `T | None`
  needs unions), an annotation naming one where it cannot stand for its specialization (a field
  of another class, a dataclass's), an exception class with an unannotated `__init__` (a handler
  cannot know which specialization it caught), and objects of two specializations in one
  variable or container

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
- reflected operator methods (`__radd__` & co), which CPython calls when the left operand's class
  has no method for the operator and the right operand's class is another (`3 & o` calls
  `o.__rand__(3)`), and first when the right operand's class derives from the left one's and
  has the reflected method that one has not; and `**`, `**=` and `pow()` of objects whose class
  defines `__pow__`, `__ipow__` or `__rpow__`
- an `==` or `!=` between objects of different classes, which CPython would reflect to the right
  operand's `__eq__`, and between values of other types that cannot be equal (`1 == "1"`, or an
  `int | None` and a `str | None`, which CPython finds equal only when both are `None`)
- comparing or sorting objects in a container when the `__eq__` or ordering method the operation
  calls is annotated to take another class, which CPython calls anyway
- a constant tuple index out of range (CPython raises `IndexError` where it runs)
- `sum(iterable, start)` with a `bool` start: its result is the original bool when the iterable
  is empty, and an `int` or `float` otherwise, which cannot share one static type here. Use
  `sum(iterable, int(start))` for a numeric result, including on empty inputs.
- a tuple for `str.startswith()` or `endswith()` with an item that is neither a `str` nor a
  `str | None` (CPython raises `TypeError` at the first such item it reaches)
- two different functions where one value goes (a variable, a field, a list's items, a dict's
  values, the two arms of a conditional expression) that is not annotated `Callable`: each function
  is a type of its own, and so is each lambda and def inside a function
- `Callable[..., R]`, a call of a `Callable` with keyword arguments or with another number of
  arguments than its parameter types, and a function where a `Callable` is expected whose result is
  not the `Callable`'s return type (an `int` for a `float`, as for a function's own return)
- a lambda or a def inside a function that reads a variable of the functions around it which may
  not be assigned where it is defined (but a def's own name), which a `del` or the end of an
  `except ... as` clause unbinds, or which is a variable of the comprehension it is in; a decorated
  def inside a function that reads its own name (what its decorators give binds it only once they
  have run), and a class inside a function
- printing a function, also inside a container, and comparing containers of functions (CPython
  prints a function's address)

### Classes, dataclasses and NamedTuples

- a class method's `cls` used as a value or assigned, `@staticmethod` or `@classmethod` on a
  special method, a method of objects called through its class (`C.m(o)`), and decorators other
  than these, `@dataclass` and `@overload`
- a class that defines (by a `def` or a class attribute) or inherits `__new__`, `__getattr__`,
  `__getattribute__`, `__setattr__` or `__delattr__`, which CPython calls implicitly and Pystachy
  never does (in an imported module, an error where the program uses the class; its class
  statement still runs), and an exception class whose base defines `__init_subclass__`, which
  CPython calls when it creates the class (also in an imported module, whose code creates it when
  it is imported)
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
  `(1, 2) == t` works for a `tuple[int | None, int]`), and `int | None` arguments of builtins
  outside the [supported optional operations](typing.md#optional-values-and-narrowing)
  (`divmod()`, `sum()` of a `list[int | None]`)
- a value that may be `None` where CPython would pass it on and that is not narrowed, a
  `list[T]` or `dict[K, T]` passed or assigned where a `list[T | None]` or `dict[K, T | None]` is
  expected (as mypy does: the container could then be given a `None` that its other references do
  not expect; mypy takes it for a `Sequence[T | None]` or `Mapping[K, T | None]`, a list and a dict
  here), and an argument that may be `None` of a builtin function other than `len()`, `int()`,
  `float()`, `ord()`, `hex()`, `oct()`, `bin()`, `dict()`, `sum()`, `round()`, `os.system()`,
  `os.path.exists()` and those that take `None` (and `round(x, n)` of a `float` `x` and an `n`
  that may be `None`, which would return an `int` or a `float` by whether `n` is `None`)
- a read that needs the type of a local that only `None` has been assigned so far, where no other
  value assigned to it can be typed yet and the context expects none (annotate it:
  `x: T | None = None`)
- an empty `[]` or `{}` assigned to a local first assigned `None`, a list display of only `None`
  items (`[None] * n`, `print([None])`) or a dict display of only `None` values that no annotation
  or other operand gives a type, and an empty list that `append(None)` fills first (annotate them)
- a module global first assigned `None` whose other values in module code cannot be typed where it
  is first assigned (`for w in ws: last = w`), or that only functions or other modules give another
  value (annotate it at module level: `last: str | None = None`)

### Dict keys, set elements and `bool` values

- dict key types that may be `None`, and tuple keys holding other items (a `float`, a `list`, an
  object, a NamedTuple); set elements of these types too, and frozensets as set elements or keys
- a `bool` added to a set of ints (CPython keeps it as the `bool` it is, which prints as `True`)
- unpacking in a set display (`{*xs}`), a set operator with an operand that is not a set or
  frozenset (`s | [1]`: CPython's `TypeError`), or with sets of different element types
  (`{1} | {"a"}`), and an empty `set()` or `frozenset()` that nothing gives a type
- a `bool` where an `int` is stored (`x: int = True`: CPython keeps the `bool`, which prints as
  `True`), also as a dict key or a tuple key's item where the keys hold an `int` (`d[True] = v`,
  `setdefault()`, a display: CPython keeps a key it adds as the `bool`; a lookup, `pop()`, `del`
  and `d[True] op= v` take it, but the last only where `v` runs no code of the program and changes
  no dict, since CPython adds the key as the `bool` where `v` deletes it; `get()` and `in` also
  take a `bool | None`, which other lookups reject)

### Typing forms

- `typing.ClassVar`, `os.PathLike` other than in a union with `str`, a `TypeVar` named other than
  by a function's or method's parameters and return (in `__init__` or a special method that is
  no template, a field, a variable's annotation, or as a value), but a generic class's that its
  objects bind, a `TypeVarTuple` but unpacked (`*Ts`) in `tuple[...]`, `Callable[[...], R]` and
  `*args`, a generic class whose `Generic[...]` is not its one base, `class C[T]` (PEP 695), a type
  variable of a generic class that no argument of a call binds (`C[int]()`), `C[T]` in an
  annotation, a `TypeVar`'s constraints and a bound other than a string, a bare
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
- `==` between exceptions (or an exception and `None`) where an exception class defines `__eq__`
  or `__ne__` (`is` works), but between objects of classes with a base in common
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
  from `OSError` (or for `OSError` itself), and `super()` outside the methods of exception classes,
  in a static method without parameters, without arguments in a class method (where it binds the
  class), or with arguments other than the method's own class and `self` (`super(Base, self)`, or a
  local that hides the class's name), or calling a class method of the base that uses `cls`

### Builtins

- `range()`, `enumerate()`, `zip()` or `reversed()` nested inside `enumerate()`, `zip()` or
  `reversed()` in supported loops or consumers, and `zip(strict=...)`. Materialize the inner
  expression as a list first. `reversed(range(...))` is supported.
- a keyword argument Pystachy does not take (`os.path.realpath(p, strict=True)`)
- `dict.update()` of a dict of other key or value types, of an iterable other than a list of
  `(key, value)` tuples of the dict's types (a generator could see the pairs set so far), or with
  keyword arguments where the keys are not `str`, and `dict.fromkeys()` of a generator, or without
  a value where no annotation gives the values a type that can be `None`
- an `encoding=` constant other than UTF-8 and Latin-1
- `functools.lru_cache()` and `cache()` of a function whose parameters or return are not
  annotated, that returns `None`, that takes `*args` or `**kwargs`, or whose parameter is no dict key type (a `float`,
  an object), or of a builtin, a method or a lambda; a required keyword-only parameter or a
  call through the cache that explicitly supplies a keyword-only argument (an optional
  keyword-only parameter's default may be used); and `cache_parameters()`

### Source text

- f-strings that reuse their own quote inside a field (PEP 701), `\N{...}` escapes, non-ASCII
  identifiers and tabs in indentation
- a source file whose coding declaration names an encoding other than UTF-8, Latin-1 and ASCII
- source nested more than 5,000 levels deep (expressions, statements and `elif` branches; a `**`
  or `lambda` counts twice), and source whose nesting would overflow CPython's parser stack of
  6,000 levels of its grammar rules (a MemoryError in CPython), counted as measured on CPython
  3.13 (a bracket 24 to 33 levels, a block 7, a comparison's operand 3, ...) so that Pystachy
  stops at most a few dozen levels before CPython does
