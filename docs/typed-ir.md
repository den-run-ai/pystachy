# A typed IR for Pystachy

This document designs the typed intermediate representation that the README names as the main next step. Issue #4 §4 asks for the same thing: "a small typed IR separating lexical resolution, type checking, effects, and backend lowering". The issue also asks to "preserve the existing useful LLVM/mem2reg delegation" and says "a large framework is not required".

This is the preparation step, and none of it is implemented yet. Function names refer to `pystachy.py` at commit `bd4cd6a` (6,952 lines). Counts and timings were measured on that commit in October 2026, with LLVM 18.

> **Status.** This design was written against commit `bd4cd6a`, and its counts (lines, calls,
> programs) are that commit's. The PRs it ships with have since changed some of what §1 describes:
> - #4 §1 B and C are fixed: the loader recognizes `os`, `sys` and `TYPE_CHECKING` only where no
>   local binding hides them (`special()`), so §1.2 item 7's first point no longer holds.
> - The O(F × G) cost of `flow_program` (#4 §2) is gone: Flow works over the names each function
>   mentions, with an undo log.
> - A `Symtable` pass now mirrors CPython's symbol table on every parsed module (#15). It is the
>   natural starting point for the resolver track of §6.4.
> - Step 0's tooling has landed: `tools/irsame.sh` (`make irsame REF=<commit>`), `make check-ir`
>   (also a `make verify` step) and the `tests/ir/` probes, with bug B's probe in `tests/ir/pending/`.
> - #17's cases 2 and 4 (§9, question 4) now compile.
> - Bugs A to F of §1.3 are fixed in their own commits (wf/defects), outside the IR steps.
>
> - Steps 5 to 8, then step 4, have landed in that order (one commit each, every one byte-identical
>   on the corpus). Where they differ from the text below:
>   - the op table is `IROPS`, since the lexer's `OPS` holds Python's operators; `raise` has the
>     letters T R N, and the effect letters are listed in `FX`;
>   - `rt()` builds `rt` ops, whose operands are typed as their `RUNTIME` entry spells them (`S`,
>     `*T`, `#`, ...) and whose `Ins.x` holds the descriptor text of a `#` parameter; `call_fn`
>     and module imports build `call` and `init` ops (from step 14). A raw op is then a load, a
>     store or arithmetic, never a call, a phi or a terminator, and the verifier checks that (and
>     that each op holds the numbers its lowering prints), so effect summaries are exact in R, A,
>     U and I. `IFn.fx` holds each function's summary, computed by `Gen.effects`
>     once the program is built (`Gen.opfx` gives one op's letters, `fxs` spells them), and
>     `IFn.n` the last number its builder gave, for passes that add values or blocks;
>   - `RUNTIME` entries use `%X` for LLVM types the type language cannot spell (`%ptr`, `%i32`,
>     `%ovf`), and also cover `pys_init`, `pys_finish` and `llvm.frameaddress.p0`;
>     `tools/check_runtime.py` (`make check-runtime`, a `make verify` step) checks types,
>     coverage, and the R, A, U and N letters (and rL rD for an entry that walks a value by its
>     descriptor) against runtime.c's call graph;
>   - hole ids count from 1 (0: no hole), and hole ops carry their operands like other `rt` ops;
>     a list comprehension's result list is a hole too, which `listcomp` fills with the list type
>     once it knows the element type (a list hole lowers as it was built, so this changes no output);
>   - `anyall` records a `seq` `Loop` too;
>   - the verifier also runs in `tools/check_ir.sh` (`make check-ir`, and so `make verify`), which
>     compiles the compiler itself, the benchmarks and the `tests/ir` probes, and fails on an
>     internal error as on an IR that `llvm-as` rejects;
>   - the jump to the first cold block that follows the `ret` a function falls into is a block
>     without a label (LLVM starts one after a terminator), so that each block still ends with
>     its one terminator.
>   - an `Ins` starts with shared empty lists (`NONUMS`, `NOVALS`, `NOLABELS`) and gets lists of
>     its own when it has numbers, operands or labels; `Gen.program` checks that the shared ones
>     stayed empty. Raw ops, most of the IR, so need none. `Gen.program` also drops each
>     function's IR (blocks, slots, loops, cold blocks) once it is lowered, keeping its summary.
>     With that, the native self-compile's live heap at its last collection is 21.1 MiB (17.0
>     before the IR; 40.8 while the IR was kept to the end), its peak 77.2 MiB (71.6), and its
>     time 1.15 to 1.2 times what it was.
>
> `docs/typed-ir-prototype.diff` is the prototype of steps 5 to 7 (plus `check`, `ovf` and
> `list_get`) that §6.5 measures; it applies to `bd4cd6a`'s `pystachy.py`. Appendix A records how
> this design was chosen.

## Summary

- **Where the cut is.** `Gen` keeps its single walk over the AST. That walk resolves names where they are used, checks and infers types, folds static tests and instantiates templates. Only its output changes. Today it appends LLVM text to `self.body`. Instead it builds one `IFn` per compiled function, made of blocks of typed instructions (`Ins`). A separate lowering prints the LLVM text after the whole program has been built. Type checking stays a single walk because static folding decides which code gets type-checked at all (§4.4).
- **Small, and written in the subset.** The IR has:
  - five classes: `Val`, `Ins`, `Blk`, `Loop` and `IFn`;
  - about 35 op strings;
  - two tables, `OPS` and `RUNTIME`, which give every op and every runtime function its effects.

  There is one instruction class dispatched on an op string, in the same way the AST has one `Node` class with a kind string. Types stay canonical strings.
- **LLVM still builds the SSA form.** Locals stay zero-initialised `alloca`s in the entry block. `phi`s appear only where expressions join. The JIT and AOT pipelines do not change.
- **Every step is checked byte for byte.** After each migration step, the `ir` output of 358 programs must be unchanged: the tests, deviations, benchmarks, error cases and the compiler itself. The bootstrap fixed point must still hold. The one exception is the last step, which renumbers values and string constants; it is checked with a normalising diff instead.
- **Evidence from a prototype.** A prototype of the first IR steps reached the fixed point and produced identical output for all 358 programs. It covers the container, lowering at the end, the two text patches turned into ops, and the `check`, `ovf` and `list_get` ops, in +133/−46 lines.
  - Native self-compile time did not change measurably.
  - The native compiler's live heap at its last collection doubled, from 12.3 to 24.6 MiB, because the IR is kept until the end.
- **What it buys:**
  - typing that no longer reads LLVM text;
  - explicit effects and checks, which the optimizations in the README need. For example, 223 of the 1,083 `pys_list_get` calls in the compiler's own output re-check a bound the loop has just tested.
  - a place for a second and a third lowering: WebAssembly GC, and the CPython-extension mode of #4 §4.
- **The first steps (§6.3)** are tooling plus four small refactors that change no output:
  - non-null facts and constness kept on values instead of in LLVM text;
  - class-id registration split from the descriptor text;
  - declarations stored as data;
  - a table of runtime signatures and effects.

## 1. Why

### 1.1 One walk, six jobs

`Gen` (4,112 lines) does all of these jobs in one walk over each function's AST:

| job | where it happens today |
|---|---|
| lexical resolution | **The Loader** qualifies module-level names (`Loader.qname`, `qmod`, `qstmts`).<br>**`Gen`** resolves the rest at each use, through ordered probes in `load_name`, `call`, `is_global`, `bound` and `dotted`.<br>**`aliases`** is filled when an `import` statement is compiled. |
| declarations | the declaration steps of `Gen.program`; `declare_fn`, `declare_fields`, `scan_fields`/`guess`, `check_special`; `typeof`/`vtype`/`ann_problem` |
| definite assignment | `flow_program` and `Flow`. Their results live on the AST (`Node.chk`) and in tables keyed by name (`FnInfo.uflags`, `gflag`, `late`, `ClassInfo.fflag`). |
| type checking and inference | `expr` and everything under it:<br>- the expected type `want`;<br>- `coerce`;<br>- templates (`call_fn`, `instance`);<br>- empty containers (`empty`, `refine`, `lookahead`, `dry`, `fill`). |
| static folding | `static`, `has`, `isinst` and `static_type`, applied in `if`, `while`, `assert`, conditional expressions and `and`/`or` |
| emission | everywhere: 105 lines call `rt`, 126 call `ins` and 69 call `place` |

The README's table of Ouro v1's weaknesses ends with this one: "type checking and emission are one class with no IR". Its verdict is "still true".

### 1.2 What it costs

1. **A type cannot be computed without emitting code.**
   - Every expression method returns `Val(v, t)`, where `v` names LLVM text already appended to `self.body`.
   - `Gen.lookahead` sometimes needs the type of an expression that the function will compile later. To get it, `Gen.dry` compiles the expression into a body that it then drops.
   - `dry` restores only `body`, `cur` and `term`. Everything else leaks:
     - the value counter;
     - allocas;
     - cold blocks;
     - `@s.N` constants;
     - `declare` lines;
     - `called` marks;
     - class ids;
     - template instances, which stay compiled and emitted for good;
     - the error position.
   - The leaked error position is a visible bug. In the program below, the error "cannot infer the type of 'xs'" names line 4, where `dry` looked, instead of line 3, where `xs` is read:

     ```python
     def f() -> None:
         xs = []
         print(xs)
         xs.append(None)
     ```
2. **Facts that arrive late are patched into the text.**
   - **Template returns.** Inside a template, a `return None` that comes before the first `return` with a value is emitted as the text `ret <none>`. `Gen.function` rewrites it once the return type is known.
   - **Dict key kinds.** A dict created empty is emitted as `pys_dict_new(i64 <keysN>, i64 0)`. At the end, `Gen.program` rewrites every line of the program's output, replacing each `<keysN>` with the key kind that the dict's first use showed.
3. **Typing decisions read the emitted text.**
   - **Constness.** Whether an operand is a constant is decided by testing its spelling with `startswith("%")`. This happens for:
     - the tuple index in `Gen.index`;
     - the range step in `for_range` (twice);
     - a slice bound in `expr`;
     - the exact int/float comparison in `cmp2`.
   - **Non-null facts.** These are keyed by register name in `Gen.nn`, and they do not follow control flow. In the program below, both reads of `q.x` get a None check, even though they come right after the test that ruled None out:

     ```python
     def g(q: P | None) -> int:
         if q is not None and q.x > 0:
             return q.x
         return 0
     ```
4. **A template is compiled in the middle of its caller.**
   - `instance` saves the 29 per-function fields of `Gen` into a `Frame`, compiles the template's body, then restores them.
   - `function` appends the instance's `define` to the output before its caller's. So the order of the output is the order in which compilations finished.
5. **Program tables are side effects of emission.**
   - `desc` gives a class its id (`O<id>`) the first time a descriptor mentions it. Those ids decide which object helpers the lazy fixpoint in `program` compiles.
   - `call_fn` marks a function as `called`, which decides which imported functions get compiled. Calls made inside `dry` count too.
   - `rt` writes each runtime `declare` line from the operand text of whichever call site comes first.
   - A global's type is fixed by its first store in emission order.
6. **The runtime ABI is part of typing.**
   - The `METHODS` signatures mix the type language with the calling convention:
     - `*` marks an 8-byte slot;
     - `#` marks a descriptor argument;
     - defaults are written as LLVM literals such as `null` and `9223372036854775807`.
   - Every container operation calls `to_slot` or `from_slot` in the middle of type checking.
   - A second backend would have to rewrite all of `Gen`.
7. **Name resolution is spread out.**
   - A function's local and global sets are computed in five places: `Loader.bindings`, `Loader.qstmts`, `flow_program` (twice), `fl_fields` and `Gen.function`.
   - `Loader.simplify` folds `os.name` and `TYPE_CHECKING` tests before any of those computations run. So a parameter named `os` or `TYPE_CHECKING` is ignored (#4 §1 B and C).
   - `flow_program` copies all module globals for each function, which is the O(F × G) cost of #4 §2.
8. **Language-level optimizations have nowhere to live.** LLVM sees only opaque runtime calls. The compiler's own output has 84,906 lines and 295 functions. In it:
   - **List reads.** 223 of the 1,083 `pys_list_get` calls follow the loop's own `i < len` test on the same index, and the runtime then tests the bound again.
   - **Dict lookups.** `if k in d: d[k] += 1` makes three hash lookups: `pys_dict_has`, `pys_dict_getitem` and `pys_dict_set`. The output has 326 `pys_dict_has` calls and 174 `pys_dict_getitem` calls.
   - **None tests.** There are 3,099 None tests (`icmp eq ptr ..., null`). Of these, 2,102 test a local that the same function already tested with no store in between. The scan ignores control flow, so this is an upper bound.
9. **Declarations are encoded in strings and AST shapes.**
   - `FnInfo.dglob` packs four states into one string: `""`, `@d.<f>.<p>`, `=None` and `!message`.
   - Several facts are read off the AST or a symbol name:
     - a dataclass is recognised by `len(node.kids) > 1` (`is_dc`);
     - a synthesized `__init__` is recognised by its first kid being `noann`;
     - a module's init is recognised by its symbol starting with `@init.`.
   - A declaration that fails in an imported module gets the placeholder type `int` or `None`, with a message in `FnInfo.bad` or `ClassInfo.bad`. So a poisoned field type-checks as `int`.
10. **Nothing checks the output.** `pystachy ir` does not run `llvm-as`, and there is no IR-level test. The fixed point and the differential tests are the only checks.

### 1.3 Defects found on the way

Preparing this design turned up six defects on the declaration and inference side. Each needs its own fix and its own test. None of them belongs in an IR step (§6.4).

| | defect | where |
|---|---|---|
| A | In an imported module, an unused function or field annotated with `Iterable[int]`, `int \| None` or `dict[float, X]` is a fatal error. `ann_problem`, the test for deferring an error, only approximates `typeof`:<br>- it never checks the base name of `X[...]`;<br>- it never checks dict key types;<br>- it never checks that `X \| None` names a class. | `declare_fn`, `declare_fields`, `scan_fields` |
| B | `self.x = f()` in `__init__`, where `f` returns None, gives the field the type `None`. The output then holds `%C.A = type {void, i64}`, which `llvm-as` rejects: the compiler crashes downstream instead of giving a diagnostic. | `guess` passes a function's `ret` through without checking it |
| C | `self.x = -True` is rejected with "expected bool, got int", while CPython stores -1. `guess` gives `-e` the type of `e`, but `expr` gives `int`. | `guess` |
| D | `check_special` runs on every class, used or not. In an imported module:<br>- `def __len__(self):` (no annotation) fails with "__len__ must return int";<br>- `def __eq__(self, other: object) -> bool` fails with "__eq__ must return bool", because the bad annotation left the placeholder return type `None`. | `Gen.program`, `check_special` |
| E | After a failed look-ahead, the error names the line that `dry` looked at (§1.2, item 1). | `dry` does not restore `self.line` |
| F | `fills` evaluates `static()` in the environment of the read, not of the fill site, so the look-ahead can follow the wrong branch. | `fills` |

## 2. Goals and non-goals

**Goals**
- **Separate the four concerns of #4 §4:** lexical resolution, type checking, effects and lowering.
  - Typing and folding stay in one walk.
  - LLVM text exists only in lowering.
  - Effects are data.
  - Resolution gets its own pass, on a parallel track (§6.4).
- **Keep it small:** about 35 ops, a table of runtime operations, no pass manager and no new type language. The IR adds about 500 to 800 lines to the compiler.
- **Stay in the subset.**
  - One `Ins` class dispatched on an op string; `list[T]`; dicts keyed by `str` or `int`.
  - No inheritance and no first-class functions.
  - Deterministic: dicts iterate in insertion order and numbers come from counters, so stage1 == stage2 == stage3 keeps holding.
- **Keep the LLVM/mem2reg delegation and the runtime ABI:**
  - allocas plus mem2reg;
  - checked arithmetic with one cold block per message;
  - None as null;
  - 8-byte container slots;
  - descriptors.
- **Keep every error message, and the order in which errors are found.** `tests/errors` checks only the first message, so lowering never reports a user error.
- **Make each step verifiable by identical output.** Then the IR can land in small pieces, next to the compatibility work on the same code.

**Non-goals**
- A separate type checker over the AST (§4.4 explains why).
- SSA construction, dominators or register allocation in Pystachy.
- A second backend in this work. The IR is done when one could be written without reading LLVM text.
- Behaviour changes inside IR steps. Bug fixes and optimizations are separate commits.
- Faster compilation. The IR costs time (§6.5), and a budget caps that cost.

**Alternatives considered**
- **Check first, then emit.** A type checker over the AST, followed by a code generator over the typed AST.
  - Rejected. Static folding, first-return typing and the template rule "nothing after a return" decide which code is type-checked. The second walk would have to repeat every decision of the first.
- **A backend-neutral, structured IR built in one move.** Regions instead of blocks; no registers, labels, slots or null.
  - It is the right end state for Wasm and CPython (§3.8).
  - Building it directly would mean re-deriving `Gen`'s block state outside the emitter. In templates, `term` decides what gets compiled, and the type of a conditional expression depends on which arms end.
  - There would be no byte-identical oracle along the way.
- **Resolution and declarations first, IR after.**
  - This gives the cleanest separation.
  - It is also the largest change, and the one most entangled with the open compatibility work.
  - Its parts are kept as a parallel track (§6.4) and as the small byte-identical steps 1 to 4.

## 3. The IR

### 3.1 Data structures

Everything below is written in the subset. Values and instructions:

```python
class Val:
    # an operand: a value of type t
    def __init__(self, v: str, t: str):
        self.v = v        # its LLVM spelling until the re-baseline: "%t12" "%a0" "@g.n" "@s.3" "42" "null"
        self.t = t        # a canonical type, or a backend pseudo-type "%addr" / "%slot" (3.2)
        self.nn = False   # proved not None: self, a new object (replaces Gen.nn)


class Ins:
    # one instruction; op decides which fields mean something (the op table, 3.4)
    def __init__(self, op: str, t: str, s: str):
        self.op = op            # "load" "store" "check" "ovf" "rt" "call" "phi" "raw" ...
        self.t = t              # result type; "" when it defines no value
        self.s = s              # text immediate: a message "Kind: text", a RUNTIME key, a callee,
                                # a class, a Python operator; for "raw", one line of LLVM text
        self.x = ""             # the static type a generic operation works on (its descriptor)
        self.k = 0              # int immediate: field or flag index, tuple index, hole id
        self.r: list[int] = []  # numbers of the values it defines, as the builder gave them
        self.a: list[Val] = []  # operands, in evaluation order
        self.b: list[str] = []  # labels: successors (br, cbr, check) or phi predecessors
        self.line = 0           # k * LINES + line of its source, for errors and later debug info
```

Blocks, loops and functions:

```python
class Blk:
    # one basic block; it becomes one LLVM block
    def __init__(self, label: str):
        self.label = label          # "entry" or "L<n>"
        self.code: list[Ins] = []   # ends with exactly one terminator


class Loop:
    # the shape of one loop, for loop passes and structured backends; lowering ignores it
    def __init__(self, kind: str):
        self.kind = kind            # "while" "range" "rrange" "seq"
        self.mode = ""              # seq: "" enumerate zip reversed items keys values
        self.head = ""              # the block that tests whether to go on
        self.body = ""
        self.step = ""              # continue's target
        self.exit = ""              # break's target, after the else block
        self.seqs: list[Val] = []   # what a seq loop steps through
        self.ctr = ""               # the slot of its counter or index
        self.stop = Val("", "")     # a range loop's stop, evaluated once


class IFn:
    # one compiled function: a function, a method, a module's init, a helper or a template instance
    def __init__(self, f: FnInfo):
        self.f = f                      # f.ret is final once the IFn is complete
        self.ps: list[str] = []         # the parameters passed (None-typed ones are dropped)
        self.slots: list[Ins] = []      # entry-block storage ("slot" ops)
        self.blocks: list[Blk] = [Blk("entry")]
        self.loops: list[Loop] = []
        self.cold: dict[str, str] = {}  # message "Kind: text" -> label of the block that raises it
        self.n = 0                      # the counter behind %tN, LN and %name.N
        self.cur = "entry"              # the block being filled, and whether it has ended
        self.term = False
        self.key = ""                   # a template instance: ",".join(argument types)
        self.site = 0                   # and the line of the call that compiled it
```

`Gen` gains these fields:
- `fn: IFn` and `blk: Blk`: the function and block being built. They replace `body` and `allocas`.
- `fns: list[IFn]`: finished functions, in completion order.
- `holes: list[str]` (§5.2).

### 3.2 Types

**The type language does not change.** Types are the canonical strings of today:
- `int`, `float`, `bool`, `str`, `None`, `file`;
- `list[T]`, `dict[K,V]` with `K` either `int` or `str`, and `tuple[A,B]` including `tuple[]`;
- qualified class names (`mod$C`).

Every helper (`targs`, `elem`, `subst`, `tname`) and every error message is written in terms of these strings, so they stay as they are.

**Special forms:**

| form | where it may occur |
|---|---|
| `list[?]`, `dict[?,?]` | Values made by an empty-container site before its variable is refined. The creating `Ins` holds the hole id in `k`, and the final type ends up in `Gen.holes` (§5.2). |
| `""` | Only during elaboration: an unannotated template parameter, or a template's return type before its first value return. Never in a finished `IFn`. |
| `!message` | A poisoned declaration (§6.4), which replaces today's placeholder `int`/`None`. Elaboration raises the message when it reaches the declaration. Never in an `IFn`. |
| `%addr`, `%slot` | Backend pseudo-types, which no canonical type can spell. `%addr` is a storage address: an alloca, a global, a field. `%slot` is an 8-byte container slot. Both disappear at the re-baseline (§3.8). |

**Class types are nullable.** `opt()` erases `Optional[C]` and `C | None` to `C`, so `C` means "a C or None". The fact that a value is not None lives on the value (`Val.nn`), not in the type. Dynamic values (M4, #9) will add explicit `C|None` and scalar optionals (§7.6).

**`lt` and `rtt` become lowering-only.** They map types to LLVM types and to the runtime's bool-as-i64 convention. Types are not interned; if profiles show string compares on types, `list[str]` plus `dict[str, int]` can intern them later.

### 3.3 Operands and constants

**Operands are `Val`s.**
- Until the re-baseline, `Val.v` is the final LLVM spelling. Converted ops and not-yet-converted `raw` text can therefore refer to each other, which is what lets the migration convert one construct at a time.
- At the re-baseline, `v` is replaced by a value id, and the lowering assigns spellings.

**Constants are tested in one place.** One helper, `Gen.lit(v)`, answers "is this operand a constant?". It replaces the five spelling tests of §1.2. Until the re-baseline its body is the spelling test; afterwards it tests whether the defining op is `const`.

**Non-null is a property of the value.** `Val.nn` replaces `Gen.nn`. It is set for:
- the method receiver `%a0`;
- a load of `self` that the method never reassigns;
- a new object.

### 3.4 Instructions

The tables below list each op's operands (`a`), immediates, result type, effects (§3.7) and LLVM lowering. Ops marked T end their block.

**Control**

| op | operands | immediates | result | effects | lowering |
|---|---|---|---|---|---|
| `br` | – | `b`: [target] | – | T | `br label` |
| `cbr` | c: bool | `b`: [then, else] | – | T | `br i1` |
| `check` | bad: bool | `s`: "Kind: text"; `b`: [next] | – | T R | `br i1 bad, label %cold, label %next`, with the cold label from `IFn.cold[s]` |
| `ret` | [v] | – | – | T | `ret <lt> v`, or `ret void` |
| `ret.none` | – | – | – | T | `ret void` or `ret ptr null`, from the instance's final return type |
| `raise` | kind: str, message: str | `s`: kind | – | T N | `pys_raise`, then `unreachable` |
| `unreachable` | – | – | – | T | `unreachable` (after `sys.exit`) |
| `phi` | values | `b`: predecessors | t | – | `phi` |
| `select` | c, x, y | – | t | – | `select` |

**Storage** (lowered to entry-block allocas, which mem2reg turns into SSA)

| op | operands | immediates | result | effects | lowering |
|---|---|---|---|---|---|
| `slot` | – | `s`: name ("" for a hidden counter); `k` = 1 for an "is assigned" flag | – | – | `alloca` plus `store zeroinitializer` (or `store i1 false`), in `IFn.slots` |
| `load` | addr | – | t | rG or rO for a global or field; none for a slot | `load` |
| `store` | addr, v | – | – | wG or wO for a global or field | `store` |
| `fld` | o: C | `s`: class; `k`: field index | `%addr` | – | `getelementptr %C.<class>` |
| `fflag` | o: C | `k`: flag index | `%addr` | – | the same GEP, to the flag after the fields |

Globals, hidden defaults (`@d.*`) and flags (`@g.x.def`) are addresses, written as `Val("@g.x", "%addr")`.

**Scalars**

| op | operands | immediates | result | effects | lowering |
|---|---|---|---|---|---|
| `ovf` | x, y: int | `s`: + - * | int and bool (overflowed) | – | `llvm.s{add,sub,mul}.with.overflow` and two `extractvalue`s, so it defines three numbers |
| `arith.i` | x, y: int | `s`: & \| ^ | int | – | `and`/`or`/`xor` |
| `arith.f` | x, y: float | `s`: + - *, or unary - | float | – | `fadd`/`fsub`/`fmul`/`fneg` |
| `not`, `inv` | x | – | bool / int | – | `xor` |
| `cmp.i`, `cmp.f` | x, y | `s`: Python operator | bool | – | `icmp`/`fcmp` through `ICMP`/`FCMP` (`!=` is `une`) |
| `cmp.ref` | x, y | `s`: is, is not | bool | – | `icmp eq`/`ne ptr` |
| `isnull` | v: C | – | bool | – | `icmp eq ptr v, null` |
| `conv` | x | `s`: i2f b2i b2f | float / int | – | `sitofp`/`zext`/`uitofp` |

**Objects, tuples and lengths**

| op | operands | immediates | result | effects | lowering |
|---|---|---|---|---|---|
| `new` | – | `s`: class | C, not None | A | `pys_alloc(ptrtoint (gep %C null, 1))` |
| `len` | x: list, dict or str | – | int | rL / rD / none | `load i64, ptr x` (the header) |
| `tuple.new` | elements | – | tuple | A | `pys_alloc(8n)` plus one store per element |
| `tuple.get` | x | `k`: index | the element type | – | GEP and load |

**Calls**

| op | operands | immediates | result | effects | lowering |
|---|---|---|---|---|---|
| `call` | arguments | `s`: the callee's symbol (a function, method or template instance) | its return type | the callee's summary (U while unknown) | direct `call`; arguments of type None are left out |
| `init` | – | `s`: module | – | U | `call void @init.<module>()` |
| `rt` | arguments | `s`: a RUNTIME key; `x`: the static type for a `#` descriptor; `k`: hole id for `list.new`/`dict.new` | from RUNTIME | from RUNTIME | `call @<symbol>`, plus the descriptor constant |

**Transitional** (all gone by the re-baseline)

| op | operands | immediates | result | effects | lowering |
|---|---|---|---|---|---|
| `raw` | – | `s`: LLVM text | – | all | the text |
| `box`, `unbox` | v | – | `%slot` / t | – | `bitcast`/`zext`/`ptrtoint` and their inverses |

**About `rt`.** Every operation the C runtime implements is an `rt` op whose key names a `RUNTIME` entry. This covers about 110 operations:
- list, dict and str operations and methods;
- the CALLS builtins;
- formatting;
- files and I/O;
- `int`'s `//`, `%`, `**`, `<<`, `>>` and `/`;
- `float`'s `/`, `//`, `%`, `**`;
- `math`, `os`, `time`.

The keys follow the runtime's names: `list.get` is `pys_list_get`, `dict.has` is `pys_dict_has`, `dict.getitem` is `pys_dict_getitem`. Optimization passes match these keys. A generic operation (`eq`, `repr`, `format`, `list.find`, `list.sort_r`, `list.minmax`, ...) carries in `x` the full static type it works on. Lowering turns that type into the descriptor string, which `sconst` already registered when the op was built.

### 3.5 Blocks, terminators and loops

**Blocks.**
- One IR block is one LLVM block. Lowering visits blocks in creation order, which is the order `place` put them in.
- Phi predecessors are labels taken from the builder's current block (`IFn.cur`), as today.
- Every block ends with exactly one terminator.
- Code after a terminator opens a fresh block, as `emit` does today. So dead code in ordinary functions is still type-checked and emitted, while in template instances `stmts` stops after a terminator.

**Loops.** `Loop` records are written by `while_`, `for_range`, `for_rrange` and `for_seq`, and lowering ignores them. They keep the shapes that loop optimizations and a structured backend need:
- where a range loop's stop was evaluated;
- which sequences a `seq` loop steps through, and in which mode;
- which slot holds the counter;
- where `break` lands, after the `else` block.

**The control-flow graph.** The source is structured, so the graph is reducible. The only edges that are not structured are `check`'s implicit raising edge and the joins of expression `phi`s.

### 3.6 Checks and cold paths

**How a check works.**
- `check(bad, "Kind: text")` ends its block. Its one explicit successor is the next block, and its raising edge is implicit.
- `IFn.cold` maps each message to a label. The label is taken at the first check with that message, which keeps today's numbering.
- `Gen.function` places the cold blocks after the body. Each holds a `raise` and an `unreachable`, so there is still one cold block per function and message.
- `check` names only the message, not the cold block. An exception lowering can therefore route the same check to a handler later, without changing the builder (§7.2).

**Where checks are emitted:**
- **Overflow** (`iop` is `ovf` plus `check`): `+`, `-` and `*`, unary `-`, `abs`, and enumerate's start. `for_range` instead uses the overflow flag of its increment to end the loop.
- **None receiver** (`notnone` is `isnull` plus `check`): field access, method calls, `len` of an object.
- **Definite assignment:** a local's flag, a global's flag, a field's flag, and "function not defined yet". Each is three ops: `load` of the flag, `not`, `check`.
- **Other run-time conditions:**
  - a `range` step of 0;
  - `__len__` returning a negative number;
  - `divmod` of floats by zero;
  - a computed format spec on an object or file, which must be empty.
- **Messages chosen at run time** (`none_operand`, `richcmp`): a `raise` whose message operand comes from a `select`.

**Checks that stay inside the runtime.** Bounds and key checks stay inside runtime calls, marked R: `pys_list_get`'s index check and `pys_dict_getitem`'s `KeyError`. The optimizations of §7.1 split them out.

### 3.7 Effects

Effects are letters, kept in two tables next to `METHODS` and `CALLS`. `OPS` gives the letters of each op. `RUNTIME` gives each runtime operation its signature, its effects and its LLVM symbol:

```python
# "result:params|effects|symbol". Params use the METHODS language: S the receiver, T K V its
# element, key and value types, * an element (an 8-byte slot in the LLVM binding),
# # the descriptor of the static type in Ins.x. "" as symbol means pys_<key, with . as _>.
RUNTIME: dict[str, str] = {
    "list.get": "*T:S,int|R rL|",
    "list.set": "None:S,int,*T|R wL|",
    "list.append": "None:S,*T|A wL|",
    "list.find": "int:S,*T,#|rL rD U?|",
    "dict.getitem": "*V:S,*K|R rD|",
    "dict.has": "bool:S,*K|rD|",
    "dict.set": "None:S,*K,*V|A wD|",
    "eq": "bool:*T,*T,#|rL rD rO U?|pys_eq",
    "repr": "str:*T,#|A rL rD rO U?|pys_repr",
    "cmp_if": "int:int,float||pys_cmp_if",
    "raise": "None:str,str|N|pys_raise",
    ...
}
```

**The letters.**

| letter | meaning |
|---|---|
| R | May raise. Today a raise prints its message, flushes stdout and exits (closing the open files). |
| N | Never returns. |
| A | Allocates; a collection may run. A collection also closes the open files that nothing refers to any more, flushing them and reporting a failed close on stderr. That is not I, rF or wF: when a dropped file is closed is unspecified (README), and any change to the program's allocations moves it. |
| U | May run user code: a direct call, a dunder, or a callback from the runtime through `pys_obj_eq/cmp/repr`. U implies every other letter. `U?` means U when the static type contains a class. |
| I | I/O, the process, or global runtime state (`pys_repr_enter`/`leave`). |
| rL / wL | Reads / writes lists, contents or length. |
| rD / wD | Reads / writes dicts. |
| rO / wO | Reads / writes object fields and their flags. |
| rG / wG | Reads / writes globals and their flags. |
| rF / wF | Reads / writes file state. |

**What has no letter:**
- Reading strings and tuples, which are immutable once built.
- Loads and stores of slots, which are never address-taken.
- Dict operations never call user code, because keys are only `int` or `str`.

**Rules that follow from the letters:**
- An R op must not move across an I or a U op, because every error flushes stdout and exits.
- A list length read is invalidated by any wL or U op. `for_seq` re-reads the length each round, because the loop body may change the list.

**Summaries and checks.**
- Each `IFn` gets a summary: the union of its ops' letters, where a call counts with its callee's summary. A callee that is unfinished or recursive counts as all letters.
- Because lowering runs after the whole program has been built, a fixpoint over the call graph gives exact summaries.
- While the migration lasts, `rt` checks that each call site's declaration matches its `RUNTIME` entry, so the corpus verifies the table.
- `tools/check_runtime.py` checks the table against the prototypes in `runtime.c`.

### 3.8 The end state

During the migration, the IR still carries LLVM spellings so that each step can be identical. The last step (§6.2, step 16) removes them:

| until the re-baseline | after it |
|---|---|
| `Val.v` is an LLVM spelling; `Ins.r` holds numbers given by the builder | value ids; lowering numbers `%tN` densely per function |
| a constant is a `Val` whose spelling is a literal | a `const` op; `lit` tests the op |
| labels such as `L12` | block ids |
| `load`/`store` on `%addr` | `local.get`/`local.set` (slot id), `global.get`/`global.set` (qualified name), `field.get`/`field.set` (class, field) |
| `box`/`unbox` and `%slot`; bools passed to the runtime as `conv b2i` | gone: lowering converts at each use, with a cache per block, so `augassign`'s shared dict key is converted once |
| None of a class type is `Val("null", C)` | `const None : C` |
| cold blocks are built by `Gen.function` | built by lowering |
| `@s.N` and `declare`s numbered while building | numbered in lowering order; constants that nothing references are dropped |
| `dry` leaks numbers, slots, strings and declares | a scratch region keeps only template instances, `called` marks and refinements of other variables |

After this step the IR contains no LLVM text. `class Lower` is then the only code that knows LLVM, and a second lowering can be written beside it.

### 3.9 An example

This is the end-state dump (`pystachy ir --typed`) of a word count, shortened:

```python
def count(words: list[str]) -> dict[str, int]:
    d: dict[str, int] = {}
    for w in words:
        if w in d:
            d[w] += 1
        else:
            d[w] = 1
    return d
```

```
fn @f.count(words: list[str]) -> dict[str,int]                       effects: A R rL rD wD
  slot s0 words: list[str]   slot s1 d: dict[str,int]   slot s2 w: str   slot s3: int
b0: v0 = param 0; local.set s0 v0; v1 = const 0 : int
    v2 = rt dict.new v1 : dict[str,int] [A]; local.set s1 v2
    v3 = local.get s0 : list[str]; local.set s3 v1; br b1
                          ; loop seq: head b1, body b2, step b5, exit b6, over v3, counter s3
b1: v4 = local.get s3; v5 = len v3 : int [rL]; v6 = cmp.i < v4 v5; cbr v6 b2 b6
b2: v7 = rt list.get v3 v4 : str [R rL]; local.set s2 v7
    v8 = local.get s1; v9 = local.get s2; v10 = rt dict.has v8 v9 : bool [rD]; cbr v10 b3 b4
b3: v11 = rt dict.getitem v8 v9 : int [R rD]; v12 = const 1
    v13, v14 = ovf + v11 v12; check v14 "OverflowError: integer result does not fit in 64 bits"
b7: rt dict.set v8 v9 v13 [A wD]; br b5
...
```

The dump shows two optimizations:
- **The list read can be unchecked.** `rt list.get v3 v4` follows `cmp.i < v4 (len v3)` with no wL or U op between them.
- **The three dict operations can share one lookup.** `dict.has`, `dict.getitem` and `dict.set` act on the same values, with no wD or U op between them.

## 4. Passes

### 4.1 The pipeline

```
source ─► Lexer ─► Parser ─► Loader ─► Declare ─► Flow ─► Elaborate ─────► IR: one IFn per compiled
                                        (Gen.program's   (unchanged)  (Gen's walk:    function, in the order
                                         declaration                   types, folds,   they were finished
                                         steps)                        instantiates)       │
                                                                                           ├─► IR passes (later)
                                                                                           ▼
                                                     Lower: LLVM text ─► opt mem2reg,instcombine,simplifycfg + lli
                                                                       │ llvm-link runtime.bc + clang -O2
```

### 4.2 Lexical resolution

**Today.** Resolution is split between the Loader, which qualifies module-level names, and `Gen`, which probes its tables at each use.

**In the IR, names are already resolved:**
- slots;
- qualified globals (`@g.<qname>`);
- the callee instance of a `call`;
- module inits;
- `RUNTIME` keys for builtin modules (`modattr`).

So no backend ever resolves a name, and the IR does not have to wait for a separate resolver.

**The resolver is a parallel track (§6.4).** It has two subset classes:

```python
class Scope:
    # a module, function or comprehension body: what each name means in it
    def __init__(self, kind: str, parent: int):
        self.kind = kind                    # "module" "def" "comp"
        self.parent = parent                # enclosing scope id; -1 for a module
        self.names: dict[str, int] = {}     # name -> binding id: parameters, then locals by CPython's rule
        self.decl: dict[str, bool] = {}     # names declared global
        self.refs: dict[str, int] = {}      # module-level bindings this scope reads or writes


class Bind:
    def __init__(self, kind: str, name: str, scope: int):
        self.kind = kind   # local comp global func class bmod builtin poison
        self.name = name   # qualified name; the dotted path for bmod; the message for poison
        self.scope = scope
```

**How it is built.**
- `Node` gains `b`, the binding of a name or of the root of an attribute chain, and `sc`, the scope of a def, comprehension or module.
- One function computes a scope: parameters, local names, `globals_in`, and the `global_order` errors. It replaces the five computations of §1.2.
- The Loader builds the scopes. `Loader.simplify` consults them before it treats `os`, `sys` or `TYPE_CHECKING` specially, which fixes #4 §1 B and C.

**The binder.** It runs after the Loader and maps each name to a binding. It first runs in *mirror mode*: `Gen` keeps its probes, and any disagreement with the binder is an internal error. Once the corpus shows no disagreement, these probes are deleted:
- the probe chains in `load_name` and `call`;
- `is_global`, `bound`, `dotted` and `qtype`;
- the comprehension shadowing done through `hide` and `compvars`.

**What stays in elaboration.** Facts that depend on the instance or the program point:
- a local without a slot yet: "read before its first assignment";
- a parameter whose argument is None (`nonevars`, `noneglobals`): a constant None;
- a `?` type: the look-ahead.

**Flow then tracks less.** It tracks `scope.names ∪ scope.refs` instead of a copy of every module global. Its work per function becomes proportional to the function's size and references, and its marks do not change. This is the bounded design #4 §2 asks for.

### 4.3 Declarations

The declaration steps of `Gen.program` keep their code and order. They record data instead of encodings:
- **`FnInfo.dkind: list[int]`** (`DINL`, `DGLOB`, `DNONE`, `DBAD`) replaces the four states of `dglob`. `dglob` keeps only the hidden global's name or the message.
- **`FnInfo.synth`** (an `__init__` the compiler wrote), **`FnInfo.retann`**, **`FnInfo.modinit`** and **`ClassInfo.dc`** replace the shape tests:
  - `is_dc`'s kid count;
  - the `noann` test in `function`, `fl_fields` and `hoist_class`;
  - the `@init.` prefix test.

**Two later changes alter output, so they are behavioural fixes (§6.4):**
- `ann(n)`, a fallible `typeof` that returns a type or `!message`, replaces `ann_problem` (bug A).
- The poison type `!message` replaces the placeholder types. This changes the struct layout printed for a bad imported class.

### 4.4 Elaboration: typing, folding and instantiation

**This is `Gen`'s walk, with its logic unchanged:**
- `stmts`, `stmt`, `expr`;
- `call`, `call_fn`, `instance`, `method`, `bmethod`, `builtin`, `consume`;
- `static`, `has`, `isinst`, `static_type`;
- `empty`, `refine`, `lookahead`, `fills`, `typed_now`, `dry`, `fill`;
- `hoist`, `hoist_class`, `obj_helpers`, `listcomp`, `percent`, `format_`, `print_`, `open_`, `coerce`.

Its builder primitives keep their names and signatures (`tmp`, `label`, `emit`, `ins`, `place`, `br`, `cbr`, `rt`, `checked`, `guard`, `iop`, `notnone`, `alloca`, `raise_`, `sconst`), but now they make `Ins`.

**It stays one walk with folding, because folding decides what gets type-checked:**
- The untaken branch of an `isinstance`, `hasattr` or `is None` test that the types decide is never compiled, and it may be ill-typed.
- In a template instance, nothing after a terminator is compiled.
- The first `return` with a value fixes an instance's return type, and a recursive call before it is an error.
- The type of a conditional expression depends on which arms reach the join.

A second walk would have to repeat all of this.

**The expected type `want` still flows top-down.** It types empty displays, `None` and comprehension elements. `coerce` still allows only:
- identity;
- None becoming the null of a class type (`int` does not become `float`);
- bool becoming int in `ival` and in `METHODS` int parameters (`as_int`).

Numeric promotion stays inside the operators (`as_float`). These conversions become `conv` ops.

**Every user-facing error is raised here, in today's order.** This includes:
- `generic_use`'s "tuples are limited to 9 elements" and "X values cannot be compared or printed";
- `alloca`'s "cannot infer the type of 'x'";
- the template check "returns both None and X", which `function` makes after `stmts` by scanning its `IFn` for `ret.none` (prototyped).

### 4.5 Effects

Effects are tables, plus one summary per function (§3.7). Nothing reads them in the byte-identical steps except the IR verifier (`PYSTACHY_IRCHECK=1`), which checks two things:
- every op is in `OPS`;
- every `rt` key is in `RUNTIME`.

Their uses come later:
- **Soundness conditions** for the passes of §7.1.
- **LLVM attributes** on declarations: `noreturn` on `pys_raise` and `pys_exit*`; `memory(none)` on `pys_cmp_if` and `pys_range_len`; `nounwind` while nothing unwinds.
- **Exceptions:** which calls need an error test (§7.2).
- **Eligibility** in the CPython-extension mode.
- **A sharper `Flow.user_call`.**

### 4.6 Lowering

Lowering turns each `IFn` into LLVM text.

**What it takes over:**
- `function`'s tail: the `define` line, `entry:`, the allocas;
- the `ret <none>` and `<keysN>` patches, as the lowering of `ret.none` and `dict.new`;
- `dispatch`;
- the header and `@main` from `program`;
- `lt` and `rtt`;
- the text half of `desc`;
- `global_var`'s text.

At step 15 these move out of `Gen` into `class Lower`, which holds a reference to `Gen`'s tables. This keeps the diff small until then.

**It keeps today's contract exactly:**
- every slot is an entry-block `alloca` with a zero store (or `i1 false` for a flag), with a load or store at each use;
- `phi`s only where the builder made them;
- `ptr nonnull %a0` for `self`, and None-typed parameters dropped;
- bools passed to the runtime as `i64`;
- `%C.<class>` structs with the flag `i1`s after the fields;
- `@pys.roots`;
- `@main` calling `pys_init`, then `@main.init`, then `pys_finish`.

Pystachy builds no SSA itself.

**Five rules make output identical until the re-baseline:**
- **R1. The builder owns numbering.** `%tN`, `LN` and `%name.N` come from `IFn.n`, in exactly today's order, and are stored in the `Ins`. Lowering never allocates a number. An op that prints several defining lines (`ovf`) reserves its numbers with `put(i, k)` the way separate instructions were numbered. That includes the label `emit` opens between the first and second numbers when the op starts dead code (§6.3, step 0).
- **R2. The builder fills the program tables, in today's order:** `decls`, `strs`/`consts` (`@s.N`), `globs`/`gcroots`, `ocls`, `called`, `holes`. Lowering only reads them, together with `f.ret`.
- **R3. The output order is today's:** functions in completion order (`Gen.fns`, so template instances come before their callers), then `dispatch`, then the header.
- **R4. Each op prints exactly the lines of the helper it replaces.**
- **R5. Lowering cannot fail on user input.** Its only error is "internal error: no lowering for op X". This rule stays after the re-baseline.

### 4.7 What in Gen becomes what

| today | after |
|---|---|
| `program`'s declaration steps, `declare_fn`, `declare_fields`, `scan_fields`, `guess`, `dc_methods`, `synth`, `check_special`, `class_problem`, `typeof`, `vtype`, `scan_imports`, `check_import` | **Declare**: the same code, recording data (§4.3) |
| `flow_program`, `Flow`, `fl_*` | **Flow**: unchanged; later over bindings (§4.2) |
| `is_global`, `bound`, `dotted`, `qtype`, the probe chains of `load_name` and `call`, the five local-set computations | **Resolve** (parallel track); elaboration then switches on the binding |
| the typing half of everything under `stmt` and `expr`, `instance`, `static` & co, `empty` & co, `hoist`, `obj_helpers`, `coerce`, the registration half of `desc` (`generic_use`) | **Elaborate**: unchanged logic, builds `Ins` |
| `tmp`, `label`, `emit`, `ins`, `place`, `br`, `cbr`, `rt`, `checked`, `guard`, `iop`, `notnone`, `alloca`, `raise_`, `sconst` | **builder primitives**: same names, now making `Ins` |
| `to_slot`, `from_slot`, `rarg`, `rres` | builder primitives making `box`/`unbox`/`conv` until the re-baseline, then lowering helpers |
| `function`'s tail, the two text patches, `dispatch`, the header in `program`, the text of `desc`, `lt`, `rtt`, `global_var` | **Lower** |
| `Frame`, `save`, `restore` | keep the typing fields. The emission fields move into `IFn` (step 9). After step 15 they can become one context object, swapped by reference. |

## 5. How the hard parts map

### 5.1 Templates

**What `instance()` keeps:**
- the key `",".join(argument types)` into `FnInfo.insts`;
- the names `@f.<name>.<k>`, numbered in order of first compile;
- the `making` chain, with its error suffix and its limit of 100 levels;
- the error for a recursive call before the first return;
- sharing `params`, `defaults`, `dglob`, `dtypes` and `uflags` between the generic `FnInfo` and its instances.

**What it does differently:**
- It saves the typing state in `Frame`, which now also holds `fn` and `blk`.
- It builds a new `IFn` for the instance, appends it to `Gen.fns` when it is complete, and restores.

**Ordering and calls.**
- The caller's `call` op is built after the instance is complete, so its result type is `g.ret`.
- `Gen.fns` is in completion order, so instances still precede their callers in the output.

**Template-specific rules.**
- An early `return None` is a `ret.none` op instead of the text `ret <none>`. It is lowered from the final `f.ret`.
- `stmts` keeps its rule of stopping after a terminator in instances.

**Specialization accounting.** `IFn.key` and `IFn.site` give #4 §4 what it asks for. `pystachy ir --stats` prints, per template:
- the instance keys;
- each instance's op count;
- the call that compiled it;
- the nesting depth.

### 5.2 Empty-container placeholders

**Holes replace placeholder tokens.**
- `empty()` builds `rt list.new` or `rt dict.new` with `k` set to a new hole id, and type `list[?]` or `dict[?,?]`.
- `Gen.holes[k]` starts as `""`.
- `lkk` and `gkk` hold each variable's hole ids instead of `<keysN>` tokens.
- `refine` writes the final type into `holes[k]` for every hole of the variable. It replaces `keykind`.
- `fill`, `x[k] = v`, `+=`, a store and `lookahead` trigger refinement exactly as today.

**Earlier values stay unrefined.** Values made before the refinement keep their `?` type, and only `len`, truth tests, `fill` and assignment may read them (`allowq`).

**Lowering reads the holes.**
- Lowering prints a dict's key kind from `holes[k]`, using 0 when nothing filled the hole, as today.
- Lowering runs after the whole program has been built. A global dict filled by a function compiled later therefore needs no patch.
- A comprehension's result list gets a hole too: `pys_list_new(0)` is emitted before the first `lcappend` fixes the element type. A typed backend thus knows every element type at creation.

**Look-ahead and `dry`.**
- `dry()` builds into scratch blocks and drops them (prototyped). Until the re-baseline its other leaks stay byte for byte.
- `fills` should use only facts that hold for the whole function: parameters and `nonevars` that the function never stores. That is the fix for bug F, which is behavioural.
- #17's cases 2 and 4 (a global dict read before the function that fills it, and a `*args` template whose list nothing fills) are open questions (§9).

### 5.3 Static folding

Folding stays entirely in elaboration:
- `static`, `has`, `isinst`, `only_class` and `static_type` read the same environment as today: `ltype`, `nonevars`, `noneglobals`, `gflag`, and Flow's `Node.chk`.
- A pruned branch produces no IR, so it is still never type-checked.
- An `isinstance` or `hasattr` call that folds outside an `if` reaches the IR as a constant `cbr` operand, as it does today, and `simplifycfg` or a later pass removes it.
- Because folding happens once, before any backend, every backend inherits the CPython-compatible dispatch in templates.

### 5.4 Deferred errors

**The rule stays "an error only where the code is compiled".**
- Errors stay fatal during elaboration.
- An `IFn` exists exactly when its code was elaborated:
  - lazy library functions once `called`;
  - template instances per call;
  - taken branches.
- These all raise when elaboration reaches them: `FnInfo.bad`, `ClassInfo.bad`, `unsupported`, `DBAD` defaults, and the Loader's `badattr` and `badimport` nodes.
- So a finished `IFn` never contains poison. The exception is lenient mode (`obj_helpers`), whose unsupported comparisons are deliberate run-time `raise`s.

**Poison in declarations.** On the declaration side, the poison type `!message` and the fallible `ann()` fix bugs A and D at their source (§6.4).

**Recoverable elaboration later.** The CPython-extension mode will need elaboration that records the first error and abandons the `IFn`, instead of exiting (§7.4).

### 5.5 Definite assignment

**Flow is unchanged.** `Node.chk`, `uflags`, `gflag`, `late` and `fflag` still decide which reads are checked. The builder makes the checks explicit:
- **Flags:**
  - a `slot` with `k = 1` for each flagged local;
  - `@g.<name>.def` for globals, functions and classes;
  - `fflag` for fields.
- **Writes:** `store true` on assignment and `def`; `store false` on `del`.
- **Reads:** `load`, `not` and `check` on a marked read. The message is "UnboundLocalError", "NameError", or "AttributeError" for another module's `late` global.

**Later passes.** A pass can drop a check that follows another check of the same flag with no `store false` in between. Today only LLVM does that, and only after mem2reg. Running Flow per instance after folding would sharpen the marks (§9).

### 5.6 Module init, defaults and None arguments

**Module init.**
- `@init.<module>`'s run-once guard becomes ordinary IR at the start of the function: `load` of `.done`, `cbr`, `ret`, `store`.
- `uimport` becomes `init`.

**Global types.**
- Module code is still compiled first, so global types are still fixed by the first store in elaboration order.
- Imported modules' literal constants are still declared before that.

**Defaults.**
- The `defaults`/`cdefaults` markers still run `hoist`/`hoist_class` at the position of the `def` or `class`. These store into hidden `@d.*` globals.
- `call_fn` chooses between loading the hidden global and evaluating the default inline by `dkind`, at the same moment as today.

**None arguments.**
- A None argument is still left out of the call.
- The callee's parameter reads as a constant None (`nonevars`).
- The flow-sensitive rebinding of such a parameter outside branches stays an elaboration rule: a new slot type from that point on.

### 5.7 Objects, descriptors and the object protocol

**Objects.**
- Lowering prints the struct layout from `ClassInfo`: the fields, then one `i1` per `fflag` entry.
- A constructor is `new` followed by a `call` of `__init__`.
- A method call is a static `call`, preceded by `isnull` and `check` unless `Val.nn` says the receiver is not None.

**Descriptors and class ids.**
- `generic_use(t)` does what `desc` does during elaboration, but produces no text. It walks the type in the same order, registers classes in `ocls` in the same order, and raises the same two errors.
- `desc` keeps only the text.
- So the `O<id>` numbering and the lazy fixpoint over `obj_helpers` do not change.

**The object protocol.**
- The `@o.eq/cmp/repr.<class>` helpers stay synthesized ASTs, elaborated in lenient mode into ordinary `IFn`s.
- `dispatch` (`pys_obj_*`) belongs to the LLVM lowering.
- Another backend would call the same helpers in its own way: from monomorphized generic helpers in Wasm, or as `tp_richcompare` and `tp_repr` in CPython.

**`with` and temporary files.**
- `withs` holds `Val`s.
- `close_withs` and `close_temp` still emit the close and drop calls at each exit.
- A cleanup region is part of the exceptions work (§7.2).

## 6. Migration plan

### 6.1 The oracle

**Each step must pass four checks:**
1. `make`: the bootstrap fixed point.
2. `tools/irsame.sh`, run against the previous commit with both the native and the CPython-hosted compiler. It compares:
   - byte for byte, the `ir` output of `tests/*.py`, `tests/deviations/*.py`, `bench/*.py`, `pystachy.py` and `tests/ir/*.py`;
   - for the 126 `tests/errors/*.py`, the full stderr and the exit status.

   That is 358 programs today, about 5 s with the native compilers.
3. `make test`, as a sanity run.
4. Native self-compile time no worse than 1.3× the reference. `tests/verify.sh` already records it.

**Behaviour changes never go into these steps.** A bug fix or an optimization is its own commit. Its expected changes in the oracle are reviewed, and new tests are added.

### 6.2 Steps

The first four steps are refactors that make later steps possible. Steps 5 to 7, and parts of step 8, were prototyped on `bd4cd6a` (§6.5).

0. **Tooling, with no compiler change (§6.3).** `tools/irsame.sh`, `make irsame`, the `tests/ir/` probes, and `make check-ir`.
1. **Facts on values instead of in text.**
   - `Val.nn` replaces `Gen.nn`.
   - `Gen.lit(v)` replaces the five constness tests.
2. **Registries on the typing side.** `generic_use(t)` registers `ocls` and raises `desc`'s errors; `desc` only spells.
3. **Declarations as data.** `dkind`, `synth`, `retann`, `modinit`, `dc` (§4.3).
4. **The RUNTIME table.**
   - `rt` and `checked` build each `declare` line from the table. A call site that disagrees with the table is an internal error.
   - Add `tools/check_runtime.py`.
   - The decls keep their insertion order.
5. **The IR container** (prototyped).
   - `Ins`, `Blk`, `IFn`.
   - `body` and `allocas` become `fn` and `blk`, in `Gen` and in `Frame`.
   - `emit` makes `raw` ops through a new `add`, which opens a fresh block when the current one has ended.
   - `place` and `br` start new `Blk`s.
   - `alloca` writes `fn.slots`.
   - `dry` swaps the blocks.
   - `function` prints its `IFn` at its end.
6. **Lower at program end** (prototyped).
   - `function` appends its `IFn` to `Gen.fns`.
   - `program` lowers all of them, in order, just before `dispatch`.
7. **Holes become ops** (prototyped with tokens).
   - `ret.none` replaces `ret <none>`.
   - `rt dict.new` and `rt list.new` carry hole ids.
   - `Gen.holes` replaces `keykind`.
   - Both text patches are deleted.
8. **Control and checks.**
   - `br`, `cbr`, `ret`, `unreachable`, `phi`, `select`, `check` (prototyped) and `raise`.
   - `ovf` through `put()` (prototyped).
   - `Loop` records in `while_`, `for_range`, `for_rrange` and `for_seq`.
   - The IR verifier under `PYSTACHY_IRCHECK=1`, turned on in `tests/run.sh`:
     - one terminator per block, and only at its end;
     - phi predecessors exist;
     - every op is listed in `OPS`;
     - every `rt` key is in `RUNTIME`.
9. **Per-function emission state into `IFn`.**
   - `n`, `cur`, `term` and `cold` move into `IFn`; `Frame`, `save` and `restore` lose them.
   - The 26 lines that use `self.cur` and the 27 that use `self.term` change mechanically.
10. **Storage.**
    - `slot`, `load` and `store` in `alloca`, `load_name`, `read`, `store_name`, `declare`, `del_name`.
    - Hidden counters and `@d.*` defaults.
    - The init guard.
11. **Objects.** `new`, `fld`, `fflag`, and `isnull` plus `check`, in `field`, `getfield`, `setfield`, `notnone`, the constructor in `call`, and `hasattr`.
12. **Scalars.**
    - `arith.*`, `cmp.*`, `conv`, `not` and `inv`, in `arith`, `unary`, `cmp2`, `compare`, `truth`, `as_int` and `as_float`.
    - Constants still come from `lit`.
13. **Runtime calls.**
    - The 105 `rt` lines become `rt` ops with keys, a descriptor type in `x`, and explicit `box`/`unbox`/`conv`.
    - Split into small PRs by family: containers; strings and formatting; files and I/O; numbers and `math`.
14. **Calls.**
    - `call` and `init`.
    - `IFn.key` and `IFn.site`.
    - `pystachy ir --stats` (op histogram, `raw` count, ops per function and per template instance).
15. **Sweep.**
    - Convert the remaining `raw` sites until `ir --stats` shows none over the corpus, then delete the op.
    - Extract `class Lower`.
    - Add a lint, `tools/irlint.py`, that rejects LLVM text (` ptr `, ` i64 `, `%`, `@`) in the string literals of `Gen`'s elaboration methods.
    - Optionally replace `Frame` with a context object swapped by reference.
16. **Re-baseline.** This is the one step that is not byte-identical, and it is optional until a second backend needs it.
    - **What changes:**
      - lowering numbers values and blocks densely, per function;
      - `Val` holds value ids;
      - `const` replaces literal spellings;
      - `box`/`unbox` and `%addr` go;
      - string constants and declares are numbered in lowering order;
      - `dry` leaks nothing but instances, `called` marks and refinements;
      - lowering builds the cold blocks (§3.8).
    - **How it is verified:** with `tools/irnorm.py`, plus the full tests, the fixed point and `make verify`. `irnorm.py` does three things:
      - it renames `%tN`, `LN` and `%name.N` per function, and `@s.N` and `O<id>` program-wide, by first appearance;
      - it sorts declares;
      - it drops allocas that are never loaded.

      After normalization, old and new output must be identical, apart from the dropped dead code.

### 6.3 The first steps in detail

**Step 0: tooling, with no compiler change.**
- **`tools/irsame.sh OLD NEW`.** It runs both compilers in `ir` mode over the corpus of §6.1 in `PYSTACHY_JOBS` workers. It stops at the first differing file and prints a short diff.
- **`make irsame REF=<commit>`.** It writes `git show REF:pystachy.py` and `REF:runtime.c` into `build/ref/`, builds `build/ref/pystachy`, and runs `irsame` against `./pystachy`.
- **`make check-ir`.** It runs `llvm-as -o /dev/null` on the `ir` output of the corpus.
  - Today's corpus passes.
  - Once bug B's probe is added, it fails until B is fixed: today that probe prints `%C.A = type {void, i64}`.
- **`tests/ir/*.py`.** These are probes for paths the corpus never takes. They are only compiled (by `irsame` and `check-ir`), not run:
  - **Dead code after `return`, `raise` and `sys.exit`, whose first instruction defines several values.** `ins` takes its number before `emit` opens the block for dead code. So the output reads as below, and `put()` must reproduce it. No corpus program has such an op at the start of a block (0 of 1,297 checked operations).

    ```
      ret i64 %t2
    L4:
      %t3 = call {i64, i1} @llvm.smul.with.overflow.i64(i64 3, i64 4)
      %t5 = extractvalue {i64, i1} %t3, 0
    ```
  - **A template instantiated inside `lookahead`'s `dry`.**
  - **A global dict created empty in module code and filled only by a function** (`REG = {}`, `def add(k: str) -> None: REG[k] = 1`, `add("a")`, then `show()`).
  - **One guard message repeated in a function.**
  - **Nested template instances.**
  - **A template with `return None` before a return of an object.**

**Step 1: facts on values.**
- Add `self.nn = False` to `Val`.
- Set it in three places:
  - `load_name` for `self` when the method never reassigns it;
  - `function` for the receiver `Val("%a0", ...)`;
  - `call` for a constructed object.
- Read it where `Gen.nn` is read today: `notnone`, `none_operand`, `format_`, `isnull`, `richcmp`, `eqcall`, the `hasattr` case of `builtin`, and `obj_str`.
- Copy it wherever a `Val` is rebuilt from another's spelling. `irsame` shows any missed copy as a diff.
- Delete `Gen.nn` and its `Frame` field.
- Add `lit(v)` (today: `not v.v.startswith("%")`) and use it in `index`, `for_range`, the slice bounds in `expr`, and `cmp2`.

**Step 2: registries on the typing side.**
- Split `desc` into `generic_use(t)`, which recurses in the same order, registers classes in `ocls` and raises "tuples are limited to 9 elements" and "values cannot be compared or printed", and a text-only `desc`.
- Every caller of `desc` calls `generic_use` first.

**Step 3: declarations as data.**
- `declare_fn`, `default_problem` and `hoist` set `dkind`. `call_fn` reads it instead of the prefixes of `dglob`.
- `declare_fields` and `dc_methods` set `synth` and `dc`. `declare_fn` sets `retann` and `modinit`.
- `is_dc`, `function`, `fl_fields` and `hoist_class` read the flags.

**Step 4: the RUNTIME table.**
- Add `RUNTIME` beside `METHODS` and `CALLS`, with one entry per runtime function and per `llvm.*.with.overflow` intrinsic.
- `rt(name, ret, args)` finds the entry by symbol and checks that the call site's types agree.
- `tools/check_runtime.py` parses the prototypes in `runtime.c` and checks every entry.
- The effects letters are recorded, unused, for later.

**Steps 5 to 7: the prototype.**
- These are the diffs described in §6.2. The prototype adds `Ins`, `Blk`, `IFn`, `Gen.fns`, `add`, `put`, `lower` and `lower_ins`.
- It changes `Frame`, `save`, `restore`, `emit`, `place`, `br`, `guard`, `checked`, `alloca`, `empty`, `dry`, `function`, `program` and the `return` case of `stmt`.
- It routes five `pys_list_get` sites through one `list_get` op.
- It deletes the two patch loops.

### 6.4 Behaviour fixes and the resolver track

**Bug fixes.** Bugs A to F are fixed in their own commits, each with a test, and never inside an IR step:
- **B** first, because it is a crash. Validate the type `guess` returns: `None` or `""` is a poison type in an imported class and an error in the main program ("annotate the field").
- **A and D** together. They are the declaration side of M1's lenient annotations (#6):
  - a fallible `ann()` that returns a type or `!message` replaces `ann_problem`;
  - `!message` replaces the placeholder types;
  - `check_special` records its problem in `f.bad` for imported classes, and skips methods that are already poisoned.
- **C:** `guess(-e)` gives `int` for a bool operand.
- **E:** `dry` restores `self.line`.
- **F:** `fills` uses only facts that hold for the whole function.

**The resolver track.** The resolver of §4.2 can land at any time, because no IR step depends on it. It is a sequence of PRs:
1. One shared scope builder for the five computations (byte-identical).
2. The binder in mirror mode (byte-identical).
3. `Gen` reads bindings, and the probes are deleted (byte-identical).
4. Flow over referenced bindings (byte-identical, with before and after timings in the style of #4 §2).
5. `simplify` consults scopes (behavioural; it fixes #4 §1 B and C).

**Coordination with work already under way.**
- #4 §1 and #4 §2 are being addressed directly, alongside this design. If those fixes land first, the scope builder should reuse whatever they build for shadowing and for referenced globals rather than duplicate it.
- The README deviation "an import of a builtin module binds its names for the whole program" stays in mirror mode. Removing it is its own behaviour change.

### 6.5 Cost and budget

**Measured on the prototype** (steps 5 to 7, plus `check`, `ovf` and `list_get`):

| measure | result |
|---|---|
| lines | +133/−46 |
| bootstrap | fixed point holds (85,903 lines of IR) |
| corpus | 358 of 358 programs identical |
| native self-compile time | unchanged within noise |
| CPython-hosted self-compile time | from unchanged to +30% across runs (0.5 s to about 0.65 s at worst) |
| native live heap at the last collection | 12.3 → 24.6 MiB |
| native peak heap | 55.4 → 58.2 MiB |

Across the corpus, no runtime function is ever declared with two signatures, so one `RUNTIME` entry per function is enough.

**Projected for the full migration:**
- **Lines:** +500 to +800 (+8 to +12%).
  - About 100 for the classes and builder primitives.
  - About 250 for the lowering of about 35 ops.
  - About 150 for the `OPS` and `RUNTIME` tables.
  - About 100 for the verifier and `--stats`.
  - Against that, the text patches, `Gen.nn` and part of `Frame` go away.
- **Size of the compiler's own IR:** about 60,000 operations.
- **Compile time:** native self-compile +10 to 30%; CPython-hosted +25 to 60%.
- **Memory:** the live heap roughly doubles again (about 40 MiB).

**Containment:**
- The 1.3× gate in §6.1.
- If memory matters, lower each `IFn` when it is complete and keep only the positions of global holes that are still unresolved, which brings back a small patch for those.
- If profiles show the chain of op-string compares, intern op names to ints.

## 7. What it enables next

### 7.1 Language-level optimizations

Each optimization is a behavioural step after step 14. Each is a function over an `IFn`, and each can be switched off for differential runs (`PYSTACHY_OPT=-name`):

1. **Unchecked list reads in sequence loops.**
   - The pattern: a `list.get` at the loop's index, after the loop's own `cmp.i < len`, with no wL or U op between them.
   - Such a read lowers to an inline load.
   - Measured: 223 of the 1,083 `pys_list_get` calls in the self-compile.
2. **Dict lookup fusion.**
   - The pattern: `dict.has`, then `dict.getitem` and/or `dict.set`, on the same dict and key, with no wD or U op between them.
   - Rewrite: one `dict.find`, which returns an entry index or -1, followed by `dict.entry_val` and `dict.entry_set`. These are three new runtime functions.
   - Writing an existing entry never moves entries.
   - `if k in d: d[k] += 1` drops from three hash lookups to one.
   - LLVM cannot do this: the calls are opaque, and stores lie between them.
3. **None-check elimination.**
   - A forward dataflow over blocks tracks "this slot or value is not None". The facts come from `check`, `new`, `self`, and the true edge of `isnull`.
   - Joins intersect the facts. A store of a value that may be None kills them, and so does the head of a loop that stores the slot.
   - Upper bound: 2,102 of the 3,099 tests.
   - `clang -O2` already removes many. The gain is in the JIT tier, in the IR's size, and in backends without GVN.
4. **Bounds hoisting for `for i in range(len(xs))`.**
   - The conditions:
     - the `Loop` has `stop = len(xs)`;
     - the loop never stores the slots of `xs` and `i`;
     - the body has no wL and no U op.
   - Then reads of `xs[i]` become unchecked.
5. **Attributes from effects.** `noreturn`, `memory(none)` and `nounwind` on runtime declarations.

### 7.2 Exceptions (M5, #10)

The README's next steps mention `invoke` and landing pads. This design proposes an error flag instead:
- **The runtime side.** The runtime sets `pys_exc` and returns a sentinel instead of exiting.
- **The compiled-code side.** Compiled code tests the flag after an R op only where something can catch the exception:
  - inside a `try` region;
  - at calls in functions that sit, through the call graph, under a handler. The effect summaries compute these.
- **Changes to the IR.**
  - `check`, `raise`, R-effect `rt` ops and `call` change only in their lowering.
  - Cold blocks are pooled per handler and message.
  - `with` becomes a cleanup region.
  - `accel_try`'s import fallback (#4 §1 D and E) becomes a real handler around `init` calls.

The reasons for the flag:
- **Callbacks through C.** The C runtime calls user code back from timsort (`__lt__`) and from `pys_eq`/`pys_repr` (through `pys_obj_*`). Landing pads would have to unwind through those C frames.
- **One protocol for both modes.** The CPython-extension mode needs exactly the flag protocol (NULL or -1, plus `PyErr`).

### 7.3 A WebAssembly GC backend

It needs the re-baseline (§3.8) and becomes a second lowering over the same `IFn`s:
- **Control flow.** Structured control flow comes from the reducible CFG and the `Loop` records.
- **Locals.** Slots become Wasm locals.
- **Containers.** Holes give every container's element type at creation, so lists and dicts become typed arrays with no `ptrtoint`.
- **The runtime.** `RUNTIME` keys bind to a runtime written in the subset, whose generic helpers are Pystachy templates.
- **Errors.** `check` and `raise` map to `throw`.

### 7.4 The CPython-extension mode (#4 §4)

A third lowering, for the eligible `IFn`s. Containers stay Python objects, as #4 §4 asks. What it needs:
- **Eligibility.**
  - An `IFn` is eligible when it elaborated without error and every op it holds has a C-API lowering.
  - The diagnostics name the ops that do not.
  - This requires recoverable elaboration: `err` records the first error and abandons the `IFn` instead of calling `sys.exit`. The subset has no exceptions, so this has to be built from poison values and early returns.
- **None.** None is `Py_None`, not NULL. Only the LLVM lowering knows that None is `null`.
- **Reference counting.** Reference counts are derived in that lowering from liveness, plus a new-or-borrowed column in `RUNTIME`. They never appear in the shared IR.
- **Errors.** `check` and `raise` become `PyErr_*` plus an error return (§7.2).
- **Boundary checks.** `str` is byte-indexed and `int` is 64-bit in standalone mode. The boundary must check or reject these, so that the same IR does not mean different things.

### 7.5 Classes as templates (M2, #7)

- Declarations get keyed by instance types: one `ClassInfo`, struct and method set per list of field types, named like template instances.
- The IR does not change. It needs steps 3 (declarations as data) and 14 (`call`) first.

### 7.6 Dynamic values (M4, #9)

- **New type forms:** `C|None` and scalar optionals (`int|None`), and later a tagged dynamic value.
- **New ops:** box, tag test and unbox, each with R for CPython's `TypeError`.
- **Narrowing.** `Val.nn` and the None-check pass of §7.1 generalize to narrowing facts.
- **What changes when `C` stops meaning "C or None":** every place that compares class types has to be audited.

### 7.7 Other gains

- Debug information and the last traceback line can come from `Ins.line`.
- Golden tests of `ir --typed` dumps (`tests/ir/*.ir`).
- An `llvm-as` step in `make verify`.

### 7.8 What stays out of scope

- A type checker separate from elaboration.
- SSA construction.
- A general pass manager.
- Inlining (LLVM does it).
- Changes to the runtime's ABI in IR steps.
- Structured regions as the core of the IR.

## 8. Risks

| risk | how it is contained |
|---|---|
| **Numbering is coupled to the builder.** Identity depends on `%tN`, `LN` and `%name.N` being allocated in exactly today's order. Ops that define several values, and a label opened inside them in dead code, can shift numbers that the corpus never exercises. | `put()` reproduces the order. The `tests/ir` probes cover the dead-code case. The verifier (`PYSTACHY_IRCHECK=1`) checks that each op holds exactly the numbers its lowering prints (`Ins.r`). |
| **Lowering reads state late.** An op that reads mutable builder state (`ltype`, `gtypes`, `cur`) at lowering time would print different text. | Ops carry everything as fields. Lowering reads only the op, `f.ret`, `holes` and the program tables (R2). |
| **Error order.** Moving any check into lowering changes which error is reported first. | R5: lowering cannot fail on user input. `irsame` compares the full stderr of all error cases. |
| **Memory and time.** The whole program's IR is alive at the end. | The 1.3× gate, lowering per function as a fallback, and interning op names. |
| **Friction with the subset.** One `Ins` class whose fields mean different things per op. A local has one type per function. A field initialised from an index expression needs an annotation (`self.blk: Blk`). | The op table documents each field, `PYSTACHY_IRCHECK` verifies it, and `ir --typed` shows it. The prototype already compiled itself. |
| **Quirks are kept until the re-baseline.** `dry`'s leaks (counter gaps, dead allocas, strings, declares, speculative instances), declaration order taken from call sites. | They are listed in §3.8, and step 16 removes them under `irnorm`. Bug fixes stay out of identity steps. |
| **The IR could stay shaped like LLVM.** If the migration stops before step 16, `Val.v` still holds LLVM spellings, and a Wasm or CPython backend gains nothing. | The exit criteria are counted by `ir --stats` (`raw` ops, `%slot` and `%addr` values) and checked by the lint of step 15. |
| **The re-baseline exposes order dependences.** Renumbering `@s.N` or `O<id>` could expose a dependence in `dispatch` or in the lazy fixpoint. | `O<id>` stays in elaboration order, and only `@s.N` and declares follow lowering. `irnorm`, the full tests, the fixed point and `make verify` guard it. |
| **Merge conflicts** with the compatibility work in the same code (the PR stack and the M0 fixes). The conversions touch about 105 `rt`, 126 `ins` and 69 `place` lines. | Small PRs, one construct each, never mixed with behaviour changes. `make irsame` makes a rebase verifiable in seconds. |
| **Unsound effects make the optimizations unsound.** For example, forgetting that `pys_list_find`, `sort_r`, `minmax`, `pys_eq`, `pys_repr` and `pys_format` can call user code. | Unknown callees count as all effects. `check_runtime.py` and the call-site check validate the table. Each pass can be switched off. The tests of loops that change what they iterate run under GC stress and UBSan. |
| **Typing stays coupled to emission** while `Val.v` holds spellings. | Accepted. Steps 1 to 4 remove every typing decision that reads text, the lint keeps it out, and step 16 removes the spellings. |
| **Holes resolved after use.** A hole lowered before it is resolved would print the wrong key kind. | Lowering runs after the whole program, and the verifier rejects a `?` type outside a hole's creation site. |

## 9. Open questions

1. **Exceptions protocol.** Is the error flag (§7.2) the right replacement for the README's `invoke`/landing-pad plan? This should be decided before M5 starts, because it decides whether `check` lowers to a branch or to a flag test.
2. **When to re-baseline.** Should step 16 come right after step 15, or wait until a second backend needs it? Waiting keeps the byte-identical oracle longer. Doing it early stops `dry`'s leaks and the counting in `put()` from spreading into new code.
3. **Speculative instances.** Template instances and `called` marks made only inside `dry` are compiled and emitted although nothing calls them. Pruning them by the reachability of lowered calls changes output. Should it be part of the re-baseline?
4. **Late reads of holes.** #17's case 2 reads a global dict before the function that fills it has been compiled. Its case 4 builds a list that nothing fills. Some operations do not depend on the element type at elaboration time: `print`, `repr`, `len`, truth, `return`. These could take a hole-typed value and leave the descriptor to lowering, once all holes are resolved. Is that sound for every reader, and what type should a hole that nothing fills get?
5. **Program end or per function.** Should lowering stay at the program's end, which global holes and exact effect summaries need, or move to each function's end with a patch for the remaining global holes, which roughly halves memory?
6. **Flow per instance.** Should Flow run per template instance on the IR, after folding, so that a branch the instance never compiles no longer forces a check?
7. **Nullability in the type.** When does `C` stop meaning "C or None"? WasmGC wants `(ref $C)` versus `(ref null $C)` in signatures, and M4 needs `C|None`. Is a per-value fact enough until then?
8. **Structure for Wasm.** Are the reducible CFG and the `Loop` records enough for structured control flow, or should `if` and `with` regions be recorded too?
9. **Recoverable elaboration.** What is the smallest design for it, given that the subset has no exceptions, and given that continuing after an error could make the compiler itself fail on a malformed type?
10. **Interning.** Should op names and types become ints? Only if profiles of the native compiler show the string compares.


## Appendix A. How this design was chosen

Three readers mapped the compiler (the declaration side of `Gen`, its emission side, and the
front and back ends around it). Three designs were then written independently from those maps:
*lowering first* (keep `Gen`'s walk, make it build the IR, print LLVM in a separate pass),
*analysis first* (separate resolution, checking, effects and lowering as passes over a typed IR)
and *backend agnostic* (a structured, backend-neutral IR with LLVM as one of three lowerings).
Two judges scored them independently, 0 to 10, after re-running the lowering-first prototype in a
scratch copy (fixed point, 358 of 358 programs identical, native time unchanged, live heap
doubled):

| design | fits the subset | incremental | separation | enables | cost |
|---|---:|---:|---:|---:|---:|
| lowering first | 9, 9.5 | 9, 9 | 4, 4 | 6, 6 | 8, 8.5 |
| analysis first | 7, 8 | 7, 6.5 | 9, 9 | 8, 8 | 5, 6 |
| backend agnostic | 6, 6.5 | 6, 6 | 7, 6.5 | 9, 9 | 6, 6.5 |

Both recommended lowering first as the vehicle, because only it had working evidence and
byte-identical steps, and both grafted the same ideas from the others, which this document
includes: the `check-ir` step and a checked `RUNTIME` table; `Val.nn`, one constness helper,
the `generic_use()`/`desc` split and declarations as data, as small identical steps before any
construct is converted; `Loop` records and integer hole ids; fine-grained effect letters; the
backend-neutral vocabulary of §3.8 as the end state, with a lint against LLVM text as its exit
criterion; error-flag exceptions and recoverable elaboration recorded as decisions; and the
scope builder and binder as a parallel track.
