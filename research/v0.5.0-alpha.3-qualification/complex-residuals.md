# Added complex union residuals

The completed 94f4 census adds **542 rejected union reads and 409 unproved payload-bit obligations in 21 functions across nine new fixtures**. Every verdict remains rejected. The maintained report lists the functions once under union because both counters use the same closed-union function result.

Every retained first diagnostic requires the declared member set without null. Its recorded known-domain text matches those same members plus null. The adapter recognizes the public spelling `complex` as a nonnullable value representation, but the internal spelling `_pystachy_complex$complex` conservatively adds null. This concerns the union wrapper, distinct from a complex payload that the emitted code may separately check for null.

| Fixture | Rejected functions | Union reads unproved | Payload bits unproved |
|---|---:|---:|---:|
| `complex_union_none.py` | 1 | 12 | 8 |
| `dynany_complex_union_identity.py` | 2 | 30 | 21 |
| `complex_union_container_eq.py` | 4 | 89 | 48 |
| `complex_union_enum_eq.py` | 1 | 33 | 22 |
| `complex_union_identity.py` | 2 | 74 | 52 |
| `complex_union_nested.py` | 1 | 6 | 4 |
| `complex_union_object_eq.py` | 1 | 6 | 4 |
| `complex_union_tuple_search.py` | 3 | 38 | 25 |
| `complex_unions.py` | 6 | 254 | 225 |

## Source and emitted-IR disposition

### complex_union_none.py

Previously reviewed main.init read uses f.widen's normal return. Its null arm raises and is unreachable thereafter; its normal arm returns a fresh box. This is an interprocedural return fact, not a caller-local null check.

### dynany_complex_union_identity.py

Previously reviewed f.choose normal return is boxed and nonnull; the null arm raises. f.check transports this same pointer through a tuple; equality receives a load of that selected value. The model does not retain the required return-domain fact.

### complex_union_container_eq.py

All main.init arguments to lists/dicts/search are freshly allocated union boxes. The first reads in lists/dicts/search inspect those nonoptional union arguments; the generated equality specialization receives the other boxed argument or its tuple round trip. The model admits null for the union wrapper because one member has the internal complex class spelling.

### complex_union_enum_eq.py

The three calls to numbers receive fresh union boxes for int or complex values. Its first union-tag read inspects that parameter. The optional maybe helper is a separate function; its None inputs do not flow into numbers. The failure concerns the wrapper's conservative domain, before the IntEnum/IntFlag value comparisons.

### complex_union_identity.py

The five calls to search receive fresh boxes from main.init. Its first failing pointer t12 is the unchanged pointer stored in and recovered from a one-element tuple containing x. The equality specialization receives a boxed search argument or its tuple round trip. The optional mixed helper is distinct and does not supply the rejected nonoptional specialization.

### complex_union_nested.py

Both calls to show pass fresh union boxes, one for a complex instance and one for a list of complex instances. Its first failing tag load reads the same incoming wrapper after repr/list-print preparation. The descriptor distinguishes wrapper tags from nested container payloads; the conservative internal complex member adds null to the wrapper domain.

### complex_union_object_eq.py

Both calls to numbers pass fresh int/complex union boxes. Its first tag read dispatches the v argument before foreign reflected equality. The optional helper accepts None separately; no None input is passed to numbers in this fixture.

### complex_union_tuple_search.py

Every normal return of pick and fpick comes from pys_ubox, including both branches of each function. main.init stores the return in globals, round-trips it through a tuple, and then reads the tag. The rejected equality specializations receive the same boxed values. The adapter retains a nullable declared return domain despite these normal-return bodies.

### complex_unions.py

The initial vals list contains six fresh union boxes. main.init's first failing pointer t46 is a reload of the current list element after describe/repr; describe does not replace that global. describe's parameter, fold's two value parameters, and numeric's parameters all originate from nonoptional boxed members at their recorded call sites. The two rejected equality specializations receive numeric's boxed arguments. Optional fold results and later optional iteration use separate null-sensitive paths; they do not establish a local guard at these first rejected sites.

## Evidence and limits

`review.json` binds every source/oracle and raw LLVM hash, the exact residual row and first-site domain reconstruction, complete relevant emitted functions, the adapter/report source hashes, and the compiler/runtime source-equivalence receipt. Separate native CI evidence establishes successful recorded-oracle JIT and AOT executions of these fixtures. The complex-null deviation uses its handwritten TypeError oracle; that case is not a CPython parity claim.

The retained runtime contract shows `pys_ubox` allocates through the nonnull allocator on normal return. The review traces the needed normal-return and pointer-transport facts in each fixture; it does not assert a local guard where the code depends on an interprocedural contract.

Only each function's first reported failure is explained here. Neither this source/IR review nor the runtime passes discharge its later Lean obligations. The full 542 union reads and 409 payload obligations remain unproved. No compiler, Lean checker or runtime was executed for this review.
