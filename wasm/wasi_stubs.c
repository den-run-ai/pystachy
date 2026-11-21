#define _GNU_SOURCE   /* (memmem) */
/* What runtime.c calls that WASI (wasm32-wasi, preview 1) does not provide: processes, signals,
   users, dynamic loading and threads fail with ENOSYS, as on a platform without them, so that a
   program reaching them raises the OSError the runtime makes of errno; the rest of the runtime
   runs unchanged. LLVM/WASI commands have no unwinder. The direct reactor supplies its own
   _Unwind_ForcedUnwind to reach the emitted program's handlers. */
#include <errno.h>
#include <pthread.h>
#include <pwd.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <unwind.h>

#define NOSYS(r) do { errno = ENOSYS; return (r); } while (0)

/* processes */
pid_t fork(void) { NOSYS(-1); }
int execv(const char *path, char *const argv[]) { (void)path; (void)argv; NOSYS(-1); }
int execve(const char *path, char *const argv[], char *const envp[]) { (void)path; (void)argv; (void)envp; NOSYS(-1); }
pid_t waitpid(pid_t pid, int *status, int options) { (void)pid; (void)status; (void)options; errno = ECHILD; return -1; }
int system(const char *cmd) { return cmd ? -1 : 0; }   /* (no shell: system(NULL) is 0) */
pid_t setsid(void) { NOSYS(-1); }
int kill(pid_t pid, int sig) { (void)pid; (void)sig; NOSYS(-1); }
int pipe(int fds[2]) { (void)fds; NOSYS(-1); }
int dup(int fd) { (void)fd; NOSYS(-1); }
int dup2(int fd, int to) { (void)fd; (void)to; NOSYS(-1); }

/* Older wasi-libc lacks chmod. Newer releases provide it alongside other POSIX calls. */
__attribute__((weak)) int chmod(const char *path, mode_t mode) { (void)path; (void)mode; NOSYS(-1); }

/* users: one, whose id is 0 and whom the user database does not hold */
uid_t getuid(void) { return 0; }
uid_t geteuid(void) { return 0; }
struct passwd *getpwuid(uid_t uid) { (void)uid; return 0; }
struct passwd *getpwnam(const char *name) { (void)name; return 0; }

/* signals: nothing delivers one; a handler is accepted and never runs */
int sigemptyset(sigset_t *set) { *set = (sigset_t){0}; return 0; }
int sigfillset(sigset_t *set) { *set = (sigset_t){0}; return 0; }
int sigaddset(sigset_t *set, int sig) { (void)set; (void)sig; return 0; }
int sigdelset(sigset_t *set, int sig) { (void)set; (void)sig; return 0; }
int sigismember(const sigset_t *set, int sig) { (void)set; (void)sig; return 0; }
int sigprocmask(int how, const sigset_t *set, sigset_t *old) {
  (void)how; (void)set;
  if (old) *old = (sigset_t){0};
  return 0;
}
int pthread_sigmask(int how, const sigset_t *set, sigset_t *old) { return sigprocmask(how, set, old); }
int sigaction(int sig, const struct sigaction *act, struct sigaction *old) {
  (void)sig; (void)act;
  if (old) *old = (struct sigaction){0};
  return 0;
}

/* dynamic loading */
void *dlopen(const char *path, int mode) { (void)path; (void)mode; return 0; }
void *dlsym(void *handle, const char *name) { (void)handle; (void)name; return 0; }
char *dlerror(void) { return "dynamic loading is not supported on WASI"; }
int dlclose(void *handle) { (void)handle; return 0; }

/* threads: _thread.stack_size accepts what POSIX would */
int pthread_attr_init(pthread_attr_t *a) { (void)a; return 0; }
int pthread_attr_destroy(pthread_attr_t *a) { (void)a; return 0; }
int pthread_attr_setstacksize(pthread_attr_t *a, size_t n) { (void)a; return n < 16384 ? EINVAL : 0; }

/* the unwinder: no frame has a handler (llc lowers a landing pad's invoke to a call), so a forced
   unwind returns at once, and the raise ends the program as runtime.c's throw_ then does */
__attribute__((weak))
_Unwind_Reason_Code _Unwind_ForcedUnwind(struct _Unwind_Exception *e, _Unwind_Stop_Fn stop, void *arg) {
  (void)e; (void)stop; (void)arg;
  return _URC_END_OF_STACK;
}
static _Noreturn void no_unwinder(void) { abort(); }   /* (pys_personality: never called) */
uintptr_t _Unwind_GetDataRelBase(struct _Unwind_Context *c) { (void)c; no_unwinder(); }
uintptr_t _Unwind_GetTextRelBase(struct _Unwind_Context *c) { (void)c; no_unwinder(); }
uintptr_t _Unwind_GetRegionStart(struct _Unwind_Context *c) { (void)c; no_unwinder(); }
_Unwind_Word _Unwind_GetIPInfo(struct _Unwind_Context *c, int *before) { (void)c; (void)before; no_unwinder(); }
void *_Unwind_GetLanguageSpecificData(struct _Unwind_Context *c) { (void)c; no_unwinder(); }
void _Unwind_SetGR(struct _Unwind_Context *c, int i, _Unwind_Word v) { (void)c; (void)i; (void)v; no_unwinder(); }
void _Unwind_SetIP(struct _Unwind_Context *c, _Unwind_Word v) { (void)c; (void)v; no_unwinder(); }

/* runtime.py declares the C library's functions with LP64's types: a size_t is an i64. wasm32's
   is 32 bits, and a call whose signature differs from the definition traps, so wasm/build.sh
   renames runtime.py's calls to these, which convert the lengths. */
#include <string.h>
int pys_wasi_memcmp(const void *a, const void *b, int64_t n) { return memcmp(a, b, (size_t)n); }
void *pys_wasi_memchr(const void *s, int c, int64_t n) { return memchr(s, c, (size_t)n); }
void *pys_wasi_memmem(const void *h, int64_t hn, const void *n, int64_t nn) { return memmem(h, (size_t)hn, n, (size_t)nn); }

/* memory: runtime.c's page heap takes its regions from aligned_alloc (map_pages) and gives each
   back whole */
#include <sys/mman.h>
int munmap(void *p, size_t n) { (void)n; free(p); return 0; }

/* the working directory: WASI's C library starts at "/", and wasm/run.mjs passes node's as PWD */
__attribute__((constructor)) static void wasi_cwd(void) {
  const char *d = getenv("PWD");
  if (d && *d == '/') chdir(d);
}
