/* Optional native map/row backend: real workers, disjoint coverage, partial launch
   failure, inherited signal masks, GC roots, and joining before SIGINT delivery.
   The production callback is compiler-proven numeric code. This probe adds
   synchronization and counters only to observe the scheduler independently.
   usage: make parallelprobe; build/parallelprobe interrupt or interrupt-rows (dies by SIGINT) */
#define _GNU_SOURCE
#include <pthread.h>
static int probe_create(pthread_t *, const pthread_attr_t *, void *(*)(void *), void *);
static int probe_join(pthread_t, void **);
#define pthread_create probe_create
#define pthread_join probe_join
#ifndef PYSTACHY_PARALLEL
#define PYSTACHY_PARALLEL
#endif
#include "../runtime.c"
#undef pthread_create
#undef pthread_join

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static List *input, *output;
static I *roots[] = {(I *)&input, (I *)&output};
static pthread_t owner;
static int launch_limit = -1, attempts, created, joined, interrupt_test;
static unsigned char *visits;
static atomic_int worker_calls, worker_error, sent_interrupt;
static pthread_mutex_t gate_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_cond = PTHREAD_COND_INITIALIZER;
static int gate_expected, gate_arrived;
static I row_width;

static _Noreturn void bad(const char *what) {
  fprintf(stderr, "parallelprobe: %s\n", what);
  exit(1);
}
static int probe_create(pthread_t *t, const pthread_attr_t *attr,
                        void *(*run)(void *), void *arg) {
  if (launch_limit >= 0 && attempts++ >= launch_limit) return EAGAIN;
  int error = pthread_create(t, attr, run, arg);
  if (!error) created++;
  return error;
}
static int probe_join(pthread_t t, void **result) {
  int error = pthread_join(t, result);
  if (!error) joined++;
  if (interrupt_test && joined == 3)
    fputs("parallelprobe: joined before SIGINT\n", stderr);
  return error;
}
static double scalar(double x) {
#pragma clang fp contract(off)
  return x * 1.5 + 0.25;
}
static void numeric_kernel(const double *src, double *dst, I lo, I hi, I width) {
  (void)width;
  for (I i = lo; i < hi; i++) dst[i] = scalar(src[i]);
}
static void numeric_rows_kernel(const double *src, double *dst, I lo, I hi, I width) {
#pragma clang fp contract(off)
  for (I row = lo; row < hi; row++) {
    double total = 0.0;
    for (I column = 0; column < width; column++) total = total + scalar(src[row * width + column]);
    dst[row] = total;
  }
}
static void observed_kernel(const double *src, double *dst, I lo, I hi, I width) {
  int worker = !pthread_equal(pthread_self(), owner);
  if (worker) {
    sigset_t mask;
    if (pthread_sigmask(SIG_BLOCK, 0, &mask) || !sigismember(&mask, SIGINT))
      atomic_store(&worker_error, 1);
    atomic_fetch_add(&worker_calls, 1);
    if (interrupt_test && !atomic_exchange(&sent_interrupt, 1)) {
      if (pthread_kill(owner, SIGINT)) atomic_store(&worker_error, 1);
    }
  }
  if (gate_expected) {
    /* A timed barrier establishes that real workers and owner are simultaneously
       inside the callback. No timing-based speed assertion or busy wait. */
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline); deadline.tv_sec += 10;
    pthread_mutex_lock(&gate_mutex);
    if (++gate_arrived == gate_expected) pthread_cond_broadcast(&gate_cond);
    while (gate_arrived < gate_expected) {
      if (pthread_cond_timedwait(&gate_cond, &gate_mutex, &deadline)) {
        atomic_store(&worker_error, 1); break;
      }
    }
    pthread_mutex_unlock(&gate_mutex);
  }
  for (I i = lo; i < hi; i++) visits[i]++;
  if (row_width) numeric_rows_kernel(src, dst, lo, hi, width);
  else numeric_kernel(src, dst, lo, hi, width);
}
static double input_value(I i) { return (double)i / 8.0 - 16.0; }
static List *new_input(I n) {
  List *l = pys_list_new_atomic(n);
  for (I i = 0; i < n; i++) {
    double x = input_value(i);
    memcpy(&l->a[i], &x, sizeof x);
  }
  l->len = n;
  return l;
}
static void check_result(List *l, I n, I width) {
  I count = width ? n / width : n;
  if (l->len != count || !atomic_items(l->a)) bad("result length or backing allocation kind");
  for (I i = 0; i < count; i++) {
    double want = scalar(input_value(i));
    if (width) {
      want = 0.0;
      for (I column = 0; column < width; column++) want = want + scalar(input_value(i * width + column));
    }
    if (memcmp(&l->a[i], &want, sizeof want)) bad("result differs from sequential arithmetic");
  }
}
static void run_case(I n, I workers, int fail_after, int barrier, I width) {
  sigset_t before, after;
  pthread_sigmask(SIG_BLOCK, 0, &before);
  launch_limit = fail_after; attempts = created = joined = 0;
  row_width = width;
  I count = width ? n / width : n;
  atomic_store(&worker_calls, 0); atomic_store(&worker_error, 0);
  gate_expected = barrier; gate_arrived = 0;
  visits = calloc(count ? (size_t)count : 1, sizeof *visits);
  if (!visits) bad("probe allocation failed");
  input = new_input(n);
  output = width ? pys_parallel_rows_f64(input, width, workers, observed_kernel) :
                   pys_parallel_map_f64(input, workers, observed_kernel);
  if (output == input || output->a == input->a) bad("result aliases input");
  if (created != joined || atomic_load(&worker_error)) bad("worker join, signal mask or overlap");
  if (barrier && (created != barrier - 1 || atomic_load(&worker_calls) != barrier - 1))
    bad("parallel execution was not observed");
  if ((n < 32768 || workers == 1 || count < 2) && created) bad("serial threshold started a worker");
  if (fail_after >= 0 && created != fail_after) bad("partial launch failure was not exercised");
  if (io_busy || io_intr) bad("owner signal state not restored");
  pthread_sigmask(SIG_BLOCK, 0, &after);
  for (int signal_number = 1; signal_number < NSIG; signal_number++)
    if (sigismember(&before, signal_number) != sigismember(&after, signal_number))
      bad("owner signal mask not restored");
  for (I i = 0; i < count; i++)
    if (visits[i] != 1) bad("a range was skipped or executed more than once");
  for (I i = 0; i < n; i++) {
    double original = input_value(i);
    if (memcmp(&input->a[i], &original, sizeof original)) bad("input changed");
  }
  free(visits); visits = 0;
  input = 0;
  collect();
  check_result(output, n, width);
}
__attribute__((noinline)) static List *transient_map(I n) {
  /* The source has no program/global root while the output's allocations collect. */
  return pys_parallel_map_f64(new_input(n), 4, numeric_kernel);
}
__attribute__((noinline)) static List *transient_rows(I n, I width) {
  return pys_parallel_rows_f64(new_input(n), width, 4, numeric_rows_kernel);
}
int main(int argc, char **argv) {
  pys_init(argc, argv, __builtin_frame_address(0), roots, 2);
  owner = pthread_self();
  gc_stress = 1;
  if (argc > 1 && (!strcmp(argv[1], "interrupt") || !strcmp(argv[1], "interrupt-rows"))) {
    interrupt_test = 1;
    run_case(65536, 4, -1, 0, !strcmp(argv[1], "interrupt-rows") ? 8 : 0);
    bad("SIGINT was not delivered after joining");
  }
  I sizes[] = {0, 1, 31, 16383, 32767, 32768, 65539};
  I workers[] = {1, 2, 4, 8};
  for (I i = 0; i < 7; i++) for (I j = 0; j < 4; j++) run_case(sizes[i], workers[j], -1, 0, 0);
  run_case(65539, 4, -1, 4, 0);
  for (int fail_after = 0; fail_after < 3; fail_after++) run_case(65539, 4, fail_after, 0, 0);
  run_case(1048583, 64, -1, 0, 0);
  output = 0; launch_limit = -1;
  output = transient_map(65539);
  collect(); check_result(output, 65539, 0);
  I row_sizes[] = {0, 7, 217, 32767, 32774, 65541};
  for (I i = 0; i < 6; i++) for (I j = 0; j < 4; j++) run_case(row_sizes[i], workers[j], -1, 0, 7);
  run_case(65541, 4, -1, 4, 7);
  for (int fail_after = 0; fail_after < 3; fail_after++) run_case(65541, 4, fail_after, 0, 7);
  run_case(65536, 64, -1, 2, 32768); /* more workers than indivisible rows */
  run_case(65536, 64, -1, 0, 65536); /* one long row must stay sequential */
  output = 0; launch_limit = -1;
  output = transient_rows(65541, 7);
  collect(); check_result(output, 65541, 7);
  puts("parallelprobe: 34 maps and 31 row batches, overlap, launch failures, masks and transient GC roots passed");
  return 0;
}
