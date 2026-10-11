# Pystachy FFI: recommendation

The question: the best FFI mechanism for Pystachy, with minimal impact, that can work with CPython in
both directions, and whether it should be JIT, AOT or both.

- **Written:** 2026-10-11.
- **Main:** `4dc548a` (origin/main, checked with `git ls-remote` today). Line references below are
  against that commit unless they name a prototype function.
- **Prototype:** branch `ffi` at `4051925` in `SCRATCH/stage3/tree`, as one patch in
  `SCRATCH/stage3/ffi-prototype.patch` (107 files, +3543/−53). It applies cleanly to `4dc548a`
  (re-checked today).
- **SCRATCH** = `/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad`.
- `/home/user/pystachy` was not changed.
- **Saved copies** on branch `claude/ffi-research`: the patch is `research/ffi/final/ffi-prototype-on-4dc548a.patch`, the logs and scripts of `SCRATCH/stage5` and `SCRATCH/stage6` are under `research/ffi/final/logs/`, and the reports are in `research/ffi/stage3/*.json`. SCRATCH itself is temporary.

## The answer

| Direction | Mechanism | Tier | Reason |
|---|---|---|---|
| Pystachy calls C | `@ffi.extern("lib")` on a typed `...` stub. When the `def` runs, the function is looked up in the library's own handle (`dlopen` + `dlsym`), as `ctypes.CDLL` does. | **Both**, from the same IR | The library is neither linked nor passed to lli, so JIT, AOT and CPython bind the same library. A call costs 3.9 ns. |
| Pystachy calls CPython | `lib/pyobj.py`: subset code that calls CPython's stable ABI through `@ffi.extern`, embedding any shared libpython ≥ 3.12 | **Both**; AOT is the reference tier | lli loads libpython as easily as the linker links it. The JIT differs only in the documented ways listed in §2. |
| CPython calls Pystachy | `pystachy ext mod.py`: an abi3 (3.12+ GIL) or abi3t (3.15+, GIL and free-threaded) extension module of `@ffi.export` functions, both from byte-identical program IR | **AOT only** | CPython imports shared objects, and `pystachy run` is a separate lli process (#108: "not a resident compiler service"). An in-process JIT would put libLLVM or llvmlite inside CPython, while the .so imports in 0.27–0.45 ms. |

Calls work both ways in one process: an extension module can use `pyobj`, and nested
Python→Pystachy→Python→Pystachy re-entry matches the source run under GC stress 1 (tests
`ext/viajson.py`, `ext/reent.py`).

**One mechanism.** A builtin module `ffi` (`extern`, `export`, `string_at`, the C integer types)
whose plain-Python **twins** live in `tools/rt_cpython` (the `_rt.py` precedent), with `pyobj`'s.
Every FFI file is a Python file, `PYTHONPATH=$PYSTACHY_HOME/tools/rt_cpython python3 file.py` is the
oracle, and a program may use only what the twins offer (anything else is a file:line error).
**Pay for use:** programs that do not use it keep byte-identical IR (irsame 1240/1240 plus 69 extra
files), runtime.py is unchanged, nothing includes `Python.h`, and the driver never runs python3.

**Merge order: S0, S1, S3, S2, then S4–S6 when needed.** #4 §4 names an AOT CPython-extension mode
as the candidate, and #108 names #4's "CPython-hosted compiled functions" as the route to packages:
both point at S3, which needs only S1 plus `pyembed.c`'s stdio hooks. S2 (embedding) carries most
of the remaining deviations (Ctrl-C finalization, release timing, scheduling, JIT residuals).

## 1. Pystachy calls C: `@ffi.extern` (JIT and AOT)

### What you write

```python
# cdemo.py
from ffi import extern, string_at, c_int, c_uint, c_void_p


@extern("libz.so.1")
def adler32(adler: c_uint, buf: str, n: c_uint) -> c_uint: ...


@extern("libc.so.6")
def strdup(s: str) -> c_void_p: ...


@extern("libc.so.6")
def free(p: c_void_p) -> None: ...


@extern("libc.so.6")
def atoi(s: str) -> c_int: ...


@extern("libm.so.6")
def copysign(x: float, y: float) -> float: ...


p = strdup("Wikipedia")
s = string_at(p, 9)
free(p)
print(s, adler32(1, s, 9), atoi("-5"), copysign(1.0, -0.0))
for bad in ["a\0b", "x"]:
    try:
        print(atoi(bad) if bad != "x" else adler32(-1, bad, 1))
    except (ValueError, OverflowError) as e:
        print(type(e).__name__, e)
```

```
$ pystachy run cdemo.py                                        # JIT
$ pystachy build cdemo.py && ./cdemo                           # AOT
$ PYTHONPATH=$PYSTACHY_HOME/tools/rt_cpython python3 cdemo.py  # the oracle (ctypes twin)
Wikipedia 300286872 -5 -1.0
ValueError embedded null character
OverflowError can't convert negative int to unsigned
```

All three runs print this today on the prototype, the JIT and AOT runs under GC stress 7
(`SCRATCH/stage6/ex/c`).

### How it keeps the contract

The twin `extern` (`tools/rt_cpython/ffi.py`) binds `ctypes.CDLL(lib or None)` at the decorator,
binds arguments with `inspect.signature` (keywords and defaults as natively), and makes every check
the stub makes, with the same message; ctypes itself checks nothing (`c_int(2**40)` silently
becomes 0). The C integer types are `int` subclasses. `tests/ffi/c_*.out` were recorded by CPython
with the twin; JIT and AOT must match them.

### Boundary rules

| Annotation | C type | Check |
|---|---|---|
| `c_int` / `c_uint` | 32-bit, sign- or zero-extended | `OverflowError` out of range |
| `c_int64`, `c_ssize_t` | 64-bit | |
| `c_uint64`, `c_size_t` | 64-bit | an argument must be ≥ 0; a result must be < 2**63 |
| `c_void_p` | a pointer carried as an int (NULL is 0) | |
| `float` | `double`, passed unchanged (−0.0, inf and NaN included) | |
| `str` (argument) | `const char *` to the str's UTF-8 bytes, valid during the call | `ValueError` for an embedded NUL |
| `c_buf` (argument) | the same pointer, NULs allowed | |
| `str` / `str \| None` (result) | the `char *` is copied | NULL raises `ValueError` / gives `None` |

- **Types.** A bare `int` is a compile error (without the header, the width is unknown). So are
  `bool`, containers, classes, other optionals, a body other than `...`, unannotated parameters,
  `*args`, non-literal library names, `@extern` on a method, one symbol with two signatures (or
  other types than RUNTIME's), the `pys_`/`pyx_`/`PyInit_`/`PyModExport_` prefixes and `main`, the
  library `"python"`, and `ffi.track`/`untrack`/`collected`, which belong to lib/pyobj.py. Structs
  by value, varargs and callbacks are not offered: LLVM IR does not lower the C ABI, so write a small
  C shim with scalar arguments.
- **Lifetimes.** A str argument's pointer is valid only during the call, as with ctypes. A returned
  `char *` is copied at once (free the original with the library's own function). `c_void_p`
  handles are ints, which the conservative GC ignores. Nothing new is rooted.
- **Exceptions.** A missing library raises `OSError`, and a missing symbol `AttributeError`, at the
  `def`, with `dlerror()`'s text, as ctypes does. An extern call has every effect, so inside a
  `try` it is an `invoke`. A C++ exception or `longjmp` across Pystachy frames, or wrong widths, is
  undefined behaviour.
- **Threads.** The runtime stays single-threaded with no TLS; C's own threads must not touch
  Pystachy memory. Inside an extension module an extern call keeps the GIL (ctypes releases it),
  which changes only scheduling.
- **Locale and JIT.** Once an `@extern` is bound, float text uses the C locale whatever `setlocale`
  a C function calls. Under `pystachy run` the library is opened with `RTLD_DEEPBIND`, so lli's own
  libraries (libz, libzstd, libedit, ...) cannot shadow it. `@extern("")` means "the process's own
  libraries", which differ by process (§7): name the library.

### What changes on main

**pystachy.py:**
- `ffi` added to MODULES (5180) and builtin_has (3175);
- `ffi.extern` and `ffi.export` added to INERT_DECOS (5361);
- `ffi.string_at` added to CALLS (5126), and the FFI's RUNTIME entries (5590);
- `ffi` left out of the missing-module message at 3604, which is what keeps irsame exact;
- the `@extern` branch in `declare_fn` (8041; +14 at 8057, beside runtime mode's stub at 8048);
- new `Gen.externtype` and `Gen.cextern` after 9814, which `program()` calls for user externs (10993);
- the `pys_c_bind` call where the `def` runs (13207);
- a program's own `ffi.py` shadows the builtin: Loader.find (3590) and the driver (16674);
- `-ldl` on the AOT link (16781).

**runtime.c:**
- `pys_c_bind`, `pys_c_check`, `pys_c_str`, `pys_cstr` and `pys_string_at`, appended after 2946;
- the locale-free float conversions at 385–1644 (one null test for programs without the FFI).

**Other files:** the extern half of `tools/rt_cpython/ffi.py`, and `tests/ffi/c_*.py` plus
`tests/ffi/errors/c_*.py`.

**Estimated size** (the branch is not yet split): about +165 lines in pystachy.py and +50 in
runtime.c.

## 2. Pystachy calls CPython: `lib/pyobj.py` (JIT and AOT; AOT is the reference)

### What you write

```python
# jsondemo.py
from pyobj import import_module, of_int, of_str, of_list

json = import_module("json")
s = json.attr("dumps").call([of_list([of_int(1), of_str("héllo")])])
print("json:", s)
d = json.attr("loads").call([of_str('{"a": [10, 20, 30]}')])
print(d[of_str("a")][of_int(1)].to_int() + 1)
try:
    json.attr("loads").call([of_str("{bad")])
except ValueError as e:
    print("caught:", e)
s.close()
```

```
$ export PYSTACHY_LIBPYTHON=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
$ pystachy run jsondemo.py                       # JIT: lli -dlopen=$PYSTACHY_LIBPYTHON
$ pystachy build jsondemo.py && ./jsondemo       # AOT: links that libpython with an rpath
$ PYTHONPATH=$PYSTACHY_HOME/tools/rt_cpython python3 jsondemo.py   # the oracle
json: [1, "h\u00e9llo"]
21
caught: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

All three runs print this today, JIT and AOT under GC stress 3 (`SCRATCH/stage6/ex/emb`). Record
oracles with the same CPython minor version as the libpython, because stdlib messages change between
versions.

### How it keeps the contract

The twin `tools/rt_cpython/pyobj.py` is the same API over live objects. pyobj's public surface is
exactly the twin's `__all__`: `Object`, `import_module`, `of_int`, `of_float`, `of_str` and
`of_list`. The compiler enforces this for "GLUE" modules, which are lib modules that use `ffi`
(`Loader.take`, `Loader.qmod`, `Gen.glue_field`). Importing another name, calling `Object(...)` or
reading an Object's fields is a file:line error. Before this rule existed, these gave a segfault, or
compiled natively while the twin raised.

### Boundary rules

- **Types.** Every conversion is an explicit call: `of_int`/`to_int` (64-bit, `OverflowError`
  beyond), `of_float`/`to_float` (`PyFloat_AsDouble`: a str is not parsed, in the twin too),
  `of_str`/`str()`/`repr()` (UTF-8, lone surrogates kept), and `of_list`, an *explicit* copy of a
  `list[Object]` into a new Python list. No container is converted implicitly. Pystachy code reaches Python's containers as Objects,
  without copying. This follows #108 ("initially restrict typed/dynamic adapters to scalars. Do not
  copy mutable containers") and #4 §4 ("keep mutable Python objects as Python objects by default").
- **Lifetimes.** An Object owns one reference; `close()` is idempotent and a closed Object raises
  `ValueError`. Each operation owns a reference to every object it passes to CPython while it runs
  (`_own`). A dropped Object is released once a collection finds it unreachable, at the next pyobj
  operation at any depth (never inside `collect()`), or at exit. Each tracked reference counts 512
  bytes plus `sys.getsizeof` toward the collector's budget (`pys_track`), so dropping large Python
  objects starts collections. At exit the references are released, then `Py_FinalizeEx` runs
  `atexit` handlers and joins non-daemon threads; a failed flush there exits 120, as CPython does.
- **Exceptions.** A Python exception becomes the first class in its `__mro__` that Pystachy has,
  with the same `str()` (`JSONDecodeError` arrives as `ValueError`, in the twin too). `SystemExit`
  keeps its code, `KeyboardInterrupt` stays itself, and if `str(e)` raises, that exception is raised.
- **Threads and the GIL.** CPython starts on pyobj's first import with `Py_InitializeEx(0)` (no
  Python signal handlers). Before that, `pye_preinit` applies PEP 538 coercion and PEP 540 UTF-8
  mode and sets the program name from the loaded libpython, so `sys.executable`, `subprocess` and
  `multiprocessing` (forkserver on 3.14+) run the same CPython. The program holds the GIL only
  inside an operation, so Python threads run while compiled code runs. A SIGINT that reaches a
  CPython thread is forwarded to the main thread.
- **Stdio: one stdout, one stdin.** Before an operation runs Python code, Pystachy's pending output
  is written; before Pystachy writes after one, Python's `sys.stdout`/`sys.stderr` is flushed. A
  replaced `sys.stdout` (`redirect_stdout`, `None`) receives Pystachy's prints, and `input()` and
  `sys.stdin` go through Python's `sys.stdin` (runtime.c's `std_hook` and `in_hook`, set by
  `pyembed.c`).
- **JIT residuals.** JIT and AOT agree on every probe, but under `pystachy run` the embedded
  CPython loads extension modules with `RTLD_DEEPBIND` (so `readline` gets libreadline, not lli's
  libedit; `sys.getdlopenflags()` shows it), and `@extern("")` sees lli's process. AOT is therefore
  the reference tier for embedding.

### What changes on main

**pystachy.py:**
- the GLUE rules (Loader 3634–3637, 4785, 4860–4884; `Gen.glue_field` after 8547 and its calls at
  9559, 13302 and 14083; the constructor check at 15399; ffi.track only in lib at 4654 and 16026);
- the `"python"` library token and the libpython ≥ 3.12 floor in the driver (16684–16687);
- `-dlopen=$PYSTACHY_LIBPYTHON` and `-extra-object=pyembed.o` on the lli line (16798);
- libpython with an rpath on the AOT link (16781).

**runtime.c:**
- the tracked-reference table, swept after `files_sweep` (222/234), with counters in
  `PYSTACHY_GC=stats` (310);
- `finish_hook` in `pys_finish` (1814–1828);
- `std_hook` in `put1` (1853) and `pys_file_flush` (2059);
- `in_hook` in `pys_input` (1890) and `read1`/readline (2013–2015).

**New files:** `lib/pyobj.py` (479 lines), `pyembed.c` (317, shared with S3), the pyobj twin (143),
and `tests/ffi/py_*.py`.

**Estimated size:** about +50 lines in pystachy.py and +60 in runtime.c.

## 3. CPython calls Pystachy: `pystachy ext` (AOT only)

### What you write

```python
# fastmath.py
from ffi import export


@export
def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@export
def check(n: int) -> int:
    if n < 0:
        raise ValueError(f"negative: {n}")
    return _twice(n)


def _twice(n: int) -> int:  # private: not exported, any type is fine
    return n * 2
```

```python
# client.py: plain Python
import fastmath

print(fastmath.fib(90), fastmath.check(4))
for f in [lambda: fastmath.check(-5), lambda: fastmath.fib(2**64), lambda: fastmath.fib(n=3)]:
    try:
        f()
    except Exception as e:
        print(type(e).__name__, e)
```

```
$ pystachy ext fastmath.py                 # fastmath.abi3.so  (3.12+ GIL; defines only PyInit_fastmath)
$ pystachy ext fastmath.py --abi abi3t     # fastmath.abi3t.so (3.15+; defines only PyModExport_fastmath)
$ python3 client.py                                             # with the .so
$ PYTHONPATH=$PYSTACHY_HOME/tools/rt_cpython python3 client.py  # the oracle: the source module
2880067194370816120 8
ValueError negative: -5
OverflowError int too big to convert
TypeError fib() takes no keyword arguments
```

The .so run (GC stress 1) and the source run print this identically today
(`SCRATCH/stage6/ex/ext`). `fib(90)` from the same build also ran on 3.12.3, 3.14.8 and 3.15.0
(abi3) and on 3.15.0t (abi3t). On 3.14t the guard's `ImportError` names the abi3t module.

### How it keeps the contract

The source module is the oracle. The twin `ffi.export` wraps each function with the trampoline's
exact semantics: owner thread only, no keywords, exact arity, the 64-bit range check,
`__index__`/`__float__` coercions, bool exactly `True`/`False`, results range-checked with
Pystachy's message, and exceptions rebuilt as below. To keep the two equal by construction, every
public function in ext mode must be `@export` (or be named `_x`), Pystachy code may not call an
`@export` function, and a public class or variable is an error.

### Boundary rules

- **Types.** Positional `int` (int64), `float`, `bool` and `str` in; the same or `None` out. No
  defaults, `*args` or keyword-only parameters yet. A str is copied once as UTF-8.
- **Exceptions.** Every entry ends in a catch-all landing pad, so no Pystachy exception unwinds
  through CPython frames (letting it unwind leaked a reference per crossing and broke the
  interpreter with RecursionError after about 1000 crossings, stage 2). An exception leaves as the
  builtin class of its name, or the nearest builtin base of a module's own class, with `args`
  rebuilt from their repr: `KeyError('zz')`, `ValueError('bad', 7)` and `SystemExit('so long')`
  match CPython.
- **Lifetimes.** Values are copied both ways; no Pystachy pointer reaches CPython. Module globals
  are rooted. The outermost entry sets the stack bottom, and a depth counter (`pys_enter`/
  `pys_leave`) keeps it during nested re-entry. An `atexit` handler releases every tracked reference
  and closes the module's files before module teardown; later calls raise `RuntimeError`. One
  successful import per process (a failed one may be retried). Exported functions have the module
  as `__self__`, so they pickle by name and `multiprocessing` works.
- **Threads and the GIL.** Only the importing thread may call (`RuntimeError` otherwise, in the twin
  too). Compiled code holds the GIL, but it changes hands during pyobj call-outs and `print`'s
  writes, so safety rests on the owner-thread check. abi3t declares `Py_mod_gil` = used: 3.15t turns
  the GIL on with CPython's RuntimeWarning, and `PYTHON_GIL=0` makes the import fail. An `.abi3.so`
  raises `ImportError` on 3.13t and 3.14t (they load it but cannot use it), and in a subinterpreter.
  Stack switching (greenlet) is unsupported and not detected.
- **Stdio.** `print` goes to the host's `sys.stdout` (`redirect_stdout` works; `None` prints
  nothing), and `input()` reads the host's `sys.stdin`.

### Why AOT only

- CPython imports shared objects, and `pystachy run` execs lli as another process (pystachy.py:16798).
- An in-process ORC JIT does work (stage 1, through ctypes and libLLVM 18, and through llvmlite), but:
  - it brings a 117–123 MB libLLVM, or llvmlite 0.50.0 (a 56.9 MiB wheel, 173 MiB installed,
    LLVM 22.1.0, which does not promise to read LLVM 18 textual IR);
  - it relies on an LLJIT C API whose header says "NOT stable", and on libgcc_s loaded RTLD_GLOBAL;
  - RSS was 65 MiB against 9 MiB.
- The .so imports in 0.27–0.45 ms. The development loop is S5's compile-on-import cache, which is
  still AOT.

### What changes on main

**pystachy.py:**
- `Gen.pyext` (after 9814);
- `program()` emits the module instead of `@main` (11135), and records the module's variables for
  the ext rules (11168), with `self.eh` on in ext mode (10837);
- `__name__` is the module's name (Loader 4520);
- the rejection of Pystachy calls to `@export` functions (15593);
- `compile_program` takes the ext name (16595);
- the `ext` command and its build steps (16631, 16773–16776): llvm-link of program, pyext and
  pyembed; `--only-needed` with the runtime; `opt internalize` keeping only the entry; `clang -shared`.

**runtime.c:** library mode, appended after `pys_init` (1866–1884): `pys_init_lib`, `pys_enter`,
`pys_leave` and `lib_depth`; plus `defenc` restoring the host's LC_CTYPE (1768).

**New files:** `pyext.c` (257 lines, one file for both ABIs; `-DPYX_ABI3T` selects abi3t), the
`export` twin (about 70), `tools/abi_check.sh` (28), and `tests/ffi/ext/`.

**Estimated size:** about +130 lines in pystachy.py and +50 in runtime.c.

## 4. CPython ABI targets, and why

- **abi3, floor 3.12** (wheel tag `cp312-abi3`).
  - 3.12 is the first version whose stable ABI has `PyErr_GetRaisedException`, `PyObject_Vectorcall`
    and `PyObject_VectorcallMethod`, which the glue uses.
  - 3.11 is deliberately excluded, although it has security support until 2027-10. An abi3 module
    there fails with the loader's generic `ImportError` (undefined `PyErr_GetRaisedException`).
  - Entry: `PyInit_<name>`, multi-phase init. `PyInit_` is only soft-deprecated by PEP 793.
- **abi3t, 3.15+** (PEP 803, Final; wheel tag `cp315-abi3.abi3t`).
  - Entry: `PyModExport_<name>` (PEP 793, Final), returning a PEP 820 slot array with `Py_mod_abi`.
  - `None`, `True` and `False` come from `Py_GetConstantBorrowed`.
  - It is the only stable-ABI way to free-threaded builds.
- **Both from one IR.** With both files in one directory:
  - 3.12 to 3.15 GIL builds load the `.abi3.so`, because 3.15 lists `.abi3.so` before `.abi3t.so`;
  - 3.15t loads the `.abi3t.so`;
  - 3.13t and 3.14t get the guard's `ImportError`.

  **Gap:** free-threaded 3.13t and 3.14t cannot use Pystachy modules. PEP 779 made 3.14t officially
  supported. See open decision 4.
- **Header-free glue.** `pyext.c` and `pyembed.c` declare only the stable-ABI functions they call.
  - The ABI is then what the glue declares, not what some installed header says.
  - Building an extension needs no Python install.
  - `tools/abi_check.sh` (sh, nm and awk) checks that only the entry is defined and that every Py
    import is in the stable ABI of the target version. It needs `Misc/stable_abi.toml`.

  (`pystachy ext` is not part of the Python-free stage, so "Python.h would break that stage" is
  *not* the reason.)
- **Embedding** takes any shared libpython ≥ 3.12, GIL or free-threaded; the driver refuses an older
  one. It uses stable-ABI calls plus a few interpreter-level ones:
  - `Py_InitializeEx`, `Py_FinalizeEx`, `PyGILState_*` and `PyEval_SaveThread`;
  - the deprecated `Py_SetProgramName`;
  - `Py_UTF8Mode`, found with dlsym.

  An AOT binary is tied to the libpython it links.
- **Not targeted.**
  - HPy: its README says it is "no longer actively maintained".
  - The PyNI draft: it has no PEP number.
  - PEP 809 abi2026: still a Draft, re-checked 2026-10-11.

## 5. Why not the alternatives

| Alternative | Why not |
|---|---|
| A JIT inside CPython (ORC through libLLVM's C API, or llvmlite) | It works, but costs 117–123 MB of libLLVM, or llvmlite's 173 MiB installed. Other measured costs: 23 ms to compile (735 ms with the runtime as bitcode), 65 vs 9 MiB RSS, an LLJIT C API marked "NOT stable", and libgcc_s made global. llvmlite is LLVM 22, while Pystachy emits LLVM 18 text. The AOT .so imports in under 0.5 ms, and S5 covers the edit loop. |
| typed-ir.md §7.4's CPython lowering now (containers as PyObjects, refcounts from liveness) | Blocked on recoverable elaboration and on step 16: loads, stores and arithmetic are still raw ops holding LLVM text (typed-ir.md, Status: about 58,000), and step 16's re-baseline has not started. It would also re-baseline the compiler's own IR. The wrapper approach ships now behind the same `@export` entry points, and §7.4 can replace the wrappers later. |
| HPy, PyNI, PEP 809 | HPy is unmaintained, PyNI has no PEP number, and PEP 809 is a Draft. abi3 and abi3t are Final and shipping. |
| Glue built against `Python.h`, or version-specific builds | No speed gain: stage 2 (SOTA's E1) measured about 16 ns per call for version-specific, abi3 and abi3t builds alike. Headers make the ABI whatever is installed and require a Python install to build. A header-free version-specific build stays possible for 3.14t (open decision 4). |
| One shared `libpystachy` runtime across extensions | It would need a stable ABI for the runtime across Pystachy versions, would lose the whole-program `-O2`/LTO inlining that `pystachy build` relies on, and would merge heaps and root sets. Each module instead carries its own internalized runtime (a 79.6 KB .so). The per-program `pys_obj_*` callbacks are *not* the obstacle: they could be registered at init. |
| Header importers in the compiler (libclang, Zig translate-c, bindgen) | Each is a second toolchain of libclang or Aro size. Zig moved translate-c out of the language. Typed stubs are what Codon, Julia `@ccall` and LPython use. |
| Copying containers across the boundary (the draft's S4) | Dropped because of #108: identity and shared mutation need an explicit contract first. |
| A JIT for CPython calling Pystachy through lli | lli is a separate process. #108 confirms that the JIT driver is not a resident service. |

## 6. Staged plan

The prototype has S1–S3 in one branch; splitting it into PRs is still to do, and the split is
clean (S1: cextern, CTYPES, the extern runtime functions, twin and `c_` tests; S3: pyext.c, library
mode, Gen.pyext, the ext rules, pyembed.c's stdio hooks; S2: pyobj, pyembed.c's embedding part, the
track table, the finish hook).

| Stage | What changes | Acceptance |
|---|---|---|
| **S0** Decision record | `docs/ffi.md` (338 lines in the prototype) as #4 §4's architecture decision. `docs/history.md:73` moves from open to decided. Links from language.md and testing.md. | Reviewed before code. Each claim cites §9's evidence. |
| **S1** `@ffi.extern` | As §1. About +165 pystachy.py and +50 runtime.c lines, plus the extern twin (~110). | `make` reaches the fixed point and runtime.py's IR is unchanged. `make irsame REF=<parent>` is all identical. `tests/run.sh`, check-ir, check_runtime, rtabi and lint pass. `tests/ffi/c_*` match their twin-recorded `.out` in JIT and AOT under GC stress 7. Every `errors/c_*` gives its message. **Still to add:** run the `c_` and error cases in verify's python-free stage (it runs only tests/run.sh today, although these cases need no Python). |
| **S3** `pystachy ext` | As §3. About +130 pystachy.py and +50 runtime.c lines; pyext.c, the export twin, abi_check.sh, and pyembed.c's stdio hooks. | abi_check passes for each module. Clients are identical to source+twin on 3.12, 3.13 and 3.14 (abi3), on 3.15 (abi3 and abi3t) and on 3.15t (abi3t), under GC stress 1 and UBSan trap mode. The guards hold: 3.13t, 3.14t, `PYTHON_GIL=0` and 3.11. memclient's peak RSS is bounded and wrclient's file contents after exit match. Each call costs ≤ 30 ns net and import takes ≤ 1 ms. **Still to add:** `__text_signature__` and docstrings in `ml_doc`, and wiring abi_check into verify and CI (vendor `stable_abi.toml`). |
| **S2** `lib/pyobj.py` | As §2. About +50 pystachy.py and +60 runtime.c lines; lib/pyobj.py, its twin, and pyembed.c's embedding part. | `tests/ffi/py_*` are identical to the twin on 3.12, 3.13, 3.13t, 3.14, 3.14t, 3.15 and 3.15t, in JIT and AOT, under GC stress 3. `py_big` peaks below 200 MiB without stress. Live and pending reference counts are 0 at exit. 3.11 is refused by the driver. |
| **S4** Wider boundary, each piece optional | `@export` keywords and literal defaults. A **zero-copy buffer** (`Object.buffer()` over `PyObject_GetBuffer`/`PyBuffer_Release`, stable since 3.11, with a stated lifetime), which #4 §4 asks to prioritize. Exported exception classes. Optional C prototype strings checked against `@extern`. A buffer helper for vectorcall in pyobj. `@export(ascii=True)`. Optionally a cp314t build. **No copied containers** (#108). | Each piece matches the twin, and programs that do not use it keep identical IR. |
| **S5** Compile on import (still AOT) | A meta-path finder for `# pystachy: ext` modules, caching `.so` files under `__pycache__`, keyed by the hashes of the source, compiler, runtime, glue and ABI. | Cache invalidation, concurrent importers, and the oracle with the hook off. **Cold-import target to be set after profiling:** `pystachy ext` takes 671 ms against 150 ms for `pystachy build` of the same file, so the draft's 200 ms target is unvalidated. |
| **S6** Callbacks, objects, threads (when needed) | Callbacks built on #108 Candidate A's function objects and boxed calling convention (#8, #9), through catch-all trampolines. A pin table for exported objects. Any-thread entry through the TLS-free, GIL-serialized segment switch (stage 2: 0 of 200 runs wrong, against 199–200 of 200 with per-thread bottoms). Cross-runtime cycles documented as leaks plus weak references (as PEP 818, JPype, nanobind on PyPy). A `PyCriticalSection` world lock must park state at every call-out: it is suspended whenever its thread detaches. | Each piece passes under GC stress. `pystachy run` still works for the whole corpus (the guard against native TLS). Pin and handle counts are 0 at exit. |

## 7. Deviations to document

Against CPython running the same files with the twins. All but the last bullet are already in the
prototype's `docs/ffi.md`.

- **str** is byte-indexed UTF-8 in either direction (the existing deviation; #120). A C string that
  is not UTF-8 is read as it is, where the twin raises `UnicodeDecodeError`.
- **`@extern("")`** sees whatever the process has loaded: python3 links libz, lli has LLVM's
  dependencies, an AOT build only libc and libm (`zlibVersion`: found by the twin and the JIT,
  `AttributeError` at the `def` in AOT). **JIT embedding** shows `RTLD_DEEPBIND` in
  `sys.getdlopenflags()`.
- **pyobj exceptions** are the nearest Pystachy class (`JSONDecodeError` → `ValueError`).
- **Release timing:** `__del__` and weakref callbacks run after a collection; a file written through
  a dropped Object gets its data only then (`close()` it); `sys.getsizeof` is shallow; peak memory
  stays about one collector budget (32 MiB) above CPython's.
- **Stdio:** the text order is defined, not when bytes reach the fd (`os.write`, children and C
  stdio may interleave differently); stdin that C stdio read ahead before pyobj's import is not
  Python's; thread-dependent order is not defined by the oracle.
- **Embedding:** `sys.path[0]` is the executable's directory in AOT; the CPython-hosted compiler
  passes its own PEP 538 `LC_CTYPE` on; **Ctrl-C** ends the program at once, so CPython is not
  finalized (no `atexit`, no thread joins, Python's buffered output lost), except during the
  program's own write; float text is the C locale's whatever Python's `setlocale` says.
- **Extension modules:** the 64-bit boundary; an exception raised at import leaves as its nearest
  builtin class; one import per process; importing thread only; the GIL rules above; no re-entry
  from `sys.stdout`/`stderr`/`stdin` while the module does I/O; `sys.stdout.write` with
  `sys.stdout = None` is a no-op; calls after the host's `atexit` handlers raise `RuntimeError`; out
  of memory inside a collection, or out of stack, ends the host.
- **Not yet in docs/ffi.md:** exported functions have no `__doc__` or signature
  (`inspect.signature(m.fib)` raises `ValueError` on the .so; checked today; S3 should set `ml_doc`);
  import from a subinterpreter raises `ImportError` (checked today, 3.14 `concurrent.interpreters`);
  spawn/forkserver workers do not re-run the main script's top level, since the embedded `__main__`
  has no `__file__` (stage-4 refuter's finding, not re-run); a daemon thread that `pthread_exit`s
  through compiled frames at finalization leaves `lib_depth` raised, harmless only because the
  process is ending.

## 8. Open decisions for the maintainer

1. **Merge order.** S1 → S3 → S2 (recommended, for #4 §4 and #108), or S1 → S2 → S3, which puts the
   smaller pyobj surface first.
2. **Default `--abi`.** abi3 (recommended: 3.12–3.15 GIL builds today) or abi3t. For wheels, ship
   both side by side.
3. **abi3 floor.** 3.12 (recommended), or 3.13. A 3.13 floor would allow `PyList_GetItemRef` and
   `Py_GetConstantBorrowed` everywhere. Either way 3.11 is excluded while it still has security
   support.
4. **Free-threaded 3.13t and 3.14t.** Leave the gap (only 3.15t is served), or add a header-free
   version-specific cp314t build. pyext.c's only layout dependency there is the free-threaded
   `PyObject` header inside `PyModuleDef`.
5. **Embedded stdout cost.** Exact order costs about 440 ns on a Pystachy `print` right after a
   pyobj operation (540 vs 100 ns). The alternative is to route all of Pystachy's output through
   `sys.stdout` once CPython is embedded: one buffer, simpler, with a per-print cost.
6. **Ctrl-C in embedding.** Accept the deviation, or design a deferred finalization (the handler
   cannot run Python).
7. **str at the extension boundary.** Convert, with byte semantics inside (prototype behaviour), or
   reject non-ASCII by default (typed-ir §7.4's "check or reject"). #120 makes this matter for text
   libraries.
8. **Deprecated embedding APIs.** `pyembed.c` uses `Py_SetProgramName` and `Py_UTF8Mode`. Accept
   them, or move to PEP 741's `PyInitConfig`, which is not in the Limited API.
9. **CI coverage.**
   - Vendor `Misc/stable_abi.toml`, so abi_check can run in verify and CI.
   - Make the `ffi` step fail, rather than skip, when python3 has no shared libpython. The step
     still passes when it skips the embedding and extension cases.
   - Add the `c_` cases to the python-free stage.
10. **Platforms.** x86-64 Linux with glibc only, or also AArch64 Linux and macOS. macOS needs
    `-undefined dynamic_lookup` and has no `RTLD_DEEPBIND`.
11. **Finding libpython.** `PYSTACHY_LIBPYTHON` only, or also a `--libpython` flag.

## 9. Evidence

### The prototype on current main

The checks below come from the fix round's report and logs (`SCRATCH/stage5/logs`). Most of them ran
on `d89c8b9`. The final commit `4051925` changes only one line of `tests/ffi/ext/wrclient.py`, and
`make verify` and the 3.14 and 3.15t FFI runs were repeated on it.

| Check | Result |
|---|---|
| `make` (three-stage fixed point) | stage1 == stage2 == stage3, 225,035 lines of IR; runtime.py rt1 == rt2 == rt3, 10,393 lines, byte-identical to base's compiler |
| `make irsame REF=base` (4dc548a) | 1240 programs identical, including `tests/ffi_own.py` (a program with its own ffi.py), plus 69 files outside the corpus |
| `tests/run.sh` (JIT and AOT) | 1933 passed, 0 failed |
| check_runtime / rtabi / check-ir | 276 entries and 69 exception classes agree / 76 functions, 2524 uses, 596 programs, 0 mismatches / 597 programs accepted |
| `make lint` | exit 0 with ruff 0.16.8 (the pin is 0.17.0) and shellcheck 0.11.0, including clang `-Werror` on pyext.c (both ABIs) and pyembed.c |
| `tests/ffi/run.sh` (93 cases) | 93/0 on 3.12, 3.13, 3.14, 3.15 and 3.15t; 72/0 on 3.13t and 3.14t (ext skipped by design); 34/0 on 3.11 (below the floor); 91/0 with `python3 -m pystachy` (py_coerce skipped, documented). Re-run today on 3.13: 93/0. |
| The new tests against the pre-fix FFI (the stage-3 port on 4dc548a) | 54 passed, 39 failed when re-run today (the fix report recorded 54/37): the suite catches the refuters' issues |
| `probe5.sh` (S1, S2 on 7 CPythons in JIT and AOT, S3 on 5 CPythons plus guards) | 215 same, 0 different; 3 documented deviations observed exactly as documented |
| `refute5.sh` (every case of the 15 refuter issues) | 64 same, 0 different; 2 documented deviations observed |
| UBSan trap mode over all three directions | 46 same, 0 different; trap instructions present (140 in zstats.exe, 272 in jsondemo.exe, 234 in fastmath.abi3.so) |
| `make verify` on 4051925 (not dirty) | 19/19 steps in 694 s: tests-cpython, tests-native, tests-opt-off, python-free and gc-stress 1933/0 each; ubsan 2718/0; ffi 93/0 |
| Patch | applies cleanly to 4dc548a (re-checked today) |
| This document's three examples | identical across twin, JIT and AOT (C, embedding), and across source+twin and the .so (ext), checked today |

**History.** Three stage-4 refuters found 15 blocking issues in the stage-3 port: −0.0 lost through
`@extern`; lli's libraries shadowing `@extern` libraries and embedded readline; segfaults
(`Object(5)`, a raising `str()`); twins that did not specify the native API; two stdio buffers;
unbounded memory from dropped large objects (2871 MiB against the twin's 27); no release at the
host's exit; the compat-config locale and `sys.executable`; `LC_NUMERIC` breaking float text;
unchecked NULLs. All 15 were fixed in `d89c8b9` and re-checked by `refute5.sh` above. The fixes have
**not** had an independent refutation pass of their own.

### Measurements

All on a 4-CPU Xeon (`SCRATCH/stage5/logs/measure.log`; import times from
`SCRATCH/stage6/import-time.log`).

- **@extern call** (libm `hypot` through the stored pointer, AOT): 3.9 ns, against 3.7 ns for the
  stage-3 direct call.
- **Extension call**, net of the loop, 3.13 abi3: `check(4)` 18.1 ns, against 223 ns through ctypes
  and 24.1 ns for pure Python; `fib(10)` 20.0 ns. The stage-3 build measured 19.8–22.4 ns on 3.12,
  3.14, 3.15 and 3.15t.
- **Extension import**, median of 21 fresh processes, final build: 0.39 ms (3.12), 0.39 ms (3.13),
  0.38 ms (3.14), 0.27 ms (3.15), 0.45 ms (3.15t abi3t).
- **Extension size and build:** the .so is 79,600 bytes (abi3) or 79,392 (abi3t); `pystachy ext`
  takes 671 ms with warm caches.
- **pyobj operations**, embedded 3.13, AOT: `of_int(i).to_int()` 122 ns;
  `neg.call([of_int(i)]).to_int()` 523 ns; `len(o.attr(n))` 327 ns (189 before the owned references
  and the `sys.getsizeof` charge); a print after an operation 540 ns, against 46 ns alone. Under
  CPython with the twin, the first two took 207 and 606 ns (stage 3).
- **Start-up, AOT, median of 21:** hello 3.01 ms; an `@extern` of libm 2.93 ms; embedding 3.13
  13.73 ms. CPython's start and finalization cost about 10.7 ms.
- **Start-up, JIT** (`pystachy run`, compile included): 46.9 ms for `@extern` of libm, 94.9 ms for
  embedding.
- **Peak RSS of dropped large objects**, twin vs native:

  | Case | Twin | Native | Stage 3 |
  |---|---|---|---|
  | 300 × 10 MB | 27 MiB | 67 MiB | 2871 MiB |
  | 3000 × 1 MiB | 11 MiB | 44 MiB | 3022 MiB |
  | 1000 × 1 MiB inside one extension call | 14 MiB (source) | 42 MiB | 1013 MiB |

- **Many small drops:** 3,000,000 dropped `of_int` Objects take 48 collections, about 7 ms of GC
  in all (6.9 and 7.1 ms in two runs), and a 3.0 MiB heap peak.

### What was not run or not verified

- No independent refutation of the stage-5 fixes; not run on GitHub CI.
- Only x86-64 Linux (Ubuntu 24.04, glibc, LLVM 18.1.3). 3.13t–3.15t are python-build-standalone
  builds; 3.15.0 is two days old; no distribution build was tried.
- The UBSan runtime had to be installed in this container (libclang-rt-18-dev). The final lint used
  ruff 0.16.8; the pinned 0.17.0 ran (stage-4 refuter) on the stage-3 tree only.
- `tools/abi_check.sh` is not in verify or CI; `tests/ffi/c_nosym.out` records Debian's libm path.
- Per-call cost after the fixes was measured on 3.13 only. S4–S6 are designs only.

## 10. Where things are

- Prototype tree: `SCRATCH/stage3/tree` (branch `ffi`, base `4dc548a`). Patch:
  `SCRATCH/stage3/ffi-prototype.patch`.
- The prototype's user guide and decision record: `docs/ffi.md` in that tree.
- Logs: `SCRATCH/stage5/logs/` (all.log, probe.log, refute.log, ubsan.log, verify.log,
  verification.json, measure.log).
- Scripts: `SCRATCH/stage5/{all5,probe5,refute5,ubsan5}.sh`.
- Today's checks: `SCRATCH/stage6/` (`ex/`, `import-time.log`, `ffi-3.13-recheck.log`,
  `ffi-prefix-compiler.log`).
- Earlier stages: `SCRATCH/stage1/digest.txt` (research) and `SCRATCH/stage2out/` (proposals,
  judgments, the draft, refutations).
- The stage-4 refuters' fixtures: `SCRATCH/stage4/`, `SCRATCH/stage4rec/` and
  `SCRATCH/stage3/refute-interop/`.
