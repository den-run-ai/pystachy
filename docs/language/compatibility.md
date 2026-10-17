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
  tuples holding the same NaN object compare, and sort, as if they held different ones.
  Scalar union boxes retain this rule; a shared box does not give its NaN payload identity. The
  sum of an empty `list[float]` is `0.0` (`sum(xs, 1)`: `1.0`), and its `math.prod()` is
  `1.0`, where CPython returns the int start.

### Text and file positions

- `str` is a byte string holding UTF-8: `len`, indexing, slicing, iteration, `find`/`index`
  and `write()`'s result (but a Latin-1 file's) count bytes (a slice's step selects bytes too:
  `s[::-1]` of non-ASCII text reverses its bytes, as `"".join(reversed(s))` does), case
  mapping and the `is*()` tests but `isspace()` know only ASCII, `replace("", s)`'s gaps are
  bytes, and `chr(i)` for `i < 256` is that byte (above, its UTF-8; `"%c" % i` is the
  character's UTF-8 for every `i`).
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
  A format spec's width or precision written in non-ASCII decimal digits (`f"{x:٣}"`) is an
  invalid spec (`ValueError`), where CPython reads the digits as a number.
- `str.encode()`, `bytes.decode()` and `bytes(s, encoding)` know the UTF-8, Latin-1 and ASCII
  codecs, by the names and aliases `codecs.lookup()` finds them by. Another encoding raises
  `LookupError: unknown encoding: NAME`, where CPython would use its codec, and so does the
  `namereplace` error handler (`unknown error handler name`), which needs the characters' names.

To find byte-oriented operations while porting, compile with
`PYSTACHY_UNICODE_AUDIT=1 ./pystachy run app.py` or
`PYSTACHY_UNICODE_AUDIT=1 ./pystachy build app.py -o app`. The generated code raises
`NotImplementedError: Unicode audit: ...` when a non-ASCII string reaches `len`,
indexing/iteration (including `list`, `tuple`, `zip`, `enumerate` and `reversed`), slicing,
search/count/bounded prefix methods, replacement, case mapping, ASCII character tests,
or `expandtabs`. Checks apply to imported Python library code too. A built executable
keeps its checks; setting the variable only when running an existing executable does
not add or remove checks. The shared runtime cache is independent of this setting.

This is a conservative porting aid, not Unicode semantics: even a byte-correct delimiter
search or copy may be flagged. Printing, equality, concatenation and character-aware
runtime operations such as whitespace splitting remain usable. `chr(128..255)`, file
write counts, invalid UTF-8 input and other unlisted boundaries are not audited.
Each check scans the string until the first non-ASCII byte; repeated ASCII indexing can
be quadratic in audit builds. Default builds retain their existing behavior and cost.
A cached ASCII flag and code-point operations remain follow-ups to #120.

- In `"+"` modes, a write after reads goes where CPython's text layer stopped reading ahead,
  which Pystachy models in 8 KiB chunks. After `read(n)` for an `n` above that, CPython has
  read ahead by about `n` characters instead; and when a `for` loop over the file stops
  early, CPython 3.13 keeps its read-ahead across a write, so the next `read()` returns the
  text from before the write.

### Containers and evaluation order

- `dict.keys()`, `.values()` and `.items()` return list snapshots, so `enumerate()`, `zip()`
  and `reversed()` of them do not notice a dict that changes size (a plain `for` over
  `d.items()` and `iter(d.items())` step the dict itself and do), and neither do `in`,
  `min()` and `max()` over `d.values()` when an `__eq__` or `__lt__` of the values changes the
  dict, where CPython raises `RuntimeError`; they print as lists and compare equal to lists. A
  snapshot is taken where the call is evaluated, so a later argument that changes the dict
  does not change it (`sum(d.values(), d.pop(k))`, `e.update(d.items(), k=d.pop(k))`,
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

- A set of objects hashed by identity (whose classes define neither `__eq__` nor `__hash__`)
  iterates in an order that their addresses decide, as CPython's does, so no two runs need
  share it (`sorted()` gives one). `dict.fromkeys(s)` of a set of objects whose class defines
  `__hash__` calls it again for each element, where CPython takes the hashes the set keeps, and
  a `functools.cache()` or `lru_cache()` function hashes such an argument more than once per
  call (CPython's, once); `d.update(o)`, and `dict(o)` and `o.copy()` of an `o` with many
  deleted keys (which merge `o` into a new dict), go on with what is left of `o` where a key's
  `__eq__` changes `o`, where CPython raises `RuntimeError: dict mutated during update`.
  `hash()` of a NaN is 0, where CPython's is its float object's identity hash.

- `min()` and `max()` stream the items of generator expressions and iterator objects of type
  `int`, `float`, `bool` or `str` when called without keyword arguments, and an iterator
  object's items with `key=`. Other element types and generator expressions with `key=` first
  materialize the items, as do `math.fsum()` and `math.prod()`. Where CPython stops at an item
  (a `__lt__` that raises, or fsum's `OverflowError: intermediate overflow in fsum`), those
  materialized paths have already evaluated later items, and an exception from one of them
  comes first.

### Functions and object identity

- Private class names are not mangled: `__field` and `__method` retain their literal names.
  A subclass can therefore collide with a base's private fields or replace its private
  methods. Use distinct names across the hierarchy until name mangling is supported.

- Runtime-length tuples use a different layout from fixed-shape tuples. Converting a
  fixed-shape tuple to `tuple[T, ...]`, or boxing its scalar elements for an optional-element
  annotation, creates a new tuple. Values compare equally, but identity across such a
  conversion is not preserved. Empty runtime-length tuples are not interned. `tuple(t)`
  preserves identity when `t` already has the requested runtime-length representation.

- `is` between `Callable`s compares the function they hold and its env or bound object, as `==`
  does, so two reads of one bound method (`o.m`) made `Callable`s are the same object, where
  CPython makes a new method object at each read.

- A function declared or inferred to return a value that ends without a `return` raises
  `RuntimeError` there, where CPython returns `None`. A function declared to return `T | None`
  (or `Optional[T]`) for a class T (a dataclass or `NamedTuple` too) or an `int`, `float`,
  `bool`, `str`, `list`, `dict` or `tuple` T, and a template that returns objects or `T | None`,
  return `None` there, as CPython does.

- A left operand of `+ - * / // % @ & | ^ << >>` (or of their in-place forms) whose class
  defines the operator's method, but which is `None` when the code runs, raises CPython's
  `TypeError` for `None` (`unsupported operand type(s) for |: 'NoneType' and 'B'`), also where
  the right operand's class defines the reflected method, which CPython calls with `None`
  instead (`B.__ror__(b, None)`; reflected methods are not supported, below).

- A comparison method that `@dataclass` writes, called directly (`p.__eq__(q)`, `p.__lt__(q)`)
  with `None` or an object of another class, compares the fields (`__eq__` returns `False` for
  `None`) or raises `TypeError` where CPython's returns `NotImplemented`. The operators
  (`p == q`, `p < q`) decline such an operand as CPython does.

- An optional value that is `None`, passed to a builtin method's parameter that has a
  default (`s.split(sep)`, `s.strip(chars)`), means the default, as an explicit `None` does,
  also where CPython raises `TypeError` (the fill character of `ljust()`, `rjust()` and
  `center()`).

- A key object (an instance of a class that defines `__call__`) that is `None` when `sorted()`,
  `list.sort()`, `min()` or `max()` runs is no key, as in CPython, but where the items are
  objects (whose comparison methods the keyed call never compiles), or have no order without a
  key here (a closed union, functions): it is called then, raising
  `TypeError: 'NoneType' object is not callable`, where CPython orders the items. A
  `Callable | None` key for such items is a compile-time error.

- The text of `getattr(o, name)` with a run-time name (see [reflection](semantics.md#reflection))
  shows the addresses CPython shows, but not CPython's: a method wrapper's or builtin method's
  object address is the object's, a builtin method of the type (`__new__`, `__init_subclass__`)
  and a static method (`<function C.m at 0x...>`) show the address of the class's reflection
  record, as no type or function object exists at run time.

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
  exception instead, so that an `except KeyError` does not run. The `KeyError` of a dict or set
  lookup that misses an object key runs the key's `__repr__` as it is raised, likewise, where
  CPython runs it only when the error is printed.

- An `__exit__` whose traceback parameter is not annotated `TracebackType | None` (from `types`)
  is given `None` for it where CPython passes the exception's traceback (`tb is None` is true);
  annotated so, it takes an object of `TracebackType` that has none of a traceback's attributes.
  (`tests/deviations/with_traceback_none.py`)

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
  assignments must obey the [local binding rules](typing.md#variables-and-empty-containers).
  For example, augmented assignment that changes type (`a /= b` on ints) is still
  rejected when it is compiled.

- An optional import of a module that Pystachy does not find runs its handler, also where
  CPython would find the module (a standard library module Pystachy lacks, or a package
  installed for CPython), and so does one of a name that a builtin module of Pystachy lacks
  (`from math import sumprod`); a handler that may end the program is rejected instead (see the restrictions below). A
  module whose code raises keeps the globals that code set before the raise, where CPython
  discards the half-run module; a later import runs the code again over them.

- `sys.warnoptions` is `[]`, CPython's for a program run without `-W` options, also where the
  environment sets `PYTHONWARNINGS` or `PYTHONDEVMODE`: CPython adds their options to it, and
  Pystachy does not read them.

- `sys.version_info` is a tuple of its items, CPython 3.13.16's: comparisons, indexing,
  slicing and unpacking work as on CPython's, and its attributes are read as
  `sys.version_info.major` and the like, but `str()` and `repr()` show `(3, 13, 16, 'final', 0)`.
  Reads share one immutable object (`sys.version_info is sys.version_info` is `True`).

- A module without a docstring that binds `__doc__` itself, where the first statement that
  names `__doc__` is a `def` or `class`, has no `__doc__` until its code binds it: a function's
  earlier read raises `NameError`, where CPython's reads `None`.

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

- A suspended generator that the program drops (a variable that goes, `del`, a generator kept
  only in a container, a temporary such as `next(g())`'s, one still suspended when the program
  ends) is never closed: its `finally` blocks and `with` blocks do not run, where CPython closes
  it as its last reference goes (at the latest as the interpreter shuts down). A generator
  that a `for` loop's iterable has just made is closed as CPython closes it, where the loop is
  left, and so is a generator that `yield from` delegates to when its delegating generator is
  closed so. (`tests/deviations/gen_finalization.py`) Where an exception leaves a consumer's
  generator expression (`any(f(x) for x in g())`), the generator it iterates is closed before
  the handler runs; CPython closes it once the handler has finished, as the exception's
  traceback holds the expression's frame until then. (`tests/deviations/gen_genexp_close_timing.py`)

- In a program without `try` or `with` statements, a `StopIteration` raised by a function that a
  generator calls ends the program as `StopIteration`, where PEP 479 makes it
  `RuntimeError: generator raised StopIteration` as it leaves the generator; nothing could catch
  either, and the exit status is the same. A `raise StopIteration` or a `next()` in the
  generator's own body is converted, and so is everything in a program with `try` or `with`.
  (`tests/deviations/gen_pep479_no_try.py`)

- The `StopIteration` that `next()`, `send()` or `throw()` raises as a generator returns a value
  has no value (`str(e)` is empty, `repr(e)` is `StopIteration()`), where CPython's shows it; a
  generator's static type does not hold its return type. `r = yield from g()` gets the value.
  (`tests/deviations/gen_stop_value.py`)

- A generator expression's first iterable is evaluated where it is written, but a `range()`,
  `enumerate()`, `zip()` or `reversed()` there checks its arguments (a zero step), and a dict's or
  set's iterator records its size, when the generator first runs, not where it is made.

## Rejected rather than miscompiled

CPython can execute these constructs, often raising a runtime error. Pystachy instead rejects
them at compile time with a `file:line: error:`. The lists are grouped by feature; the
[typing](typing.md), [module](modules.md) and [execution](semantics.md) references explain the
supported alternatives.

### Generators

- a `yield from` whose value is used other than assigned to a variable (`r = yield from g()`),
  the value of a `yield from` that delegates to a generator other than a call of a generator
  function (whose return type is not known), and a `return v` of a value other than `None` in a
  generator annotated `Iterator[T]` or `Iterable[T]`
- `send()` of a value other than `None` to a generator whose send type is `None` (its function is
  annotated `Iterator[T]`, `Generator[Y, None, R]` or not at all), a send type that cannot be
  `None` (`next()` sends `None`), a `yield from` that sends on to a generator with another send
  type, or to an iterator that is no generator, in a generator that takes a value from `send()`
- the value of `close()` (in CPython 3.13, what the generator returns as it closes), `throw()` with
  more than one argument (the deprecated `throw(type, value, traceback)`), a generator's `send`
  or `throw` method as a value
- a generator function's return annotation other than `Iterator[T]`, `Iterable[T]` or
  `Generator[Y, S, R]`, async generators, and printing or comparing a generator object
- an unannotated generator function that delegates to itself (`yield from f(...)`) before its
  first `yield`, whose yield type is not known there
- a generator expression made a value (not a direct argument of a consumer) that reads a
  variable of a comprehension around it, a variable of a function around its own, or a variable
  of its function that may be bound again (or not yet be bound) where it is written: CPython
  reads such a variable when the generator runs (late binding), and Pystachy passes its value
  where the expression is
- `reversed()` of a generator, `len()` of one, `dict()` of one (a dict comprehension over it
  works), and a generator where a list is expected

### Context managers

- a `with` item whose value is neither a file nor an object of a class of the program that
  defines `__enter__` and `__exit__` (a union of such classes, a class without `__exit__`: CPython's
  `TypeError` message), and `with suppress(...) as x` or `suppress()` with something other than
  exception classes named (`contextlib.suppress` is compiled as an except clause) or used outside
  a `with` statement's item
- an exception class as a value (`cm.__exit__(KeyError, None, None)`, `issubclass(t, cls)` of a
  variable `cls`), `type(e)` of an exception object that may be `None` (but for
  `type(e).__name__`, which is `NoneType` for `None`), attributes of an exception's class other
  than `__name__`, and a `nullcontext(None)` that is not `nullcontext()`
- `contextlib`'s `ExitStack`, `redirect_stdout`, `redirect_stderr`, `chdir`, `aclosing`,
  `asynccontextmanager` and `AsyncExitStack` (not ported: `lib/compatibility.md`)

### Names and scopes

- a read of a name that nothing binds, and an attribute, operation or format spec that the static
  types rule out (`unicode`, `obj.missing`, `1 + "a"`, `f"{obj:>6}"` of an object without
  `__format__`), where CPython raises `NameError`, `AttributeError` or `TypeError` as it runs, also
  in a `try` whose clause catches it, but for a module-level feature test such as
  `try: unicode / except NameError:`, which is [decided at compile time](modules.md#compile-time-branches)
- a function, class, method or import name bound twice, or a name that is both a variable and a
  function, class or import, also in a function: a parameter or local that an import in it binds
  too (`pi = 3.0` ... `from math import pi`), but for a from-import of a Python module's variable,
  which assigns the local; for a [class rebound to its instance](modules.md#module-scope)
  (`class C: ...` directly followed by `C = C()`, of a class without bases but `object`,
  decorators, `__init__` or `__new__`); and for a module-level `def` or `class` that rebinds a function
  or class an earlier from-import or `import *` of a Python module bound, where nothing may read the import's
  binding in between ([module scope](modules.md#module-scope)). Not caught: reads during an import
  cycle through another module's code or a module alias (including a self-import). These reads,
  as `m.name` or through a function of the module, raise `AttributeError` or `NameError` where
  CPython reads the imported value (`tests/deviations/star_rebound_self.py`)
- a class-body default that names an earlier class attribute (Pystachy has no class scope), also
  one named like a builtin or `__name__`, also in an imported module, and `__doc__` in a class
  body (the class's docstring)
- a local read textually before its first assignment (declare it first: `x: int`), where a name
  that a function deletes, defines with `def` or `class`, or binds with `:=`, a `match` capture
  or a `type` statement is its local too, also where the name is a class's that the read uses
  (`C.m()`, `C.x`, `C.x = v`, `isinstance(o, C)`, `raise C(...)`)
- a read of a function's local that only code dropped at compile time binds
- in a comprehension, an iterable, condition or `for` target (`d[k]`, `o.a[k]`) that reads a
  variable which only its own or a later `for` clause binds (`[a for x in xs for a in b for b in
  ys]`: CPython raises `UnboundLocalError` once a clause runs it)
- in a comprehension, a later `for` clause that binds an earlier clause's variable to a value of
  another type, where a clause between them reads it after a loop between them (`[y for b in
  [[1, 2]] for y in b if len(b) > 1 for b in [3]]`)
- an assignment expression (`:=`) in a class body, including a lambda default evaluated there,
  which CPython makes bind a class attribute
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
- `del` of another module's attribute, an assignment of another module's `__doc__`, and `del`
  of a module's own `__doc__`
- an assignment of anything but the literal `False` to `m.TYPE_CHECKING`, or its `del`, where
  module m's `TYPE_CHECKING = False` makes its tests of it decided at compile time: from
  another module, or from m's own code after it imports itself
- in an imported module, uncompiled code that may run code of the program when its `def`
  or `class` statement runs (a call of a function or class; a callable of the program given to a
  builtin, such as `sorted(xs, key=C.m)`; any other decorator of a class or method; a metaclass but `abc.ABCMeta`; a base that defines
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
- an `__iter__` that is not a generator and returns something other than an iterator object
  (a list it returns as it is is rejected by CPython too: `iter() returned non-iterator of type
  'list'`); in an `__iter__` annotated `-> Iterator[T]` that returns `iter(x)`, an `x` other than
  a list, a tuple, a `str` or an object with such an `__iter__` (a dict or its `keys()`,
  `values()` or `items()`, whose iterator raises if the dict changes size, or an object whose
  `__iter__` returns an iterator object: leave out the annotation), and a call of that
  `__iter__` (`o.__iter__()`)
- a `__reversed__` that is not a generator and returns anything but `iter(xs)` or
  `reversed(xs)` of a list, a tuple, a `str` or an object with an `__iter__` annotated as above
  (also an iterator object, which CPython iterates over)
- `iter(callable, sentinel)`; `iter()` of `enumerate()`, `zip()`, `map()`, `filter()` or
  `reversed()`; `next(it, default)` where the default's type and the
  items' join to no type; and an iterator class without `__iter__` where CPython 3.13 calls
  `iter()` of the iterator again: in a comprehension and in `str.join()`
- a class in an inheritance hierarchy whose `__init__` calls `iter()` or takes an
  `Iterator[T]` or `Iterable[T]` parameter (a class template, see
  [iterators](semantics.md#iterators))
- iterating over an object, or `x in o`, by its `__getitem__` alone (CPython's old sequence
  protocol), and `reversed()` of an object without `__reversed__` (by its `__len__` and
  `__getitem__`)
- reflected operator methods (`__radd__` & co), which CPython calls when the left operand's class
  has no method for the operator and the right operand's class is another (`3 & o` calls
  `o.__rand__(3)`), and first when the right operand's class derives from the left one's and
  has the reflected method that one has not
- object power with an object or optional numeric exponent, reflected `__rpow__`, and
  three-argument `pow(o, n, modulus)`. With a builtin `int`, `float` or `bool` exponent,
  `o ** n` and `pow(o, n)` call `__pow__`, and `o **= n` calls `__ipow__` when present,
  otherwise `__pow__`. A base-typed receiver whose subclass introduces `__ipow__` that the
  base lacks must be narrowed to the concrete receiver type before `**=`. Returning
  `NotImplemented` remains unsupported
- an `==` or `!=` between objects of different classes, which CPython would reflect to the right
  operand's `__eq__`, and between values of other types that cannot be equal (`1 == "1"`, or an
  `int | None` and a `str | None`, which CPython finds equal only when both are `None`)
- comparing or sorting objects in a container when the `__eq__` or ordering method the operation
  calls is annotated to take another class than the objects' class or one of its bases, which
  CPython calls anyway; this includes the method of a subclass whose objects the container may
  hold, for objects of ordinary and exception classes (`Base() in xs`, `xs.count(x)`,
  `xs.index(x)`, `xs == ys`, `sorted(xs)` or `<` of tuples holding them, where `Sub(Base)` defines
  `__eq__(self, other: "Sub")` or `__lt__(self, other: "Sub")`), and comparing dataclass or
  NamedTuple objects there whose fields hold such objects (`[NT(Sub(1))] == [NT(Base(1))]`);
  printing such a container works, also one of those dataclass or NamedTuple objects
- `x == y`, `!=` or an ordering of values typed by a class (ordinary or exception) when the
  method CPython calls for a subclass whose objects they may be is annotated to take only that
  subclass (`x == y` of `E`-typed values where `F(E)` defines `__eq__(self, other: "F")`; CPython
  calls it with an `E`)
- a constant fixed-shape tuple index out of range (CPython raises `IndexError` where it runs; runtime-length tuples check indices at runtime)
- slicing a fixed-shape tuple or NamedTuple by bounds or a step that are not integer literals,
  unless its items have one type a `tuple[T, ...]` can hold (the result is then one); assigning
  to or deleting a slice of anything but a list (CPython raises `TypeError` for a `str` or a
  tuple, and a dict takes the slice object as a key); and assigning to a list slice a value that
  is not iterable, or whose items are not the list's item type (as for `list.extend()`; a
  tuple's items must share one type)
- unpacking a value that is not iterable (`a, *b = 5`) or a tuple whose length does not fit the
  targets (CPython raises `TypeError` or `ValueError` where it runs), and a starred target over
  tuple items of types no one type holds, unless the target is annotated (`rest: list[int | str]`)
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

- multiple inheritance; ordinary inheritance involving a class template, `Generic`, NamedTuple
  or builtin type, or a dataclass and a class that is not one; a decorated subclass other than
  a dataclass deriving from a dataclass; overriding a method with another kind of method
  (instance, static or class method); calls whose possible instance-method overrides cannot
  accept the arguments or return a common supported type, and calls through a base-typed
  object of a static or class method that a subclass overrides. See
  [single inheritance](typing.md#single-inheritance).
- assigning an inherited class attribute through a subclass that does not declare its own
  default; changing an inherited field's type; reading derived-only fields through a base
  annotation without [supported narrowing](typing.md#single-inheritance) of a stable local or
  parameter
- an inherited class method using `cls` called through a base-typed object, or inherited across
  modules or with nonconstant defaults; `super()` outside a supported instance-method context,
  or explicit `super(C, self)` with an unrelated class or a different receiver expression
- a class method's `cls` used as a value or assigned, `@staticmethod` or `@classmethod` on a
  special method, a method of objects called through its class (`C.m(o)`) outside an ordinary
  inheritance hierarchy, and decorators other than these, `@property` (and its `.setter` and
  `.deleter`), `@dataclass` and `@overload`
- a class that defines (by a `def` or a class attribute) or inherits `__new__`, `__getattr__`,
  `__getattribute__`, `__setattr__` or `__delattr__`, which CPython calls implicitly and Pystachy
  never does (in an imported module, an error where the program uses the class; its class
  statement still runs), and a class whose base defines `__init_subclass__`, which
  CPython calls when it creates the class (also in an imported module, whose code creates it when
  it is imported)
- `@dataclass(slots=True)` and `weakref_slot=`, `@dataclass` and `field()` options that are not
  `True` or `False` literals, `field(metadata=...)`, a `default_factory` that is not a function,
  a class or a lambda without parameters, `dataclasses.fields()` other than as a loop's iterable,
  `asdict()` and `astuple()` with a factory or of fields that join in no type (see
  [reflection](#reflection)), `InitVar`, `object.__setattr__()` in a frozen dataclass, `FrozenInstanceError` other than in an
  `except` clause, `hash()` of a dataclass object, a base dataclass's field declared again with
  another type, and `repr=False` in a dataclass whose base has the `__repr__` `@dataclass` writes
- a property's `@x.getter`, a second setter or deleter, a setter or deleter of another name than
  its property, `property()` called as a function, assigning `super().x`, and `del` of an
  attribute that is not a property
- a class attribute without an annotation in a dataclass or NamedTuple, and an assignment through
  its class to a dataclass's or NamedTuple's class attribute, or to one its class body does not
  bind
- reading through an object (`o.encode(s)`, `self.encode`) a class attribute that the class
  body binds to a Python function (`encode = enc`), which CPython binds to the object as a
  method; reading it through the class is supported, as is reading a builtin function's class
  attribute through an object
- a NamedTuple without fields, assigned a field outside its `__init__`, whose class defines
  `__getitem__` or `__iter__`, compared or added through its own operator method with another type,
  given to `hasattr()` of a name it does not define, `_make()` of a tuple whose length is not the
  number of fields (CPython's `TypeError`), `_asdict()` of fields of different types,
  `_field_defaults` of an annotated NamedTuple, `hash()` of one whose class defines `__eq__` or
  `__hash__`, the functional `NamedTuple("P", [...])`, slicing an object (whose `__getitem__`,
  `__setitem__` or `__delitem__` would take a slice object), a tuple `*` a number that is not a
  constant, and CPython's class-creation errors of a NamedTuple (a field after a default, an
  underscored field, an overwritten `__init__`) and of a dataclass (a field without a default
  after one with it, also a base's, a mutable default, `order=True` without `eq`, a generated
  method the class defines, a frozen dataclass deriving from one that is not, or the reverse)
- `collections.namedtuple()` other than as a module's top-level `NAME = namedtuple(...)` with
  literal arguments (in a function or a compound statement, a non-literal argument, `*` or `**`
  arguments, `rename=` other than `True` or `False`, a name that something else binds too, a
  typename or field name with non-ASCII characters); a namedtuple without fields; a namedtuple
  class as a base, also `class C(namedtuple(...))`; reading its `__doc__`, or a field through its
  class (`NAME.field`, a descriptor in CPython: assigning `NAME.field.__doc__` a string literal is
  accepted, another value is not); a field given `None`, and objects of two specializations in one
  variable or container, as in other [class templates](#templates-and-empty-containers); and
  `_field_defaults` whose defaults are all `None`

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

- dict key types that may be `None` (but objects, which may be), tuple keys holding other items
  (a `float`, a `list`, a NamedTuple), and NamedTuple and exception objects as keys; set
  elements of these types too, frozensets as set elements or keys, and `hash()` of these types
  but a NamedTuple (whose hash is its fields' tuple's);
  objects whose class has a `__hash__` or `__eq__` that is no method (`__hash__ = None`) as keys
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
  `*args`, a generic class whose `Generic[...]` is not its one base, a PEP 695 generic class
  with a base or with a `ParamSpec` (`**P`) or more than one `TypeVarTuple` among its type
  parameters, a type variable of a generic class that neither arguments nor context bind,
  `C[X]` for a class with a `TypeVarTuple` or unannotated or variadic `__init__` parameter, a `TypeVar`'s constraints and a bound other than a string, a bare
  `Final` but in an assignment (in a class body, of a constant), an `@overload` stub that the `def`
  implementing it does not follow in its block past other `def`s only (in an imported module, one
  that no `def` of its name follows, also a method, is an error where it is called; also one after
  that `def`: CPython keeps the stub, whose calls raise `NotImplementedError`), and a stub's
  default other than a constant
- typing's names in a function's local variable annotations that are not imported (CPython never
  evaluates those)
- a type alias used other than by annotations (`print(Row)`, `Row()`, `del Row`, `Row.__value__`,
  `isinstance(x, Num)`), but an alias of `int`, `float`, `str` or `bool`; a recursive type alias;
  a `type` statement other than at a module's top level, or for a name that another statement
  binds too; a generic `type` statement's alias named without its type arguments, and type
  arguments for a type alias with a `TypeVarTuple` or `ParamSpec` parameter; in an assigned
  alias's value, a subscript of a typing name other than its generic aliases, `Optional`,
  `Union`, `Callable`, `Tuple`, `Literal`, `Annotated` and the single-type forms
  (`Generic[T]`, `Concatenate[...]`), also where no annotation names the alias; a `type`
  statement's string value that is not an expression, also where nothing evaluates it; an
  annotation whose type aliases expand to more than 65,536 nodes

### Exceptions and exception classes

- `raise` of anything but an exception
- an `except` clause that names something other than exception classes (a variable), and `except*`
- `except ... as x` in a function where `x` is a global (the end of the clause deletes it, as `del`
  would), and at a module's top level where `x` is a global of another type that a function reads
  (the function would not see the exception)
- `==` between exceptions of builtin classes (`except Exception as e`), or such an exception and
  `None`, where an exception class defines `__eq__` or `__ne__` (`is` works), and between objects
  of exception classes with no base in common where neither class nor any of their subclasses
  defines a comparison method but another exception class defines `__eq__` or `__ne__`. Objects
  of exception classes otherwise compare as CPython compares them, by the methods of the
  objects' own classes (a right operand's reflected method first where its class derives from
  the left one's), also between classes with no base in common, and else by identity; a method
  annotated to take only its own class is rejected where CPython would call it with another
  class's object (see [Objects and operators](#objects-and-operators))
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
- exception attributes other than `__cause__` (`e.args`, `e.__context__`, `e.__traceback__`),
  `__cause__` of an object of an exception class (catch it as a builtin class to read it), and
  reading those attributes where the class has no such field (`self.args`, `S(5).value`),
  `BaseException`'s methods other than `__str__` and `__repr__` (`e.add_note()`,
  `e.with_traceback()`), a field of a class deriving from a value's class read after `isinstance()`
  tested the value (`isinstance()` does not change the type of a value), a call `x.__init__(...)`
  on an object of a class that a class deriving from it defines `__init__` again for,
  `Base.method(self, ...)` naming a base other than the class's own, one whose `__init__` may leave
  a field of the base unassigned where the base's code reads it (a method it calls on `self`, or a
  method of the base it calls through `super()` that reads the field or uses `self` otherwise than
  as `self.field`, before the field is assigned), or where a def or lambda that it defines before
  the field is assigned reads it (call `super().__init__()` first),
  keyword arguments where no class of its line has an `__init__` (but those its builtin base's
  takes, such as `ImportError`'s `name` and `path`), more than three arguments for one deriving
  from `OSError` (or for `OSError` itself); for exception classes, `super()` outside their methods,
  in a static method without parameters, without arguments in a class method (where it binds the
  class), or with arguments other than the method's own class and `self` (`super(Base, self)`, or a
  local that hides the class's name), or calling a class method of the base that uses `cls`

### Builtins

- `enumerate()`, `zip()` or `reversed()` nested inside `enumerate()`, `zip()` or `reversed()`
  in supported loops or consumers, and `zip(strict=...)`. Materialize the inner expression as a
  list first. `reversed(range(...))` is supported, and a `range()` in `enumerate()` or `zip()` is
  a [range object](semantics.md#range-objects).
- of a [range object](semantics.md#range-objects): ordering comparisons and assigning its
  attributes (CPython's `TypeError` and `AttributeError`); `in` of other than an int or a bool,
  and indexing, `index()` and `count()` of other than an int (CPython takes a bool as an int, and
  compares other values with the items); `==` with a value that may be `None` but is not a range;
  `dir()` and `vars()`
- a keyword argument Pystachy does not take (`os.path.realpath(p, strict=True)`)
- a `key=` that may be `None` (`Callable | None`) of items that have no order without a key (a
  closed union, functions)
- `dict.update()` of a dict of other key or value types, of an iterable other than a list of
  `(key, value)` tuples of the dict's types (a generator could see the pairs set so far), or with
  keyword arguments where the keys are not `str`, and `dict.fromkeys()` of a generator, or without
  a value where no annotation gives the values a type that can be `None`
- an `encoding=` constant other than UTF-8 and Latin-1
- `bytearray`, `memoryview`, binary files (`open(..., "rb")`), `expandtabs()`, `title()` and
  `istitle()`, `%` formatting of bytes (`b"%d" % 1`), a search of a bytes for an int
  (`b.find(97)`), keyword arguments to its methods (as to a str's) but `hex()`'s and
  `translate()`'s, and comparing a bytes with a str (`b"a" == "a"`, which CPython makes `False`)
- `str.format()` and `str.format_map()` of a format string other than a literal or a module
  global bound once to one (`fmt.format(x)` of a parameter, also of an f-string; a global whose
  name anything else in the program binds, even a function's local), either method or
  `str.format` as a value other than `map()`'s function `"...".format`, `*` of a `str` or of a
  list followed by other positional arguments, `**` of more than one dict whose keys only run
  time knows, and a field's item key that the static types rule out (`"{0[1]}"` of a
  `dict[str, int]`, where CPython raises `KeyError`)
- `functools.lru_cache()` and `cache()` of a function whose parameters or return are not
  annotated, that returns `None`, that takes `*args` or `**kwargs`, or whose parameter is no dict key type (a `float`,
  a NamedTuple), or of a builtin, a method or a lambda; a required keyword-only parameter or a
  call through the cache that explicitly supplies a keyword-only argument (an optional
  keyword-only parameter's default may be used); and `cache_parameters()`

<a id="reflection"></a>

### Reflection

The [reflection rules](semantics.md#reflection) list what is supported; these are rejected:

- `type(x)` as a value (a class object, #7), `type(e)` of an exception other than
  `type(e).__name__`, and `type(x).__name__` of a function, file or callable
- `getattr()` of a name only the run time knows whose value is used (kept, passed on, called,
  compared, a sort key: `attrgetter(input())`), its text with a format spec, and its text for a
  dataclass, a generic class, a class with annotated class attributes or a builtin value (#487,
  #489)
- reflection over classes with private attributes (`__x`): CPython mangles their names (to
  `_C__x`), which Pystachy does not (see [functions and object identity](#functions-and-object-identity))
- `setattr()` of a run-time name on an object whose class does not close its names with
  `__slots__` (it may add an attribute: #489), with a value that does not fit every slot field,
  or that may name a slot no code assigns; `delattr()` and `del o.x` of a field (#489)
- `vars(x)` and `x.__dict__` other than printed, iterated, formatted or copied; of a class whose
  `__init__` assigns two new attributes in one branch or loop, through a property's setter, or
  outside `__init__`, whose `__post_init__` adds an attribute, or one of whose fields `__init__`
  may leave unassigned and other code may assign (unless it is the last); and of a class
  attribute the program may also assign through an object
- `getattr`, `setattr`, `hasattr` and `dir()` of exception objects, and `dir()` of files and
  functions
- a loop over constant names whose body defines a function, lambda or class, or assigns the
  loop variable (the name is then a run-time name), and loops that would compile their body more
  than 256 times
- `dataclasses.replace(obj, **changes)` of a `dict[str, T]` (which field a key names is known only
  at run time, #489)

### Source text

- `\N{...}` escapes (in f-strings too), non-ASCII identifiers and tabs in indentation
- a source file whose coding declaration names an encoding other than UTF-8, Latin-1 and ASCII
- source nested more than 5,000 levels deep (expressions, statements and `elif` branches; a `**`
  or `lambda` counts twice), and source whose nesting would overflow CPython's parser stack of
  6,000 levels of its grammar rules (a MemoryError in CPython), counted as measured on CPython
  3.13 (a bracket 24 to 33 levels, an f-string's replacement field 33, a block 7, a comparison's
  operand 3, ...) so that Pystachy stops at most a few dozen levels before CPython does
