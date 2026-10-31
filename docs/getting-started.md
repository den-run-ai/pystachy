# Your first compiled program

Pystachy is useful for CPU work expressed as typed Python loops, functions and
containers. Start with a small part of your application whose output you can
check with CPython. The [language](language.md) and [library](../lib/README.md)
references describe the supported subset; arbitrary Python packages may require
adaptation or the explicit [CPython bridge](ffi.md#calling-cpython-libpyobjpy).

## Install and run

Follow [installation](install.md) for a native archive, Docker or a source build.
After installation, save this as `squares.py`:

```python
def sum_squares(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total


print(sum_squares(10))
```

Run the same source three ways:

```sh
python3 squares.py
pystachy run squares.py
pystachy build squares.py -o squares
./squares
```

Each execution prints `285`. `run` compiles and executes the program with JIT;
`build` produces a native executable you can run again without compiling. This
example does not need Python at runtime once built.

From a source checkout, use `./pystachy` after `make`, or replace `pystachy` with
`python3 -m pystachy` to use the hosted compiler before bootstrapping.

## Try an unsupported construct

Insert a `match` statement immediately after the function definition:

```python
def sum_squares(n: int) -> int:
    match n:
        case 0:
            return 0
    total = 0
    for i in range(n):
        total += i * i
    return total


print(sum_squares(10))
```

CPython still prints `285`. `pystachy run squares.py` rejects this program:

```text
squares.py:2: error: 'match' statements are not supported
```

The diagnostic identifies the source file, line and unsupported construct. Replace
the three-line `match` block with a supported conditional:

```python
    if n == 0:
        return 0
```

Run the CPython, JIT and AOT commands again; each prints `285`. You can also call
`sum_squares(0)` and check that all three return `0`. See
[unsupported features](language.md#unsupported-features) when a diagnostic names
a construct your program needs. `pystachy check` checks syntax only; compiling
and executing the relevant path gives stronger evidence.

## Measure the work you care about

This ten-element example is too small to demonstrate a useful speedup. Start with
correctness and a representative input, then separate these costs:

| Command or region | What you measure |
|---|---|
| `pystachy build squares.py -o squares` | AOT compilation |
| `./squares` | Executable startup and program execution |
| `pystachy run squares.py` | JIT compilation, startup and execution |
| A timer around repeated calls inside the program | Steady work after startup, excluding compilation |

JIT compiles on each invocation; its runtime compilation cache can make the first
invocation slower. Warm that cache when comparing repeated runs, and report cold
startup separately. Repeat measurements, compare medians, and check outputs in
every mode. Ordinary integers are checked signed 64-bit values: increasing the
input enough to overflow is a correctness change, not a useful timing sample.

Use [performance](performance.md) for reproducible comparisons and LLVM inspection,
or a complete application such as the [event router](../examples/route/README.md).
To see where a program is analyzed, optimized and lowered, follow the
[compiler pipeline](internals.md#compilation-pipeline).
