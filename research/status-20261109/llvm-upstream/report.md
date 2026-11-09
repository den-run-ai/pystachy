# [CodeGen] Landing-pad PHI reuses post-invoke copies at -O0

## Problem

At `-O0`, a landing-pad PHI can read a value that is written only after the invoked call returns. PHIElimination lowers the normal successor's identical PHI first, with copies after the call, then reuses its incoming register for the landing-pad PHI (`LoweredPHIs`, `reusedIncoming`) instead of copying before the call. On the exceptional edge that register is unset or stale.

## Reproducer

`repro.ll`:
```llvm
declare void @may_throw(i64)
declare i32 @__gxx_personality_v0(...)
declare ptr @__cxa_begin_catch(ptr)
declare void @__cxa_end_catch()

define i64 @count(i64 %start) personality ptr @__gxx_personality_v0 {
entry:
  invoke void @may_throw(i64 %start)
          to label %loop unwind label %lpad

loop:
  %i = phi i64 [ %start, %entry ], [ %next, %loop ]
  %next = add i64 %i, 1
  invoke void @may_throw(i64 %next)
          to label %loop unwind label %lpad

lpad:
  %j = phi i64 [ %start, %entry ], [ %next, %loop ]
  %lp = landingpad { ptr, i32 } catch ptr null
  %exn = extractvalue { ptr, i32 } %lp, 0
  %c = call ptr @__cxa_begin_catch(ptr %exn)
  call void @__cxa_end_catch()
  ret i64 %j
}
```
`driver.cpp`:
```cpp
#include <cstdint>
#include <cstdio>
extern "C" int64_t count(int64_t);
extern "C" void may_throw(int64_t x) { if (x >= 3) throw 0; }
int main() { std::printf("%lld %lld\n", (long long)count(0), (long long)count(7)); }  // expect: 3 7
```
```
clang++ -O0 repro.ll driver.cpp && ./a.out   # prints "2 2", expected "3 7"
clang++ -O1 repro.ll driver.cpp && ./a.out   # prints "3 7"
llc -O0 -print-after=phi-node-elimination repro.ll -o /dev/null
```
After PHI elimination (23.1.6), `%11` is assigned only after each call's closing `EH_LABEL`, and `bb.2.lpad` reads `%11`.

## Scope

Reproduces with Ubuntu's LLVM 18.1.3 and apt.llvm.org's 20.1.8, 22.1.8 and 23.1.6 on x86-64 Linux. On `main`, `LowerPHINode` still reuses an identical PHI when all its edges are critical, with no EH-pad check. Splitting critical edges before code generation avoids it. Found through Pystachy's JIT `-O0` mode (den-run-ai/pystachy#1188); reduced with AI assistance (Claude Code) and checked on each version above.

## Expected

The landing-pad PHI gets copies before each invoke, or PHIs in EH pads are never merged with PHIs in other blocks.
