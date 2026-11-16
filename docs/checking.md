# Checking a program

`pystachy check FILE.py` tells you whether Pystachy can compile a program, without
generating code. It runs the compiler that `pystachy ir` runs, through the typed
program's finalization: imports, declarations, typing, specialization, layout
selection, effect analysis and export admission. It does not lower to LLVM, compile
`runtime.py` or run LLVM tools, and it never executes the program.

```sh
pystachy check app.py                 # every failed function, one line each
pystachy check app.py --json          # the same, and the compiler's decisions, as JSON
pystachy check mod.py --ext           # as pystachy ext would compile it
pystachy check app.py --syntax        # only parse it, as CPython does before running it
```

A program that compiles checks silently, with exit status 0. Otherwise the status is 1,
and each problem is one line on stderr. Invalid arguments give status 2.
`--max-errors N` (default 20) bounds how many failed units are found before checking
stops.

## What is checked

The compiler checks the code that it reaches. A module's code, and every function or
method of the main program that is not a template, is checked. A template, such as a
function with an unannotated parameter or an inferred result, is checked for each
combination of argument types that the program calls it with. Functions and methods
of imported modules are checked only where they are called. Code that nothing reaches is
not checked, and the JSON report lists it (`unreached`). A function whose declaration
already shows that it cannot be compiled has that `problem` listed there too.

This is not a PEP 484 type checker. Annotations mean what the
[typing reference](language/typing.md) says, and the check accepts exactly the programs
that compilation accepts. `pystachy check --syntax` keeps the earlier behavior: it
parses the file and makes the checks that CPython makes before running a file
(`tools/syntax_sweep.py` compares it with CPython's `compile()`).

## Errors in several functions

Compilation stops at its first error. The check continues with the rest of the program
by retrying the compilation with fresh compiler state, as an
[inference retry](internals.md#frontend-and-specialization) does. In each retry, the
bodies of the units that have already failed are left out: each one raises
`NotImplementedError` instead. A unit is a function, a method, or a closure or lambda,
for each template instance. The first error that the check reports is always the error
that `pystachy ir` reports.

Leaving a body out changes nothing for its callers when its result is annotated or
`None`. Otherwise, code that uses its result is checked against a placeholder. A unit
whose types may depend on such a result is reported as a note, not as an error:

```text
app.py:2: error: unsupported operand type(s) for +: 'int' and 'str' (compiling add(int, str) for the call at app.py:10)
app.py:5: note: g(None) was not checked: its types may depend on add(int, str), which failed
app.py:16: error: unsupported operand type(s) for +: 'int' and 'str'
```

A unit is tainted when it receives the inferred result or yields of a unit that was
left out, or is compiled while a tainted unit is being compiled. A template instance
can only be tainted in the second way, because its argument types may come from that
result. When module code or a class declaration receives such a result, a global or a
field layout can carry it to any later unit. Every later failure is then a note. Fix
the reported errors and check again to see what the notes hid.

Some failures cannot be isolated, and checking stops at them with a note:

| Failure | Why checking stops |
|---|---|
| A syntax, scope or import error | The program did not load. |
| An error in module code | Module code is one unit: the rest of that code, and the functions compiled after it, are not checked. |
| An error in a declaration (a field, an annotation, a class) | No function body has been compiled yet. |
| An export that fails admission (`--ext`, as `pystachy ext` compiles it) | Every function was already checked; the exports after it were not. |
| An error in code the compiler writes (helpers, dispatchers, adapters, dataclass methods) or an internal error | No body of the program can be left out. |
| A unit that fails again with its body left out | The retry made no progress. |

## The JSON report

`--json` writes one JSON object to stdout and nothing to stderr. It has `version` 1,
the checked `file`, a `status` (`ok`, `errors`, or `incomplete` when checking stopped
early), the number of compilation `attempts` (inference retries included), the number of
`errors` and why checking `stopped`.
Each element of `diagnostics` has the error's `severity` (`error` or `note`), `code`,
`file`, `line`, `message` and specialization `context`, as
[compiler inspection](compiler-inspection.md) reports them. It also has the failed
`unit` (its `name`, `kind` and the `place` of its definition), the unit it may depend
on (`after`) and whether its body was left out.

When an attempt completed, the report adds the decisions that the compiler made for
the program's own files (not those of `lib/`). Each decision kind has its own section:

| Section | What it records |
|---|---|
| `typing` | Each compiled body, once per template instance: the parameter and result types it was checked with, whether the result was inferred, and its `status` (`checked`, `partly checked` when it used a result left out, `left out`). |
| `layouts` | Each class layout: its members in struct order, with hidden assignment flags and identity boxes counted, and the class it is a layout of. A class template has one layout per specialization (`Box-1`, shown as `Box[int]`). |
| `specializations` | Each template's instances: a function's by the types of its arguments, a class's by the types of the call that made each layout. |
| `policies` | Each file's representation of `int` (checked 64-bit, or promoting with `# pystachy: python-int`) and of `typing.Any` (inferred, or dynamic boxes with `# pystachy: dynamic-any`). |
| `unreached` | The functions and methods with no compiled body. |

Every parameter, result and field appears three ways: the Python `type` the compiler
checked it as, the compiler's `representation` of it, and the machine `storage` of that
representation. In a module that opts in to promoting integers, for example, a function
can take an `int` stored as `i64` and return an `int` represented as `int+` (a
promoting integer), stored as `{i64, ptr}`.

These records describe one compilation of one program. A change elsewhere in the
program, such as a new call with other argument types, can change them. Discovery is the
only stage that makes these decisions. Once it completes, a later stage cannot add a
template instance, a class specialization or a field layout
(see [pipeline](typed-ir.md#pipeline)).

## Cost

Each attempt is a full frontend compilation without code generation. A program with no
errors costs one attempt. Each failed unit adds one, up to `--max-errors`. The check
skips LLVM lowering and code generation, and the runtime that `run` and `build` also
compile.
