/* Real pipe readiness and EINTR behavior without a signal/pipe Python facade.
   The public API's JIT/AOT contract is tested separately in lib_select.py and
   ffi/c_select.py. This calls the same runtime, including its GC and errors.
   Usage: make selectprobe; timings have no performance pass/fail threshold. */
#define _GNU_SOURCE
#include <sys/select.h>
static int probe_pselect(int, fd_set *, fd_set *, fd_set *, const struct timespec *, const sigset_t *);
#define pselect probe_pselect
#include "../runtime.c"
#undef pselect
#include <sys/time.h>
#include <sys/wait.h>

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static volatile sig_atomic_t signals;
static int inject_sigint;
static int probe_pselect(int n, fd_set *r, fd_set *w, fd_set *x, const struct timespec *t, const sigset_t *mask) {
  /* Deterministic delivery at the boundary after io_in, before the kernel wait.
     The runtime must still block SIGINT here, then atomically unblock it. */
  if (inject_sigint) { inject_sigint = 0; raise(SIGINT); }
  return pselect(n, r, w, x, t, mask);
}
static void interrupted(int sig) {
  (void)sig;
  if (++signals > 5000) _exit(3);  /* watchdog if a retry keeps restarting its timeout */
}
static _Noreturn void bad(const char *what) { fprintf(stderr, "selectprobe: %s\n", what); exit(1); }
static void check_empty_result(void **out) {
  for (int i = 0; i < 3; i++) if (((List *)out[i])->len) bad("expected three empty lists");
}
static void restored_mask(void) {
  sigset_t mask;
  if (sigprocmask(SIG_SETMASK, NULL, &mask) || sigismember(&mask, SIGINT) || !sigismember(&mask, SIGUSR2))
    _exit(5);  /* also used by a child that must exit with the syscall error */
}
static void error_mask(List *r, List *none, int fd) {
  pid_t child = fork();
  if (child < 0) bad("error mask fork");
  if (!child) {
    if (!freopen("/dev/null", "w", stderr)) _exit(2);
    std_out.closed = std_err.closed = 1;
    close(fd);
    if (atexit(restored_mask)) _exit(2);
    pys_select(r, none, none, 0, 0);  /* EBADF must restore the mask before raising */
    _exit(4);
  }
  int status;
  if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) != 1)
    bad("syscall error changed caller signal mask");
}
static void pending_sigint(List *none, int before_wait) {
  pid_t child = fork();
  if (child < 0) bad("pending SIGINT fork");
  if (!child) {
    if (!freopen("/dev/null", "w", stderr)) _exit(2);
    std_out.closed = std_err.closed = 1;
    sigint_on = 1; signal(SIGINT, on_sigint);
    sigset_t unblocked; sigemptyset(&unblocked); sigaddset(&unblocked, SIGINT);
    if (sigprocmask(SIG_UNBLOCK, &unblocked, NULL)) _exit(2);
    signal(SIGALRM, SIG_DFL); alarm(2);  /* a lost signal must fail, not hang CI */
    if (before_wait) inject_sigint = 1;
    else io_intr = 1;  /* already noted by the I/O signal handler */
    pys_select(none, none, none, 0, 1);
    _exit(4);
  }
  int status;
  if (waitpid(child, &status, 0) != child ||
      !((WIFSIGNALED(status) && WTERMSIG(status) == SIGINT) || (WIFEXITED(status) && WEXITSTATUS(status) == 130)))
    bad(before_wait ? "SIGINT lost before blocking syscall" : "already-pending SIGINT ignored");
}
int main(void) {
  gc_init(__builtin_frame_address(0), NULL, 0);
  int p[2];
  if (pipe(p)) bad("pipe");
  List *r = pys_list_new_atomic(2), *w = pys_list_new_atomic(1), *x = pys_list_new_atomic(0);
  pending_sigint(x, 0);
  pending_sigint(x, 1);
  /* Preserve the caller's mask, including an intentionally blocked SIGINT. */
  sigset_t block, original, after;
  sigemptyset(&block); sigaddset(&block, SIGINT); sigaddset(&block, SIGUSR2);
  if (sigprocmask(SIG_BLOCK, &block, &original)) bad("block test mask");
  check_empty_result(pys_select(x, x, x, 0, 0));
  if (sigprocmask(SIG_SETMASK, NULL, &after) || !sigismember(&after, SIGINT) || !sigismember(&after, SIGUSR2))
    bad("select changed caller signal mask");
  sigdelset(&after, SIGINT);
  if (sigprocmask(SIG_SETMASK, &after, NULL)) bad("unblock test SIGINT");
  pys_list_append(r, p[0]); pys_list_append(r, p[0]); pys_list_append(w, p[1]);
  error_mask(r, x, p[0]);
  void **out = pys_select(r, w, x, 0, 0);
  restored_mask();
  if (((List *)out[0])->len || ((List *)out[1])->len != 1 || ((List *)out[1])->a[0] != p[1]) bad("empty pipe readiness");
  if (write(p[1], "x", 1) != 1) bad("pipe write");
  pys_list_identity(r, 1);
  I untouched = r->ids[2];
  pys_list_set(r, 0, p[0]);  /* a raw replacement leaves its new identity pending */
  if (r->ids[1]) bad("raw replacement did not invalidate identity");
  out = pys_select(r, x, x, 0, 1);
  if (((List *)out[0])->len != 2 || ((List *)out[0])->a[0] != p[0] || ((List *)out[0])->a[1] != p[0]) bad("readable duplicates");
  List *ready = out[0];
  if (!r->ids[1] || !ready->ids || ready->ids[1] != r->ids[1] || ready->ids[2] != untouched)
    bad("readiness result lost pending or retained numeric identity");
  char byte;
  if (read(p[0], &byte, 1) != 1 || byte != 'x') bad("pipe read");

  struct sigaction sa = {0}; sa.sa_handler = interrupted; sigemptyset(&sa.sa_mask);
  if (sigaction(SIGALRM, &sa, NULL) || sigaction(SIGUSR1, &sa, NULL)) bad("sigaction");
  /* Repeated EINTR must not restart the original timeout each time. The alarm
     timer remains active until the wait returns; a broken retry loop hangs. */
  struct itimerval timer = {{0, 2000}, {0, 2000}}, off = {{0, 0}, {0, 0}};
  if (setitimer(ITIMER_REAL, &timer, NULL)) bad("setitimer");
  double start = pys_monotonic();
  check_empty_result(pys_select(r, x, x, 0.02, 0));
  double elapsed = pys_monotonic() - start;
  if (setitimer(ITIMER_REAL, &off, NULL)) bad("stop timer");
  restored_mask();
  if (sigprocmask(SIG_SETMASK, &original, NULL)) bad("restore test mask");
  if (!signals || elapsed < 0.019) bad("EINTR lost timeout or signal");

  /* A tiny readiness loop: a producer interrupts the wait, then delivers three
     bytes, then EOF. Every retry must restore the descriptor bitsets. */
  pid_t child = fork();
  if (child < 0) bad("fork");
  if (!child) {
    close(p[0]); usleep(10000); kill(getppid(), SIGUSR1);
    for (int i = 0; i < 3; i++) { usleep(1000); if (write(p[1], &"abc"[i], 1) != 1) _exit(2); }
    close(p[1]); _exit(0);
  }
  close(p[1]);
  int nread = 0;
  for (;;) {
    out = pys_select(r, x, x, 0, 1);
    if (((List *)out[0])->len != 2) bad("blocking retry readiness");
    ssize_t n = read(p[0], &byte, 1);
    if (n == 0) break;
    if (n != 1 || nread >= 3 || byte != "abc"[nread++]) bad("readiness loop bytes");
  }
  int status;
  if (waitpid(child, &status, 0) != child || status || nread != 3) bad("producer exit");
  close(p[0]);
  printf("selectprobe: pipe readiness, numeric identity, duplicate descriptors, EOF, pending SIGINT, EINTR deadline and blocking retry passed (%.3fs timeout)\n", elapsed);
  return 0;
}
