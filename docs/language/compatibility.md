# CPython compatibility

Known differences and compile-time restrictions, using CPython 3.13 as the reference.
This is a guide to known limits, not a guarantee that every other Python program compiles.

| Find | Reference |
|---|---|
| Code that compiles but behaves differently | [Deviations](#deviations-from-cpython) below |
| Code rejected at compile time | [Restrictions](#rejected-rather-than-miscompiled) below |
| Supported language rules | [Types](typing.md), [execution](semantics.md), [modules](modules.md) |
| Module-specific APIs and gaps | [Library compatibility](../../lib/compatibility.md) |
| Experimental opt-ins | [Dynamic `Any`](../dynamic-any.md), [promoting ints](../python-int.md) |
| How compatibility is checked | [Testing](../testing.md) |

## Deviations from CPython

These programs can compile and run with different results, errors or timing of effects.

### Numbers

| Case | Pystachy behavior |
|---|---|
| Ordinary `int` | Signed 64-bit. Oversized results, intermediates and `int()` conversions raise `OverflowError`. Use explicit [`mpz`](../mpz.md) or opt in to [promoting ints](#promoting-ints-opt-in-prototype). |
| `int ** negative int` | `ValueError`; `0 ** -1` still raises `ZeroDivisionError`. |
| Negative float to a fractional power | `ValueError`; CPython returns a complex number. |
| NaN identity | Unboxed NaNs have no identity, including inside scalar union boxes: `nan in [nan]` is false. Container equality and sorting treat a shared NaN as distinct values. `hash(nan)` is 0, rather than an identity hash. |
| Empty `list[float]` | `sum(xs)` returns `0.0`, `sum(xs, 1)` returns `1.0`, and `math.prod(xs)` returns `1.0`; CPython preserves the integer start. |
| Native JSON | Typed `JSONValue` rejects integers outside 64 bits; dynamic `Any` decoding promotes them. Nesting is limited by recursion depth and a 2,000-container cap. See [JSON limits](../../lib/compatibility.md#json). |

**Masked arithmetic:** in `x & y`, a tree of `+`, `-`, `*` and `<<` under either
operand (including nested `&`, `|`, `^`) retains the low 64 bits at each step; shift
counts stay checked. With an exact, nonnegative opposite operand,
`(k * 0xCC9E2D51) & 0xFFFFFFFF` matches CPython. An oversized final masked result
raises only after the whole expression is evaluated
([deviation](../../tests/deviations/int_masked_overflow.py)).

### Text and file positions

#### Unicode

`str` uses UTF-8 storage. Length, indexing, slicing, iteration, search offsets,
replacement, padding, formatting and text `read(n)` count **code points**, not
visible characters: combining marks count separately. `chr()`, escapes, `ord()`
and `repr()` use the same code points. Whitespace stripping/splitting, `splitlines()`
and `isspace()` recognize CPython's Unicode whitespace and line breaks.
`isalpha()`, `isalnum()`, `isdecimal()`, `isdigit()` and `isnumeric()` use Unicode
15.1.0 properties, matching the pinned CPython. Decimal digits, digits and numeric
characters are distinct: `"²".isdigit()` is true and `"²".isdecimal()` is false;
`"Ⅳ".isnumeric()` is true and `"Ⅳ".isdigit()` is false. Combining marks are not
letters, so `"e\u0301".isalpha()` is false. Bytes character tests remain ASCII-only.
See [storage and indexing costs](../internals.md#values-and-runtime).

- **Case mapping and case tests:** `upper()`, `lower()`, `swapcase()`,
  `capitalize()`, `title()`, `casefold()`, `isupper()`, `islower()` and `istitle()`
  remain ASCII-only ([#120](https://github.com/den-run-ai/pystachy/issues/120)).
- **Invalid UTF-8:** builtin text files read/write unchecked bytes, where CPython
  decodes or raises `UnicodeDecodeError`. Each invalid byte counts as one character
  for length, widths, padding, precision and `expandtabs()`. `read(n)` counts
  non-continuation bytes instead, so malformed input can return `len(text) > n`.
- **Surrogates:** U+D800–U+DFFF retain their three-byte encoding and can be printed
  or written to UTF-8 files; CPython normally raises `UnicodeEncodeError`.
  `sys.stderr` escapes them (including uncaught errors and `sys.exit()` messages).
  Their `repr()`, `ascii()` and `ord()` match CPython.

#### Codecs and files

- **Conversions:** `str.encode()`, `bytes.decode()` and `bytes(s, encoding)` support
  UTF-8, Latin-1 and ASCII, including codec aliases. Other codecs and the
  `namereplace` error handler raise `LookupError`.
- **Builtin text files:** UTF-8 and Latin-1 only. An unsupported constant encoding
  is rejected; one computed at runtime raises `NotImplementedError` on opening.
  Latin-1 reads convert bytes to UTF-8 strings; writing a character above U+00FF
  raises `UnicodeEncodeError` before any text is written. `write()` returns the
  character count for both encodings. [`TextIOWrapper`](../../lib/compatibility.md#io)
  has its own codec and buffering contract.
- **Text update modes (`+`):** writes after reads approximate CPython's read-ahead
  in 8 KiB chunks. CPython reads ahead by roughly `n` characters for larger
  `read(n)` calls. After early exit from file iteration, CPython 3.13 retains
  read-ahead across a write, so its next read can return pre-write text
  ([large read](../../tests/deviations/io_rplus_big_read.py),
  [iteration](../../tests/deviations/io_iter_write_read.py)).

- **Binary files:** `open()` supports literal binary modes. A computed binary mode
  raises `NotImplementedError` at runtime. See [binary file limits](../../lib/compatibility.md#binary-files)
  for argument/type restrictions and append buffering differences.

#### Formatting limits

- Width or precision above `10**8` raises
  `ValueError: Too many decimal digits in format string`. CPython accepts widths
  and most precisions up to `2**63 - 1`, and float precision up to `2**31 - 1`;
  its overflow messages differ (`width too big` / `precision too big`).
- Non-ASCII decimal digits in a format specification, such as `f"{x:٣}"`, raise
  `ValueError`; CPython reads them as numbers.

#### Unicode audit

Enable checks **when compiling**, including for imported library code:

```sh
PYSTACHY_UNICODE_AUDIT=1 ./pystachy run app.py
PYSTACHY_UNICODE_AUDIT=1 ./pystachy build app.py -o app
```

The checks raise `NotImplementedError: Unicode audit: ...` for non-ASCII input to
case mapping, case tests and `expandtabs()`, even when the result would match
CPython. Character classification, code-point operations, printing, equality,
concatenation and Unicode whitespace operations remain usable. File write counts, invalid UTF-8 decoding and
other unlisted boundaries are **not audited**.

Each check scans to the first non-ASCII byte; default builds omit it. An AOT
executable keeps its compiled checks: changing the variable when running it has
no effect. The shared runtime cache is independent of this setting.

### Containers and evaluation order

- **Dict views are snapshots.** `keys()`, `values()` and `items()` produce lists
  when evaluated: they print/compare as lists and miss later mutations, including
  those in later call arguments. `enumerate`, `zip`, `reversed`, and `in`/`min`/`max`
  over values can therefore miss size changes that CPython detects. Plain `for`
  loops and `iter()` over `d.items()` traverse the dict and detect size changes.
- **Set order differs.** String hashes are not CPython's randomized hashes;
  constant displays do not reuse CPython's frozenset constants or `.pyc` layouts.
  Identity-hashed objects depend on addresses in both runtimes. Use `sorted()`
  when order matters.
- **Set callbacks may run later.** `min()`/`max()` snapshot a set before calling
  `key=`, so size changes are not detected. `intersection()` and
  `intersection_update()` consume a generator expression before testing its items;
  CPython interleaves generation and testing.
- **Hash callbacks can repeat.** `dict.fromkeys(set_of_objects)` recomputes user
  hashes; CPython reuses the set's hashes. `cache()`/`lru_cache()` may hash an
  argument more than once per call; CPython does so once.
- **Some consumers materialize inputs.** `min()`/`max()` stream scalar generator
  expressions and iterator objects (`int`, `float`, `bool`, `str`) without keywords,
  and iterator objects with `key=`. Other types and generator expressions with
  `key=` materialize first. With `default=`, lists and dynamic inputs stay live;
  other inputs materialize, as do those of `math.fsum()`/`math.prod()`.
  Later input effects or exceptions can therefore
  precede a comparison error or `fsum()` overflow.

### Functions and object identity

- **Private names:** supported classes use lexical name mangling: `__field` written
  in class `C` names `_C__field`, including in inherited method bodies. String arguments
  to reflection and call keyword labels retain their literal spelling. Direct reads of
  statically missing attributes remain compile-time errors; private `__slots__` entries
  remain unsupported.
- **Tuple constants:** literal-only displays share a module constant; `()` is
  shared everywhere. CPython also folds operator expressions such as `(1 + 2, 3)`.
  Pystachy recreates those tuples, and tuples whose annotations retype/box items.
- **Tuple conversions:** fixed-shape to runtime-length tuples, or scalar to
  optional-element tuples, create new objects. Empty runtime-length tuples are
  not interned. `tuple(t)` preserves identity only when its representation fits.
- **Callables:** `is` compares the function and its environment/bound object, as
  `==` does. Two reads of `o.m` converted to `Callable` compare identical; CPython
  creates separate bound-method objects.
- **Missing return:** a value-returning function reaching its end raises
  `RuntimeError`. Supported optional returns and templates returning objects or
  optional values return `None`; see [typing](typing.md#function-and-method-templates).
- **Operators on `None`:** an optional left operand whose class defines an
  arithmetic/bitwise operator raises `TypeError` when it is `None`, even if
  CPython would call the right operand's reflected method.
- **Direct dataclass comparisons:** generated `__eq__`/ordering methods called
  directly compare fields or raise `TypeError` for another class; `__eq__(None)`
  is false. CPython returns `NotImplemented`. Operator syntax declines such
  operands as CPython does.
- **Optional method arguments:** `None` selects a builtin method's default,
  including padding fill characters for which CPython raises `TypeError`.
- **Optional sort keys:** a callable object that is `None` normally means no key.
  For object items, closed unions or functions, it is instead called and raises
  `TypeError`; a `Callable | None` key for these items is rejected at compile time.
- **Reflection text:** runtime-name `getattr()` prints substitute addresses for
  method wrappers, builtin methods and static methods; there are no corresponding
  Python type/function objects. See [reflection](semantics.md#reflection).

### Errors and control flow

- **Earlier errors:** statically invalid operations (such as ordering dicts or a
  constant tuple index out of range) fail compilation, before any program output.
- **Uncaught errors:** only the final traceback line is printed, without name
  suggestions; stdout is flushed and exit status is 1. Compile-time
  `SyntaxWarning`s are omitted.
- **Process failures:** out-of-memory, Ctrl-C and unguarded stack exhaustion end
  execution without `except`/`finally` cleanup. Explicitly raised `MemoryError`
  or `KeyboardInterrupt` remains an ordinary exception.

#### Recursion

`sys.setrecursionlimit()` enforces a default limit of 1,000 in JIT and AOT, raising
catchable `RecursionError` with normal cleanup. Nonpositive limits raise
`ValueError`, values outside C `int` raise `OverflowError`, and lowering to/below
active native depth raises `RecursionError` without changing the limit.

Depth starts at one for module execution. Only potentially re-entered source
functions, lambdas, methods and running generator bodies count; this includes
indirect calls and runtime callbacks. Non-recursive helpers, suspended generators,
dispatch adapters and runtime helpers do not count. A resumed generator uses its
current caller's depth. Inlining and tail-call optimization preserve these rules.
CPython counts every Python frame, so bounded recursion can fail at a different
call; exact depths and messages differ
([deviation](../../tests/deviations/recursion_uncounted_frames.py)).

Counted entries also check the native stack. A raised recursion limit can still
produce `RecursionError` where CPython completes, because native frames use stack
space ([deviation](../../tests/deviations/recursion_native_stack.py)). This is not
protection for foreign code, exhausted guard margins, unknown/switched stacks, custom Linux
kernel guard gaps, or mappings and stack-limit changes after initialization. On Linux,
extensions and glibc's bounds fallback inspect mappings once and allow the default 256-page
guard gap above an accessible predecessor; failed `/proc/self/maps` inspection retains the
platform bounds. Extensions use the importing thread's bounds. See [native recursion depth](../internals.md#native-recursion-depth)
for margins, platform limits and implementation details. Recursive aliases retain
a separate budget; JSON retains its 2,000-container cap (roughly 500 decoded or
1,000 encoded containers at the default recursion limit).

#### Exception contents

Exception arguments are formatted at construction, after all arguments are
evaluated. CPython formats `args` when needed. Later mutations are invisible;
argument `__str__`/`__repr__` failures replace the intended exception. Missing-key
`KeyError` similarly calls the key's `__repr__` immediately. Single-argument
`SyntaxError`, `IndentationError` and `TabError` also test the argument's truth
immediately ([deviation](../../tests/deviations/exc_syntax_error_truth.py)).

For user exceptions, redundant formatting is omitted when `__init__` is proven
to replace it: its first initializer call must be `super().__init__(...)` or
`Base.__init__(self, ...)`, an unconditional standalone statement without starred arguments;
earlier code and arguments may use `self` only for plain field reads/writes,
cannot return/yield or name `locals`, `vars`, `eval`, `exec`, `dir`, `breakpoint`
or `super`, and any user base must meet the same rules.
`OSError`/`SystemExit` subclasses, classes defining `__new__`, `__del__`,
`__getattr__`, `__getattribute__`, `__setattr__` or `__delattr__`, and decorated
or generator/async initializers retain eager formatting
([coverage](../../tests/programs/exceptions/exc_keep_repr_effects.py)).

- Assigning an exception class's `__module__ = "builtins"` raises
  `NotImplementedError`; other names work
  ([deviation](../../tests/deviations/exc_class_module_builtins.py)).
- `__exit__` receives `None` for the traceback unless that parameter is annotated
  `TracebackType | None`. With that annotation it receives an attribute-free
  placeholder ([deviation](../../tests/deviations/with_traceback_none.py)).

### Modules and libraries

- **Builtin imports** bind names program-wide, even inside functions. Python
  module imports (including re-exported builtins) keep normal function scope.
- **Pure-Python libraries** can differ from CPython's C accelerators in errors,
  accepted keywords and callback order; see the [shared library differences](../../lib/compatibility.md#pure-python-accelerators).
  A program's `stat.py` or `posixpath.py` can shadow a module CPython loads at startup.
- **Uncompiled code** omits some import-time errors: uncompiled imported classes are
  not created, and uncalled templates are not type-checked. Syntax errors remain
  errors. See [import-time scope](modules.md#unsupported-code-in-imported-modules).
- **Optional imports** can take the fallback where CPython finds an installed
  module or API. A failed module retains globals already assigned; a later import
  reruns its code over them. See [optional imports](modules.md#optional-imports).
- **Unbound globals** read as `m.x` raise `AttributeError` without CPython's
  circular-import/renaming hints. `from m import x` raises `ImportError`, using the
  file path from compilation rather than a runtime installation.
- **Module `__doc__`:** without a docstring, if its first mention is in a `def` or
  `class` and module code later assigns it, an earlier read raises `NameError`
  instead of returning `None`.
- **Module `__file__`:** the absolute path of the source file the module was compiled
  from. An executable built ahead of time keeps that path wherever it runs, also once
  the source has moved. A `lib/` module names Pystachy's file, not CPython's. A builtin
  module (`os`, `sys`, `math`) has no `__file__`, where CPython's `os` and extension
  modules have one, and neither has a namespace package, whose `__file__` is `None` in
  CPython: both are rejected
  ([error test](../../tests/errors/io/file_name.py)).

| Runtime value | Difference |
|---|---|
| `sys.warnoptions` | `[]`; `PYTHONWARNINGS` and `PYTHONDEVMODE` are ignored. Extension modules use the host's value. |
| `sys.prefix`, `base_prefix`, `exec_prefix`, `base_exec_prefix` | The build-time Pystachy home, also in AOT executables; no virtual-environment distinction. `gettext` finds no bundled catalog there. |
| `sys.version_info` | One shared immutable tuple for CPython 3.13.16. Attributes/comparisons work, but `str()`/`repr()` show `(3, 13, 16, 'final', 0)`. |
| `sys.stdin`, `sys.stdout`, `sys.stderr` | Always files. When descriptor 0, 1 or 2 is closed at startup, CPython's stream is `None` for the whole run. `input()` raises CPython's `RuntimeError: lost sys.stdin` (`stdout`, `stderr`); other uses reach the closed descriptor, or the file a later `open()` gets with that number. Reading `sys.stdin` raises `OSError` or reads that file, and `print()` can raise `OSError` or write there. In CPython the stream methods raise `AttributeError`, and `print()` treats a `None` file as `sys.stdout`, writing nothing if that is `None` too. |

### Memory and resource lifetime

- **Collection is conservative and batched.** There is no reference counting or
  `__del__` execution. Allocation elision can delay collection, file closing,
  weak-reference clearing and `ffi.track` release; only unretained objects/fixed
  tuples containing `int`, `float` and `bool` are eligible. See [optimization](../internals.md#whole-program-optimization).
- **Close files explicitly.** Dropped files close on collection or exit; buffers
  contribute to collection pressure. Temporary files used in one expression close
  immediately, and opening a file with an existing writer first triggers collection.
  Conservative roots can still retain a dropped writer, delaying writes or
  reordering appends.
- **Dropped suspended generators never close**, including at exit, so their
  `finally`/`with` cleanup is lost. A generator created as a `for` iterable closes
  when that loop exits, as do its `yield from` delegates when it is closed
  ([deviation](../../tests/deviations/gen_finalization.py)).
- **Generator-expression cleanup can be early.** When an exception escapes a
  consumer's generator expression, its inner generator closes before the handler;
  CPython retains it through the handler's traceback ([deviation](../../tests/deviations/gen_genexp_close_timing.py)).
- **PEP 479:** without any `try`/`with` in the program, a helper's escaping
  `StopIteration` terminates as `StopIteration`, not `RuntimeError`. A direct
  `raise StopIteration`/`next()` in the generator body, or any program with
  `try`/`with`, uses normal conversion ([deviation](../../tests/deviations/gen_pep479_no_try.py)).
- **Generator return values:** `next()`/`send()`/`throw()` raise a value-less
  `StopIteration`; `yield from` still gets the return value
  ([deviation](../../tests/deviations/gen_stop_value.py)).
- **Generator-expression setup:** the first iterable is evaluated immediately,
  but `range`/`enumerate`/`zip`/`reversed` validate arguments and dict/set iterators
  record size only on the first resume.

### Dynamic `Any` (opt-in prototype)

`# pystachy: dynamic-any` enables runtime-typed boxes. Concrete annotations and
native storage still impose checks: incompatible values raise `TypeError`, while
CPython ignores annotations. A native `list[int]` can share its object and storage
with `Any`; dynamic writes reject incompatible items before storing them. `extend`
and `+=` retain a successful prefix, while slice replacement checks all its items
before writing. The native descriptor also enforces the integer-container policy. Existing
boxed lists stay unrestricted, and `isinstance(value, list)` does not prove their
item layout. See the [native-list deviation](../../tests/deviations/dynany_native_int_list_store.py).
Unsupported selected comparison bodies also raise
`TypeError`; they do not silently fall back to identity or a lower-priority method.

Runtime argument packs support fixed user callables and prepared constructors.
Variadic targets, erased callable signatures, custom mappings, builtin methods,
unprepared classes and adapters whose bodies cannot compile raise
`NotImplementedError` when selected. See the
[runtime-call boundaries](../../tests/deviations/dyn_star_reducer_boundaries.py)
and [unavailable-body case](../../tests/deviations/dyn_star_reducer_unsupported_body.py).

The prototype's [operation matrix](../dynamic-any.md#operations),
[typed/dynamic boundary](../dynamic-any.md#the-typeddynamic-contract) and
[deviations](../dynamic-any.md#deviations) define comparison adapters, field writes,
iteration, reflection and identity limits.

### Promoting ints (opt-in prototype)

`# pystachy: python-int` enables integer promotion past 64 bits. The
[promoting-int guide](../python-int.md) defines supported storage and operations.
Remaining [64-bit boundaries](../python-int.md#64-bit-boundaries) raise
`OverflowError`; modules without the opt-in keep their own integer policy.

Typed-int `is` is rejected. Converting a 64-bit tuple containing `-2**63` to
promoting ints creates a new tuple. Combining both opt-ins preserves wide integer
values across `Any`, but [typed-container and generator identity gaps](../dynamic-any.md#deviations)
remain. See all [promoting-int deviations](../python-int.md#deviations).

## Rejected rather than miscompiled

These constructs fail at compile time with a `file:line: error:` diagnostic, including cases
where CPython would raise only when the code runs. The linked references describe supported
alternatives.

### Generators

See [generator semantics](semantics.md#generators).

- **Delegation and returns:** a `yield from` result used except as `r = yield from g()`;
  obtaining that result from anything but a direct generator-function call; a non-`None`
  return under `Iterator[T]` or `Iterable[T]`; unannotated recursive delegation before the
  first `yield` establishes the item type.
- **Sending:** a non-`None` value when the send type is `None`; a send type excluding `None`;
  forwarding to a different send type, or to a non-generator iterator while accepting send values.
- **Methods:** using `close()`'s result, `throw()` with multiple arguments, or `send` / `throw`
  as method values.
- **Other forms:** return annotations outside `Iterator`, `Iterable` and `Generator`; async
  generators; printing, comparing, `reversed()`, `len()` or `dict()` of a generator; passing
  one where a list is required. A dict comprehension works.
- **Stored generator expressions:** capturing a surrounding comprehension variable, a variable
  of an outer function, or a local that may be unbound or rebound. These require late binding.

### Context managers

See [context-manager semantics](semantics.md#context-managers) and
[`contextlib` coverage](../../lib/compatibility.md#contextlib).

- `with` values outside files and program classes defining both `__enter__` and `__exit__`,
  including unions of such classes; `with suppress(...) as x`; `nullcontext(None)`.
- Exception class-object attributes other than `__name__`, `__qualname__` and `__module__`.
- Unported `ExitStack`, `redirect_stdout`, `redirect_stderr`, `chdir`, `aclosing`,
  `asynccontextmanager` and `AsyncExitStack`.

### Names and scopes

- **Static errors:** unbound names, impossible attributes, operations or format specs, even
  inside a handler for the corresponding runtime error. Module-level
  [feature tests](modules.md#compile-time-branches) are an exception.
- **Rebinding:** duplicate function, class, method or import bindings; mixing those names with
  variables, including parameters or locals rebound by imports. The exceptions are Python
  variable from-imports, immediate `C = C()` rebinding and module-level definitions replacing
  imports under the [module-scope rules](modules.md#module-scope).
- **Class scope:** defaults referring to earlier class attributes, even builtin-like names or
  `__name__`; class-body `__doc__`; `:=`, including in a lambda default evaluated there.
- **Local scope:** reads textually before the first assignment, or where only discarded code
  binds the local. `del`, `def`, `class`, `:=`, match captures and `type` also establish locals.
  Declare the type before an early read: `x: int`.
- **Comprehensions:** reading a variable from its own or a later `for` clause, including in
  an assignment target; retyping an earlier loop variable after an intervening loop and read,
  as in `[y for b in [[1, 2]] for y in b if len(b) > 1 for b in [3]]`.
- Calling a builtin that the module also binds as a variable (`sum = 0; sum(xs)`).

Import-rebinding checks miss intervening reads through import cycles or module aliases,
including self-imports. These may raise `NameError` / `AttributeError` instead of reading the
imported value ([test](../../tests/deviations/star_rebound_self.py)).

### Modules and imports

See [module initialization](modules.md#finding-and-running-modules),
[optional imports](modules.md#optional-imports) and [module scope](modules.md#module-scope).

- **Unproven bindings:** a nested function or generator expression reading an enclosing
  function's module import before it is known to have run; globals typed only by a template
  not yet compiled; from-imports of globals assigned only by functions; early global reads
  whose first binding is a `for` / `with` target or still has an unknown type. Declare globals
  at module level, or use `m.x` for function-assigned globals.
- **Import order:** another module's nonconstant globals read while it is importing; package
  attributes colliding with submodules when their meaning depends on import timing; module-level
  aliases used before assignment, including cyclic from-import aliases. Function and
  module-attribute alias reads use runtime guards; `A = m.C` still uses a conservative
  early-read check.
- **Optional imports:** a possible `ImportError` other than a definite module-top-level raise;
  a possibly unbound from-import; handlers using `as e`, re-raising, or potentially ending
  the program when the module is missing; a failing module importing its caller back.
  Optional from-imports also require a definite binding, excluding conditional, deleted,
  annotation-only, function-created or star-imported names.
- **Module structure:** imported modules binding `__name__`; syntax errors even in imports
  that never run; module-level `def` / `class` inside compound statements; compiled class
  bodies beyond fields, methods, docstrings, `pass` and `...`.
- **Mutation:** `__all__` changes beyond `+=`, `append` and `extend`; star imports from builtin
  modules; deleting another module's attributes, assigning its `__doc__`, or deleting one's
  own `__doc__`; deleting or assigning anything but literal `False` to a module's
  compile-time `TYPE_CHECKING` flag, including through self-import.
- **Uncompiled definitions:** code outside the
  [restricted import-time evaluation](modules.md#unsupported-code-in-imported-modules),
  including user calls/callbacks, user-valued attributes/operands/container keys, attribute or
  item assignment, comprehensions, unsupported class statements/decorators or metaclasses
  (except `abc.ABCMeta`), base hooks (`__init_subclass__`, `__class_getitem__`), descriptors
  with `__set_name__`, and unbound or conditional names. Decorators must be dotted names or
  calls thereof; evaluated annotations must use [supported forms](typing.md#annotations).
  Rebound `object` or decorator names cannot stand in for the builtins.
- Imported functions, lambdas, classes or tuple displays nested beyond CPython's marshal limit.

### Templates and empty containers

Compilation rejects programs exceeding these limits:

| Resource | Limit |
|---|---:|
| Serialized type | 65,536 bytes |
| One template signature | 1,048,576 bytes |
| Active signatures combined | 1,048,576 bytes |
| Nested template compilations | 100 |
| Specializations across all functions and imports | 4,096 |
| Retained signature bytes | 16,777,216 |
| Inference/join passes | 8 |

Completed specializations count; reused ones add nothing. Size checks precede allocation,
including tuple repetition. Finite type-changing recursion works within these bounds.
Diagnostics summarize large types; retained-size errors name the largest template.

Other rejections:

- **Empty containers:** first filling one with `[]` / `{}` (`d[k] = []`); unresolved empty
  literals; empty template returns whose default `list[int]` / `dict[int, int]` type does not
  fit and whose context supplies none. See [inference](typing.md#variables-and-empty-containers)
  and [contextual results](typing.md#contextual-template-results).
- **Type joins:** incompatible storage/return types, a joined union used where it is not
  accepted, or `None` joined with an unfilled empty container. Recursive calls must follow
  the returns establishing the complete return type, including optionality.
  See [inferred unions](typing.md#inferred-unions).
- **`None` specialization:** unsupported operations such as `p.upper()` or `p[0]`, even
  inside runtime branches or catching handlers; incompatible rebinding across runtime
  branches, loops or a `for` target. `len`, `int`, `float` and `ord` raise at runtime.
  Statically resolved branches can reinitialize the parameter; see [templates](typing.md#function-and-method-templates).
- **Class templates:** fields specialized from `None`; unspecialized class annotations where
  context cannot select a specialization; unannotated exception constructors; mixing two
  specializations in one variable or container.

### Objects and operators

See [object protocols](semantics.md#object-protocols) and
[callables and closures](typing.md#functions-callables-and-closures).

- **Calls:** arguments incompatible with parameters, including `raise E` when `E.__init__`
  requires arguments; methods missing `self` / `cls`.
- **Protocol results:** non-`bool` comparisons or `__bool__`; non-`str` `__str__` / `__repr__`;
  `__len__` returning neither `int` nor `bool`.
- **Iteration:** non-generator `__iter__` returning a noniterator; `Iterator[T]`-annotated
  `__iter__` returning `iter(x)` beyond lists, tuples, strings and similarly annotated
  classes, or calling that method directly. Omit the annotation for iterator-object returns.
  Non-generator `__reversed__` has the same source restriction and must return `iter(xs)`
  or `reversed(xs)`.
- **Iterator operations:** `iter(callable, sentinel)`; `iter()` of `enumerate`, `zip`, `map`,
  `filter` or `reversed`; `next(it, default)` without a common item/default type; iterator
  classes lacking `__iter__` in comprehensions or `str.join`; inheritance-hierarchy
  constructors calling `iter()` or accepting `Iterator[T]` / `Iterable[T]`.
- **Fallbacks and power:** `__getitem__`-only iteration/membership; `__len__` / `__getitem__`
  fallback for `reversed`; reflected arithmetic; `NotImplemented`; object or optional
  numeric power exponents; three-argument object `pow`. Before `**=`, narrow a base-typed
  receiver if only its subclass defines `__ipow__`.
- **Comparisons:** equality between unrelated ordinary classes outside inheritance
  hierarchies when the left operand has no applicable comparison method; methods whose
  parameter type excludes a possible operand. The method restriction covers direct
  base-typed comparisons, container membership/equality/sorting, subclass overrides,
  and nested dataclass or NamedTuple fields. Printing these containers works.
- **Tuples and slices:** constant out-of-range fixed-tuple indices; nonliteral fixed-tuple /
  NamedTuple slices unless a homogeneous runtime tuple can hold the result; slice mutation
  outside lists; noniterable or incompatible list-slice values (`list.extend` likewise requires
  homogeneous tuple items); unpacking noniterables or wrong-arity tuples; heterogeneous
  starred remainders without a compatible annotation; object slicing through slice-protocol
  methods; nonconstant tuple repetition.
- **Specific builtins:** `sum(..., start)` with a bool start (use `int(start)`); a
  `startswith` / `endswith` tuple containing anything beyond `str` / `str | None`.
- **Function values:** mixing functions without a `Callable` annotation; `Callable[..., R]`;
  keyword calls, wrong arity or incompatible return types through `Callable`; printing
  functions, including inside containers; comparing containers of functions.
- **Closures:** capturing possibly unassigned or later-unbound enclosing variables, or
  comprehension variables; a decorated nested function capturing its own name; nested
  classes. An undecorated nested function may reference itself.

### Classes, dataclasses and NamedTuples

See [fields and records](typing.md#fields-dataclasses-and-namedtuples) and
[single inheritance](typing.md#single-inheritance).

- **Inheritance:** multiple bases outside the [method-only secondary base](typing.md#a-method-only-secondary-base) subset; ordinary hierarchies involving templates, `Generic`,
  NamedTuple or builtins; mixed dataclass/ordinary hierarchies; decorated subclasses except
  dataclass-from-dataclass; changing method kind; incompatible virtual call signatures or
  results; overridden static/class methods called through base-typed objects.
- **Inherited members:** assigning inherited class attributes through subclasses without their
  own defaults; changing field types; derived-only fields without supported narrowing;
  inherited `cls`-using classmethods through base-typed objects, across modules or with
  nonconstant defaults; `super` outside supported instance-method contexts, with an unrelated
  class or a different receiver.
- **Methods and hooks:** using or assigning `cls` as a value; static/class decorators on special
  methods; `C.m(o)` outside ordinary inheritance; decorators beyond staticmethod, classmethod,
  property/setter/deleter, dataclass and overload. Defining or inheriting `__new__`,
  `__getattr__`, `__getattribute__`, `__setattr__` or `__delattr__`, or a base defining
  `__init_subclass__`, is rejected.
- **Properties and attributes:** getter decorators, duplicate/misnamed setters or deleters,
  `property()` calls, assigning `super().x`, deleting nonproperty attributes; unannotated
  dataclass/NamedTuple class attributes, writes to them through their classes or to other class
  attributes lacking a class-body binding; reading a Python-function class attribute through an instance.
- **Dataclass options:** `slots=True`, `weakref_slot`, nonliteral boolean options,
  `field(metadata=...)`, `InitVar`, factories beyond functions/classes/zero-argument lambdas;
  `fields()` outside loop iteration; custom factories or incompatible field joins in
  `asdict` / `astuple`; `object.__setattr__` in frozen records; `FrozenInstanceError` outside
  handlers; hashing; field retyping; `repr=False` under a generated base `__repr__`.
- **NamedTuple operations:** no fields; assigning fields outside `__init__`; custom `__getitem__`
  / `__iter__`; custom comparison/addition with another type; `hasattr` for absent names;
  wrong-arity `_make`; heterogeneous `_asdict`; annotated `_field_defaults`; hashing with
  custom `__eq__` / `__hash__`; functional `NamedTuple(...)`.
- **Record creation errors:** underscored NamedTuple fields, invalid default order or overridden
  `__init__`;
  dataclass nondefault fields after defaults (including inherited ones), mutable defaults,
  `order=True` without `eq`, generated-method conflicts and frozen/nonfrozen inheritance.
- **`collections.namedtuple`:** forms beyond a uniquely bound, module-top-level
  `NAME = namedtuple(...)` with literal arguments; argument unpacking, nonboolean `rename`,
  non-ASCII names, no fields or inheritance; reading `__doc__` or `NAME.field`
  (literal `NAME.field.__doc__ = "..."` works); `None` fields, mixed specializations or
  all-`None` `_field_defaults`.

### Optional values

See [optional operations and narrowing](typing.md#optional-values-and-narrowing).

- `is` between `int | None` values; converting or adding scalar
  containers to containers of boxed optional items (`int`, `float`, `bool`); unnarrowed
  optional values where the operation does not accept them. Tuples can copy-box items.
- Passing or assigning `list[T]` / `dict[K, T]` as optional-element containers, including
  through `Sequence` / `Mapping` aliases; optional builtin arguments beyond `len`, `int`,
  `float`, `ord`, `hex`, `oct`, `bin`, `dict`, `sum`, `round`, `os.system`, `os.path.exists`,
  `os.path`'s one-path string functions and functions accepting `None`; `round(float, n)`
  with optional `n`.
- Reads needing the type of a local/global/field assigned only `None` when neither later
  assignments nor context can supply it yet, including assignments in uncompiled templates
  or later module code. Annotate the optional type.
- Unannotated empty containers assigned after `None`; all-`None` displays without context or
  a typed fill before use; filling such lists with scalar `extend` / `+=`; first filling an
  empty list with `append(None)`. Annotate the container.

### Dict keys, set elements and `bool` values

- Nullable keys/elements except user objects; tuple keys containing unsupported members
  such as floats, lists or NamedTuples; NamedTuple, exception or frozenset keys/elements;
  hashing these types except NamedTuples; classes with nonmethod `__hash__` / `__eq__`.
- Bool stored as int, including set elements, dict keys, tuple-key members, `setdefault` and
  displays. Bool-key lookup, `pop` and `del` work; augmented assignment requires an RHS that
  runs no user code and mutates no dict. Only `get` and `in` also accept optional bool keys.
- Set-display unpacking; operators with nonsets or different element types; unresolved
  empty `set()` / `frozenset()`.

### Typing forms

See [annotations](typing.md#annotations), [aliases](typing.md#type-aliases) and
[generic classes](typing.md#explicit-generic-classes).

- **Type variables:** `ClassVar`; `PathLike` outside a union with `str`; `TypeVar` outside template parameters
  and returns, except bound class type variables; constraints or nonstring bounds;
  `TypeVarTuple` outside unpacking in tuple, Callable or `*args`; unbound class type variables.
- **Generic classes:** `Generic[...]` alongside another base; PEP 695 classes with bases,
  `ParamSpec` or multiple `TypeVarTuple`s; explicit `C[X]` with a `TypeVarTuple` or unannotated /
  variadic constructor parameters.
- **Declarations:** bare `Final` outside assignments (class assignments must be constant);
  missing imports for typing names even in local annotations; overload stubs not followed in
  the same block by their implementation with only intervening `def`s, or nonconstant
  stub defaults. Imported missing/late implementations fail when called.
- **Aliases:** runtime use except aliases of `int`, `float`, `str` or `bool`; recursion outside
  the [bounded value-union form](typing.md#recursive-value-aliases-prototype); non-top-level or
  rebound `type` names; generic aliases without arguments; arguments for `TypeVarTuple` /
  `ParamSpec` aliases; alias expansion beyond 65,536 nodes. Assigned aliases only subscript
  supported generic aliases, `Optional`, `Union`, `Callable`, `Tuple`, `Literal`, `Annotated`
  and single-type forms. Invalid forms (such as `Generic[T]` / `Concatenate[...]`) and invalid
  string expressions in `type` statements fail even when unused.
- **Dynamic `Any`:** typed mutable containers other than the supported native `list[int]`
  boundary becoming `Any`, unimplemented prototype operations,
  runtime `**` expansion of native dictionaries with non-str keys, or None-first storage
  that cannot select `Any` initially:
  generator/closure locals, function-assigned globals, fields assigned outside their class's
  methods, and all-`None` displays. See the [prototype contract](../dynamic-any.md).

### Exceptions and exception classes

See [user exception classes](semantics.md#user-exception-classes) and
[class objects](semantics.md#exception-classes-as-values).

- **Raising/catching:** raising nonexceptions; handlers naming nonclasses, or class objects
  that may be `None`; nested handler tuples; `except*`; function handlers binding globals
  with `as`, or module handlers rebinding differently typed globals read by functions.
- **Class-object calls:** multiple arguments or keywords; equality with program objects.
  A mismatched user-constructor argument type raises `TypeError` instead of constructing
  ([test](../../tests/deviations/exc_class_call_init_type.py)); calling the `NoneType` class
  object obtained from an optional exception raises instead of returning `None`
  ([test](../../tests/deviations/exc_class_call_nonetype.py)).
- **Equality:** builtin exceptions (including against `None`) when a user exception defines
  `__eq__` / `__ne__`; unrelated user exception classes when neither hierarchy defines
  comparisons but another exception class does. Use `is`. Narrow comparison annotations
  have the [object-comparison restrictions](#objects-and-operators).
- **Storage:** mixing builtin and user exceptions in typed storage, or unrelated user
  exception classes in one list. Annotate a common user base, or catch the concrete class.
- **Inheritance:** multiple bases; `SyntaxError` hierarchies, Unicode decode/encode/translate
  errors or exception groups as bases; decorators; overriding base methods except
  `__init__`, `__str__` and `__repr__`; `cls`-using methods through potentially subclassed
  receivers, or inherited across modules or with nonconstant defaults.
- **Fields and class attributes:** assigning inherited class attributes through subclasses;
  rebinding a class attribute also rebound elsewhere in its hierarchy; redeclaring inherited
  fields except same-type class defaults; reserved builtin fields (`args`, `SystemExit.code`,
  `OSError.errno/strerror/filename/filename2`, `ImportError.msg`). Fields set by builtin
  initialization (`StopIteration.value`, `AttributeError.name/obj`, `NameError.name`,
  `ImportError.name/path/name_from`) must be assigned after it or given class-body defaults.
- **Attributes:** exception metadata beyond `__cause__`; user-exception `__cause__` (catch as
  a builtin exception); absent builtin fields; BaseException methods beyond `__str__` /
  `__repr__`; derived fields after `isinstance`, which does not narrow exception values.
- **Initialization:** `x.__init__()` when a subclass overrides it; explicit calls naming
  anything but the immediate base; base-field reads or other uses of `self` before base
  fields initialize, including through methods, `super` or closures. Call
  `super().__init__()` first. Without a user
  constructor, keywords must be accepted by the builtin base; `OSError` takes at most three
  positional arguments here.
- **`super`:** outside exception methods, in parameterless static methods, without arguments
  in classmethods, with anything but the method's own class and `self`, or calling a base
  classmethod that uses `cls`.

### Builtins

- **Iterator wrappers:** nested `enumerate`, `zip` or `reversed` wrappers; `zip(strict=...)`.
  Materialize the inner iterator first. `reversed(range(...))` works.
- **Ranges:** ordering, attribute assignment, non-int/bool membership, non-int indexing /
  `index` / `count`, equality with optional nonranges, `dir` and `vars`.
- **Sentinels:** `object()` arguments, attribute assignment, equality with user/exception
  objects, mixed-type variables/returns/`dict.get` defaults, or aliases / `type(x) is object` without any
  module calling `object()`. See [sentinels](semantics.md#sentinels).
- **Reserved modules:** `_pystachy_iterators`, `_pystachy_range`, `_pystachy_object`.
- **Arguments:** unsupported keywords; optional `key=` when items lack a supported natural
  order; `open()` encoding constants beyond UTF-8 and Latin-1.
- **Dict methods:** `update` with different key/value types, pair iterables beyond lists of
  matching tuples, or keyword arguments for nonstring keys; `fromkeys` with generators or
  implicit `None` values without a contextual type.
- **Bytes:** `bytearray`, `memoryview`, `expandtabs`, `title`, `istitle`, `%`
  formatting, integer search arguments, method keywords except `hex` / `translate`, and
  equality with strings.
- **Formatting:** format strings beyond literals or uniquely bound module literals whose
  names are never shadowed; format methods as values except literal `"...".format` in `map`;
  unpacked strings, or unpacked lists followed by positional arguments; multiple dict expansions with
  runtime keys; statically impossible field-item keys.
- **Caching:** `lru_cache` / `cache` on unannotated functions, `None` returns, variadic arguments,
  non-key parameter types, builtins, methods or lambdas; required keyword-only parameters or
  explicitly supplied keyword-only arguments; `cache_parameters`.

<a id="reflection"></a>

### Reflection

See [reflection rules](semantics.md#reflection).

- **Types:** stored `type(x)` values outside the
  [dynamic-Any class registry prototype](../dynamic-any.md#class-values-and-type-keyed-registries)
  and exception class objects; dynamic class calls beyond ordinary reconstruction
  and the bounded annotated-factory path, runtime class creation and metaclasses. Type names of files
  remain unsupported.
- **Runtime names:** retaining, passing, calling, comparing or sorting by a `getattr` result;
  formatting its text with a spec, or obtaining that text for dataclasses, generics, classes
  with annotated class attributes or builtins; `setattr` without slots, with values incompatible with any
  slot or with slots no code assigns; `delattr` and field deletion.
- **Instance dictionaries:** `vars` / `__dict__` beyond printing, iteration, formatting or
  copying; ambiguous insertion order from multiple new fields in branches/loops, field
  additions through setters, outside `__init__` or in `__post_init__`, or later assignment to a potentially
  uninitialized nonlast field; class attributes also assigned through objects.
- **Targets:** `getattr`, `setattr`, `hasattr` and `dir` on exceptions; `dir` on files/functions.
- **Expansion:** constant-name loops defining functions/lambdas/classes, reassigning the loop
  variable or expanding the body over 256 times; `dataclasses.replace` with runtime dict keys.

### Source text

- Named Unicode escapes (`\N{...}`, including f-strings), non-ASCII identifiers, indentation
  tabs, and source encodings outside UTF-8, Latin-1 and ASCII.
- Nesting over 5,000 source levels (`**` and `lambda` count twice), or the 6,000-level CPython
  parser-stack budget. Grammar weights follow CPython 3.13: brackets 24–33, f-string fields
  33, blocks 7 and comparison operands 3. The check can stop a few dozen levels earlier.
