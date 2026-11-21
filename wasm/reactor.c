/* runtime.wasm's entry (wasm/README.md): a WASI reactor that a program module, compiled from
   typed IR without LLVM (wasm/tir_wasm.py), runs on. wasm/run.mjs instantiates it, allocates the
   program's data with its malloc, instantiates the program, which imports its memory and
   functions, and calls pys_wasi_run: the program's arguments, pys_init, the program's module
   code (its export init, which this module imports as program.init), pys_finish. */
#include <stdint.h>
#include <stdlib.h>
#include <wasi/api.h>

typedef int64_t I;
void pys_init(int argc, char **argv, char *sb, I **roots, I nroots);
void pys_finish(void);
__attribute__((import_module("program"), import_name("init"))) void program_init(void);

__attribute__((export_name("pys_wasi_run"))) int pys_wasi_run(void) {
  __wasi_size_t argc, size;
  if (__wasi_args_sizes_get(&argc, &size)) abort();
  char **argv = calloc(argc + 1, sizeof *argv), *buf = malloc(size);
  if (!argv || !buf || __wasi_args_get((uint8_t **)argv, (uint8_t *)buf)) abort();
  /* (no roots: the collector is off, wasm/README.md) */
  pys_init((int)argc, argv, __builtin_frame_address(0), 0, 0);
  program_init();
  pys_finish();
  return 0;
}
