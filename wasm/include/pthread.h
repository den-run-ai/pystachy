/* WASI (wasm32-wasi, single-threaded) has no threads: the runtime asks only for its own stack's
   bounds and validates _thread.stack_size, which wasm/wasi_stubs.c answers. */
#ifndef PYSTACHY_WASI_PTHREAD_H
#define PYSTACHY_WASI_PTHREAD_H
#include <sys/types.h>
#include <signal.h>
pthread_t pthread_self(void);
int pthread_attr_init(pthread_attr_t *a);
int pthread_attr_destroy(pthread_attr_t *a);
int pthread_attr_setstacksize(pthread_attr_t *a, size_t n);
int pthread_attr_getstack(const pthread_attr_t *a, void **addr, size_t *n);
int pthread_getattr_np(pthread_t t, pthread_attr_t *a);
int pthread_sigmask(int how, const sigset_t *set, sigset_t *old);
#endif
