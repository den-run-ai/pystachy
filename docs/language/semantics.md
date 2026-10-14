# Execution and expressions

This reference expands the [language guide](../language.md). Types, function specialization,
closures and class fields are described in [typing](typing.md); imports and builtin APIs are in
[modules](modules.md).

## Statements

| Category | Supported statements |
|---|---|
| Assignment | Simple, chained, annotated and augmented assignment; fixed-shape tuple/list unpacking and swaps |
| Control flow | `if` / `elif` / `else`, `while`, `for`, loop `else`, `break`, `continue`, `return` |
| Scope and definitions | `global`, `nonlocal`, `def`, nested function definitions, lambdas, supported class definitions |
| Runtime checks | `assert`, `raise`, `try` / `except` / `else` / `finally` |
| Resources | `with open(...) as f:`, including several file contexts, with or without parentheses |
| Deletion | `del` of a local, list item, dict key or supported object's item |
| Other | Imports, docstrings, `pass` and `...` |

`+=` on a list extends it in place. Object in-place operators use `__iadd__` and the
corresponding methods when supported. Deleting a variable makes later reads raise
`NameError` or `UnboundLocalError`; deleting a global from a function is unsupported.

Loops can consume ranges, lists, strings, dictionaries, sets, files, homogeneous tuples and
NamedTuples, supported objects, and dictionary `items()`, `keys()` and `values()`.
`enumerate(..., start=...)`, `zip()` and `reversed()` work in supported contexts.
A dictionary or set whose size changes while its iterator is active raises `RuntimeError`.
`zip()` creates its operands' iterators in order, before iteration starts.

Restrictions on nested iterator-like expressions, snapshots and mutation are listed in
[compatibility](compatibility.md).

## Literals and formatting

Numeric literals support decimal, hexadecimal, octal, binary and underscore separators.
Strings support raw and triple-quoted literals, implicit concatenation and escapes other
than `\N{...}`.

F-strings support `!r`, `!s`, `!a`, debug `=`, nested format specifications and the
format-spec mini-language. `%` formatting requires a literal format string. It supports
`s r a d i u x X o e E f F g G c`, flags, widths and precisions, but not named substitutions,
`*` widths or precisions, or integer precisions. A variable format string such as
`fmt % value` is rejected.

## Operators and containers

Supported operations include arithmetic, bitwise operations, chained comparisons,
`in` / `not in`, boolean operations returning operands, conditional expressions, negative
indices, and string/list slices without a step. Integer `//` and `%` floor as in Python;
true division is correctly rounded, and int/float comparisons are exact within the
supported types.

Container expressions include list, dict, set and tuple displays; list and set
comprehensions; and tuple concatenation or repetition by a constant. Set and frozenset
operations support union, intersection, difference, symmetric difference, subset ordering
and in-place forms.

`is` and `is not` are supported for identity-bearing values, not numbers.
Booleans use their two fixed values, so `flag is True` behaves as equality.
Comparisons with `None` are supported where the static types permit them.

## Iterator-like expressions

Generator expressions, `range()`, `reversed()`, `enumerate()`, `zip()`, `map()` and
`filter()` can be direct arguments of `list`, `sorted`, `sum`, `min`, `max`, `any`, `all`,
`math.fsum`, `math.prod`, `str.join` and `list.extend`.

These expressions are compiled for their consumer rather than creating a general generator.
`map()` and `filter()` evaluate their function before iteration.
`any()` and `all()` stop at the deciding item, including over files.
`list.extend()` appends each generated item as it is produced.
`x in range(...)` is also supported.

Some consumers materialize input before processing it; see the
[evaluation-order differences](compatibility.md#containers-and-evaluation-order).

## Object protocols

Object operations use the following methods. In supported ordinary hierarchies, instance-method
overrides dispatch on the concrete receiver; the static type still controls which operations
and fields are available. See [single inheritance](typing.md#single-inheritance).

| Operation | Methods |
|---|---|
| Binary operators `+ - * / // % @ & \| ^ << >>` | `__add__` and the corresponding methods |
| In-place operators | `__iadd__` and counterparts, otherwise the binary method |
| Unary `-`, `+`, `~` | `__neg__`, `__pos__`, `__invert__` |
| Equality and ordering | `__eq__`, `__ne__` and rich comparisons |
| Truth and length | `__bool__`, `__len__` |
| Representation | `__str__`, `__repr__`, `__format__` |
| Call, indexing, assignment, deletion | `__call__`, `__getitem__`, `__setitem__`, `__delitem__` |
| Membership and iteration | `__contains__`, or supported `__iter__` |

Rich comparisons use reflection, such as trying `b.__gt__(a)` for `a < b`.
Reflected arithmetic methods such as `__radd__` and object `__pow__` are unsupported.
Objects in containers compare, sort and print through their methods.
Lists and tuples test items with equality before ordering them, then compare length if all
common items are equal. Sorting and `min()` use `<`; `max()` uses `>`.

Object calls accept the keyword and default arguments of `__call__`.
For `o[k] += value`, both indexing and assignment methods are used.
Membership uses `__contains__`, taking its result's truth; without it, membership searches
the supported iterator.

A supported `__iter__` is annotated `-> Iterator[T]` or `-> Iterable[T]` and returns
`iter(xs)` for a list, tuple, string or another object with the same supported protocol.
It works in loops, comprehensions, unpacking and the consumers above, plus `math.dist()`.
`list()`, `sorted()` and `list.extend()` call its `__len__`, if present, as a length hint.
Generator implementations, general `__next__` iterator classes, and direct calls of
`o.__iter__()` are unsupported.

A missing protocol method produces a compilation error using CPython's message.
An object that is `None` when the operation executes raises the corresponding runtime error.

## Exceptions

### Builtin exceptions

`try` supports `except`, `else` and `finally` in CPython's combinations, except
`except*`. Handlers can name a builtin or user exception class, a tuple of classes, or use
a bare `except:`, with or without `as name`.

Handlers follow CPython 3.13's hierarchy: `LookupError` catches `KeyError`, whereas
`Exception` does not catch `SystemExit`. `IOError` is an alias for `OSError`.
Handlers catch runtime failures, explicitly raised exceptions, failures from another
function or module, and failures in callbacks such as a sort comparison.

An exception class is looked up when the handler is reached or before the exception is
constructed. If its class statement has not executed, lookup raises `NameError`.
The `as` binding is cleared on every exit from its handler and can have another type before
or after that handler.

Calling a builtin exception class produces an exception value. Values can be stored,
printed, converted to `str` / `repr`, formatted, raised, compared by identity, and tested
with `isinstance()` or `type(e).__name__`. An annotation such as `Exception` names the
builtin exception value type; it does not accept arbitrary user exception objects.

`OSError(errno, strerror[, filename])` selects the subclass associated with the errno.
`ImportError`, `AttributeError` and `NameError` accept their supported keyword arguments.
Exception attributes such as `args` are unsupported.

### Control flow

`finally` runs on normal completion, exceptions, `return`, `break` and `continue`.
A return value is computed before `finally`; a return, break or continue in `finally`
discards the exception in flight.

Bare `raise` re-raises the currently handled exception, with the prior handler restored
when an inner handler exits. `raise ... from ...` evaluates and validates its cause, but
the abbreviated error output does not show exception chaining. A cause that is not an
exception raises `TypeError`.

An exception leaving a file context closes the file. If closing fails, its `OSError`
replaces the exception being handled. A failed Python-module import leaves its imported
names unbound and is retried on a later import; see [module initialization](modules.md).

Actual memory exhaustion, native stack exhaustion and Ctrl-C bypass ordinary handlers and
cleanup. Uncaught exceptions have abbreviated output. These are documented in
[errors and control flow](compatibility.md#errors-and-control-flow).

### User exception classes

A user exception class has one base: a supported builtin exception class or another
exception class in the program. It supports fields, constructors, class-body defaults,
methods, docstrings and custom `__str__` / `__repr__`.

A subclass inherits fields and methods and can override `__init__`, `__str__` and
`__repr__`. String conversion and uncaught error output use the object's actual class.
`super().__init__`, `super().__str__`, `super().__repr__`, explicit base calls and
`super(E, self)` are supported within the documented restrictions.

Positional constructor arguments are retained for default string and repr output.
`super().__init__(...)` resets them. Without a constructor in the user class or a user
base, positional arguments are forwarded to the builtin base. An `OSError` or `SystemExit`
subclass with its own constructor keeps no builtin args (and `SystemExit` code is `None`)
until `super().__init__` is called.

An `except E as e` binding uses the nearest common user exception base of the handler's
classes, otherwise the builtin exception type. An uncaught user exception prints
`module.E: message` (`E` in the main program) and exits with status 1; a `SystemExit`
subclass exits using its code. Exception values keep identity when raised.

Additional inheritance, constructor and attribute restrictions are in
[exception restrictions](compatibility.md#exceptions-and-exception-classes).

## Syntax errors

Source checks apply to the whole file, including unused templates, imported definitions and
branches dropped at compile time. Pystachy checks tokenization, grammar, name binding and
statement placement, aiming to match CPython's error location and message.

Checks include bracket and indentation limits, unterminated literals, invalid targets,
argument-list errors, invalid `global` / `nonlocal`, misplaced control-flow statements,
late future imports and excessive statically nested blocks. Error selection follows the
parser, tokenizer where reached, symbol table, then compiler checks.

Some messages fall back to `invalid syntax` where CPython is more specific.
Patterns inside `match` statements are not checked, and the supported source syntax has
[additional restrictions](compatibility.md#source-text).
`tools/syntax_sweep.py` compares `pystachy check` with CPython's `compile()`;
`pystachy check` checks parsing and syntax, not whether a program can compile.

