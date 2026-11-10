/* AOT diagnostic only. Force-include solely in a plain build of retained.py.
   The ordinary build compiles just runtime.c as C; no extension or JIT glue.
   This exposes the existing conservative collector without changing runtime.c. */
#ifndef TOML_BOUNDARY_RETAINED_H
#define TOML_BOUNDARY_RETAINED_H
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <stdint.h>
static void collect(void);
static int64_t gc_live;
/* @extern resolves this name through dlsym, so neither LLVM's only-needed
   runtime link nor later dead-code removal may discard the definition. */
__attribute__((used, noinline, visibility("default"))) int64_t toml_boundary_collect_live(void) {
  collect();
  return gc_live;
}
#endif
