# `subprocess` and `inspect` in MicroPython, PyPy and GraalPy

Research date: 2026-11-12. Sources are the projects' own repositories and docs.

## How to read this file

- Every finding ends with its source URL. GitHub URLs are pinned to the commit SHAs below.
- **[Inference]** marks a conclusion I drew from the cited code rather than a statement the
  source makes. Nothing here was verified by running any of the three implementations.
- "Diff" findings come from comparing the project's vendored file against the matching
  CPython tag with `diff -u`.

| Short name | Repository and ref | Commit |
|---|---|---|
| MP | `micropython/micropython`, branch `master` | `d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645` |
| MPL | `micropython/micropython-lib`, branch `master` | `92ee97d94c4b558cf4e6d27a4534401f1e9b9f50` |
| PYPY | `pypy/pypy`, branch `py3.11` | `3ce8ee955977343ff96902fdedbc5dad535d0f95` |
| PYPY27 | `pypy/pypy`, branch `main` (the 2.7 line) | `a41581967716bc5d9cdd1c1cf4a77ea0455af277` |
| GP | `oracle/graalpython`, branch `master` | `cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5` |

CPython baselines for the diffs:

- PyPy: tag `v3.11.17`, because `lib-python/stdlib-version.txt` says "the output for git status is: v3.11.17".
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/stdlib-version.txt>
- GraalPy: tag `v3.13.14`, because `PythonLanguage.java` has `MAJOR = 3`, `MINOR = 13`, `MICRO = 14`.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/PythonLanguage.java#L189-L191>
- CPython files: `https://raw.githubusercontent.com/python/cpython/<tag>/Lib/{subprocess,inspect}.py`.

---

## 1. MicroPython

### subprocess

- **There is no `subprocess` module today, in core or in micropython-lib.** A recursive
  listing of both trees at the pinned commits has no path containing `subprocess`. In the
  core tree the only `inspect` matches are `tests/cmdline/repl_inspect*` and
  `repl_micropyinspect*`, which test the REPL `-i` flag.
  <https://github.com/micropython/micropython-lib/tree/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50> and
  <https://github.com/micropython/micropython/tree/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645>

- **micropython-lib used to ship an empty placeholder.** A top-level `subprocess/` package
  was added on 2014-05-08 ("subprocess: Add dummy module.") and removed on 2020-03-20
  ("top: Remove all empty packages."). `subprocess.py` was 0 bytes and `metadata.txt` said
  `srctype=dummy`. Its `setup.py` described the purpose: "This is a dummy implementation of
  a module for MicroPython standard library. It contains zero or very little functionality,
  and primarily intended to avoid import errors (using idea that even if an application
  imports a module, it may be not using it onevery code path, so may work at least
  partially)."
  - Last tree that had it: <https://github.com/micropython/micropython-lib/tree/eae01bd4e4cd1b22d9ccfedbd6bf9d879f64d9bd/subprocess>
  - Added: <https://github.com/micropython/micropython-lib/commit/5b23b9014ddd595cbdfa561ba4e142e217659dbd>
  - Removed: <https://github.com/micropython/micropython-lib/commit/444b45e4311f00270a9efa466429751c5e3ca619>

- **The only maintainer statement I found is an issue reply.** In micropython-lib issue
  #122 ("How to use subprocess in Micropython", 2016-11-22), dpgeorge (GitHub "Member")
  answered: "The subprocess module is not implemented. You can try using os.system instead."
  <https://github.com/micropython/micropython-lib/issues/122>

- **The unix port's built-in `os` offers `system` only, as far as process creation goes.**
  `ports/unix/modos.c` defines `getenv`, `putenv`, `unsetenv`, `system` and `errno`.
  `system` is a direct libc call:
  ```c
  MP_THREAD_GIL_EXIT();
  int r = system(cmd);
  MP_THREAD_GIL_ENTER();
  RAISE_ERRNO(r, errno);
  return MP_OBJ_NEW_SMALL_INT(r);
  ```
  <https://github.com/micropython/micropython/blob/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/ports/unix/modos.c#L82-L93>

- **`os.system` is a build-time option, on for the standard unix variants.**
  `mpconfigvariant_common.h` sets `#define MICROPY_PY_OS_SYSTEM (1)`, and `extmod/modos.c`
  registers `system` under `#if MICROPY_PY_OS_SYSTEM`. The module table in `extmod/modos.c`
  has no `popen`, `fork`, `exec*`, `waitpid` or `kill` entries. The `coverage`, `longlong`,
  `nanbox` and `standard` variants include the common header.
  - <https://github.com/micropython/micropython/blob/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/ports/unix/variants/mpconfigvariant_common.h#L96-L100>
  - <https://github.com/micropython/micropython/blob/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/extmod/modos.c#L163-L247>

- **`python-stdlib/os` adds no process functions.** It is `from uos import *`, an optional
  `path` import, and a `stat_result` namedtuple wrapper around `stat`.
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/python-stdlib/os/os/__init__.py>

- **`unix-ffi/os` adds the POSIX process primitives by calling libc through FFI.** The
  bindings are declared with `ffilib`:
  ```python
  fork_ = libc.func("i", "fork", "")
  pipe_ = libc.func("i", "pipe", "p")
  _exit_ = libc.func("v", "_exit", "i")
  getpid_ = libc.func("i", "getpid", "")
  waitpid_ = libc.func("i", "waitpid", "ipi")
  system_ = libc.func("i", "system", "s")
  execvp_ = libc.func("i", "execvp", "PP")
  kill_ = libc.func("i", "kill", "ii")
  ```
  The Python-level functions are `fork`, `pipe`, `_exit`, `execvp`, `getpid`, `waitpid`,
  `kill`, `system` and `popen`. `environ` is the placeholder `{"WARNING": "NOT_IMPLEMENTED"}`.
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/unix-ffi/os/os/__init__.py#L29-L57>

- **`unix-ffi` `os.popen` is `pipe` + `fork` + `dup` + `system` + `_exit`, with no `exec`.**
  ```python
  def popen(cmd, mode="r"):
      import builtins
      i, o = pipe()
      if mode[0] == "w":
          i, o = o, i
      pid = fork()
      if not pid:
          if mode[0] == "r":
              close(1)
          else:
              close(0)
          close(i)
          dup(o)
          close(o)
          s = system(cmd)
          _exit(s)
      else:
          close(o)
          return builtins.open(i, mode)
  ```
  **[Inference]** The parent returns a plain file object and `popen` never calls `waitpid`,
  so the caller gets no exit status and the child is not reaped by this function.
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/unix-ffi/os/os/__init__.py#L297-L316>

- **These were added piecemeal by the original author.** `system()` on 2014-07-04,
  `execvp()` on 2015-10-11, `popen()` on 2016-12-21.
  - <https://github.com/micropython/micropython-lib/commit/4e3154ba21a385bc97d15985c413e1dc17e4dfb5>
  - <https://github.com/micropython/micropython-lib/commit/a1cf086eb389780358e40bda1bb9ce798117c6f9>
  - <https://github.com/micropython/micropython-lib/commit/d47419bb73993580eea677b548b1ce526845ebd2>

- **The `unix-ffi` directory is declared unmaintained.** Its README says: "These are
  packages that will only run on the Unix port of MicroPython, or are too big to be used on
  microcontrollers." and "**Note:** This directory is unmaintained."
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/unix-ffi/README.md>

- **The "differences from CPython" material has no `subprocess` or `inspect` entry.** The
  module-level difference pages are generated from `tests/cpydiff/modules_*.py`; the files
  there cover only `array`, `errno`, `json`, `os` (`environ`, `getenv`), `random`, `struct`
  and `sys`. `docs/library/os.rst` does not document `system`.
  <https://github.com/micropython/micropython/tree/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/tests/cpydiff>

### inspect

- **`inspect` lives only in micropython-lib, as one 149-line pure-Python file**
  (`manifest.py`: `metadata(version="0.2.1")`). Core has no `inspect` module.
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/python-stdlib/inspect/inspect.py>

- **Stated intent, from the 2015 commit that created it:** "Only few most obvious functions
  are implemented, several more added with dummy implementation. The intention of this
  module will likely always stay to be able to run software which depends on this module
  for exceptional parts (like error reporting), not to actually inspect objects."
  <https://github.com/micropython/micropython-lib/commit/7eb7eba659854fdd9223bbd3398dc3603c856e80>

- **Full list of what the file defines, and how** (same URL as the first bullet):

  | Name | Kind | Implementation |
  |---|---|---|
  | `getmembers(obj, pred=None)` | real | `dir(obj)` + `getattr`, optional predicate, sorted list of `(name, value)` |
  | `isfunction(obj)` | real | `isinstance(obj, type(isfunction))` |
  | `isgeneratorfunction(obj)` | real | `isinstance(obj, type(_g))` where `_g = lambda: (yield)` |
  | `isgenerator(obj)` | real | `isinstance(obj, type((_g)()))` |
  | `iscoroutinefunction` | alias | `= isgeneratorfunction` |
  | `iscoroutine` | alias | `= isgenerator` |
  | `ismethod(obj)` | real | `isinstance(obj, type(_Instance.meth))` (bound-method type) |
  | `isclass(obj)` | real | `isinstance(obj, type)` |
  | `ismodule(obj)` | real | `isinstance(obj, type(sys))` |
  | `getargspec(func)` | stub, raises | `raise NotImplementedError("This is over-dynamic function, not supported by MicroPython")` |
  | `getmodule(obj, _filename=None)` | stub, constant | `return None  # Not known` |
  | `getmro(cls)` | stub, constant | `return [cls]` |
  | `getsourcefile(obj)` | stub, constant | `return None  # Not known` |
  | `getfile(obj)` | stub, constant | `return "<unknown>"` |
  | `getsource(obj)` | stub, constant | `return "<source redacted to save you memory>"` |
  | `currentframe()` | stub, constant | `return None` |
  | `getframeinfo(frame, context=1)` | stub, constant | `return ("<unknown>", -1, "<unknown>", [""], 0)` |
  | `Signature` | empty class | `class Signature: pass` |
  | `signature(f)` | partial | arity only; see below |

- **Generators and coroutines are indistinguishable.** The file says: "In MicroPython
  there's currently no way to distinguish between generators and coroutines." and aliases
  `iscoroutinefunction = isgeneratorfunction`, `iscoroutine = isgenerator`.
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/python-stdlib/inspect/inspect.py#L31-L33>

- **`signature()` reports arity only.** The file's own comment: "This `signature()`
  function is very limited. It's main purpose is to work out the arity of the given
  function, ie the number of arguments it takes. The return value is an instance of
  `Signature` with a `parameters` member which is an OrderedDict whose length is the number
  of arguments of `f`." Parameter names are placeholders (`"x{}".format(i)`); there are no
  kinds, defaults or annotations.
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/python-stdlib/inspect/inspect.py#L88-L149>

- **How `signature()` gets the arity, and what it relies on in core:**
  - Built-ins: by type identity against four exemplars (`type(globals)` is 0 args,
    `type(abs)` 1, `type(hasattr)` 2, `type(setattr)` 3). Any other built-in type falls to
    `raise NotImplementedError("unsupported function type")`.
  - Bytecode functions, generator functions and closures: it reads the function object's
    memory. It takes `id(f)` as an address, overlays `uctypes.struct(...)`, fetches the
    bytecode pointer with `uctypes.bytearray_at(fun_obj[3], 8)`, and decodes the prelude
    ("See py/bc.h:MP_BC_PRELUDE_SIG_DECODE_INTO macro.") to compute
    `num_args = A + K - num_closed_over`.
  - **[Inference]** So it depends on the built-in `uctypes` module, on `id()` returning the
    object address, on the in-memory layout of function and closure objects, and on the
    bytecode prelude encoding. It is not a language-level introspection API.
  - Macro it mirrors: <https://github.com/micropython/micropython/blob/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/py/bc.h#L104-L125>
  - **[Inference]** The C macro's loop is `for (unsigned n = 0; z & 0x80; ++n)`; the Python
    port initialises `n = 0` and never increments it, so it looks correct only while the
    prelude needs at most one continuation byte. I did not run it.

- **Recent additions (all 2025, by Damien George):**
  - 2025-04-11 "inspect: Fix isgenerator logic." and "inspect: Add basic unit tests."
  - 2025-04-14 "inspect: Implement iscoroutinefunction and iscoroutine."
    <https://github.com/micropython/micropython-lib/commit/5b496e944ec045177afa1620920a168410b7f60b>
  - 2025-09-19 "inspect: Implement a very basic signature function." (PR #1043). The commit
    message says it "returns only a simple `Signature` instance with a `parameters`
    attribute that holds an `OrderedDict` whose length matches the arity of the input
    function". The PR description gives the motive: "The main aim here is to support
    PyScript".
    <https://github.com/micropython/micropython-lib/commit/b4565b41eab684722d9fcb2deee322869e47c359> and
    <https://github.com/micropython/micropython-lib/pull/1043>
  - 2025-10-06 "inspect: Support closures/generators/async-funcs in inspect.signature."
    <https://github.com/micropython/micropython-lib/commit/852f2cceff9f35ecf59db303400b8cd8e63dbc1d>

- **Core has no frame access for `currentframe()` to use.** `py/modsys.c` has no
  `_getframe` entry, and `sys.settrace` is off by default
  (`#define MICROPY_PY_SYS_SETTRACE (0)`). **[Inference]** This is why `currentframe()`
  can only return `None`.
  - <https://github.com/micropython/micropython/blob/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/py/modsys.c>
  - <https://github.com/micropython/micropython/blob/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/py/mpconfig.h#L1844-L1847>

### Reuse CPython's module or write a subset?

- **Built-in modules are deliberately subsets.** `docs/library/index.rst`: "Most Python
  standard library modules implement a subset of the functionality of the equivalent Python
  module", and "The following standard Python libraries have been "micro-ified" to fit in
  with the philosophy of MicroPython. They provide the core functionality of that module
  and are intended to be a drop-in replacement for the standard Python library."
  <https://github.com/micropython/micropython/blob/d2d095d0fe6e83c53fd0ef90643f7d2b8b1c1645/docs/library/index.rst#L6-L54>

- **micropython-lib's `python-stdlib` is "compatible but reduced".** README:
  "Compatible versions of modules from The Python Standard Library. These should be drop-in
  replacements for the corresponding Python modules, although many have reduced
  functionality or missing methods or classes (which may not be an issue for most cases)."
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/README.md>

- **Some are adapted from CPython, some extend the built-in "micro" modules.**
  `python-stdlib/README.md`: "Many packages are implemented in pure Python, often based on
  the original CPython implementation. (e.g. `collections.defaultdict`)" and "Some packages
  are based on or extend from the built-in "micro" modules in the MicroPython firmware".
  <https://github.com/micropython/micropython-lib/blob/92ee97d94c4b558cf4e6d27a4534401f1e9b9f50/python-stdlib/README.md>

---

## 2. PyPy

### subprocess

- **`subprocess.py` is CPython's file with three small PyPy edits.** Diff of
  `lib-python/3/subprocess.py` against CPython `v3.11.17` shows only:
  1. Windows `_get_handles` / `_make_inheritable(self, handle, close=False)`: "PyPy: If the
     initial handle was obtained with CreatePipe, close it."
  2. POSIX `_communicate`: "PyPy: release the view on exit, the GC would only do it later"
     (`with _PopenSelector() as selector, input_view:`).
  3. POSIX `_communicate`: "PyPy: release the slice now, the GC would only do it later, and
     it holds the export input_view shares (issues 5612, 5613)" (`chunk.release()`).

  Edits 2 and 3 exist because PyPy has no reference counting. The spawn logic
  (`_execute_child`, `_use_posix_spawn`, `_fork_exec` call) is unchanged.
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/subprocess.py#L1425-L1433> and
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/subprocess.py#L2107-L2154>

- **`_posixsubprocess` is an RPython built-in module with a C helper, not a `lib_pypy`
  module.** `pypy/module/_posixsubprocess/moduledef.py` exposes exactly one function,
  `'fork_exec': 'interp_subprocess.fork_exec'`. The child-side work is in
  `_posixsubprocess.c`, whose header says: "This file is mostly a copy of CPython's
  Module/_posixsubprocess.c" / "modified for PyPy: Removed dependency on Python API."
  `lib_pypy/` has no `_posixsubprocess` file.
  - <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_posixsubprocess/moduledef.py>
  - <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_posixsubprocess/_posixsubprocess.c#L1-L2>

- **It is a default module on POSIX and removed on Windows.** `pypyoption.py` lists
  `"_posixsubprocess"` in `working_modules` and removes it under `sys.platform == "win32"`
  ("unix only modules").
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/config/pypyoption.py#L43-L74>

- **`fork_exec` uses plain `fork()`; `vfork` is never used.** The docstring says: "Note:
  PyPy does not use vfork, so allow_vfork is a NOOP argument". The body calls
  `pid = os.fork()` and then, in the child, the C function `pypy_subprocess_child_exec`
  (declared via `rffi.llexternal(..., releasegil=True)`), followed by `os._exit(255)`.
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_posixsubprocess/interp_subprocess.py#L139-L302>

- **`preexec_fn` is supported.** It is stored on a module-level `PreexecCallback` and passed
  to the C helper as a function pointer (`PreexecCallback.run_function`), which calls
  `self.space.call_function(self.w_preexec_fn)`. Fork hooks run only when a `preexec_fn` is
  given (`if need_after_fork: run_fork_hooks('before', space)`). The docstring keeps
  CPython's warning: "WARNING: preexec_fn is NOT SAFE if your application uses threads."
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_posixsubprocess/interp_subprocess.py#L101-L115>

- **CPython's "disable GC around fork" step is dropped, with a stated reason:** "No need to
  disable GC in PyPy: - gc.disable() only disables __del__ anyway. - appelvel __del__ are
  only called at specific points of the interpreter."
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_posixsubprocess/interp_subprocess.py#L175-L178>

- **[Inference] `posix_spawn` is never used on this branch.** `subprocess.py` keeps
  CPython's gate `if _mswindows or not hasattr(os, 'posix_spawn'):` in `_use_posix_spawn()`.
  PyPy's `posix` module definitions (`moduledef.py`, `interp_posix.py`, `app_posix.py`)
  contain no `posix_spawn`; they define `fork`, `forkpty`, `execv`, `execve`, `spawnv`,
  `spawnve` and `system`. So `_USE_POSIX_SPAWN` should be `False` and every POSIX `Popen`
  goes through `_fork_exec`.
  - <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/subprocess.py#L695-L746>
  - <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/posix/moduledef.py#L120-L136>

- **`_pypy_install_libs_after_virtualenv` is a 2.7-only hack.** It is in
  `lib-python/2.7/subprocess.py` on `main`, where `Popen.__init__` pattern-matches the
  argument lists old virtualenv versions used ("--- PyPy hack, see
  _pypy_install_libs_after_virtualenv() ---") and copies `libpypy-c.so` into the new
  environment. The function inspects its caller with `sys._getframe(2)`. It is absent from
  the `py3.11` file.
  <https://github.com/pypy/pypy/blob/a41581967716bc5d9cdd1c1cf4a77ea0455af277/lib-python/2.7/subprocess.py#L342-L355> and
  <https://github.com/pypy/pypy/blob/a41581967716bc5d9cdd1c1cf4a77ea0455af277/lib-python/2.7/subprocess.py#L1316-L1338>

- **`cpython_differences` says nothing about `subprocess`.** No occurrence in the `.rst` at
  the pinned commit or on the published page.
  <https://doc.pypy.org/en/latest/cpython_differences.html>

### inspect

- **`inspect.py` is CPython's file with substantial PyPy patches** (diff against
  `v3.11.17`: 146 lines added, 13 removed). Most address one fact, stated in the file: "PYPY:
  In PyPy, methods wrapping builtin code have type 'method' not
  'builtin_function_or_method'. Use the code object type to detect them."
  (`_builtin_code_type = type(dict.update.__code__)`).
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/inspect.py#L155-L197>

- **The individual patches** (same file):
  - `ismethod`: returns `False` for a `MethodType` whose `__func__.__code__` is builtin
    code. "PYPY: MethodType in PyPy includes bound methods wrapping builtin code (e.g.
    [].append). Exclude those — they should be reported by isbuiltin()."
    [L351-L359](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/inspect.py#L351-L359)
  - `isbuiltin`: also true for cpyext builtin functions and for bound methods with builtin
    code, except slot-wrapper names.
    [L563-L573](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/inspect.py#L563-L573)
  - `ismethodwrapper`: "PYPY: PyPy has no distinct MethodWrapperType — slot wrappers like
    object().__str__ and builtin methods like [].append are both 'method'. Distinguish them
    by name". It uses a hard-coded `_SLOT_WRAPPER_NAMES` set that "mirrors CPython's static
    slotdefs list in typeobject.c".
    [L575-L582](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/inspect.py#L575-L582)
  - `isfunction` is unchanged (`isinstance(object, types.FunctionType)`).
  - `getargs`: accepts builtin code objects. "PyPy extension: built-in function objects
    have a __code__ too. There is no co_code on it, but co_argcount and co_varnames and
    co_flags are present."
    [L1378-L1385](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/inspect.py#L1378-L1385)
  - `_signature_is_functionlike`: accepts `(types.CodeType, _builtin_code_type)`, so
    builtins take the ordinary `_signature_from_function` path.
  - `_signature_from_function`: "PyPy extension, for built-in functions that take optional
    arguments but without any Python object to use as default." It reads
    `func.__defaults_count__` and fills the defaults with a `_NoValue` marker whose repr is
    `<no value>`.
    [L2443-L2491](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/inspect.py#L2443-L2491)
  - `_signature_get_user_defined_method`: "PYPY: logic changed here. In PyPy,
    types.MethodWrapperType is 'method' and types.ClassMethodDescriptorType is
    'classmethod', so _NonUserDefinedCallables is too broad to use as a gate."
    [L2029-L2060](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/3/inspect.py#L2029-L2060)
  - `_signature_fromstr`, class signatures: special cases for builtin `__new__`.
  - No hunks touch `getsource`, `getfile`, `getsourcefile` or `currentframe`.

- **The interpreter side that makes this work.** Builtin functions are function objects
  with a real `__code__` of type `builtin-code`:
  - `BuiltinCode.typedef = TypeDef('builtin-code', ...)` exposes `co_name`, `co_varnames`,
    `co_argcount`, `co_posonlyargcount`, `co_kwonlyargcount`, `co_flags`, `co_consts`, and
    no `co_code`.
    <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/interpreter/typedef.py#L682-L691>
  - `BuiltinFunction.typedef = TypeDef("builtin_function", **Function.typedef.rawdict)`, so
    builtin functions inherit `__code__`, `__defaults__`, `__text_signature__` and
    `__defaults_count__` from the function type.
    <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/interpreter/typedef.py#L805-L919>
  - `__defaults_count__` is explained in `function.py`: "PyPy extension. This is mostly to
    make inspect.py happy about methods like dict.pop(), which take a default but is None.
    Previously, inspect.py would build a signature saying that all arguments are required,
    and then unittest.mock would complain if we call it with less arguments."
    <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/interpreter/function.py#L399-L404>

- **Documented difference on method types.** `cpython_differences.rst`: "on CPython,
  ``[].__add__`` is a ``method-wrapper``, ``list.__add__`` is a ``slot wrapper`` and
  ``list.extend`` is a (built-in) ``method`` object. On PyPy these are all normal method or
  function objects (or unbound method objects on PyPy2). This can occasionally confuse some
  tools that inspect built-in types. For example, the standard library ``inspect`` module
  has a function ``ismethod()`` that returns True on unbound method objects but False on
  method-wrappers or slot wrappers. On PyPy we can't tell the difference. So on PyPy2 we
  have ``ismethod([].__add__) == ismethod(list.extend) == True``; on PyPy3 we have
  ``isfunction(list.extend) == True``. On CPython all of these are False."
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/doc/cpython_differences.rst#L526-L538>
  (published: <https://doc.pypy.org/en/latest/cpython_differences.html>)
  - **[Inference]** The doc says "we can't tell the difference", while the `inspect.py`
    patches at this branch head now do tell them apart by name table and code type. The
    doc's `isfunction(list.extend) == True` still matches the code, since `isfunction` is
    unpatched. I did not check which PyPy release first shipped these patches.

- **Documented difference on builtin argument names.** "In PyPy, most built-in functions
  accept keyword arguments (``help()`` shows the argument names). But don't rely on it too
  much because future versions of PyPy may have to rename the arguments if CPython starts
  accepting them too."
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/doc/cpython_differences.rst#L670-L679>

- **`sys._getframe` is fully implemented and hides interpreter-internal frames.**
  `inspect.currentframe` is CPython's
  `return sys._getframe(1) if hasattr(sys, "_getframe") else None`. `sys._getframe` is in
  `pypy/module/sys/vm.py`; it walks `ec.gettopframe_nohidden()` /
  `ec.getnextframe_nohidden(f)` and calls `f.mark_as_escaped()` on the result. The
  `_nohidden` walkers skip frames where `frame.hide()` is true, and `hide()` returns
  `self.pycode.hidden_applevel`. `BuiltinCode` and `ApplevelClass` (PyPy's own app-level
  helper code) set `hidden_applevel = True`.
  - <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/sys/vm.py#L28-L53>
  - <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/interpreter/executioncontext.py#L71-L83>
  - <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/interpreter/gateway.py#L740-L743>
  - `cpython_differences` does not mention `sys._getframe`. Its only tracing note is that
    `sys.settrace()` reports `StopIteration` exception events in a slightly different set
    of cases.

### Reuse CPython's module or write a subset?

- **Reuse by default, patch in place, rewrite only when forced.** `coding-guide.rst`,
  "Modules in PyPy": "PyPy reuses almost all python modules of CPython's standard library,
  currently from version 2.7.8. We sometimes need to `modify modules`_ and - more often -
  regression tests because they rely on implementation details of CPython. If we don't just
  modify an original CPython module but need to rewrite it from scratch we put it into
  :source:`lib_pypy/` as a pure application level module. When we need access to
  interpreter-level objects we put the module into :source:`pypy/module`." (The version
  number in that text is stale; the policy wording is what matters.)
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/doc/coding-guide.rst#L296-L314>

- **Changes are kept in the vendored copy and tracked against a vendor branch.** "We just
  maintain those changes in place, to see what is changed we have a branch called
  `vendor/stdlib`". `lib-python/stdlib-upgrade.txt` gives the procedure: copy CPython's
  `Lib/`, record the tag in `stdlib-version.txt`, merge `vendor/stdlib`, "fix issues".
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/doc/coding-guide.rst#L364-L375> and
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/lib-python/stdlib-upgrade.txt>

- **C extension modules need a PyPy implementation or they do not exist.**
  `cpython_differences.rst` lists modules "Supported as built-in modules (in
  :source:`pypy/module/`)" and "Supported by being rewritten in pure Python (possibly using
  ``cffi``): see the :source:`lib_pypy/` directory", then: "The extension modules (i.e.
  modules written in C, in the standard CPython) that are neither mentioned above nor in
  :source:`lib_pypy/` are not available in PyPy."
  <https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/doc/cpython_differences.rst#L713-L791>

---

## 3. GraalPy

### subprocess

- **`subprocess.py` is CPython's file with GraalPy patches, almost all for Windows.** Diff
  of `graalpython/lib-python/3/subprocess.py` against CPython `v3.13.14`:
  1. `_mswindows` is forced off under the Java backend: "GraalPy change: the Java posix
     backend is pure Java and does not expose CPython-style Windows handles. Keep it on the
     POSIX subprocess path."
     `_mswindows = not (sys.implementation.name == 'graalpy' and __graalpython__.posix_module_backend() == 'java')`
     [L72-L77](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/lib-python/3/subprocess.py#L72-L77)
  2. `startupinfo` / `creationflags` are tolerated on win32 when on the POSIX path.
  3. Windows `_make_inheritable`: "CPython closes this original handle immediately via
     refcounted finalization when the local variable is overwritten. GraalPy needs the close
     to be explicit so pipe EOF is observable."
  4. Three "Truffle change" blocks inside the POSIX `_execute_child`, all guarded by
     `sys.platform == 'win32'`: argument quoting and `cmd.exe /c` handling, `PATHEXT`
     expansion of the executable list, and using the raw status as `returncode`. One comment
     explains the cost: "emulating CreateProcess through an EmulatedPosixBackend that goes
     through Truffle API to a Java API introduces layers of escaping that are deeply
     troubling and cannot possibly be correctly handled in all cases."
     [L1858-L1902](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/lib-python/3/subprocess.py#L1858-L1902)

  On a POSIX host none of these blocks is active, so the POSIX logic is CPython's.

- **`_posixsubprocess` is a Java built-in module.** `PosixSubprocessModuleBuiltins.java` is
  annotated `@CoreFunctions(defineModule = "_posixsubprocess")` and defines one builtin,
  `@Builtin(name = "fork_exec", parameterNames = {"args", "executable_list", "close_fds", ...
  "preexec_fn", "allow_vfork"})`. It converts arguments, releases the GIL, and calls
  `context.getPosixSupport().forkExec(...)`, which dispatches to the selected backend.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/PosixSubprocessModuleBuiltins.java#L104-L325>

- **`preexec_fn` is rejected in every backend, before dispatch:**
  ```java
  if (!(preexecFn instanceof PNone)) {
      throw raiseNode.raise(inliningTarget, RuntimeError, ErrorMessages.S_NOT_SUPPORTED, "preexec_fn");
  }
  ```
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/PosixSubprocessModuleBuiltins.java#L271-L273>

- **[Inference] `gid`, `groups`, `uid` and `umask` are accepted but not applied.** The
  builtin takes `gidObject`, `groupsList`, `uidObject` and `childUmask`, but the
  `forkExec(...)` call passes none of them and the backend signature has no such
  parameters. I saw no check that rejects non-default values. (Same URL as above,
  [L314-L315](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/PosixSubprocessModuleBuiltins.java#L314-L315).)

- **`sys.executable` is special-cased.** If an entry of `executable_list` equals the
  `Executable` option, it is replaced by `PythonOptions.getExecutableList(context)` and the
  extra launcher arguments are spliced into `argv`. A comment on the helper used for the
  comparison explains: "This is needed for the special case when someone uses
  sys.executable in call to POpen".
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/PosixSubprocessModuleBuiltins.java#L232-L309>

- **Two backends, chosen by the `PosixModuleBackend` option.** The user docs say: "GraalPy
  provides two alternative implementations ("backends") of system-related functionality
  for built-in Python modules such as `os`. The `PosixModuleBackend` option determines
  which backend is used: `native` or `java`." Also: "The native backend is chosen by
  default when GraalPy is started via the `graalpy` launcher", and "The Java backend is the
  default when embedding GraalPy in Java applications using the `Context` API." The option
  itself defaults to `java` in `PythonOptions.java`.
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/docs/user/Embedding-Permissions.md#L7-L56>
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/runtime/PythonOptions.java#L232-L233>

- **Native backend: real `fork`/`vfork` + `exec` in a C helper.**
  `NativePosixSupport.forkExec` packs all strings into one native buffer plus an offsets
  array and calls C `fork_exec` in `python-libposix/src/fork_exec.c`. That file is adapted
  from CPython ("These definitions emulate CPython's equivalents so that the copy&pasted
  code below works without too many changes"). It uses `vfork()` only on Linux
  (`#if defined(__linux__)` ... `#define VFORK_USABLE 1`) and only when
  `allowVFork && pgidToSet < 0` ("Keep process-group setup on the normal fork path."),
  otherwise `fork()`. The child then runs `child_exec`, ending in `execve`/`execv`. One
  parameter is documented as "restoreSignals - currently not used".
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/runtime/NativePosixSupport.java#L2064-L2178>
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/python-libposix/src/fork_exec.c#L530-L665>

- **Java ("emulated") backend: no fork at all; a Truffle/Java process builder.**
  `EmulatedPosixSupport.forkExec` builds
  `TruffleProcessBuilder pb = context.getEnv().newProcessBuilder(argStrings);`. What the
  code does:
  - Rejects process groups: `if (pgidToSet >= 0) { throw createUnsupportedFeature("process_group in fork_exec"); }`.
    The message prefix is "Feature not supported on 'java' POSIX backend: ".
  - Ignores other arguments, by its own admission: "TODO there are a few arguments we
    ignore, we should throw an exception or report a compatibility warning". `closeFds`,
    `restoreSignals`, `callSetsid`, `fdsToKeep` and `allowVFork` are never read in the
    method body.
  - Requires `key=value` environment entries.
  - Each standard stream is either `Redirect.PIPE` (when both pipe fds are given) or
    `Redirect.INHERIT`; `stderr=STDOUT` maps to `redirectErrorStream(true)`. After start,
    the Python-level pipe fds are re-pointed at the Java process's channels.
    **[Inference]** Redirecting a child stream to an arbitrary file descriptor is not
    implemented here.
  - Failure is reported CPython-style by writing `"OSError:<hex errno>:<message>"` to the
    error pipe and returning `-1`. The code comments: "TODO returning -1 is not correct".
  - The child is tracked in an internal table (`return registerChild(process);`), so the
    "pid" is an emulated handle.
  - Throws `"forkExec was excluded"` when built with `WITHOUT_PLATFORM_ACCESS`.

  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/runtime/EmulatedPosixSupport.java#L2410-L2553>

- **Related process calls in the Java backend are also partial** (same file):
  - `waitpid`: "Only 0 or WNOHANG are supported for waitpid"; "Process groups in waitpid"
    unsupported.
    [L2125-L2150](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/runtime/EmulatedPosixSupport.java#L2125-L2150)
  - `kill`: "Sending arbitrary signals to child processes. Can only send KILL and TERM
    signals". `killpg` is unsupported.
    [L1961-L1976](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/runtime/EmulatedPosixSupport.java#L1961-L1976)
  - `execv`: emulated by starting a child, pumping its output, waiting, then exiting the
    interpreter with the child's exit code (`throw new PythonExitException(null, pr.exitValue())`).
  - `system`: runs `sh -c <cmd>` (or `cmd.exe /c`) through the same process builder.
    [L2576-L2660](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/runtime/EmulatedPosixSupport.java#L2576-L2660)

- **`os.fork` is unsupported in both backends.** The docs list, under "Limitations of the
  Native Backend": "`os.fork` is not supported" and "`_posixsubprocess.fork_exec` does not
  support the `preexec_fn` parameter". `PosixModuleBuiltins.java` has no `fork` builtin, and
  `register_at_fork` is a no-op that returns `None`.
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/docs/user/Embedding-Permissions.md#L38-L43>
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/PosixModuleBuiltins.java#L3091-L3100>

- **`multiprocessing` follows from that.** Patched `multiprocessing/context.py`:
  `get_all_start_methods` returns `['spawn']`; `ForkProcess._Popen` raises
  `NotImplementedError("'fork' not supported on GraalPy")`; `SpawnProcess._Popen` raises
  `ValueError("multiprocessing not supported with the java POSIX backend")` under the Java
  backend.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/lib-python/3/multiprocessing/context.py#L266-L304>

- **Embedding needs an explicit permission.** The `Context.Builder` table says of
  `allowCreateProcess(boolean)`: "Controls whether Python code can create new processes."
  / "Required for the `subprocess` module to work. Default is `false`." The builtin maps a
  `SecurityException` to `OSError(EPERM)`.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/docs/user/Embedding-Permissions.md#L97>

- **Doc naming over time.** At tag `graal-23.1.0` the same content was
  `docs/user/OsInterface.md`, with headings "Limitations of the Native Backend" and
  "Limitations of the Emulated Backend" and the same two bullets about `os.fork` and
  `preexec_fn`. That file is gone at `master`; the content is in `Embedding-Permissions.md`.
  <https://github.com/oracle/graalpython/blob/graal-23.1.0/docs/user/OsInterface.md>

- **[Inference] `posix_spawn` is not used.** `PosixModuleBuiltins.java` and
  `PosixSupport.java` contain no `posix_spawn`, and `subprocess.py` keeps CPython's
  `hasattr(os, 'posix_spawn')` gate, so `Popen` always goes through `fork_exec`.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/lib-python/3/subprocess.py#L703-L757>

### inspect

- **`inspect.py` is CPython's file with two small changes** (diff against `v3.13.14`):
  1. `getclosurevars` no longer uses `dis`: "GraalPy change: dis isn't supported". It adds
     every name in `code.co_names` (except `None`/`True`/`False`) to `global_names`, and
     `unbound_names` stays empty.
     [L1624-L1637](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/lib-python/3/inspect.py#L1624-L1637)
  2. `_signature_is_builtin`: "Truffle change: treat foreign executables as builtin"
     (`isinstance(obj, __graalpython__.ForeignType) and callable(obj)`).
     [L2158-L2160](https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/lib-python/3/inspect.py#L2158-L2160)

  `signature`, `isbuiltin`, `isfunction`, `getsource` and `currentframe` are unmodified.

- **Builtin signatures are generated from the `@Builtin` Java annotation.**
  `BuiltinFunctionRootNode.createSignature(factory, builtin, ...)` builds the internal
  `Signature` from `builtin.parameterNames()`, `minNumOfPositionalArgs()`,
  `maxNumOfPositionalArgs()`, `numOfPositionalOnlyArgs()`, `keywordOnlyNames()`,
  `takesVarArgs()` and `takesVarKeywordArgs()`. When the annotation gives only a count,
  it synthesises names: `$self` or `$cls`, then `a`, `b`, `c`, ...
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/nodes/function/BuiltinFunctionRootNode.java#L123-L184>

- **Builtin functions expose a computed `__signature__`.** The getter in
  `BuiltinFunctionBuiltins.SignatureNode` imports the Python `inspect` module from Java and
  builds a real `inspect.Signature` out of `inspect.Parameter(name, kind)` objects, using
  kinds `POSITIONAL_ONLY`, `POSITIONAL_OR_KEYWORD`, `VAR_POSITIONAL`, `KEYWORD_ONLY` and
  `VAR_KEYWORD`. CPython's `inspect.signature` reads `obj.__signature__` first, so it picks
  this up without any change to `inspect.py`. **[Inference]** The `Parameter` objects are
  built from name and kind only, so they carry no defaults or annotations.
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/objects/function/BuiltinFunctionBuiltins.java#L144-L224>
  - <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/lib-python/3/inspect.py#L2555-L2560>

- **`__text_signature__` is synthesised from the same data.** The getter returns a stored
  attribute if present, otherwise `signatureToText(signature, false)`, which renders
  `(a, b, /, c, *args, kw=?, **kwargs)`-style text; keyword-only parameters are written as
  `name=?`. It is read-only on builtins.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/objects/function/AbstractFunctionBuiltins.java#L358-L439>

- **Some signatures are deliberately hidden.** `Signature.isHidden()`: "Hidden signatures
  won't be shown to python as `__signature__` or `__text_signature__`. This is done to hide
  generic C function signatures, because it breaks assumptions of some packages, namely
  `pythran`". Both getters raise `AttributeError` in that case.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/objects/function/Signature.java#L165-L172>

- **`sys._getframe` is implemented; frames are materialised lazily.** The builtin is
  declared `@Builtin(name = "_getframe", parameterNames = "depth", minNumOfPositionalArgs = 0, needsFrame = true, callerFlags = CallerFlags.NEEDS_PFRAME)`.
  It calls `readFrameNode.getFrameForReference(..., ReadFrameNode.AllPythonFramesSelector.INSTANCE, depth, 0)`,
  raises `ValueError` (`CALL_STACK_NOT_DEEP_ENOUGH`) when the result is null, and calls
  `requested.getRef().markAsEscaped()`. `inspect.currentframe` is CPython's
  `sys._getframe(1) if hasattr(sys, "_getframe") else None`.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/SysModuleBuiltins.java#L927-L948>

- **Documented design and cost of frame access** (contributor docs, not user docs):
  - "A `PFrame.Reference` is created when entering a Python function. By default it only
    holds on to another reference, that of the Python caller. If there are non-Python
    frames between the newly entered frame and the last Python frame, those are ignored -
    our linked list only connects Python frames."
  - "When an event forces the frame to materialize on the heap, the reference is filled.
    This is usually only the case when someone uses `sys._getframe` or accesses the
    traceback of an exception. If the stack is still live, we walk the stack and insert the
    "calling node" and create a "PyFrame" object that mirrors the locals in the Truffle
    frame."
  - "This assumption is invalidated the first time the reference is actually needed."

  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/docs/contributor/IMPLEMENTATION_DETAILS.md#L24-L58>

### Reuse CPython's module or write a subset?

- **Pure-Python stdlib is vendored and adapted; C-implemented parts are rewritten in
  Java.** The repo's layout note: `lib-graalpython/` is "GraalPy-specific Python
  modules/patches" and `lib-python/` is "Vendored/adapted CPython stdlib + CPython tests".
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/AGENTS.md#L10-L15>

- **Built-in modules mirror CPython's C layout, in Java, sometimes with a Python half.**
  `CONTRIBUTING.md`: "For the most part, built-in modules and classes are implemented in
  the `com.oracle.graal.python.builtins` package. For each module or class, there's a Java
  class annotated with `@CoreFunctions`. Each function in a module or a class is
  implemented in a Node annotated with `@Builtin`." / "Some built-in functions, modules,
  and classes are implemented in pure Python. The files for these are in the
  _graalpython/lib-graalpython_ directory." / "When implementing a new (or fixing an
  existing) built-in, take a look at the CPython source. The layout and naming of modules
  and types is kept similar to the CPython source".
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/docs/contributor/CONTRIBUTING.md#L232-L247>

- **The vendored stdlib is refreshed by tool from CPython and PyPy.** `DEV_TASKS.md`,
  "Updating lib-python": "The following command, run on a clean branch, should guide you
  through updating our imported sources from CPython and PyPy: `mx python-src-import`".
  Local edits are marked in place with "GraalPy change" / "Truffle change" comments, as the
  diffs above show.
  <https://github.com/oracle/graalpython/blob/cb3e2dcefd6877db6fe22a096515e3dbf13c4ba5/docs/contributor/DEV_TASKS.md#L18-L27>

---

## Could not verify

- **MicroPython, documented position on `subprocess`:** nothing in the docs. The only
  statement found is the 2016 issue reply in micropython-lib #122. A GitHub search for
  issues and PRs with "subprocess" in the title across both MicroPython repos returned only
  that issue; I did not search issue bodies or the discussion forum exhaustively.
- **MicroPython, whether `unix-ffi` `os.popen`/`fork` still work on the current unix port:**
  not tested. A search-result summary of micropython-lib issue #962 said `os.popen()` failed
  on FreeBSD because `ffilib` could not find libc; I did not open that issue.
- **MicroPython, the missing `n` increment in `inspect.signature`:** read from the source
  only, not executed, so the practical effect is unconfirmed.
- **MicroPython, a subprocess-like facility elsewhere in micropython-lib:** I did not read
  `unix-ffi/multiprocessing/multiprocessing.py`.
- **PyPy, runtime behaviour:** I did not run PyPy. Statements about what
  `inspect.signature`, `isbuiltin` and `ismethod` return are read from the patched
  `inspect.py`, not observed.
- **PyPy, which release contains the `inspect.py` patches:** the findings are for the
  `py3.11` branch head; I did not map them to a release or date the commits.
- **PyPy, `inspect.getsource` on PyPy's app-level built-in helpers:** not determined.
  `getsource`/`getfile` are unpatched, but I did not trace what `co_filename` such code
  objects carry.
- **PyPy, documentation on `sys._getframe` or `subprocess`:** neither appears in
  `cpython_differences`. I found no other PyPy doc page describing them (searched
  `pypy/doc/*.rst`, excluding release notes).
- **PyPy, `os.posix_spawn`:** absent from the three `posix` module files I checked on
  `py3.11`; I did not check the `py3.12` branch.
- **GraalPy, user-facing caveats for `sys._getframe` or `inspect`:** none found in
  `docs/user/*.md`. The only description is the contributor-level
  `IMPLEMENTATION_DETAILS.md`.
- **GraalPy, docs titled "Python Standard Library Applicability" or "Native and Managed
  Execution Mode":** no such files in `docs/user/` at `master`. I confirmed only the old
  `OsInterface.md` at tag `graal-23.1.0`; it returns 404 at `graal-24.1.0` and
  `graal-25.0.0`, and I did not find which release renamed it.
- **GraalPy, handling of `user`/`group`/`extra_groups`/`umask`:** "accepted but not
  applied" is my reading of the Java call; I found no doc statement and did not run it.
- **GraalPy, a per-module policy statement** (when to keep CPython's `.py` versus rewrite):
  not found. The findings above are layout descriptions and contributor guidance, not a
  stated decision rule.
- **All three:** nothing was executed; version-specific claims hold for the pinned commits
  only.
