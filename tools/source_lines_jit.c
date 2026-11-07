#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

struct jit_code_entry {
  struct jit_code_entry *next_entry, *prev_entry;
  const char *symfile_addr;
  uint64_t symfile_size;
};
struct jit_descriptor {
  uint32_t version, action_flag;
  struct jit_code_entry *relevant_entry, *first_entry;
};

/* Observe the public GDB JIT interface inside this test's own process. */
int64_t source_debug_registered(const char *source, const char *output) {
  struct jit_descriptor *d = dlsym(RTLD_DEFAULT, "__jit_debug_descriptor");
  if (!d || d->version != 1) return -1;
  int seen = 0;
  for (struct jit_code_entry *e = d->first_entry; e && seen < 4096;
       e = e->next_entry, seen++) {
    if (e->symfile_size < 4 || memcmp(e->symfile_addr, "\177ELF", 4)) continue;
    if (!memmem(e->symfile_addr, e->symfile_size, ".debug_line", 11) ||
        !memmem(e->symfile_addr, e->symfile_size, source, strlen(source))) continue;
    FILE *f = fopen(output, "wb");
    if (!f) return -2;
    size_t written = fwrite(e->symfile_addr, 1, e->symfile_size, f);
    int failed = fclose(f);
    return written == e->symfile_size && !failed ? 1 : -3;
  }
  return 0;
}
