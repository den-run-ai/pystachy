/* Included before runtime.c under wasm32-wasi (wasm/build.sh): the POSIX declarations that
   runtime.c names and wasi-libc leaves out. WASI has no processes, signals, users or dynamic
   loading; wasm/wasi_stubs.c defines each function to fail as an unsupported platform would
   (ENOSYS), so the runtime's paths that need them raise OSError and the rest run unchanged. */
#ifndef PYSTACHY_WASI_H
#define PYSTACHY_WASI_H
#include <errno.h>
#include <signal.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#ifndef SIG_BLOCK
#define SIG_BLOCK 0
#define SIG_UNBLOCK 1
#define SIG_SETMASK 2
#endif
#ifndef SA_RESTART
#define SA_RESTART 0x10000000
#define SA_ONSTACK 0x08000000
#define SA_SIGINFO 4
#define SA_NODEFER 0x40000000
#define SA_RESETHAND 0x80000000
#endif
struct sigaction {
  void (*sa_handler)(int);
  sigset_t sa_mask;
  int sa_flags;
};
int sigemptyset(sigset_t *set);
int sigfillset(sigset_t *set);
int sigaddset(sigset_t *set, int sig);
int sigdelset(sigset_t *set, int sig);
int sigismember(const sigset_t *set, int sig);
int sigprocmask(int how, const sigset_t *set, sigset_t *old);
int sigaction(int sig, const struct sigaction *act, struct sigaction *old);
int kill(pid_t pid, int sig);

pid_t fork(void);
int execv(const char *path, char *const argv[]);
int execve(const char *path, char *const argv[], char *const envp[]);
int pipe(int fds[2]);
int dup(int fd);
int dup2(int fd, int to);
pid_t setsid(void);
uid_t getuid(void);
uid_t geteuid(void);
int chmod(const char *path, mode_t mode);

#ifndef F_DUPFD_CLOEXEC
#define F_DUPFD_CLOEXEC 1030
#endif
#ifndef ESHUTDOWN
#define ESHUTDOWN 108
#endif
/* (this wasi-libc has no process clock: time.process_time() reads the monotonic one) */
#ifndef CLOCK_PROCESS_CPUTIME_ID
#define CLOCK_PROCESS_CPUTIME_ID CLOCK_MONOTONIC
#endif
#endif
