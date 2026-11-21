/* WASI has no processes: waitpid fails with ECHILD (wasm/wasi_stubs.c). */
#ifndef PYSTACHY_WASI_SYS_WAIT_H
#define PYSTACHY_WASI_SYS_WAIT_H
#include <sys/types.h>
#define WNOHANG 1
#define WUNTRACED 2
#define WEXITSTATUS(s) (((s) & 0xff00) >> 8)
#define WTERMSIG(s) ((s) & 0x7f)
#define WIFEXITED(s) (!WTERMSIG(s))
#define WIFSIGNALED(s) (((signed char)(((s) & 0x7f) + 1) >> 1) > 0)
pid_t waitpid(pid_t pid, int *status, int options);
#endif
