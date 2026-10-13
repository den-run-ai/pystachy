/* A writable file's buffers are malloc'd outside the heap (setbuf1): they count as heap bytes,
   so that files dropped without close() start collections (#100), and whatever closes a file
   takes back exactly what was counted; a standard stream's are never counted. Deterministic
   byte and collection counts, no RSS or timing thresholds. Like listprobe, this includes the
   real runtime and links runtime.py's IR; malloc and free are wrapped to see the buffers
   themselves (runtime.c mallocs nothing else).
   usage: make fileprobe (build/fileprobe [--lib]: started as pystachy ext starts a module) */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
static void *buf_malloc(size_t n);
static void buf_free(void *p);
#define malloc(n) buf_malloc(n)
#define free(p) buf_free(p)
#include "../runtime.c"
#undef malloc
#undef free

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static _Noreturn void bad(const char *what) { fprintf(stderr, "fileprobe: %s\n", what); exit(1); }
#define NB 1024
static void *bp[NB];                   /* the buffers malloc'd and not freed, their sizes; their bytes, at most */
static I bn[NB], nb, out, peak, nomem, was[3];
static void *buf_malloc(size_t n) {
  void *p = nomem ? 0 : malloc(n);
  if (p) {
    if (nb == NB) bad("more buffers than the probe counts");
    bp[nb] = p; bn[nb++] = (I)n;
    if ((out += (I)n) > peak) peak = out;
  }
  return p;
}
static void buf_free(void *p) {
  for (I i = 0; p && i < nb; i++)
    if (bp[i] == p) { out -= bn[i]; bp[i] = bp[--nb]; bn[i] = bn[nb]; break; }
  free(p);
}

static Str *dir;                       /* the collector's roots: the temporary directory, the file the */
static File *cur;                      /* program holds, and the files it keeps in a list */
static List *held;
static I *roots[] = {(I *)&dir, (I *)&cur, (I *)&held};
static File fake;                      /* a standard stream's stand-in */
static Str *name(I i) { char b[32]; snprintf(b, sizeof b, "/%lld", (long long)i); return pys_str_add(dir, cstr(b)); }
static I ext(void) { return out - (std_out.pb ? 8192 + std_out.bs : 0); }   /* the files' buffers: sys.stdout's aside */
__attribute__((noinline)) static void scrub(int gc) {   /* erase conservative roots in dead frames; then collect */
  volatile I pad[4096];
  for (I i = 0; i < 4096; i++) pad[i] = 0;
  if (gc) collect();
  if (pad[0]) bad("scrub");
}
static void live(const char *what) {   /* after a collection, the live bytes are the open files' buffers and a little */
  scrub(1);
  if (gc_live < ext() || gc_live >= ext() + 1048576) bad(what);
}
static void exits(const char *what) {  /* the files still open are closed as at exit: exactly their buffers go */
  I h = gc_heap, o = out;
  pys_files_exit();
  if (ext() || h - gc_heap != o - out) bad(what);
}
__attribute__((noinline)) static void churn(I n, I first) {   /* the issue's program: file i buffers i * 16 KiB, */
  for (I i = 1; i <= n; i++) {                                /* gets a line, and is dropped without close() */
    cur = pys_open(name(first + i), cstr("w"), 0, 0, i * 16384);
    pys_file_write(cur, cstr("x"));
  }
}
__attribute__((noinline)) static void hold(void) {   /* four files the program keeps, of 4 MiB buffers */
  for (I i = 0; i < 4; i++) pys_list_append(held, (I)pys_open(name(1010 + i), cstr("w"), 0, 0, 1 << 22));
}
__attribute__((noinline)) static void unhold(void) { held->a[1] = held->a[3] = 0; }
__attribute__((noinline)) static void wdrop(void) {  /* a writer dropped with its text pending */
  pys_file_write(pys_open(name(1020), cstr("w"), 0, 0, 1 << 22), cstr("first"));
}
__attribute__((noinline)) static void fill(void) {   /* 16 files dropped in turn, more than the descriptors left */
  for (I i = 0; i < 16; i++) { cur = pys_open(name(1030 + i), cstr("w"), 0, 0, 1 << 20); pys_file_write(cur, cstr("y")); }
}
static void unchanged(void) { _exit(gc_allocd == was[0] && gc_heap == was[1] && gc_live == was[2] ? 3 : 4); }
static void tidy(void) {               /* at exit, a failed check's too: the temporary files go */
  char b[4200];
  for (I i = 0; i <= 3000; i++) { snprintf(b, sizeof b, "%s/%lld", dir->s, (long long)i); unlink(b); }
  rmdir(dir->s);
}

int main(int argc, char **argv) {
  if (argc > 1 && !strcmp(argv[1], "--lib")) { pys_enter(__builtin_frame_address(0)); pys_init_lib(roots, 3); }
  else pys_init(argc, argv, __builtin_frame_address(0), roots, 3);
  dir = pys_mkdtemp(); held = pys_list_new(4);
  atexit(tidy);

  /* 1. the issue's program: 128 files dropped with 136 MB of buffers in all run collections, which
     close them, their lines written, and the buffers outstanding stay within the collection limit */
  I n0 = gc_n, std = out - ext(), big = 8192 + 128 * 16384, opened = 0, written = 0;
  peak = out;
  churn(128, 0);
  I runs = gc_n - n0, most = peak - std;
  if (!runs) bad("files dropped with 136 MB of buffers run no collection");
  if (most > GC_MIN + 4 * big) bad("dropped files' buffers pile up past the collection limit");
  for (I i = 0; i < nfiles; i++) opened += !files[i]->closed;
  for (I i = 1; i <= 128; i++) { struct stat st; written += !stat(name(i)->s, &st) && st.st_size == 1; }
  if (!written || written + opened != 128) bad("a file the collector closed lost its line");
  exits("the exit's closes take back other than the files' buffers");

  /* 2. setbuf1 counts exactly a file's buffers, as handed out and in the heap, close() and the
     compiler's drop take back exactly them, and a standard stream's are never counted */
  I h = gc_heap, a = gc_allocd, o = out;
  fake.f = tmpfile(); fake.wr = fake.std = 1;
  if (!fake.f) bad("tmpfile");
  setbuf1(&fake, 1 << 20);
  if (gc_allocd != a || gc_heap != h || out - o != 8192 + (1 << 20)) bad("a standard stream's buffers are counted");
  shut(&fake);                         /* (its buffers stay, as sys.stdout's) */
  if (gc_heap != h || out - o != 8192 + (1 << 20)) bad("a standard stream's close takes back what was not counted");
  fclose(fake.f); buf_free(fake.pb);
  h = gc_heap; o = out;
  pys_file_close(&std_out);
  if (gc_heap != h || out != o) bad("sys.stdout.close() takes back what was not counted");
  scrub(1);
  File *f = pys_alloc(sizeof(File));
  f->f = fopen(name(1000)->s, "w"); f->wr = 1;
  if (!f->f) bad("fopen");
  a = gc_allocd; h = gc_heap;
  setbuf1(f, 12345);
  if (gc_allocd - a != 8192 + 12345 || gc_heap - h != 8192 + 12345) bad("setbuf1 counts other than a file's buffers");
  h = gc_heap;
  shut(f);
  if (h - gc_heap != 8192 + 12345) bad("shut takes back other than what setbuf1 counted");
  for (int how = 0; how < 2; how++) {
    scrub(1);
    f = pys_open(name(1001 + how), cstr("w"), 0, 0, 1 << 20);
    if (gc_allocd < 8192 + (1 << 20)) bad("open() hands out a file's buffers uncounted");
    h = gc_heap; o = out;
    if (how) pys_file_drop(f); else pys_file_close(f);
    if (h - gc_heap != o - out || o - out != 8192 + (1 << 20)) bad("a close takes back other than the file's buffers");
  }

  /* 3. after a collection, the open files' buffers are live bytes, and a dropped file's leave with it */
  hold();
  live("the open files' buffers are not live bytes");
  o = out;
  unhold();
  live("a dropped file's buffers stay live once the collector closes it");
  if (o - out != 2 * (8192 + (1 << 22))) bad("the collector closes no dropped file");
  exits("the exit's closes take back other than the kept files' buffers");

  /* 4. a dropped writer is closed before its file opens again, and when the descriptors run out */
  wdrop();
  scrub(0);
  o = out;
  f = pys_open(name(1020), cstr("r"), 0, 0, -1);
  Str *t = pys_file_read(f, -1);
  if (t->len != 5 || memcmp(t->s, "first", 5) || o - out != 8192 + (1 << 22))
    bad("a dropped writer is not closed before its file opens again");
  pys_file_close(f);
  struct rlimit rl, low;
  int fd = open("/dev/null", O_RDONLY);
  if (fd < 0 || close(fd) || getrlimit(RLIMIT_NOFILE, &rl)) bad("descriptors");
  low = rl; low.rlim_cur = fd + 10;
  scrub(1); n0 = gc_n;
  if (setrlimit(RLIMIT_NOFILE, &low)) bad("setrlimit");
  fill();
  if (setrlimit(RLIMIT_NOFILE, &rl)) bad("setrlimit");
  if (gc_n == n0) bad("running out of descriptors runs no collection");
  live("files closed when the descriptors ran out stay live");
  exits("the exit's closes take back other than the files' buffers");

  /* 5. PYSTACHY_GC=off: dropped files run no collection, and the exit takes back all their buffers */
  I stress = gc_stress;
  scrub(1); n0 = gc_n; o = out; gc_off = 1; gc_stress = 0;
  churn(64, 2000);
  if (gc_n != n0 || out - o != 8192 * 64 * 66) bad("PYSTACHY_GC=off collects");
  exits("PYSTACHY_GC=off: the exit's closes take back other than the files' buffers");
  gc_off = 0; gc_stress = stress;

  /* 6. a buffer that cannot be allocated changes no counter (oom() ends the program, as always) */
  fflush(stdout);
  pid_t p = fork();
  if (!p) {
    scrub(1);
    f = pys_alloc(sizeof(File));
    f->f = fopen(name(3000)->s, "w"); f->wr = 1;
    if (!f->f || !freopen("/dev/null", "w", stderr)) _exit(5);   /* (oom()'s MemoryError) */
    was[0] = gc_allocd; was[1] = gc_heap; was[2] = gc_live; nomem = 1;
    atexit(unchanged);
    setbuf1(f, 1 << 20);
    _exit(6);
  }
  int st;
  if (p < 0 || waitpid(p, &st, 0) != p || !WIFEXITED(st) || WEXITSTATUS(st) != 3)
    bad("a buffer that cannot be allocated changes the counters");
  printf("fileprobe: 128 files dropped with 136314880 bytes of buffers ran %lld collections, %lld bytes at most outstanding"
         " (limit %lld); opens, closes, collections and the exit balance; standard streams aside\n",
         (long long)runs, (long long)most, (long long)(GC_MIN + 4 * big));
  return 0;
}
