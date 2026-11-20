/* WASI has no dynamic loading: dlopen fails (wasm/wasi_stubs.c), as for a missing library. */
#ifndef PYSTACHY_WASI_DLFCN_H
#define PYSTACHY_WASI_DLFCN_H
#define RTLD_LAZY 1
#define RTLD_NOW 2
#define RTLD_GLOBAL 0x100
#define RTLD_LOCAL 0
#define RTLD_NOLOAD 4
#define RTLD_DEFAULT ((void *)0)
void *dlopen(const char *path, int mode);
void *dlsym(void *handle, const char *name);
char *dlerror(void);
int dlclose(void *handle);
#endif
