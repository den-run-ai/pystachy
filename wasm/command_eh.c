#include <unwind.h>

/* Commands catch LLVM's single Wasm exception tag. Once a raise reaches the command's
   outermost handler, let throw_ report it normally. Consume the flag here so Python code
   that formats the uncaught exception can still run its own handlers. */
static int reporting;
extern _Noreturn void pys_throw(void *exc);
_Noreturn void pys_wasi_uncaught(void *exc) {
  reporting = 1;
  pys_throw(exc);
}
_Unwind_Reason_Code _Unwind_ForcedUnwind(struct _Unwind_Exception *e, _Unwind_Stop_Fn stop, void *arg) {
  (void)stop; (void)arg;
  if (!reporting) __builtin_wasm_throw(0, e);
  reporting = 0;
  return _URC_END_OF_STACK;
}
