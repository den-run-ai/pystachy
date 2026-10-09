/* Pystachy runtime: memory, strings, lists, dicts, formatting, printing and I/O.
   `pystachy build` links it into every program as LLVM bitcode, so LLVM inlines these
   helpers across the program boundary (whole-program optimization); `pystachy run`
   links a precompiled object instead, since the JIT tier does not inline.
   Value model: every container slot is 8 bytes (int, float bits, bool, or pointer). */
#define _GNU_SOURCE
#include <ctype.h>
#include <errno.h>
#include <langinfo.h>
#include <locale.h>
#include <stdarg.h>
#include <math.h>
#include <setjmp.h>
#include <signal.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdio_ext.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

typedef int64_t I;
typedef struct { I len; char s[]; } Str;              /* immutable, NUL-terminated */
typedef struct { I len, cap; I *a; } List;
typedef struct { I len, kind, n, size; I *keys, *vals; uint64_t *hs; int32_t *idx; } Dict; /* kind 1: str keys; see dicts */
typedef struct { char *p; I n, cap; } Buf;
typedef struct Exc Exc;                                /* a raised exception (see exceptions) */
#define NONE INT64_MIN                                 /* omitted slice bound */

/* ---------- memory: conservative mark-and-sweep garbage collector ----------
   Non-moving, stop-the-world, single-threaded, and self-contained (only the C library).
   Layout. A request for n bytes gets n + 1 (one byte of slack, so a pointer one past the
   end still points into the object), rounded up to one of 40 size classes up to 8200
   bytes: 16..136 in steps of 8, then four per power of two, each 8 bytes above a multiple
   of a power of two so that 2^k-byte arrays fit tightly. Small objects live in 64 KiB
   chunks of one class each, carved from 1 MiB calloc'd arenas (big enough for malloc to map
   fresh memory, which comes zeroed at no cost); larger objects get a calloc'd block each.
   Every chunk and large object starts with a Seg header on a page boundary, and a two-level
   page map (48-bit addresses, 4 KiB pages) sends each of its pages to that header, so "is
   this word a pointer into the heap, and into which object" is a range check, two loads and
   a multiply by the reciprocal of the slot size: O(1), interior pointers included.
   Kinds. pys_alloc returns scanned memory (objects, tuples, list headers and arrays, dict
   key and value arrays); pys_alloc_atomic returns memory that is never scanned (strings, Buf
   data, dict index arrays, sort buffers). Each (class, kind) has a free list. Memory is
   handed out zeroed: the sweep zeroes dead slots, so allocation pops a slot and clears its
   link word (inlined into callers for the classes up to 136 bytes). A chunk's never-used
   slots are linked about a page at a time, so memory the program has not needed stays
   untouched (only a recycled chunk's must be zeroed). Links are stored complemented, so a
   free slot never looks like a pointer, and accessed as may_alias words, so TBAA cannot
   reorder them with the program's typed accesses to the first word of an object.
   Roots, all conservative: the C stack from the collector's frame up to the frame of @main
   (the generated @main passes its frame address to pys_init, so a @main.init inlined into
   it is covered); callee-saved registers, which __builtin_unwind_init spills into the
   collector's frame; the program's pointer-typed globals (@main passes a table of their
   addresses: under the JIT they live in memory that no scanner would find); and the
   runtime's own statics. Container slots hold ints, float bits or pointers, so every word of
   a scanned object is a possible pointer. Marking uses an explicit stack and takes big
   arrays in 4 KiB slices.
   Policy. A collection runs when a free list or a large allocation needs memory and the
   bytes handed out since the last one reach max(32 MiB, live bytes after it), so the heap
   stays near twice the live set. Dead large objects go straight back to the C allocator;
   empty chunks are kept for the next cycle's allocations, and beyond that every arena whose
   chunks are all empty is freed. A chunk that handed out nothing and lost nothing since the
   last sweep keeps its free list as is.
   The code is compact on purpose: under the JIT it is compiled again at every program start.
   Testing: PYSTACHY_GC_STRESS=N collects every N allocations, PYSTACHY_GC=off never
   collects, PYSTACHY_GC=stats prints a summary at exit. */
#define PAGE 4096
#define CHUNK 65536                    /* small-object chunk */
#define ARENA 16                       /* chunks per calloc'd arena */
#define SMALL 8200                     /* largest size class */
#define NK 80                          /* free lists: 40 classes x {scanned, atomic} */
#define GC_MIN ((I)32 << 20)           /* least allocation between collections */
typedef uintptr_t __attribute__((may_alias)) W;   /* a heap or stack word: aliases every type */
typedef struct Seg Seg;
struct Seg {                           /* header on the first page of a chunk or large object */
  Seg *next, *avail;                   /* chunk, pool or large-object list; chunks with free slots */
  char *start;                         /* first slot, or the large object */
  I size, nobj, bump, lim;             /* slot size (large: bytes + 1) and count; slots [0, bump)
                                          have been handed out; lim: bytes from start that can hold
                                          objects (bump * size, large: size, pooled: 0) */
  I nfree, nlive, nmark;               /* slots in free; survivors of the last sweep; marked now */
  uint64_t inv;                        /* ceil(2^40 / size): slot = offset * inv >> 40 */
  W free;                              /* complemented head of the free slots not yet handed out */
  void *raw;                           /* calloc'd block: the large object's, or the arena's (its
                                          first word counts the arena's chunks in use) */
  int k, large, used, dirty;           /* free list 2 * class + atomic (large: atomic); slots were
                                          handed out since the last sweep; [bump, nobj) needs zeroing */
  uint64_t mark[];                     /* one bit per slot */
};
#define HB ((I)((sizeof(Seg) + 8 + 15) & ~(size_t)15))   /* large-object header: one mark word */
static const short csize[NK / 2] = {16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128,
  136, 168, 200, 232, 264, 328, 392, 456, 520, 648, 776, 904, 1032, 1288, 1544, 1800, 2056,
  2568, 3080, 3592, 4104, 5128, 6152, 7176, 8200};
static W *fl[NK], *sfl[NK];            /* free list being allocated from; its stand-in under stress */
static Seg *avail[NK], *chunks, *pool, *bigs, ***pmap;
static uintptr_t gc_lo, gc_hi;         /* bounds of the pages in the page map */
static I gc_allocd, gc_limit = GC_MIN, gc_live, gc_heap, gc_peak, gc_n, gc_ns, gc_stress, gc_tick;
static int gc_off, gc_stats;
static char *gc_bottom;                /* the stack is scanned from the collector up to here */
static I **gc_roots, gc_nroots;        /* addresses of the program's pointer-typed globals */
static uintptr_t *mstk;                /* mark stack of (address, bytes) ranges */
static I msp, mcap;
static Str *ch1[256];                  /* runtime statics that hold heap pointers (roots) */
static List *args;
static Exc *xcur, *xhandled;           /* the exception raised last; the one being handled (see exceptions) */
typedef struct { void (*fn)(void *); void *arg; } Unwind;
static Unwind *unw;                    /* unwind actions, malloc'd: their arguments are roots (see exceptions) */
static I nunw, cunw;

static void out_flush(void);           /* stdout, before an error message (see I/O) */
void pys_finish(void);                 /* every way out of the program runs it (lli skips atexit handlers) */
static _Noreturn void oom(void) { out_flush(); fputs("MemoryError\n", stderr); pys_finish(); exit(1); }
static I cls(I n) {                    /* size class for n bytes plus one byte of slack */
  uint64_t r = (uint64_t)n + 1, y = r - 8;
  if (r <= 136) return r <= 16 ? 0 : (I)((r + 7) >> 3) - 2;
  int e = 63 - __builtin_clzll(y - 1);   /* 2^e < y <= 2^(e+1); classes are (5..8) * 2^(e-2) + 8 */
  return 16 + (e - 7) * 4 + (I)((y + (1ULL << (e - 2)) - 1) >> (e - 2)) - 5;
}
__attribute__((noinline)) static void pmap_set(uintptr_t a, uintptr_t e, Seg *v, I bytes) {
  if (e >> 48) oom();                  /* map the pages of [a, e) to v (or unmap), account bytes */
  if (v && (!gc_hi || a < gc_lo)) gc_lo = a;
  if (v && e > gc_hi) gc_hi = e;
  if ((gc_heap += bytes) > gc_peak) gc_peak = gc_heap;
  for (; a < e; a += PAGE) {
    Seg **m = pmap[a >> 30];
    if (!m && !(m = pmap[a >> 30] = calloc(1 << 18, sizeof *m))) oom();
    m[a >> 12 & 0x3ffff] = v;
  }
}
__attribute__((noinline)) static void mstk_grow(void) {
  if (!(mstk = realloc(mstk, (mcap = 2 * mcap + 4096) * sizeof *mstk))) oom();
}
__attribute__((noinline, no_sanitize("address"))) static void scan(const W *p, const W *e) {
  uintptr_t lo = gc_lo, span = gc_hi - gc_lo;   /* fixed while marking: keep them in registers */
  Seg ***pm = pmap;
  for (; p < e; p++) {                 /* mark every heap object a word in [p, e) points into */
    uintptr_t w = *p, off, i = 0;
    Seg **m, *s;
    if (w - lo >= span || !(m = pm[w >> 30]) || !(s = m[w >> 12 & 0x3ffff])) continue;
    if ((off = w - (uintptr_t)s->start) >= (uintptr_t)s->lim) continue;   /* header, tail, unused */
    if (!s->large) i = off * s->inv >> 40;
    if (s->mark[i >> 6] >> (i & 63) & 1) continue;
    s->mark[i >> 6] |= 1ULL << (i & 63); s->nmark++;
    if (s->k & 1) continue;            /* atomic: nothing to scan */
    if (msp + 2 > mcap) mstk_grow();
    mstk[msp++] = (uintptr_t)s->start + i * s->size;
    mstk[msp++] = (uintptr_t)(s->large ? s->size & ~7 : s->size);
  }
}
__attribute__((noinline, no_sanitize("address"))) static void mark_roots(void) {
  scan((const W *)((uintptr_t)__builtin_frame_address(0) & ~(uintptr_t)7), (const W *)gc_bottom);
  for (I i = 0; i < gc_nroots; i++) scan((const W *)gc_roots[i], (const W *)gc_roots[i] + 1);
  scan((const W *)ch1, (const W *)(ch1 + 256));
  scan((const W *)&args, (const W *)(&args + 1));
  scan((const W *)&xcur, (const W *)(&xcur + 1));
  scan((const W *)&xhandled, (const W *)(&xhandled + 1));
  if (nunw) scan((const W *)unw, (const W *)(unw + nunw));   /* unw is NULL before the first */
}
__attribute__((noinline)) static void rebuild(Seg *s) {   /* free list of unmarked slots below bump */
  I n = s->bump, sz = s->size;
  W *tail = &s->free;
  s->nfree = n - s->nmark; s->nlive = s->nmark; s->used = 0;
  for (I i = 0, j; i < n; i = j) {     /* runs of equal mark bits, a mark word at a time */
    uint64_t w = s->mark[i >> 6] >> (i & 63), r = w & 1 ? ~w : w;
    j = r ? i + __builtin_ctzll(r) : (i | 63) + 1;
    if (j > n) j = n;
    if (w & 1) continue;               /* [i, j) survived */
    memset(s->start + i * sz, 0, (j - i) * sz);   /* [i, j) is dead or free */
#pragma clang loop unroll(disable) vectorize(disable)
    for (I x = i; x < j; x++) { *tail = ~(uintptr_t)(s->start + x * sz); tail = (W *)(s->start + x * sz); }
  }
  *tail = ~(uintptr_t)0;
}
static void sweep(void) {
  I live = 0, spare = 0;
  memset(fl, 0, sizeof fl); memset(sfl, 0, sizeof sfl); memset(avail, 0, sizeof avail);
  for (Seg **pp = &chunks, *s; (s = *pp);) {
    I sz = s->size, m = s->nmark;
    if (!m) {                          /* empty: pool it */
      *pp = s->next; s->lim = 0; s->next = pool; pool = s; --*(I *)s->raw;
      continue;
    }
    live += m * sz;
    if (s->used || m != s->nlive) rebuild(s);   /* else nothing was allocated or died here */
    memset(s->mark, 0, (s->bump + 63) / 64 * 8); s->nmark = 0;
    if (s->nfree || s->bump < s->nobj) {
      s->avail = avail[s->k]; avail[s->k] = s; spare += (s->nfree + s->nobj - s->bump) * sz;
    }
    pp = &s->next;
  }
  for (Seg **pp = &bigs, *s; (s = *pp);) {
    if (s->mark[0]) { s->mark[0] = 0; live += s->size; pp = &s->next; continue; }
    *pp = s->next;                     /* the header lives in the block: unmap, then free */
    pmap_set((uintptr_t)s, (uintptr_t)s->start + s->size, 0, -(PAGE + HB + s->size - 1));
    free(s->raw);
  }
  gc_live = live; gc_allocd = 0; gc_limit = live > GC_MIN ? live : GC_MIN;
  I pooled = 0;                        /* keep the empty chunks the next cycle may need; beyond */
  for (Seg *s = pool; s; s = s->next) pooled += CHUNK;   /* that, free arenas with none in use */
  for (Seg *s = pool; s && pooled > gc_limit - spare; s = s->next)
    if (!*(I *)s->raw) { *(I *)s->raw = -1; pooled -= ARENA * CHUNK; }   /* -1: doomed */
  for (Seg **pp = &pool, *s; (s = *pp);) {
    I *a = s->raw;
    if (*a >= 0) { pp = &s->next; continue; }
    *pp = s->next; pmap_set((uintptr_t)s, (uintptr_t)s + CHUNK, 0, 0);
    if (--*a < -ARENA) { gc_heap -= ARENA * CHUNK + PAGE; free(a); }   /* its last chunk */
  }
}
static I nfiles;                       /* open files (see I/O): closed by the collector when unreachable */
static void files_sweep(void);
__attribute__((noinline)) static void collect(void) {
  struct timespec t0, t1;
  __builtin_unwind_init();             /* spill the callee-saved registers into this frame */
  if (gc_stats) clock_gettime(CLOCK_MONOTONIC, &t0);
  mark_roots();
  while (msp) {                        /* trace; big arrays in 4 KiB slices keep the stack short */
    I n = (I)mstk[msp - 1]; const W *p = (const W *)mstk[msp - 2];
    if (n > 4096) { mstk[msp - 2] = (uintptr_t)(p + 512); mstk[msp - 1] = (uintptr_t)(n - 4096); n = 4096; }
    else msp -= 2;
    scan(p, p + n / 8);
  }
  if (nfiles) files_sweep();
  sweep(); gc_n++;
  if (gc_stats) {
    clock_gettime(CLOCK_MONOTONIC, &t1);
    gc_ns += (t1.tv_sec - t0.tv_sec) * 1000000000 + t1.tv_nsec - t0.tv_nsec;
  }
}
static void refill(int k) {            /* give free list k more free slots */
  Seg *s = avail[k];
  if (!s && !gc_off && gc_allocd >= gc_limit) { collect(); s = avail[k]; }
  if (!s) {                            /* format a pooled chunk; its slots come lazily */
    I sz = csize[k >> 1], hdr = ((I)sizeof(Seg) + (CHUNK / sz + 63) / 64 * 8 + 15) & ~15;
    if (!pool) {                       /* a new arena: its chunks start out pooled and zero */
      char *raw = calloc(1, ARENA * CHUNK + PAGE + 16), *c;
      if (!raw) oom();
      c = (char *)(((uintptr_t)raw + 16 + PAGE - 1) & ~(uintptr_t)(PAGE - 1));
      for (int i = ARENA - 1; i >= 0; i--) {
        s = (Seg *)(c + i * CHUNK); s->raw = raw; s->next = pool; pool = s;
        pmap_set((uintptr_t)s, (uintptr_t)s + CHUNK, s, i ? 0 : ARENA * CHUNK + PAGE);
      }
    }
    s = pool; pool = s->next;
    void *raw = s->raw;
    int dirty = s->size != 0;          /* formatted before: old objects need zeroing */
    ++*(I *)raw;
    memset(s, 0, hdr);
    s->raw = raw; s->k = k; s->size = sz; s->inv = ((1ULL << 40) + sz - 1) / sz; s->dirty = dirty;
    s->start = (char *)s + hdr; s->nobj = (CHUNK - hdr) / sz; s->free = ~(uintptr_t)0;
    s->next = chunks; chunks = s; avail[k] = s;
  }
  I sz = s->size;
  if (~s->free) {                      /* the slots the last sweep freed */
    fl[k] = (W *)~s->free; s->free = ~(uintptr_t)0; gc_allocd += s->nfree * sz; s->nfree = 0;
  } else {                             /* about a page of never-used slots, so untouched memory stays so */
    I i = s->bump, j = i + (PAGE + sz - 1) / sz;
    if (j > s->nobj) j = s->nobj;
    if (s->dirty) memset(s->start + i * sz, 0, (j - i) * sz);
#pragma clang loop unroll(disable) vectorize(disable)
    for (I x = i; x < j; x++) *(W *)(s->start + x * sz) = ~(uintptr_t)(x + 1 < j ? s->start + (x + 1) * sz : 0);
    fl[k] = (W *)(s->start + i * sz); s->bump = j; s->lim = j * sz; gc_allocd += (j - i) * sz;
  }
  s->used = 1;
  if (s->bump == s->nobj) avail[k] = s->avail;   /* nothing left after this */
}
__attribute__((noinline)) static void *gc_slow(I n, int atomic) {
  if ((uint64_t)n > (uint64_t)1 << 40) oom();
  if (gc_stress && ++gc_tick >= gc_stress) { gc_tick = 0; collect(); }
  if (n >= SMALL) {                    /* large object: a page-aligned header in its own block */
    if (!gc_off && gc_allocd + n >= gc_limit) collect();
    char *raw = calloc(1, PAGE + HB + n);
    if (!raw) oom();
    Seg *s = (Seg *)(((uintptr_t)raw + PAGE - 1) & ~(uintptr_t)(PAGE - 1));
    s->raw = raw; s->large = 1; s->k = atomic; s->size = s->lim = n + 1; s->start = (char *)s + HB;
    pmap_set((uintptr_t)s, (uintptr_t)s->start + s->size, s, PAGE + HB + n);
    s->next = bigs; bigs = s; gc_allocd += n;
    return s->start;
  }
  int k = 2 * (int)cls(n) + atomic;
  if (gc_stress) fl[k] = sfl[k];       /* under stress every allocation comes through here */
  if (!fl[k]) refill(k);
  W *p = fl[k];
  fl[k] = (W *)~*p; *p = 0;
  if (gc_stress) { sfl[k] = fl[k]; fl[k] = 0; }
  return p;
}
static inline __attribute__((always_inline)) void *gc_alloc(I n, int atomic) {
  if ((uint64_t)n < 136) {             /* fast path, inlined: pop a zeroed slot of a class 16..136 */
    W **h = &fl[2 * (n < 8 ? 0 : (n + 8) / 8 - 2) + atomic], *p = *h;
    if (__builtin_expect(p != 0, 1)) { *h = (W *)~*p; *p = 0; return p; }
  }
  return gc_slow(n, atomic);
}
__attribute__((malloc, returns_nonnull)) void *pys_alloc(I n) { return gc_alloc(n, 0); }
__attribute__((malloc, returns_nonnull)) void *pys_alloc_atomic(I n) { return gc_alloc(n, 1); }
static void gc_report(void) {
  fprintf(stderr, "gc: %lld collections, %.1f ms; heap peak %.1f MiB; live %.1f MiB at the last\n",
          (long long)gc_n, gc_ns / 1e6, gc_peak / 1048576.0, gc_live / 1048576.0);
}
static void gc_init(char *sb, I **roots, I nroots) {
  const char *e = getenv("PYSTACHY_GC");
  gc_bottom = sb + 2 * sizeof(void *); /* sb is @main's frame address: include its frame record */
  gc_roots = roots; gc_nroots = nroots;
  if (!(pmap = calloc(1 << 18, sizeof *pmap))) oom();
  gc_off = e && !strcmp(e, "off");
  gc_stats = e && !strcmp(e, "stats");
  if (!gc_off && (e = getenv("PYSTACHY_GC_STRESS")) && atoll(e) > 0) gc_stress = atoll(e);
}

/* errors end the program after flushing stdout; a flush that fails is reported at exit, as
   CPython reports it, with status 120. Under a try (a handler record on the chain) they are
   raised instead, and end the program only if nothing catches them; so they are when unwind
   actions are registered, which run first (see exceptions). */
static volatile sig_atomic_t io_intr;  /* a Ctrl-C waiting for the I/O layer to finish a call (see I/O) */
static _Noreturn void kbint_exit(void);
static int kbint;                      /* the program ends with KeyboardInterrupt: pys_finish dies by SIGINT */
typedef struct Handler Handler;
static Handler *top;                   /* the innermost handler record (see exceptions) */
_Noreturn void pys_throw(Exc *e);
Exc *pys_exc_new(Str *kind, Str *msg, Str *args);
static Exc *exc_line(const char *m);
static Exc *exc_exit(I c, Str *msg);
void pys_unwind_push(void (*fn)(void *), void *arg);
void pys_unwind_pop(void);
_Noreturn void pys_fail(const char *m) {           /* m: "Kind: message", or "Kind" */
  if (io_intr) kbint_exit();
  if (top || nunw) pys_throw(exc_line(m));
  out_flush(); fprintf(stderr, "%s\n", m); pys_finish(); exit(1);
}
_Noreturn void pys_raise(Str *kind, Str *msg) {     /* raise kind(msg): CPython's last traceback line */
  if (top || nunw) pys_throw(pys_exc_new(kind, msg, 0));
  out_flush();
  fwrite(kind->s, 1, kind->len, stderr);
  if (msg->len) { fputs(": ", stderr); fwrite(msg->s, 1, msg->len, stderr); }
  fputc('\n', stderr);
  kbint = !strcmp(kind->s, "KeyboardInterrupt");
  pys_finish();
  exit(1);
}
_Noreturn void pys_exit(I c) { if (top || nunw) pys_throw(exc_exit(c, 0)); pys_finish(); exit((int)c); }
_Noreturn void pys_exit_msg(Str *msg) {          /* sys.exit(msg): msg to stderr, status 1 */
  if (top || nunw) pys_throw(exc_exit(0, msg));
  out_flush(); fwrite(msg->s, 1, msg->len, stderr); fputc('\n', stderr); pys_finish(); exit(1);
}

__attribute__((noinline)) static void put(Buf *b, const char *s, I n) {   /* not inlined: keeps repr small */
  if (b->n + n > b->cap) {
    I c = b->cap * 2 + n + 64; char *p = pys_alloc_atomic(c);
    if (b->n) memcpy(p, b->p, b->n);
    b->p = p; b->cap = c;
  }
  if (n) { memcpy(b->p + b->n, s, n); b->n += n; }   /* n = 0 on an empty Buf: b->p is NULL */
}

/* ---------- strings ---------- */
Str *pys_str(const char *p, I n) { Str *s = pys_alloc_atomic(sizeof(Str) + n + 1); s->len = n; if (n) memcpy(s->s, p, n); return s; }
static Str *cstr(const char *p) { return pys_str(p, strlen(p)); }
static Str *done(Buf *b) { return pys_str(b->p, b->n); }
static I u8enc(char *o, I c);
Str *pys_chr(I c) {                    /* below 256 the byte itself (str holds bytes); above, UTF-8 */
  if (c < 0 || c > 0x10FFFF) pys_fail("ValueError: chr() arg not in range(0x110000)");
  if (c > 255) { char b[4]; return pys_str(b, u8enc(b, c)); }
  if (!ch1[c]) { char b = (char)c; ch1[c] = pys_str(&b, 1); }
  return ch1[c];
}
static I u8char(const char *p, I n, I *cp) {   /* the character at p (n > 0 bytes left): its code point and byte
                                                  count; a UTF-8 sequence as chr() writes it, else one byte */
  unsigned char c = p[0]; I k = c >= 0xF0 ? 4 : c >= 0xE0 ? 3 : c >= 0xC2 ? 2 : 1, v = c & (0x7F >> k);
  *cp = c;
  if (k == 1 || k > n) return 1;
  for (I i = 1; i < k; i++) { if ((p[i] & 0xC0) != 0x80) return 1; v = v << 6 | (p[i] & 0x3F); }
  if (v < (k == 2 ? 0x80 : k == 3 ? 0x800 : 0x10000) || v > 0x10FFFF) return 1;
  *cp = v; return k;
}
I pys_ord(Str *s) {                    /* a byte, or one UTF-8 encoded character */
  I cp, n = 0;
  if (s->len && u8char(s->s, s->len, &cp) == s->len) return cp;
  for (I i = 0; i < s->len; n++) i += u8char(s->s + i, s->len - i, &cp);   /* the length in characters */
  char b[96]; snprintf(b, 96, "TypeError: ord() expected a character, but string of length %lld found", (long long)n); pys_fail(b);
}
Str *pys_ascii(Str *r) {                       /* ascii(): repr with non-ASCII as \xhh, \uhhhh, \Uhhhhhhhh */
  Buf b = {0}; char t[16];
  for (I i = 0; i < r->len;) {
    unsigned char c = r->s[i]; I n = c >= 0xF0 ? 4 : c >= 0xE0 ? 3 : c >= 0xC0 ? 2 : 1, cp = c;
    if (c < 128) { put(&b, (char *)&c, 1); i++; continue; }
    if (n > 1 && i + n <= r->len) {          /* a UTF-8 sequence; anything else is a lone byte */
      cp = c & (0x7F >> n);
      for (I k = 1; k < n; k++) { if ((r->s[i + k] & 0xC0) != 0x80) { n = 1; cp = c; break; } cp = cp << 6 | (r->s[i + k] & 0x3F); }
    } else n = 1;
    put(&b, t, snprintf(t, 16, cp < 0x100 ? "\\x%02llx" : cp < 0x10000 ? "\\u%04llx" : "\\U%08llx", (long long)cp));
    i += n;
  }
  return pys_str(b.p, b.n);
}
static I idx(I i, I n, const char *m) { if (i < 0) i += n; if (i < 0 || i >= n) pys_fail(m); return i; }
static void span(I *lo, I *hi, I n) {
  if (*lo == NONE) *lo = 0; else if (*lo < 0 && (*lo += n) < 0) *lo = 0; else if (*lo > n) *lo = n;
  if (*hi == NONE) *hi = n; else if (*hi < 0 && (*hi += n) < 0) *hi = 0; else if (*hi > n) *hi = n;
  if (*hi < *lo) *hi = *lo;
}
Str *pys_str_get(Str *s, I i) { return pys_chr((unsigned char)s->s[idx(i, s->len, "IndexError: string index out of range")]); }
Str *pys_str_slice(Str *s, I lo, I hi) { span(&lo, &hi, s->len); return pys_str(s->s + lo, hi - lo); }
Str *pys_str_add(Str *a, Str *b) {
  Str *s = pys_alloc_atomic(sizeof(Str) + a->len + b->len + 1);
  s->len = a->len + b->len; memcpy(s->s, a->s, a->len); memcpy(s->s + a->len, b->s, b->len); return s;
}
Str *pys_str_mul(Str *a, I n) {
  if (n < 0 || !a->len) n = 0;
  if (n && a->len > INT64_MAX / n) pys_fail("OverflowError: repeated string is too long");
  if (a->len * n > INT64_MAX - 64) pys_fail("MemoryError");
  Str *s = pys_alloc_atomic(sizeof(Str) + a->len * n + 1); s->len = a->len * n;
  for (I i = 0; i < n; i++) memcpy(s->s + i * a->len, a->s, a->len);
  return s;
}
I pys_str_eq(Str *a, Str *b) { return a == b || (a->len == b->len && !memcmp(a->s, b->s, a->len)); }
I pys_str_cmp(Str *a, Str *b) {
  int c = memcmp(a->s, b->s, a->len < b->len ? a->len : b->len);
  return c ? c : (a->len > b->len) - (a->len < b->len);
}
static I find(Str *h, Str *n, I i) {
  char *p = i <= h->len ? memmem(h->s + i, h->len - i, n->s, n->len) : 0;
  return p ? p - h->s : -1;
}
static void adjust(I *st, I *en, I n) {   /* CPython's ADJUST_INDICES: s[st:en] for the search methods */
  if (*en > n) *en = n; else if (*en < 0 && (*en += n) < 0) *en = 0;
  if (*st < 0 && (*st += n) < 0) *st = 0;
}
I pys_str_find(Str *h, Str *n, I st, I en) {
  adjust(&st, &en, h->len);
  if (en - st < n->len) return -1;
  char *p = memmem(h->s + st, en - st, n->s, n->len);
  return p ? p - h->s : -1;
}
I pys_str_rfind(Str *h, Str *n, I st, I en) {
  adjust(&st, &en, h->len);
  for (I i = en - n->len; i >= st; i--) if (!memcmp(h->s + i, n->s, n->len)) return i;
  return -1;
}
I pys_str_index(Str *h, Str *n, I st, I en) { I i = pys_str_find(h, n, st, en); if (i < 0) pys_fail("ValueError: substring not found"); return i; }
I pys_str_rindex(Str *h, Str *n, I st, I en) { I i = pys_str_rfind(h, n, st, en); if (i < 0) pys_fail("ValueError: substring not found"); return i; }
I pys_str_count(Str *h, Str *n, I st, I en) {
  I c = 0;
  adjust(&st, &en, h->len);
  if (en - st < n->len) return 0;
  if (!n->len) return en - st + 1;
  for (char *p; (p = memmem(h->s + st, en - st, n->s, n->len)); st = p - h->s + n->len) c++;
  return c;
}
I pys_str_contains(Str *h, Str *n) { return find(h, n, 0) >= 0; }
static I tail(Str *s, Str *p, I st, I en, int end) {   /* CPython's tailmatch */
  adjust(&st, &en, s->len);
  if (en - p->len < st) return 0;
  return !memcmp(s->s + (end ? en - p->len : st), p->s, p->len);
}
I pys_str_startswith(Str *s, Str *p, I st, I en) { return tail(s, p, st, en, 0); }
I pys_str_endswith(Str *s, Str *p, I st, I en) { return tail(s, p, st, en, 1); }
Str *pys_str_replace(Str *s, Str *a, Str *b) {
  Buf o = {0}; I i = 0;
  if (!a->len) {
    for (; i < s->len; i++) { put(&o, b->s, b->len); put(&o, s->s + i, 1); }
    put(&o, b->s, b->len); return done(&o);
  }
  for (I j; (j = find(s, a, i)) >= 0; i = j + a->len) { put(&o, s->s + i, j - i); put(&o, b->s, b->len); }
  put(&o, s->s + i, s->len - i); return done(&o);
}
static int ws(unsigned char c) { return c == ' ' || (c >= 9 && c <= 13) || (c >= 28 && c <= 31); }
static int instr(unsigned char c, Str *cs) { return cs ? memchr(cs->s, c, cs->len) != 0 : ws(c); }
static Str *strip(Str *s, Str *cs, int m) {
  I i = 0, j = s->len;
  if (m & 1) while (i < j && instr(s->s[i], cs)) i++;
  if (m & 2) while (j > i && instr(s->s[j - 1], cs)) j--;
  return pys_str(s->s + i, j - i);
}
Str *pys_str_strip(Str *s, Str *cs) { return strip(s, cs, 3); }
Str *pys_str_lstrip(Str *s, Str *cs) { return strip(s, cs, 1); }
Str *pys_str_rstrip(Str *s, Str *cs) { return strip(s, cs, 2); }
static I all(Str *s, int k) {                  /* 0 digit, 1 alpha, 2 alnum, 3 space */
  if (!s->len) return 0;
  for (I i = 0; i < s->len; i++) {
    unsigned char c = s->s[i];
    int d = c >= '0' && c <= '9', a = (c | 32) >= 'a' && (c | 32) <= 'z';
    if (!(k == 0 ? d : k == 1 ? a : k == 2 ? d || a : ws(c))) return 0;
  }
  return 1;
}
static I cased(Str *s, int up) {               /* isupper / islower */
  int any = 0;
  for (I i = 0; i < s->len; i++) {
    char c = s->s[i];
    if (c >= 'a' && c <= 'z') { if (up) return 0; any = 1; }
    if (c >= 'A' && c <= 'Z') { if (!up) return 0; any = 1; }
  }
  return any;
}
I pys_str_isdigit(Str *s) { return all(s, 0); }
I pys_str_isalpha(Str *s) { return all(s, 1); }
I pys_str_isalnum(Str *s) { return all(s, 2); }
I pys_str_isspace(Str *s) { return all(s, 3); }
I pys_str_isupper(Str *s) { return cased(s, 1); }
I pys_str_islower(Str *s) { return cased(s, 0); }
static Str *mapc(Str *s, int up) {
  Str *r = pys_str(s->s, s->len);
  for (I i = 0; i < r->len; i++) {
    char c = r->s[i];
    if (up && c >= 'a' && c <= 'z') r->s[i] = c - 32;
    if (!up && c >= 'A' && c <= 'Z') r->s[i] = c + 32;
  }
  return r;
}
Str *pys_str_upper(Str *s) { return mapc(s, 1); }
Str *pys_str_lower(Str *s) { return mapc(s, 0); }
static I ulen(const char *p, I n) { I k = 0; for (I i = 0; i < n; i++) k += ((unsigned char)p[i] & 0xC0) != 0x80; return k; }
static Str *pad(Str *s, I w, Str *fill, int how) {   /* how: 0 right, 1 left, 2 center; widths count code points */
  if (fill && ulen(fill->s, fill->len) != 1) pys_fail("TypeError: The fill character must be exactly one character long");
  I n = ulen(s->s, s->len), f = fill ? fill->len : 1;
  if (n >= w) return s;
  I gap = w - n, l = how == 1 ? 0 : how == 0 ? gap : gap / 2 + (gap & w & 1);   /* CPython's centering */
  if (gap > (INT64_MAX - s->len) / f) oom();
  Str *r = pys_alloc_atomic(sizeof(Str) + s->len + gap * f + 1); r->len = s->len + gap * f;
  char *o = r->s;
  for (I i = 0; i < l; i++, o += f) memcpy(o, fill ? fill->s : " ", f);
  memcpy(o, s->s, s->len); o += s->len;
  for (I i = l; i < gap; i++, o += f) memcpy(o, fill ? fill->s : " ", f);
  return r;
}
Str *pys_str_ljust(Str *s, I w, Str *fill) { return pad(s, w, fill, 1); }
Str *pys_str_rjust(Str *s, I w, Str *fill) { return pad(s, w, fill, 0); }
Str *pys_str_center(Str *s, I w, Str *fill) { return pad(s, w, fill, 2); }
Str *pys_str_zfill(Str *s, I w) {
  Str *r = pad(s, w, cstr("0"), 0);
  I z = r->len - s->len;                       /* a sign moves in front of the zeros */
  if (z && s->len && (s->s[0] == '+' || s->s[0] == '-')) { r->s[0] = s->s[0]; r->s[z] = '0'; }
  return r;
}
static void **triple(Str *a, Str *b, Str *c) { void **t = pys_alloc(24); t[0] = a; t[1] = b; t[2] = c; return t; }
void **pys_str_partition(Str *s, Str *sep) {
  if (!sep->len) pys_fail("ValueError: empty separator");
  I i = find(s, sep, 0);
  if (i < 0) return triple(s, cstr(""), cstr(""));
  return triple(pys_str(s->s, i), sep, pys_str(s->s + i + sep->len, s->len - i - sep->len));
}
void **pys_str_rpartition(Str *s, Str *sep) {
  if (!sep->len) pys_fail("ValueError: empty separator");
  I i = pys_str_rfind(s, sep, 0, s->len);
  if (i < 0) return triple(cstr(""), cstr(""), s);
  return triple(pys_str(s->s, i), sep, pys_str(s->s + i + sep->len, s->len - i - sep->len));
}
Str *pys_str_removeprefix(Str *s, Str *p) {
  return p->len && s->len >= p->len && !memcmp(s->s, p->s, p->len) ? pys_str(s->s + p->len, s->len - p->len) : s;
}
Str *pys_str_removesuffix(Str *s, Str *p) {
  return p->len && s->len >= p->len && !memcmp(s->s + s->len - p->len, p->s, p->len) ? pys_str(s->s, s->len - p->len) : s;
}
static int lowc(char c) { return c >= 'a' && c <= 'z'; }
static int upc(char c) { return c >= 'A' && c <= 'Z'; }
Str *pys_str_swapcase(Str *s) {
  Str *r = pys_str(s->s, s->len);
  for (I i = 0; i < r->len; i++) if (lowc(r->s[i]) || upc(r->s[i])) r->s[i] ^= 32;
  return r;
}
Str *pys_str_capitalize(Str *s) {
  Str *r = mapc(s, 0);
  if (r->len && lowc(r->s[0])) r->s[0] -= 32;
  return r;
}
Str *pys_str_title(Str *s) {                   /* a letter after a letter is lowered, any other raised */
  Str *r = pys_str(s->s, s->len); int prev = 0;
  for (I i = 0; i < r->len; i++) {
    char c = r->s[i];
    if (prev && upc(c)) r->s[i] = c + 32;
    if (!prev && lowc(c)) r->s[i] = c - 32;
    prev = lowc(c) || upc(c);
  }
  return r;
}
I pys_str_istitle(Str *s) {                    /* CPython's istitle, over ASCII letters */
  int prev = 0, any = 0;
  for (I i = 0; i < s->len; i++) {
    char c = s->s[i];
    if (upc(c)) { if (prev) return 0; prev = any = 1; }
    else if (lowc(c)) { if (!prev) return 0; prev = any = 1; }
    else prev = 0;
  }
  return any;
}
I pys_str_isascii(Str *s) { for (I i = 0; i < s->len; i++) if ((unsigned char)s->s[i] > 127) return 0; return 1; }
I pys_str_isdecimal(Str *s) { return all(s, 0); }
I pys_str_isnumeric(Str *s) { return all(s, 0); }
Str *pys_str_casefold(Str *s) { return mapc(s, 0); }
Str *pys_str_expandtabs(Str *s, I size) {
  Buf o = {0}; I col = 0;
  for (I i = 0; i < s->len; i++) {
    char c = s->s[i];
    if (c == '\t') {
      if (size > 0) { I n = size - col % size; col += n; while (n--) put(&o, " ", 1); }
    } else {
      put(&o, &c, 1);
      if (c == '\n' || c == '\r') col = 0; else col += ((unsigned char)c & 0xC0) != 0x80;
    }
  }
  return done(&o);
}
Str *pys_str_int(I v) { char b[32]; return pys_str(b, snprintf(b, 32, "%lld", (long long)v)); }
Str *pys_str_float(double d) {               /* Python repr(): shortest round-trip digits */
  char b[40], dig[24], o[64], *w = o;
  if (isnan(d)) return cstr("nan");
  if (isinf(d)) return cstr(d > 0 ? "inf" : "-inf");
  if (d == 0) return cstr(signbit(d) ? "-0.0" : "0.0");
  int p = 1;
  for (; p < 17; p++) { snprintf(b, 40, "%.*e", p - 1, d); if (strtod(b, 0) == d) break; }
  if (p == 17) snprintf(b, 40, "%.16e", d);
  int nd = 0, neg = b[0] == '-';
  char *q = b + neg;
  for (; *q != 'e'; q++) if (*q != '.') dig[nd++] = *q;
  int e = atoi(q + 1) + 1;                      /* position of the decimal point */
  while (nd > 1 && dig[nd - 1] == '0') nd--;
  if (neg) *w++ = '-';
  if (e > -4 && e <= 16) {
    if (e <= 0) { *w++ = '0'; *w++ = '.'; for (int i = 0; i < -e; i++) *w++ = '0'; memcpy(w, dig, nd); w += nd; }
    else if (e >= nd) { memcpy(w, dig, nd); w += nd; for (int i = nd; i < e; i++) *w++ = '0'; *w++ = '.'; *w++ = '0'; }
    else { memcpy(w, dig, e); w += e; *w++ = '.'; memcpy(w, dig + e, nd - e); w += nd - e; }
  } else {
    *w++ = dig[0];
    if (nd > 1) { *w++ = '.'; memcpy(w, dig + 1, nd - 1); w += nd - 1; }
    w += sprintf(w, "e%c%02d", e - 1 < 0 ? '-' : '+', abs(e - 1));
  }
  return pys_str(o, w - o);
}
Str *pys_float_hex(double d) {                /* float.hex(): CPython spells zero 0x0.0p+0, NaN unsigned */
  char b[40];
  if (isnan(d)) return cstr("nan");
  if (d == 0) return cstr(signbit(d) ? "-0x0.0p+0" : "0x0.0p+0");
  return pys_str(b, snprintf(b, 40, "%.13a", d));
}
I pys_float_is_integer(double d) { return isfinite(d) && d == floor(d); }
/* int() and float() of a string follow Python's grammar (whitespace around the number, a sign,
   digits with single underscores between them, 0x/0o/0b prefixes), not strtoll/strtod's */
static void repr_str(Buf *b, Str *s);
static _Noreturn void failf(const char *f, ...);
I pys_f2i(double d);
static _Noreturn void badlit(const char *what, I base, Str *s) {   /* int() (base >= 0) shows at most 200 */
  Buf b = {0}; char t[64]; I r, k = 0, cp;                          /* characters of the repr (%.200R) */
  put(&b, what, strlen(what));
  if (base >= 0) put(&b, t, snprintf(t, 64, " with base %lld", (long long)base));
  put(&b, ": ", 2); r = b.n; repr_str(&b, s);
  if (base >= 0) for (I i = r; i < b.n; i += u8char(b.p + i, b.n - i, &cp)) if (k++ == 200) { b.n = i; break; }
  put(&b, "", 1); pys_fail(b.p);
}
static int digitv(char c) { return c >= '0' && c <= '9' ? c - '0' : (c | 32) >= 'a' && (c | 32) <= 'z' ? (c | 32) - 'a' + 10 : 99; }
static int aws(unsigned char c) { return c == ' ' || (c >= 9 && c <= 13); }   /* int()/float() strip only these */
static const int32_t decruns[] = {      /* Unicode 15.1 (CPython 3.13): first of each run of decimal digits 0-9 */
  0x660, 0x6f0, 0x7c0, 0x966, 0x9e6, 0xa66, 0xae6, 0xb66, 0xbe6, 0xc66, 0xce6, 0xd66,
  0xde6, 0xe50, 0xed0, 0xf20, 0x1040, 0x1090, 0x17e0, 0x1810, 0x1946, 0x19d0, 0x1a80, 0x1a90,
  0x1b50, 0x1bb0, 0x1c40, 0x1c50, 0xa620, 0xa8d0, 0xa900, 0xa9d0, 0xa9f0, 0xaa50, 0xabf0, 0xff10,
  0x104a0, 0x10d30, 0x11066, 0x110f0, 0x11136, 0x111d0, 0x112f0, 0x11450, 0x114d0, 0x11650, 0x116c0, 0x11730,
  0x118e0, 0x11950, 0x11c50, 0x11d50, 0x11da0, 0x11f50, 0x16a60, 0x16ac0, 0x16b50, 0x1d7ce, 0x1d7d8, 0x1d7e2,
  0x1d7ec, 0x1d7f6, 0x1e140, 0x1e2f0, 0x1e4f0, 0x1e950, 0x1fbf0,
};
static Str *asciinum(Str *s) {         /* CPython's first step for int()/float() of a non-ASCII string: a
                                          Unicode space becomes ' ', a decimal digit its ASCII digit, and
                                          any other character '?', where the text then ends */
  I i = 0;
  while (i < s->len && !(s->s[i] & 0x80)) i++;
  if (i == s->len) return s;
  Buf b = {0}; put(&b, s->s, i);
  while (i < s->len) {
    unsigned char c = s->s[i]; I n = c >= 0xF0 ? 4 : c >= 0xE0 ? 3 : c >= 0xC0 ? 2 : 1, cp = c & (0x7F >> n);
    if (c < 0x80) { put(&b, s->s + i++, 1); continue; }
    if (n == 1 || i + n > s->len) cp = -1;
    for (I k = 1; cp >= 0 && k < n; k++) cp = (s->s[i + k] & 0xC0) == 0x80 ? cp << 6 | (s->s[i + k] & 0x3F) : -1;
    char o = '?';
    if (cp == 0x85 || cp == 0xA0 || cp == 0x1680 || (cp >= 0x2000 && cp <= 0x200A) || cp == 0x2028 || cp == 0x2029 ||
        cp == 0x202F || cp == 0x205F || cp == 0x3000) o = ' ';
    for (I r = 0; o == '?' && cp >= 0 && r < (I)(sizeof decruns / sizeof *decruns); r++)
      if (cp >= decruns[r] && cp < decruns[r] + 10) o = (char)('0' + cp - decruns[r]);
    put(&b, &o, 1);
    if (o == '?') break;
    i += n;
  }
  return done(&b);
}
I pys_int_str(Str *s, I base) {               /* CPython's PyLong_FromString on the ASCII form, checks in its order */
  if (base != 0 && (base < 2 || base > 36)) pys_fail("ValueError: int() base must be >= 2 and <= 36, or 0");
  Str *t = asciinum(s);
  const char *p = t->s, *e = t->s + t->len, *q; I b0 = base, nd = 0;
  while (p < e && aws(*p)) p++;
  while (e > p && aws(e[-1])) e--;
  int neg = 0, octal = 0, prev = 0;            /* octal: base 0 and a leading 0, which only 0 may have */
  if (p < e && (*p == '+' || *p == '-')) neg = *p++ == '-';
  if (e - p >= 2 && p[0] == '0') {
    int pb = (p[1] | 32) == 'x' ? 16 : (p[1] | 32) == 'o' ? 8 : (p[1] | 32) == 'b' ? 2 : 0;
    if (pb && (base == 0 || base == pb)) { base = pb; p += 2; if (p < e && *p == '_') p++; }
  }
  if (base == 0) { base = 10; octal = p < e && *p == '0'; }
  uint64_t u = 0, lim = neg ? (uint64_t)1 << 63 : ((uint64_t)1 << 63) - 1; int ovf = 0;
  for (q = p; q < e && (digitv(*q) < base || (*q == '_' && q > p && prev != '_')); prev = *q++) {
    if (*q == '_') continue;                   /* digits, with single underscores between them */
    int dv = digitv(*q); nd++;
    if (u > (lim - dv) / base) ovf = 1; else u = u * base + dv;
  }
  while (q < e && aws(*q)) q++;                /* whitespace before an embedded NUL, where CPython's C string ends */
  if (!nd || prev == '_' || (q < e && *q)) badlit("ValueError: invalid literal for int()", b0, s);
  if ((base & (base - 1)) && nd > 4300)        /* CPython's limit for its quadratic conversion */
    failf("ValueError: Exceeds the limit (4300 digits) for integer string conversion: value has %lld digits; "
          "use sys.set_int_max_str_digits() to increase the limit", (long long)nd);
  if (q < e || (octal && u)) badlit("ValueError: invalid literal for int()", b0, s);
  if (ovf) pys_fail("OverflowError: int() result does not fit in 64 bits");
  return neg ? (I)(0 - u) : (I)u;
}
double pys_float_str(Str *s) {
  Str *t = asciinum(s);
  const char *p = t->s, *e = t->s + t->len;
  while (p < e && aws(*p)) p++;
  while (e > p && aws(e[-1])) e--;
  Buf b = {0}; const char *q = p;
  if (q < e && (*q == '+' || *q == '-')) put(&b, q++, 1);
  I n = e - q;
  if ((n == 3 && !strncasecmp(q, "inf", 3)) || (n == 8 && !strncasecmp(q, "infinity", 8)) || (n == 3 && !strncasecmp(q, "nan", 3))) {
    put(&b, q, n); put(&b, "", 1); return strtod(b.p, 0);
  }
  int digits = 0, prev = 0;                    /* prev: 1 after a digit; underscores only between digits */
  for (; q < e; q++) {
    char c = *q;
    if (c >= '0' && c <= '9') { digits = 1; prev = 1; put(&b, q, 1); continue; }
    if (c == '_' && prev && q + 1 < e && q[1] >= '0' && q[1] <= '9') { prev = 0; continue; }
    if (c == '.' || c == 'e' || c == 'E' || ((c == '+' || c == '-') && q > p && (q[-1] | 32) == 'e')) { prev = 0; put(&b, q, 1); continue; }
    badlit("ValueError: could not convert string to float", -1, s);
  }
  put(&b, "", 1);
  char *end; double v = strtod(b.p, &end);
  if (!digits || *end) badlit("ValueError: could not convert string to float", -1, s);
  return v;
}

/* ---------- arithmetic with Python semantics ----------
   ints are 64-bit: a result CPython would represent as a big int raises OverflowError */
#define ZDE "ZeroDivisionError: integer division or modulo by zero"
#define OVF "OverflowError: integer result does not fit in 64 bits"
I pys_floordiv(I a, I b) {
  if (!b) pys_fail(ZDE);
  if (b == -1) { if (a == INT64_MIN) pys_fail(OVF); return -a; }
  I q = a / b; return (a % b && (a < 0) != (b < 0)) ? q - 1 : q;
}
I pys_mod(I a, I b) {
  if (!b) pys_fail("ZeroDivisionError: integer modulo by zero");
  if (b == -1) return 0;
  I r = a % b; return (r && (r < 0) != (b < 0)) ? r + b : r;
}
I pys_pow(I a, I b) {
  if (b < 0) pys_fail(a ? "ValueError: negative exponent for int ** int" : "ZeroDivisionError: 0.0 cannot be raised to a negative power");
  I r = 1, x = a;
  if (a == 0 || a == 1) return b ? a : 1;
  if (a == -1) return b & 1 ? -1 : 1;
  for (;;) {                                   /* |a| >= 2, so overflow comes within 63 steps */
    if ((b & 1) && __builtin_mul_overflow(r, x, &r)) pys_fail(OVF);
    if (!(b >>= 1)) return r;
    if (__builtin_mul_overflow(x, x, &x)) pys_fail(OVF);
  }
}
I pys_powmod(I a, I b, I m) {                 /* pow(a, b, m) as CPython's long_pow, in 128 bits: products cannot overflow */
  if (!m) pys_fail("ValueError: pow() 3rd argument cannot be 0");
  __int128 n = m < 0 ? -(__int128)m : m, x = a, r = 1;
  if (n == 1) return 0;
  if (b < 0) {                                 /* a negative exponent: the power of a's inverse modulo |m| */
    __int128 p = x, q = n, s = 1, t = 0;       /* long_invmod: Euclid with floor division */
    while (q) {
      __int128 d = p / q - (p % q && (p < 0) != (q < 0)), u = p - d * q, w = s - d * t;
      p = q; q = u; s = t; t = w;
    }
    if (p != 1) pys_fail("ValueError: base is not invertible for the given modulus");
    x = s;
  }
  x %= n;
  if (x < 0) x += n;
  for (unsigned __int128 e = b < 0 ? -(__int128)b : b; e; e >>= 1) { if (e & 1) r = r * x % n; x = x * x % n; }
  return (I)(m < 0 && r ? r - n : r);          /* the result has the sign of m */
}
I pys_shl(I a, I b) {
  if (b < 0) pys_fail("ValueError: negative shift count");
  if (!a) return 0;
  I r = b > 63 ? 0 : (I)((uint64_t)a << b);
  if (b > 63 || r >> b != a) pys_fail(OVF);
  return r;
}
I pys_shr(I a, I b) { if (b < 0) pys_fail("ValueError: negative shift count"); return a >> (b > 63 ? 63 : b); }
double pys_fdiv(double a, double b) { if (b == 0) pys_fail("ZeroDivisionError: float division by zero"); return a / b; }
double pys_idiv(I a, I b) {                  /* int / int, rounded once like CPython's true division */
  if (!b) pys_fail("ZeroDivisionError: division by zero");
  uint64_t x = a < 0 ? 0 - (uint64_t)a : (uint64_t)a, y = b < 0 ? 0 - (uint64_t)b : (uint64_t)b;
  if (x <= (1ULL << 53) && y <= (1ULL << 53)) return (double)a / (double)b;   /* both exact: one rounding */
  int k = 55 + (63 - __builtin_clzll(y)) - (63 - __builtin_clzll(x)); if (k < 0) k = 0;
  unsigned __int128 num = (unsigned __int128)x << k, q = num / y; int sticky = num % y != 0;
  double r = ldexp((double)(uint64_t)(q | sticky), -k);   /* q has 55+ bits: the sticky bit makes the conversion round once */
  return (a < 0) != (b < 0) ? -r : r;
}
I pys_cmp_if(I i, double d) {                  /* exact compare of an int with a float: -1, 0, 1, or 2 if unordered */
  if (isnan(d)) return 2;
  if (d >= 9223372036854775808.0) return -1;
  if (d < -9223372036854775808.0) return 1;
  double t = trunc(d); I j = (I)t;
  if (i != j) return i < j ? -1 : 1;
  return d > t ? -1 : d < t ? 1 : 0;
}
double pys_fpow(double a, double b) {          /* float ** float with CPython's errors */
  if (a == 0 && b < 0 && isfinite(b)) pys_fail("ZeroDivisionError: 0.0 cannot be raised to a negative power");
  if (a < 0 && isfinite(a) && isfinite(b) && b != floor(b)) pys_fail("ValueError: a negative number to a fractional power has a complex result (not supported)");
  double r = pow(a, b);
  if (isinf(r) && isfinite(a) && isfinite(b)) pys_fail("OverflowError: (34, 'Numerical result out of range')");
  return r;
}
/* math functions raise like CPython's math module: a NaN from a non-NaN argument is a domain
   error, an infinity from finite arguments a range error (or a domain error for log and sqrt) */
static double mchk(double r, double x, double y, int ovf) {
  if (isnan(r) && !isnan(x) && !isnan(y)) pys_fail("ValueError: math domain error");
  if (isinf(r) && isfinite(x) && isfinite(y)) pys_fail(ovf ? "OverflowError: math range error" : "ValueError: math domain error");
  return r;
}
#define M1(f, ovf) double pys_m_##f(double x) { return mchk(f(x), x, 0, ovf); }
M1(sqrt, 0) M1(sin, 0) M1(cos, 0) M1(tan, 0) M1(asin, 0) M1(acos, 0) M1(atan, 0) M1(sinh, 1) M1(cosh, 1) M1(tanh, 0)
M1(exp, 1) M1(log, 0) M1(log2, 0) M1(log10, 0) M1(fabs, 0) M1(log1p, 0) M1(expm1, 1) M1(exp2, 1) M1(cbrt, 0)
double pys_m_pow(double x, double y) {
  if (x == 0 && y < 0 && isfinite(y)) pys_fail("ValueError: math domain error");
  return mchk(pow(x, y), x, y, 1);
}
double pys_m_fmod(double x, double y) { if (isinf(x) || (y == 0 && !isnan(x))) pys_fail("ValueError: math domain error"); return fmod(x, y); }
double pys_m_atan2(double y, double x) { return atan2(y, x); }
/* math.hypot is CPython's vector_norm, not libm's hypot, so its last bit agrees: lossless scaling
   by a power of two, exact squares (fma), compensated summation and a differential correction of
   the square root; it never raises (inf on overflow) */
typedef struct { double hi, lo; } DL;
static DL dl_fast_sum(double a, double b) { double x = a + b; return (DL){x, (a - x) + b}; }
static DL dl_mul(double x, double y) { double z = x * y; return (DL){z, fma(x, y, -z)}; }
static double vnorm(double *v, int n, double max) {
#pragma clang fp contract(off)
  double csum = 1.0, frac1 = 0.0, frac2 = 0.0, x, h, scale; DL pr, sm; int e;
  if (max == 0.0 || n <= 1) return max;
  frexp(max, &e);
  if (e < -1023) { for (int i = 0; i < n; i++) v[i] /= 0x1p-1022; return 0x1p-1022 * vnorm(v, n, max / 0x1p-1022); }
  scale = ldexp(1.0, -e);
  for (int i = 0; i < n; i++) {
    x = v[i] * scale; pr = dl_mul(x, x); sm = dl_fast_sum(csum, pr.hi);
    csum = sm.hi; frac1 += pr.lo; frac2 += sm.lo;
  }
  h = sqrt(csum - 1.0 + (frac1 + frac2));
  pr = dl_mul(-h, h); sm = dl_fast_sum(csum, pr.hi);
  csum = sm.hi; frac1 += pr.lo; frac2 += sm.lo;
  x = csum - 1.0 + (frac1 + frac2);
  h += x / (2.0 * h);
  return h / scale;
}
double pys_m_hypot(double x, double y) {
  double v[2] = {fabs(x), fabs(y)}, max = 0.0;
  for (int i = 0; i < 2; i++) if (v[i] > max) max = v[i];   /* a NaN is never the max */
  if (isinf(max)) return max;
  if (isnan(x) || isnan(y)) return NAN;
  return vnorm(v, 2, max);
}
double pys_m_copysign(double x, double y) { return copysign(x, y); }
double pys_m_logb(double x, double b) {   /* log(x) / log(b), and a base of 1 divides by zero, as in CPython */
  double n = mchk(log(x), x, 0, 0), d = mchk(log(b), b, 0, 0);
  if (d == 0) pys_fail("ZeroDivisionError: float division by zero");
  return n / d;
}
double pys_m_degrees(double x) { return x * (180.0 / 3.141592653589793); }
double pys_m_radians(double x) { return x * (3.141592653589793 / 180.0); }
I pys_m_isfinite(double x) { return isfinite(x); }
I pys_m_isinf(double x) { return isinf(x); }
I pys_m_isnan(double x) { return isnan(x); }
I pys_m_trunc(double x) { return pys_f2i(trunc(x)); }
I pys_m_gcd(I a, I b) { uint64_t x = a < 0 ? 0 - (uint64_t)a : a, y = b < 0 ? 0 - (uint64_t)b : b; while (y) { uint64_t t = x % y; x = y; y = t; } if (x >> 63) pys_fail(OVF); return (I)x; }
I pys_m_lcm(I a, I b) {                       /* |a / gcd * b|; a product of -2**63 has no 64-bit absolute value */
  if (!a || !b) return 0;
  I g = pys_m_gcd(a, b), r;
  if (__builtin_mul_overflow(a / g, b, &r) || r == INT64_MIN) pys_fail(OVF);
  return r < 0 ? -r : r;
}
I pys_m_isqrt(I n) {
  if (n < 0) pys_fail("ValueError: isqrt() argument must be nonnegative");
  I r = (I)sqrt((double)n);
  while (r > 0 && r > n / r) r--;
  while ((r + 1) <= n / (r + 1)) r++;
  return r;
}
I pys_m_factorial(I n) {
  if (n < 0) pys_fail("ValueError: factorial() not defined for negative values");
  I r = 1; for (I i = 2; i <= n; i++) if (__builtin_mul_overflow(r, i, &r)) pys_fail(OVF);
  return r;
}
I pys_m_comb(I n, I k) {
  if (n < 0 || k < 0) pys_fail(n < 0 ? "ValueError: n must be a non-negative integer" : "ValueError: k must be a non-negative integer");
  if (k > n) return 0;
  if (k > n - k) k = n - k;
  unsigned __int128 r = 1;
  for (I i = 1; i <= k; i++) { r = r * (n - k + i) / i; if (r >> 63) pys_fail(OVF); }
  return (I)r;
}
I pys_m_perm(I n, I k) {
  if (n < 0 || k < 0) pys_fail(n < 0 ? "ValueError: n must be a non-negative integer" : "ValueError: k must be a non-negative integer");
  if (k > n) return 0;
  I r = 1; for (I i = 0; i < k; i++) if (__builtin_mul_overflow(r, n - i, &r)) pys_fail(OVF);
  return r;
}

static double pymod(double a, double b, double *q) {   /* CPython's float_divmod */
  double m = fmod(a, b), d = (a - m) / b;
  if (m) { if ((b < 0) != (m < 0)) { m += b; d -= 1; } } else m = copysign(0, b);
  if (d) { double f = floor(d); if (d - f > 0.5) f += 1; d = f; } else d = copysign(0, a / b);
  *q = d; return m;
}
double pys_fmod(double a, double b) { double q; if (b == 0) pys_fail("ZeroDivisionError: float modulo by zero"); return pymod(a, b, &q); }
double pys_ffloordiv(double a, double b) { double q; if (b == 0) pys_fail("ZeroDivisionError: float floor division by zero"); pymod(a, b, &q); return q; }
I pys_f2i(double d) {
  if (isnan(d)) pys_fail("ValueError: cannot convert float NaN to integer");
  if (isinf(d)) pys_fail("OverflowError: cannot convert float infinity to integer");
  if (!(d >= -9223372036854775808.0 && d < 9223372036854775808.0)) pys_fail("OverflowError: float too large for a 64-bit int");
  return (I)d;
}
I pys_round(double d) { return pys_f2i(nearbyint(d)); }
double pys_round_n(double x, I n) {           /* round(x, n): half-even on the exact decimal value */
  static char b[1500], o[1500];
  if (!isfinite(x) || n > 400) return x;
  if (n >= 0) { snprintf(b, sizeof b, "%.*f", (int)n, x); return strtod(b, 0); }
  if (n < -308 && fabs(x) < 1e308) return copysign(0.0, x);
  int k = n < -400 ? 400 : (int)-n, len = snprintf(b, sizeof b, "%.1080f", fabs(x));
  int h = (int)(strchr(b, '.') - b) - k, up = 0, m = h;   /* keep h integer digits, drop k */
  if (h < 0) return copysign(0.0, x);
  if (b[h] != '5') up = b[h] > '5';
  else { up = -1; for (int i = h + 1; i < len; i++) if (b[i] > '0') { up = 1; break; } }
  memcpy(o, b, h);
  if (up < 0) up = h > 0 && (o[h - 1] - '0') % 2;          /* exact tie: round half to even */
  if (up) { int i = m - 1; while (i >= 0 && o[i] == '9') o[i--] = '0'; if (i >= 0) o[i]++; else { memmove(o + 1, o, m); o[0] = '1'; m++; } }
  if (!m) o[m++] = '0';
  memset(o + m, '0', k); o[m + k] = 0;
  double r = strtod(o, 0);
  if (isinf(r)) pys_fail("OverflowError: rounded value too large to represent");
  return copysign(r, x);
}
I pys_floor(double d) { return pys_f2i(floor(d)); }
I pys_ceil(double d) { return pys_f2i(ceil(d)); }

/* ---------- generic repr / equality / ordering driven by a type descriptor ----------
   i int, f float, b bool, s str, L<e> list, D<k><v> dict, T<n><e...> tuple, O<ddd> object
   of class number ddd: the program defines pys_obj_eq/lt/repr, which dispatch on it */
I pys_obj_eq(I c, I a, I b);
I pys_obj_cmp(I c, I op, I a, I b);
Str *pys_obj_repr(I c, I a, I b);
static I ocls(const char *d) { return (d[0] - '0') * 100 + (d[1] - '0') * 10 + d[2] - '0'; }
Str *pys_default_repr(Str *cls, void *p) {
  const char *f = "<%s object at %p>"; int n = snprintf(0, 0, f, cls->s, p);
  Str *s = pys_alloc_atomic(sizeof(Str) + n + 1); s->len = n; snprintf(s->s, n + 1, f, cls->s, p); return s;
}
static void **busy; static I nbusy, cbusy;   /* objects whose generated __repr__ is running */
I pys_repr_enter(void *p) {
  for (I i = 0; i < nbusy; i++) if (busy[i] == p) return 0;
  if (nbusy == cbusy) { cbusy = cbusy * 2 + 8; busy = realloc(busy, cbusy * sizeof(void *)); if (!busy) pys_fail("MemoryError"); }
  busy[nbusy++] = p; return 1;
}
void pys_repr_leave(void *p) { for (I i = nbusy - 1; i >= 0; i--) if (busy[i] == p) { busy[i] = busy[--nbusy]; return; } }
static const char *skip(const char *d) {
  char c = *d++;
  if (c == 'O') return d + 3;
  if (c == 'L') return skip(d);
  if (c == 'D') return skip(skip(d));
  if (c == 'T') for (int n = *d++ - '0'; n > 0; n--) d = skip(d);
  return d;
}
static double dbl(I v) { double x; memcpy(&x, &v, 8); return x; }
static int printable(I c);
static char rquote(const char *s, I n) { return memchr(s, '\'', n) && !memchr(s, '"', n) ? '"' : '\''; }
static I resc(char *t, const char *s, I len, char q, I *n) {   /* the character at s as CPython's unicode_repr writes it
                                                                 between quotes q, into t (12 bytes); *n: its bytes in s */
  I c;
  *n = u8char(s, len, &c);
  if (c == q || c == '\\') { t[0] = '\\'; t[1] = (char)c; return 2; }
  if (c == '\n' || c == '\r' || c == '\t') { t[0] = '\\'; t[1] = c == '\n' ? 'n' : c == '\r' ? 'r' : 't'; return 2; }
  if (c < 32 || c == 127 || (c > 127 && !printable(c)))   /* not printable: \xhh, \uhhhh or \Uhhhhhhhh */
    return snprintf(t, 12, c < 0x100 ? "\\x%02llx" : c < 0x10000 ? "\\u%04llx" : "\\U%08llx", (long long)c);
  memcpy(t, s, *n);
  return *n;
}
static void repr_str(Buf *b, Str *s) {
  char q = rquote(s->s, s->len), t[12];
  put(b, &q, 1);
  for (I i = 0, n; i < s->len; i += n) put(b, t, resc(t, s->s + i, s->len - i, q, &n));
  put(b, &q, 1);
}
static const char *repr(Buf *b, I v, const char *d) {
  switch (*d++) {
  case 'i': { char t[32]; put(b, t, snprintf(t, 32, "%lld", (long long)v)); return d; }
  case 'f': { Str *s = pys_str_float(dbl(v)); put(b, s->s, s->len); return d; }
  case 'b': put(b, v ? "True" : "False", v ? 4 : 5); return d;
  case 's': repr_str(b, (Str *)v); return d;
  case 'L': {
    List *l = (List *)v; put(b, "[", 1);
    for (I i = 0; i < l->len; i++) { if (i) put(b, ", ", 2); repr(b, l->a[i], d); }
    put(b, "]", 1); return skip(d);
  }
  case 'D': {
    Dict *m = (Dict *)v; const char *dv = skip(d); put(b, "{", 1);
    for (I e = 0, k = 0; e < m->n; e++) {
      if (!m->hs[e]) continue;
      if (k++) put(b, ", ", 2);
      repr(b, m->keys[e], d); put(b, ": ", 2); repr(b, m->vals[e], dv);
    }
    put(b, "}", 1); return skip(dv);
  }
  case 'T': {
    int n = *d++ - '0'; I *t = (I *)v; put(b, "(", 1);
    for (int i = 0; i < n; i++) { if (i) put(b, ", ", 2); d = repr(b, t[i], d); }
    put(b, n == 1 ? ",)" : ")", n == 1 ? 2 : 1); return d;
  }
  case 'O': { Str *s = pys_obj_repr(ocls(d), v, 0); put(b, s->s, s->len); return d + 3; }
  }
  return d;
}
Str *pys_repr(I v, Str *d) { Buf b = {0}; repr(&b, v, d->s); return done(&b); }
static I entry(Dict *d, I k);
static int eqv(I a, I b, const char *d) {
  switch (*d) {
  case 'f': return dbl(a) == dbl(b);
  case 's': return pys_str_eq((Str *)a, (Str *)b);
  case 'L': {
    List *x = (List *)a, *y = (List *)b;
    if (x->len != y->len) return 0;
    for (I i = 0; i < x->len; i++) if (!eqv(x->a[i], y->a[i], d + 1)) return 0;
    return 1;
  }
  case 'D': {
    Dict *x = (Dict *)a, *y = (Dict *)b; const char *dv = skip(d + 1);
    if (x->len != y->len) return 0;
    for (I e = 0; e < x->n; e++) {
      if (!x->hs[e]) continue;
      I f = entry(y, x->keys[e]);
      if (f < 0 || !eqv(x->vals[e], y->vals[f], dv)) return 0;
    }
    return 1;
  }
  case 'T': {
    I *x = (I *)a, *y = (I *)b; const char *e = d + 2;
    for (int i = 0; i < d[1] - '0'; i++, e = skip(e)) if (!eqv(x[i], y[i], e)) return 0;
    return 1;
  }
  case 'O': return a == b || pys_obj_eq(ocls(d + 1), a, b);   /* identity first, like CPython */
  }
  return a == b;
}
I pys_eq(I a, I b, Str *d) { return eqv(a, b, d->s); }
/* a OP b for op 0..3 = < <= > >=, as CPython compares: sequences find the first pair of
   items that are not equal (identity, then ==) and apply OP to that pair only, else compare
   lengths; objects go through the program's rich comparison (reflection, TypeError) */
static int cmpop(I c, I op) { return op == 0 ? c < 0 : op == 1 ? c <= 0 : op == 2 ? c > 0 : c >= 0; }
static int opv(I a, I b, const char *d, I op) {
  switch (*d) {
  case 'f': { double x = dbl(a), y = dbl(b); return op == 0 ? x < y : op == 1 ? x <= y : op == 2 ? x > y : x >= y; }
  case 's': return cmpop(pys_str_cmp((Str *)a, (Str *)b), op);
  case 'L': {
    List *x = (List *)a, *y = (List *)b; I i = 0;
    while (i < x->len && i < y->len && eqv(x->a[i], y->a[i], d + 1)) i++;
    if (i < x->len && i < y->len) return opv(x->a[i], y->a[i], d + 1, op);
    return cmpop((x->len > y->len) - (x->len < y->len), op);
  }
  case 'T': {
    I *x = (I *)a, *y = (I *)b; const char *e = d + 2;
    for (int i = 0; i < d[1] - '0'; i++, e = skip(e)) if (!eqv(x[i], y[i], e)) return opv(x[i], y[i], e, op);
    return cmpop(0, op);
  }
  case 'O': return pys_obj_cmp(ocls(d + 1), op, a, b) != 0;
  case 'D': failf("TypeError: '%s' not supported between instances of 'dict' and 'dict'", op == 0 ? "<" : op == 1 ? "<=" : op == 2 ? ">" : ">=");
  }
  return cmpop((a > b) - (a < b), op);
}
I pys_cmpop(I a, I b, Str *d, I op) { return opv(a, b, d->s, op); }

void pys_unpack_check(I have, I want) {
  char b[96];
  if (have < want) snprintf(b, 96, "ValueError: not enough values to unpack (expected %lld, got %lld)", (long long)want, (long long)have);
  else if (have > want) snprintf(b, 96, "ValueError: too many values to unpack (expected %lld)", (long long)want);
  else return;
  pys_fail(b);
}

/* ---------- lists ---------- */
List *pys_list_new(I cap) {
  List *l = pys_alloc(sizeof(List));
  l->cap = cap > 4 ? cap : 4; l->a = pys_alloc(l->cap * 8); return l;
}
static void reserve(List *l, I n) {
  if (n <= l->cap) return;
  I c = l->cap * 2 > n ? l->cap * 2 : n; I *a = pys_alloc(c * 8);
  memcpy(a, l->a, l->len * 8); l->a = a; l->cap = c;
}
/* element access through a distinct struct type: TBAA then knows a store to an element
   never changes l->len or l->a, so LLVM hoists those loads out of loops */
typedef struct { I v; } Slot;
#define AT(l, i) (((Slot *)(l)->a)[i].v)
void pys_list_append(List *l, I v) { if (l->len == l->cap) reserve(l, l->len + 1); AT(l, l->len++) = v; }
I pys_list_get(List *l, I i) { return AT(l, idx(i, l->len, "IndexError: list index out of range")); }
void pys_list_set(List *l, I i, I v) { AT(l, idx(i, l->len, "IndexError: list assignment index out of range")) = v; }
/* a slot a list no longer uses is zeroed: the collector scans the whole array, so a stale
   pointer there would keep the removed item alive (and a removed file open) */
I pys_list_pop(List *l, I i) {
  if (!l->len) pys_fail("IndexError: pop from empty list");
  i = idx(i, l->len, "IndexError: pop index out of range");
  I v = l->a[i]; memmove(l->a + i, l->a + i + 1, (l->len - i - 1) * 8); l->a[--l->len] = 0; return v;
}
void pys_list_del(List *l, I i) { i = idx(i, l->len, "IndexError: list assignment index out of range"); memmove(l->a + i, l->a + i + 1, (l->len - i - 1) * 8); l->a[--l->len] = 0; }
void pys_list_insert(List *l, I i, I v) {
  if (i < 0 && (i += l->len) < 0) i = 0;
  if (i > l->len) i = l->len;
  reserve(l, l->len + 1); memmove(l->a + i + 1, l->a + i, (l->len - i) * 8); l->a[i] = v; l->len++;
}
void pys_list_extend(List *l, List *m) { I n = m->len; reserve(l, l->len + n); memcpy(l->a + l->len, m->a, n * 8); l->len += n; }
List *pys_list_slice(List *l, I lo, I hi) {
  span(&lo, &hi, l->len);
  List *r = pys_list_new(hi - lo); memcpy(r->a, l->a + lo, (hi - lo) * 8); r->len = hi - lo; return r;
}
List *pys_list_copy(List *l) { return pys_list_slice(l, NONE, NONE); }
void pys_list_clear(List *l) { memset(l->a, 0, l->len * 8); l->len = 0; }
List *pys_list_add(List *a, List *b) { List *r = pys_list_new(a->len + b->len); pys_list_extend(r, a); pys_list_extend(r, b); return r; }
void pys_list_imul(List *l, I n) {               /* xs *= n, in place */
  I m = l->len;
  if (n <= 0 || !m) { pys_list_clear(l); return; }
  if (m > (INT64_MAX >> 4) / n) pys_fail("MemoryError");
  reserve(l, m * n);
  for (I i = 1; i < n; i++) memcpy(l->a + i * m, l->a, m * 8);
  l->len = m * n;
}
List *pys_list_mul(List *a, I n) {
  I m = a->len;
  if (!m) n = 0;
  if (n > 0 && m > (INT64_MAX >> 4) / n) pys_fail("MemoryError");
  List *r = pys_list_new(n > 0 ? m * n : 0);
  for (I i = 0; i < n; i++) memcpy(r->a + i * m, a->a, m * 8);
  r->len = n > 0 ? m * n : 0; return r;
}
I pys_list_find(List *l, I v, Str *d) { for (I i = 0; i < l->len; i++) if (eqv(l->a[i], v, d->s)) return i; return -1; }
I pys_list_index(List *l, I v, Str *d, I st, I en) {   /* list.index(v, start, stop) */
  I i = -1;
  if (st < 0 && (st += l->len) < 0) st = 0;
  if (en < 0 && (en += l->len) < 0) en = 0;
  for (I j = st; j < en && j < l->len; j++) if (eqv(l->a[j], v, d->s)) { i = j; break; }
  if (i < 0) { Buf b = {0}; put(&b, "ValueError: ", 12); repr(&b, v, d->s); put(&b, " is not in list", 16); pys_fail(b.p); }
  return i;
}
I pys_list_count(List *l, I v, Str *d) { I c = 0; for (I i = 0; i < l->len; i++) c += eqv(l->a[i], v, d->s); return c; }
void pys_list_remove(List *l, I v, Str *d) {
  I i = pys_list_find(l, v, d);
  if (i < 0) pys_fail("ValueError: list.remove(x): x not in list");
  pys_list_pop(l, i);
}
static void rev(I *a, I n) { for (I i = 0, j = n - 1; i < j; i++, j--) { I t = a[i]; a[i] = a[j]; a[j] = t; } }
void pys_list_reverse(List *l) { rev(l->a, l->len); }
/* Portions derived from CPython's Objects/listobject.c: Copyright (c) 2001-2024 Python Software
   Foundation; All Rights Reserved; used under the PSF License Agreement (see THIRD_PARTY_NOTICES). */
/* list.sort is CPython 3.13's timsort (Objects/listobject.c, designed in listsort.txt), ported
   function by function so that it makes exactly CPython's sequence of `<` comparisons, which is
   observable (where NaNs end up, what an __lt__ with side effects sees): each ISLT(x, y) there is
   one LT(x, y) here, in the same order. Natural runs, extended to minrun items by binary insertion,
   are merged as the powersort policy decides; a merge copies the shorter run to a buffer and
   gallops while one side keeps winning. No key=; CPython's type-specialized compares make the same
   comparisons as opv. As in CPython (ob_item NULL, allocated -1), the list looks empty while it is
   sorted, and growing it from __lt__ makes the sort fail afterwards. Items can exist only in the
   merge buffer when a comparison runs the collector: the buffer is scanned memory, and it and the
   item array stay in volatile fields of the MergeState (MS) on the stack. A comparison that
   raises into a try leaves the list with all its items, in the order reached, as in CPython: an
   unwind action (sort_undo) copies back the items that are only in the merge buffer, from where
   the merge noted them last (KEEP, before each comparison that may raise), undoes reverse='s
   reversal and gives the list its array back. What it needs is in a record on the heap (Undo),
   so that it can run when the sort's frame is gone. Speed: the common item types compare
   inline, and binary insertion and the one-at-a-time merging of ints and floats use selects, as
   random data makes their branches unpredictable (merging strings or objects keeps the
   branches, which let the CPU fetch their data early). */
#define MIN_GALLOP 7
typedef struct { I s, n; int power; } Run;          /* a pending run: start, length, powersort power */
typedef struct {
  const char *d; int kind; I cls;                   /* element descriptor; its kind (below) and class id */
  I *volatile a, *volatile t;                       /* item array and merge buffer: roots for the collector */
  I n, nt, min_gallop; int np; Run p[64];           /* items; buffer size; the stack of pending runs */
  struct Undo *u;                                   /* keep: sort_undo's record, else NULL */
} MS;
typedef struct Undo {                               /* for sort_undo: the list, its item array, length, */
  List *l; I *a, n, cap; int rev;                   /* capacity and reverse=; KEEP notes fs[:fn], the */
  I *fd, *fs, fn;                                   /* items only in the buffer, and fd, where they go back */
} Undo;
#define KEEP(dst, src, k) do { if (keep) { Undo *u_ = ms->u; u_->fd = (dst); u_->fs = (src); u_->fn = (k); } } while (0)
static I sorting[1];                                /* the items of a list while it is being sorted */
enum { INT = 1, FLOAT, STR, OBJ };                  /* kinds of items whose ISLT is inline */
static inline int islt(MS *ms, I x, I y) {          /* ISLT: opv(x, y, d, 0), its common cases inline */
  int k = ms->kind;
  return k == INT ? x < y : k == FLOAT ? dbl(x) < dbl(y) : k == STR ? pys_str_cmp((Str *)x, (Str *)y) < 0 :
         k == OBJ ? pys_obj_cmp(ms->cls, 0, x, y) != 0 : opv(x, y, ms->d, 0);
}
#define LT(x, y) islt(ms, x, y)
static void binarysort(MS *ms, I *a, I n, I ok) {   /* a[:ok] is sorted: binary insertion of the rest */
  for (ok += !ok; ok < n; ok++) {
    I L = 0, R = ok, x = a[ok];
    do { I M = (L + R) >> 1; if (__builtin_unpredictable(LT(x, a[M]))) R = M; else L = M + 1; } while (L < R);   /* selects */
    memmove(a + L + 1, a + L, (ok - L) * 8); a[L] = x;
  }
}
static I count_run(MS *ms, I *a, I n) {             /* length of the run that starts a[:n], made ascending */
  I k = 1, neq = 0;
  while (k < n && !LT(a[k], a[k - 1])) k++;
  if (k == n) return k;
  if (k > 1) { if (LT(a[0], a[k - 1])) return k; rev(a, k); }   /* all equal so far: descending */
  for (k++; k < n; k++) {                           /* descending: stretches of equal items are */
    if (LT(a[k], a[k - 1])) { rev(a + k - neq - 1, neq + 1); neq = 0; }   /* reversed on the way, */
    else if (LT(a[k - 1], a[k])) break;             /* so the final reversal keeps them in order */
    else neq++;
  }
  rev(a + k - neq - 1, neq + 1); rev(a, k);
  while (k < n && !LT(a[k], a[k - 1])) k++;         /* reversed, it may go on ascending */
  return k;
}
/* gallop_left (right 0) and gallop_right (right 1): where key goes in the sorted a[:n], searching
   outwards from a[hint]; the k with a[k-1] < key <= a[k], or a[k-1] <= key < a[k]. PRE(x) says x
   goes before key: x < key for gallop_left, not key < x for gallop_right. */
static I gallop(MS *ms, I key, I *a, I n, I hint, int right) {
#define PRE(x) (right ? !LT(key, x) : LT(x, key))
  I ofs = 1, last = 0, k;
  if (PRE(a[hint])) {                               /* right, until a[hint+ofs] does not go before key */
    I max = n - hint;
    while (ofs < max && PRE(a[hint + ofs])) { last = ofs; ofs = (ofs << 1) + 1; }
    if (ofs > max) ofs = max;
    last += hint; ofs += hint;
  } else {                                          /* left, until a[hint-ofs] goes before key */
    I max = hint + 1;
    while (ofs < max && !PRE(a[hint - ofs])) { last = ofs; ofs = (ofs << 1) + 1; }
    if (ofs > max) ofs = max;
    k = last; last = hint - ofs; ofs = hint - k;
  }
  for (last++; last < ofs;) { I m = last + ((ofs - last) >> 1); if (PRE(a[m])) last = m + 1; else ofs = m; }
  return ofs;
#undef PRE
}
static I *getmem(MS *ms, I need) {                  /* merge_getmem, growing geometrically */
  if (need > ms->nt) { ms->nt = need > 2 * ms->nt ? need : 2 * ms->nt; ms->t = pys_alloc(ms->nt * 8); }
  return ms->t;
}
/* na <= nb: a goes to the buffer, merge from the left. The merges are compiled twice: into
   merge_at for keep 0, where KEEP makes no code (no cost without a try), and merge_keep */
static inline __attribute__((always_inline)) void merge_lo(MS *ms, I *a, I na, I *b, I nb, int keep) {
  I *d = a, *pa = memcpy(getmem(ms, na), a, na * 8), *pb = b, k, mg = ms->min_gallop;
  *d++ = *pb++;
  if (--nb == 0) goto done;
  if (na == 1) goto copyb;
  for (;;) {
    I ac = 0, bc = 0, w;                            /* times a and b won in a row */
    if (ms->kind == INT || ms->kind == FLOAT) do {  /* one item at a time: scalars by selects */
      w = LT(*pb, *pa); *d++ = w ? *pb : *pa;
      pb += w; nb -= w; pa += !w; na -= !w; bc = w ? bc + 1 : 0; ac = w ? 0 : ac + 1;
    } while (nb && na > 1 && ac < mg && bc < mg);   /* a step moves one side: all of CPython's exits */
    else for (;;) {                                 /* the others by branches */
      KEEP(d, pa, na);
      if (LT(*pb, *pa)) { *d++ = *pb++; bc++; ac = 0; if (--nb == 0 || bc >= mg) break; }
      else { *d++ = *pa++; ac++; bc = 0; if (--na == 1 || ac >= mg) break; }
    }
    if (!nb) goto done;
    if (na == 1) goto copyb;
    mg++;
    do {                                            /* galloping */
      mg -= mg > 1; ms->min_gallop = mg;
      KEEP(d, pa, na);
      ac = k = gallop(ms, *pb, pa, na, 0, 1);
      if (k) { memcpy(d, pa, k * 8); d += k; pa += k; na -= k; if (na == 1) goto copyb; if (!na) goto done; }
      *d++ = *pb++;
      if (--nb == 0) goto done;
      KEEP(d, pa, na);
      bc = k = gallop(ms, *pa, pb, nb, 0, 0);
      if (k) { memmove(d, pb, k * 8); d += k; pb += k; if ((nb -= k) == 0) goto done; }
      *d++ = *pa++;
      if (--na == 1) goto copyb;
    } while (ac >= MIN_GALLOP || bc >= MIN_GALLOP);
    ms->min_gallop = ++mg;                          /* penalize leaving galloping mode */
  }
done:
  if (na) memcpy(d, pa, na * 8);
  return;
copyb:                                              /* the last of a goes after the rest of b */
  memmove(d, pb, nb * 8); d[nb] = *pa;
}
/* na > nb: b goes to the buffer, merge from the right */
static inline __attribute__((always_inline)) void merge_hi(MS *ms, I *a, I na, I *b, I nb, int keep) {
  I *t = memcpy(getmem(ms, nb), b, nb * 8), *d = b + nb, *pa = b, *pb = t + nb, k, mg = ms->min_gallop;
  *--d = *--pa;                                     /* d, pa, pb: just past the next slot, a's and b's last */
  if (--na == 0) goto done;
  if (nb == 1) goto copya;
  for (;;) {
    I ac = 0, bc = 0, w;
    if (ms->kind == INT || ms->kind == FLOAT) do {
      w = LT(pb[-1], pa[-1]); *--d = w ? pa[-1] : pb[-1];
      pa -= w; na -= w; pb -= !w; nb -= !w; ac = w ? ac + 1 : 0; bc = w ? 0 : bc + 1;
    } while (na && nb > 1 && ac < mg && bc < mg);
    else for (;;) {
      KEEP(d - nb, t, nb);
      if (LT(pb[-1], pa[-1])) { *--d = *--pa; ac++; bc = 0; if (--na == 0 || ac >= mg) break; }
      else { *--d = *--pb; bc++; ac = 0; if (--nb == 1 || bc >= mg) break; }
    }
    if (!na) goto done;
    if (nb == 1) goto copya;
    mg++;
    do {
      mg -= mg > 1; ms->min_gallop = mg;
      KEEP(d - nb, t, nb);
      ac = k = na - gallop(ms, pb[-1], a, na, na - 1, 1);
      if (k) { d -= k; pa -= k; memmove(d, pa, k * 8); if ((na -= k) == 0) goto done; }
      *--d = *--pb;
      if (--nb == 1) goto copya;
      KEEP(d - nb, t, nb);
      bc = k = nb - gallop(ms, pa[-1], t, nb, nb - 1, 0);
      if (k) { d -= k; pb -= k; memcpy(d, pb, k * 8); nb -= k; if (nb == 1) goto copya; if (!nb) goto done; }
      *--d = *--pa;
      if (--na == 0) goto done;
    } while (ac >= MIN_GALLOP || bc >= MIN_GALLOP);
    ms->min_gallop = ++mg;
  }
done:
  if (nb) memcpy(d - nb, t, nb * 8);
  return;
copya:                                              /* the first of b goes before the rest of a */
  d -= na; pa -= na; memmove(d, pa, na * 8); d[-1] = pb[-1];
}
static __attribute__((noinline)) void merge_keep(MS *ms, I *a, I na, I *b, I nb) {
  if (na <= nb) merge_lo(ms, a, na, b, nb, 1); else merge_hi(ms, a, na, b, nb, 1);
}
static void merge_at(MS *ms, int i) {               /* merge pending runs i and i+1 */
  Run *p = ms->p;
  I *a = ms->a + p[i].s, na = p[i].n, *b = a + na, nb = p[i + 1].n, k;
  p[i].n = na + nb;
  if (i == ms->np - 3) p[i + 1] = p[i + 2];
  ms->np--;
  k = gallop(ms, *b, a, na, 0, 1);                  /* a[:k] and then b[nb:] are in place already */
  a += k;
  if (!(na -= k) || !(nb = gallop(ms, a[na - 1], b, nb, nb - 1, 0))) return;
  if (ms->u) { merge_keep(ms, a, na, b, nb); ms->u->fn = 0; }   /* every item is in the array again */
  else if (na <= nb) merge_lo(ms, a, na, b, nb, 0); else merge_hi(ms, a, na, b, nb, 0);
}
static void found_new_run(MS *ms, I n2) {           /* powersort: merge the runs below of greater power */
  if (!ms->np) return;
  Run *p = ms->p + ms->np - 1;
  I n = ms->n, a = 2 * p->s + p->n, b = a + p->n + n2;   /* powerloop: twice the two runs' midpoints */
  int power = 0;
  for (;; a <<= 1, b <<= 1) {                       /* the first bit where a/n and b/n differ */
    power++;
    if (a >= n) { a -= n; b -= n; } else if (b >= n) break;
  }
  while (ms->np > 1 && ms->p[ms->np - 2].power > power) merge_at(ms, ms->np - 2);
  ms->p[ms->np - 1].power = power;
}
static void sort_undo(void *p) {
  Undo *u = p;
  if (u->fn) memcpy(u->fd, u->fs, u->fn * 8);
  if (u->rev) rev(u->a, u->n);
  u->l->len = u->n; u->l->cap = u->cap; u->l->a = u->a;
}
void pys_list_sort_r(List *l, Str *d, I reverse) {
  I n = l->len, cap = l->cap, *a = l->a, m = n, r = 0, c = *d->s;
  MS ms = {.d = d->s, .kind = c == 'i' || c == 'b' ? INT : c == 'f' ? FLOAT : c == 's' ? STR : c == 'O' ? OBJ : 0,
           .cls = c == 'O' ? ocls(d->s + 1) : 0, .a = a, .n = n, .min_gallop = MIN_GALLOP};
  if (top && n > 1 && (ms.kind == OBJ || !ms.kind)) {   /* a comparison may raise into a try */
    Undo *u = ms.u = pys_alloc(sizeof(Undo));
    u->l = l; u->a = a; u->n = n; u->cap = cap; u->rev = reverse != 0;
    pys_unwind_push(sort_undo, u);
  }
  l->len = l->cap = 0; l->a = sorting;
  if (n > 1) {
    if (reverse) rev(a, n);                         /* reverse=True: reverse, sort stably, reverse back */
    while (m >= 64) { r |= m & 1; m >>= 1; }        /* merge_compute_minrun */
    m += r;
    for (I lo = 0, k; lo < n; lo += k) {
      k = count_run(&ms, a + lo, n - lo);
      if (k < m) { I f = n - lo < m ? n - lo : m; binarysort(&ms, a + lo, f, k); k = f; }   /* extend to minrun */
      found_new_run(&ms, k);
      ms.p[ms.np++] = (Run){lo, k, 0};
    }
    while (ms.np > 1) {                             /* merge_force_collapse */
      int i = ms.np - 2;
      if (i > 0 && ms.p[i - 1].n < ms.p[i + 1].n) i--;
      merge_at(&ms, i);
    }
    if (reverse) rev(a, n);
  }
  if (ms.u) pys_unwind_pop();
  int bad = l->a != sorting;                        /* items added meanwhile are dropped, as in CPython */
  l->len = n; l->cap = cap; l->a = a;
  if (bad) pys_fail("ValueError: list modified during sort");
}
void pys_list_sort(List *l, Str *d) { pys_list_sort_r(l, d, 0); }
I pys_list_minmax(List *l, Str *d, I max) {
  if (!l->len) pys_fail(max ? "ValueError: max() iterable argument is empty" : "ValueError: min() iterable argument is empty");
  I m = l->a[0];
  for (I i = 1; i < l->len; i++) if (opv(l->a[i], m, d->s, max ? 2 : 0)) m = l->a[i];   /* item > max / item < min */
  return m;
}
I pys_any(List *l) { for (I i = 0; i < l->len; i++) if (l->a[i]) return 1; return 0; }
I pys_all(List *l) { for (I i = 0; i < l->len; i++) if (!l->a[i]) return 0; return 1; }
I pys_sum_int(List *l, I s) { for (I i = 0; i < l->len; i++) if (__builtin_add_overflow(s, l->a[i], &s)) pys_fail(OVF); return s; }
static double fsum(List *l, I i, double s) {  /* CPython 3.12's compensated (Neumaier) sum of l[i:] */
  double c = 0;
  for (; i < l->len; i++) {
    double x = dbl(l->a[i]), t = s + x;
    if (fabs(s) >= fabs(x)) c += (s - t) + x; else c += (x - t) + s;
    s = t;
  }
  return c && isfinite(c) ? s + c : s;
}
double pys_sum_float(List *l, double s) { return fsum(l, 0, s); }
/* an int start: CPython adds the first float to it plainly, then sums the rest compensated */
double pys_sum_float_int(List *l, I s) { return l->len ? fsum(l, 1, (double)s + dbl(l->a[0])) : (double)s; }
double pys_sum_int_float(List *l, double s) { for (I i = 0; i < l->len; i++) s += (double)l->a[i]; return s; }   /* ints: not compensated */
I pys_range_len(I a, I b, I s) {                     /* len(range(a, b, s)) as an unsigned count */
  if (!s) pys_fail("ValueError: range() arg 3 must not be zero");
  uint64_t d = s > 0 ? (uint64_t)b - (uint64_t)a : (uint64_t)a - (uint64_t)b, st = s > 0 ? (uint64_t)s : -(uint64_t)s;
  return (s > 0 ? a < b : a > b) ? (I)((d - 1) / st + 1) : 0;
}
I pys_range_has(I x, I a, I b, I s) {               /* x in range(a, b, s) */
  if (!s) pys_fail("ValueError: range() arg 3 must not be zero");
  if (s > 0 ? !(a <= x && x < b) : !(b < x && x <= a)) return 0;
  return (s > 0 ? (uint64_t)x - (uint64_t)a : (uint64_t)a - (uint64_t)x) % (s > 0 ? (uint64_t)s : -(uint64_t)s) == 0;
}
List *pys_range_list(I a, I b, I s) {
  List *l = pys_list_new(0);
  if (!s) pys_fail("ValueError: range() arg 3 must not be zero");
  for (I i = a; s > 0 ? i < b : i > b;) { pys_list_append(l, i); if (__builtin_add_overflow(i, s, &i)) break; }
  return l;
}
List *pys_str_list(Str *s) { List *l = pys_list_new(s->len); for (I i = 0; i < s->len; i++) pys_list_append(l, (I)pys_chr((unsigned char)s->s[i])); return l; }
Str *pys_str_join(Str *sep, List *l) {
  I n = 0;
  for (I i = 0; i < l->len; i++) n += ((Str *)l->a[i])->len + (i ? sep->len : 0);
  Str *r = pys_alloc_atomic(sizeof(Str) + n + 1); char *w = r->s; r->len = n;
  for (I i = 0; i < l->len; i++) {
    Str *s = (Str *)l->a[i];
    if (i) { memcpy(w, sep->s, sep->len); w += sep->len; }
    memcpy(w, s->s, s->len); w += s->len;
  }
  return r;
}
List *pys_str_split(Str *s, Str *sep, I maxsplit) {   /* maxsplit < 0: no limit */
  List *l = pys_list_new(0); I i = 0, n = s->len;
  if (maxsplit < 0) maxsplit = INT64_MAX;     /* no limit: counting down from it cannot reach 0, or overflow */
  if (!sep) {
    for (;;) {
      while (i < n && ws(s->s[i])) i++;
      if (i >= n) return l;
      if (maxsplit-- == 0) { pys_list_append(l, (I)pys_str(s->s + i, n - i)); return l; }   /* the rest, as it is */
      I j = i; while (j < n && !ws(s->s[j])) j++;
      pys_list_append(l, (I)pys_str(s->s + i, j - i)); i = j;
    }
  }
  if (!sep->len) pys_fail("ValueError: empty separator");
  for (I j; maxsplit-- != 0 && (j = find(s, sep, i)) >= 0; i = j + sep->len) pys_list_append(l, (I)pys_str(s->s + i, j - i));
  pys_list_append(l, (I)pys_str(s->s + i, n - i));
  return l;
}
static I eol(Str *s, I i) {                    /* the length of the line break at i, 0 if none */
  unsigned char c = s->s[i], *p = (unsigned char *)s->s + i; I left = s->len - i;
  if (c == '\r') return left > 1 && p[1] == '\n' ? 2 : 1;
  if (c == '\n' || c == 11 || c == 12 || (c >= 28 && c <= 30)) return 1;
  if (c == 0xC2 && left > 1 && p[1] == 0x85) return 2;                          /* U+0085 */
  if (c == 0xE2 && left > 2 && p[1] == 0x80 && (p[2] == 0xA8 || p[2] == 0xA9)) return 3;  /* U+2028, U+2029 */
  return 0;
}
List *pys_str_splitlines(Str *s, I keep) {
  List *l = pys_list_new(0); I i = 0, st = 0;
  while (i < s->len) {
    I k = eol(s, i);
    if (!k) { i++; continue; }
    pys_list_append(l, (I)pys_str(s->s + st, i - st + (keep ? k : 0)));
    i += k; st = i;
  }
  if (st < s->len) pys_list_append(l, (I)pys_str(s->s + st, s->len - st));
  return l;
}
List *pys_str_rsplit(Str *s, Str *sep, I maxsplit) {  /* split from the right; the parts stay in order */
  List *l = pys_list_new(0); I j = s->len;
  if (maxsplit < 0) maxsplit = INT64_MAX;
  if (!sep) {
    for (;;) {
      while (j > 0 && ws(s->s[j - 1])) j--;
      if (j <= 0) break;
      if (maxsplit-- == 0) { pys_list_append(l, (I)pys_str(s->s, j)); break; }
      I i = j; while (i > 0 && !ws(s->s[i - 1])) i--;
      pys_list_append(l, (I)pys_str(s->s + i, j - i)); j = i;
    }
  } else {
    if (!sep->len) pys_fail("ValueError: empty separator");
    for (I i; maxsplit-- != 0 && (i = pys_str_rfind(s, sep, 0, j)) >= 0; j = i) pys_list_append(l, (I)pys_str(s->s + i + sep->len, j - i - sep->len));
    pys_list_append(l, (I)pys_str(s->s, j));
  }
  for (I a = 0, b = l->len - 1; a < b; a++, b--) { I t = l->a[a]; l->a[a] = l->a[b]; l->a[b] = t; }
  return l;
}

/* ---------- dicts: CPython's compact ordered layout ---------- */
/* Entries (keys, vals, hs) are kept in insertion order. A deleted entry stays in place as a
   hole with hash 0 until the table is rebuilt, so deletion is O(1) and a loop's position
   stays valid. idx is open addressing over 2*size slots holding entry + 1 (0 empty, -1
   deleted). The sizes are CPython 3.13's, because they decide what a loop that changes its
   dict sees: size is a power of two >= 8 (0 before the first insertion and after clear()),
   at most size*2/3 entries are used, and inserting into a full table rebuilds it without
   holes at the size for len*3. An int key's hash is one round of SplitMix64's mixer: the
   first shift folds the key's high bits into its low ones, the multiply spreads them up and
   the last shift brings the product's high bits down, so keys that differ only in their high
   bits (i << 46) get unrelated low bits, and distinct ints never share a hash (a bijection).
   A str key's hash is FNV-1a of its bytes with the high half folded into the low. A lookup
   in a table that fits in the cache takes a few ns, so each costs only one multiply (per
   byte for str). The probe sequence is CPython's: the first slot is the hash's low bits, and
   each step mixes five more of its bits in (perturb), so keys whose hashes share their low
   bits part after a few steps instead of piling up in one cluster. Unlike a linear probe's,
   its second slot is in another cache line, which tables larger than the cache pay for.
   tools/dictprobe.c counts the slots that lookups visit (DICT_PROBE). */
#ifndef DICT_PROBE
#define DICT_PROBE()
#endif
static uint64_t hsh(Dict *d, I k) {
  uint64_t h = (uint64_t)k;
  if (d->kind) {
    Str *s = (Str *)k; h = 1469598103934665603ULL;
    for (I i = 0; i < s->len; i++) h = (h ^ (unsigned char)s->s[i]) * 1099511628211ULL;
    h ^= h >> 29;
  } else {
    h = (h ^ h >> 30) * 0xBF58476D1CE4E5B9ULL;
    h ^= h >> 31;
  }
  return h ? h : 1;                                  /* 0 marks a hole */
}
static I keysize(I n) { I s = 8; while (s < n) s *= 2; return s; }   /* calculate_log2_keysize */
static I dfind(Dict *d, I k, uint64_t h, I *free) {    /* k's idx slot or -1; *free: where to insert k */
  I f = -1;
  if (!d->size) return -1;
  for (uint64_t m = d->size * 2 - 1, i = h & m, p = h;; p >>= 5, i = (i * 5 + p + 1) & m) {
    DICT_PROBE();
    int32_t e = d->idx[i];
    if (!e) { if (free) *free = f < 0 ? (I)i : f; return -1; }
    if (e < 0) { if (f < 0) f = i; }
    else if (d->hs[e - 1] == h && (d->keys[e - 1] == k || (d->kind && pys_str_eq((Str *)d->keys[e - 1], (Str *)k)))) return i;
  }
}
static void build(Dict *d, Dict *src, I size) {      /* d := src's items in a table of this size, holes dropped */
  I u = size * 2 / 3, *k = pys_alloc(u * 8), *v = pys_alloc(u * 8), n = 0, m = size * 2 - 1;
  uint64_t *hs = pys_alloc_atomic(u * 8); int32_t *ix = pys_alloc_atomic(size * 8);
  for (I e = 0; e < src->n; e++) {
    uint64_t h = src->hs[e], i = h & m, p = h;
    if (!h) continue;
    DICT_PROBE();
    while (ix[i]) { p >>= 5; i = (i * 5 + p + 1) & m; DICT_PROBE(); }
    k[n] = src->keys[e]; v[n] = src->vals[e]; hs[n] = h; ix[i] = (int32_t)++n;
  }
  d->len = n; d->n = n; d->size = size; d->keys = k; d->vals = v; d->hs = hs; d->idx = ix;
}
Dict *pys_dict_new(I kind, I n) {                     /* a display of n items is presized, as in CPython */
  Dict *d = pys_alloc(sizeof(Dict)); d->kind = kind;
  if (n > 5) build(d, d, n > 87381 ? 1 << 17 : keysize((n * 3 + 1) / 2));
  return d;
}
static _Noreturn void keyerr(Dict *d, I k) { Buf b = {0}; put(&b, "KeyError: ", 10); repr(&b, k, d->kind ? "s" : "i"); put(&b, "", 1); pys_fail(b.p); }
static I entry(Dict *d, I k) { I i = dfind(d, k, hsh(d, k), 0); return i < 0 ? -1 : d->idx[i] - 1; }
I pys_dict_has(Dict *d, I k) { return entry(d, k) >= 0; }
I pys_dict_getitem(Dict *d, I k) { I e = entry(d, k); if (e < 0) keyerr(d, k); return d->vals[e]; }
I pys_dict_get(Dict *d, I k, I dflt) { I e = entry(d, k); return e < 0 ? dflt : d->vals[e]; }
void pys_dict_set(Dict *d, I k, I v) {
  uint64_t h = hsh(d, k); I f = -1, i = dfind(d, k, h, &f);
  if (i >= 0) { d->vals[d->idx[i] - 1] = v; return; }
  if (d->n >= d->size * 2 / 3) { build(d, d, keysize(d->len * 3)); dfind(d, k, h, &f); }   /* full: insertion_resize */
  d->keys[d->n] = k; d->vals[d->n] = v; d->hs[d->n] = h; d->idx[f] = (int32_t)++d->n; d->len++;
}
static I dpop(Dict *d, I k, I dflt, int has) {
  I i = dfind(d, k, hsh(d, k), 0);
  if (i < 0) { if (!has) keyerr(d, k); return dflt; }
  I e = d->idx[i] - 1, v = d->vals[e];
  d->idx[i] = -1; d->hs[e] = 0; d->keys[e] = d->vals[e] = 0; d->len--;
  return v;
}
I pys_dict_pop(Dict *d, I k) { return dpop(d, k, 0, 0); }
I pys_dict_pop_default(Dict *d, I k, I dflt) { return dpop(d, k, dflt, 1); }
I pys_dict_setdefault(Dict *d, I k, I v) { I e = entry(d, k); if (e >= 0) return d->vals[e]; pys_dict_set(d, k, v); return v; }
void pys_dict_clear(Dict *d) { d->len = d->n = d->size = 0; d->keys = d->vals = 0; d->hs = 0; d->idx = 0; }
/* for loops: entry e's key and value; the next entry from e (reversed: the previous one), or
   -1 at the end, failing like CPython's dict iterators when the dict changed meanwhile:
   used = len when the loop started, count = items produced so far. As in CPython 3.13.16, a
   reversed loop also ends at a position past the entries (a rebuild made the table smaller) */
I pys_dict_key(Dict *d, I e) { return d->keys[e]; }
I pys_dict_val(Dict *d, I e) { return d->vals[e]; }
I pys_dict_end(Dict *d) { return d->n; }
static void changed(Dict *d, I used) { if (d->len != used) pys_fail("RuntimeError: dictionary changed size during iteration"); }
I pys_dict_next(Dict *d, I e, I used, I count) {
  changed(d, used);
  while (e < d->n && !d->hs[e]) e++;
  if (e >= d->n) return -1;
  if (count >= used) pys_fail("RuntimeError: dictionary keys changed during iteration");
  return e;
}
I pys_dict_prev(Dict *d, I e, I used, I count) {
  changed(d, used);
  if (e < 0 || e >= d->n) return -1;
  while (e >= 0 && !d->hs[e]) e--;
  if (e >= 0 && count >= used) pys_fail("RuntimeError: dictionary keys changed during iteration");
  return e;
}
static List *col(Dict *d, I *a) { List *l = pys_list_new(d->len); for (I e = 0; e < d->n; e++) if (d->hs[e]) l->a[l->len++] = a[e]; return l; }
List *pys_dict_keys(Dict *d) { return col(d, d->keys); }
List *pys_dict_values(Dict *d) { return col(d, d->vals); }
List *pys_dict_items(Dict *d) {
  List *l = pys_list_new(d->len);
  for (I e = 0; e < d->n; e++) if (d->hs[e]) { I *t = pys_alloc(16); t[0] = d->keys[e]; t[1] = d->vals[e]; l->a[l->len++] = (I)t; }
  return l;
}
/* copies, as CPython 3.13 makes them, since their tables decide what a loop that changes the copy
   sees: dict(d) merges d into a new empty dict, which clones a table without holes that is not
   sparse (8 slots, or more items than USABLE_FRACTION(size / 2)) and otherwise inserts the items
   into a table sized for them (estimate_log2_keysize); dict.copy() clones a table with at most a
   third of holes, and otherwise merges the same way */
static Dict *clone(Dict *d) {                         /* the same table, holes included */
  Dict *r = pys_dict_new(d->kind, 0); I u = d->size * 2 / 3;
  r->keys = pys_alloc(u * 8); r->vals = pys_alloc(u * 8); r->hs = pys_alloc_atomic(u * 8); r->idx = pys_alloc_atomic(d->size * 8);
  memcpy(r->keys, d->keys, d->n * 8); memcpy(r->vals, d->vals, d->n * 8); memcpy(r->hs, d->hs, d->n * 8);
  memcpy(r->idx, d->idx, d->size * 8); r->len = d->len; r->n = d->n; r->size = d->size;
  return r;
}
Dict *pys_dict_from(Dict *d) {
  if (d->len && d->len == d->n && (d->size == 8 || d->size / 2 * 2 / 3 < d->len)) return clone(d);
  Dict *r = pys_dict_new(d->kind, 0);
  if (d->len) build(r, d, keysize((d->len * 3 + 1) / 2));
  return r;
}
Dict *pys_dict_copy(Dict *d) { return d->len && d->len >= d->n * 2 / 3 ? clone(d) : pys_dict_from(d); }

/* ---------- formatting: f"{x:spec}" ---------- */
/* CPython's format-spec mini-language for int (and bool), float and str:
   [[fill]align][sign][z][#][0][width][grouping][.precision][type]. Widths count code points;
   other types accept only an empty spec, which the compiler turns into str(). */
static _Noreturn void failf(const char *f, ...) {
  char b[512]; va_list a; va_start(a, f); vsnprintf(b, sizeof b, f, a); va_end(a); pys_fail(b);
}
static I uoff(const char *p, I n, I k) {          /* byte offset of code point k */
  I i = 0;
  for (; i < n && k > 0; k--) { i++; while (i < n && ((unsigned char)p[i] & 0xC0) == 0x80) i++; }
  return i;
}
static I u8enc(char *o, I c) {
  if (c < 0x80) { o[0] = c; return 1; }
  if (c < 0x800) { o[0] = 0xC0 | c >> 6; o[1] = 0x80 | (c & 63); return 2; }
  if (c < 0x10000) { o[0] = 0xE0 | c >> 12; o[1] = 0x80 | (c >> 6 & 63); o[2] = 0x80 | (c & 63); return 3; }
  o[0] = 0xF0 | c >> 18; o[1] = 0x80 | (c >> 12 & 63); o[2] = 0x80 | (c >> 6 & 63); o[3] = 0x80 | (c & 63); return 4;
}
static const char *tyname(char d) {
  return d == 'i' ? "int" : d == 'b' ? "bool" : d == 'f' ? "float" : d == 's' ? "str" : d == 'L' ? "list" : d == 'D' ? "dict" : d == 'T' ? "tuple" : "object";
}
static void group(Buf *o, const char *dg, I n, char sep, int every, I minw) {   /* digits with separators */
  I z = 0, len = n + (sep ? (n - 1) / every : 0);
  while (len < minw) { z++; len = n + z + (sep ? (n + z - 1) / every : 0); }   /* zero padding is grouped too */
  for (I i = 0; i < n + z; i++) {
    char c = i < z ? '0' : dg[i - z];
    put(o, &c, 1);
    if (sep && (n + z - i - 1) % every == 0 && i < n + z - 1) put(o, &sep, 1);
  }
}
Str *pys_format(I v, Str *desc, Str *spec) {
  const char *p = spec->s, *end = spec->s + spec->len, *fill = " ";
  char d = desc->s[0], align = 0, sign = 0, type = 0, sep = 0;
  int alt = 0, zneg = 0, fillset = 0;
  I fl = 1, width = 0, prec = -1;
  if ((d != 'i' && d != 'b' && d != 'f' && d != 's') || (d == 'b' && !spec->len)) {   /* format(True, "") is str(True) */
    if (spec->len) failf("TypeError: unsupported format string passed to %s.__format__", tyname(d));
    return pys_repr(v, desc);
  }
  I cl = p < end ? uoff(p, end - p, 1) : 0;
  if (cl && p + cl < end && p[cl] && strchr("<>=^", p[cl])) { fill = p; fl = cl; fillset = 1; align = p[cl]; p += cl + 1; }
  else if (p < end && *p && strchr("<>=^", *p)) align = *p++;
  if (p < end && (*p == '+' || *p == '-' || *p == ' ')) sign = *p++;
  if (p < end && *p == 'z') { zneg = 1; p++; }
  if (p < end && *p == '#') { alt = 1; p++; }
  int numeric = d != 's';
  if (p < end && *p == '0') {                  /* zero padding: fill '0', and '=' alignment for numbers */
    if (!fillset) { fill = "0"; fl = 1; if (!align && numeric) align = '='; }
    p++;
  }
  while (p < end && *p >= '0' && *p <= '9') { width = width * 10 + *p++ - '0'; if (width > 100000000) failf("ValueError: Too many decimal digits in format string"); }
  if (p < end && (*p == ',' || *p == '_')) { sep = *p++; if (p < end && (*p == ',' || *p == '_')) failf("ValueError: Cannot specify both ',' and '_'."); }
  if (p < end && *p == '.') {
    p++;
    if (p >= end || *p < '0' || *p > '9') failf("ValueError: Format specifier missing precision");
    prec = 0;
    while (p < end && *p >= '0' && *p <= '9') { prec = prec * 10 + *p++ - '0'; if (prec > 100000000) failf("ValueError: Too many decimal digits in format string"); }
  }
  if (end - p > 1) failf("ValueError: Invalid format specifier '%s' for object of type '%s'", spec->s, tyname(d));
  if (p < end) type = *p;
  if (!type && d == 's') type = 's';
  if (!type && d != 'f') type = 'd';
  if (sep && !strchr("defgEFG%", type)) {
    if (sep == '_' && strchr("boxX", type) && type) {} else failf("ValueError: Cannot specify '%c' with '%c'.", sep, type);
  }
  Buf o = {0}; char tb[1100];
  I pre = 0;                                   /* bytes of sign and prefix, before '=' padding */
  if (d == 's') {
    if (type != 's') failf("ValueError: Unknown format code '%c' for object of type 'str'", type);
    if (sign) failf(sign == ' ' ? "ValueError: Space not allowed in string format specifier" : "ValueError: Sign not allowed in string format specifier");
    if (zneg) failf("ValueError: Negative zero coercion (z) not allowed in string format specifier");
    if (alt) failf("ValueError: Alternate form (#) not allowed in string format specifier");
    if (align == '=') failf("ValueError: '=' alignment not allowed in string format specifier");
    Str *x = (Str *)v;
    put(&o, x->s, prec >= 0 ? uoff(x->s, x->len, prec) : x->len);
  } else if ((d == 'i' || d == 'b') && strchr("bcdoxXn", type) && type) {
    if (prec >= 0) failf("ValueError: Precision not allowed in integer format specifier");
    if (zneg) failf("ValueError: Negative zero coercion (z) not allowed in integer format specifier");
    if (type == 'c') {
      if (sign) failf("ValueError: Sign not allowed with integer format specifier 'c'");
      if (alt) failf("ValueError: Alternate form (#) not allowed with integer format specifier 'c'");
      if (v < 0 || v > 0x10FFFF) failf("OverflowError: %%c arg not in range(0x110000)");
      put(&o, tb, u8enc(tb, v));
    } else {
      uint64_t u = v < 0 ? 0 - (uint64_t)v : (uint64_t)v; int base = type == 'b' ? 2 : type == 'o' ? 8 : type == 'x' || type == 'X' ? 16 : 10;
      const char *dig = type == 'X' ? "0123456789ABCDEF" : "0123456789abcdef"; char r[70]; I n = 0;
      do { r[n++] = dig[u % base]; u /= base; } while (u);
      for (I i = 0; i < n / 2; i++) { char c = r[i]; r[i] = r[n - 1 - i]; r[n - 1 - i] = c; }
      if (v < 0) put(&o, "-", 1); else if (sign == '+' || sign == ' ') put(&o, &sign, 1);
      if (alt && base != 10) { char pf[2] = {'0', type == 'X' ? 'X' : type == 'x' ? 'x' : type}; put(&o, pf, 2); }
      pre = o.n;
      I minw = fl == 1 && *fill == '0' && align == '=' ? width - pre : 0;
      group(&o, r, n, sep, base == 10 ? 3 : 4, minw);
    }
  } else {                                     /* float, or int with a float type */
    double x = d == 'f' ? dbl(v) : (double)v;
    if (type && !strchr("eEfFgGn%", type)) failf("ValueError: Unknown format code '%c' for object of type '%s'", type, tyname(d));
    int neg = signbit(x) && !isnan(x), up = type && strchr("EFG", type);
    double m = fabs(x);
    I tsz = (prec > 0 ? prec : 0) + 400; char *t = tsz > (I)sizeof tb ? pys_alloc_atomic(tsz) : tb; I n;
    if (isnan(m) || isinf(m)) n = snprintf(t, tsz, "%s%s", isnan(m) ? (up ? "NAN" : "nan") : (up ? "INF" : "inf"), type == '%' ? "%" : "");
    else if (!type && prec < 0) {
      Str *r = pys_str_float(m); n = r->len; memcpy(t, r->s, n + 1);
      char *e = strchr(t, 'e');                 /* '#': a point even in 1e+16 */
      if (alt && e && !memchr(t, '.', e - t)) { memmove(e + 1, e, n - (e - t) + 1); *e = '.'; n++; }
    }
    else if (!type) {                          /* like 'g', but the exponent starts at p-1 and a ".0" stays */
      int pr = prec ? (int)prec : 1;
      snprintf(t, tsz, "%.*e", pr - 1, m);
      int X = atoi(strchr(t, 'e') + 1), ex = X < -4 || X >= pr - 1;
      n = ex ? snprintf(t, tsz, alt ? "%#.*e" : "%.*e", pr - 1, m) : snprintf(t, tsz, alt ? "%#.*f" : "%.*f", pr - 1 - X, m);
      if (!alt) {                              /* drop the mantissa's trailing zeros, as 'g' does */
        char *e = strchr(t, 'e'); I me = e ? e - t : n;
        if (memchr(t, '.', me)) { I k = me; while (t[k - 1] == '0') k--; if (t[k - 1] == '.') k--; memmove(t + k, t + me, n - me + 1); n -= me - k; }
      }
      if (!ex && !memchr(t, '.', n)) { t[n++] = '.'; t[n++] = '0'; t[n] = 0; }
    } else if (alt && (type == 'g' || type == 'G' || type == 'n')) {
      /* glibc's %#g drops the zeros when rounding carries into the exponent (1.e+06): choose
         the notation from the rounded exponent, as CPython does, and keep every digit */
      int pr = prec < 0 ? 6 : prec ? (int)prec : 1;
      snprintf(t, tsz, "%.*e", pr - 1, m);
      int X = atoi(strchr(t, 'e') + 1);
      n = X < -4 || X >= pr ? snprintf(t, tsz, type == 'G' ? "%#.*E" : "%#.*e", pr - 1, m) : snprintf(t, tsz, "%#.*f", pr - 1 - X, m);
    } else {
      char c = type == 'n' ? 'g' : type == '%' ? 'f' : type, f[16]; int pr = prec < 0 ? 6 : (int)prec;
      snprintf(f, 16, alt ? "%%#.%d%c" : "%%.%d%c", pr, c);
      n = snprintf(t, tsz, f, type == '%' ? m * 100 : m);
      if (type == '%') { t[n++] = '%'; t[n] = 0; }
    }
    if (zneg && neg && !isinf(m) && strtod(t, 0) == 0) neg = 0;   /* z: no "-0" after rounding */
    if (neg) put(&o, "-", 1); else if (sign == '+' || sign == ' ') put(&o, &sign, 1);
    pre = o.n;
    I ip = 0; while (ip < n && t[ip] >= '0' && t[ip] <= '9') ip++;   /* the integer digits */
    I minw = fl == 1 && *fill == '0' && align == '=' ? width - pre - (n - ip) : 0;
    if (ip) group(&o, t, ip, sep, 3, minw); else for (I i = 0; i < minw; i++) put(&o, "0", 1);
    put(&o, t + ip, n - ip);
  }
  if (!align) align = numeric ? '>' : '<';
  const char *body = o.p ? o.p : "";          /* an empty body leaves o.p NULL */
  I len = ulen(body, o.n);
  if (len >= width) return pys_str(body, o.n);
  I gap = width - len, left = align == '<' ? 0 : align == '^' ? gap / 2 : align == '=' ? 0 : gap;
  Buf r = {0};
  if (align == '=') put(&r, body, pre);
  for (I i = 0; i < (align == '=' ? gap : left); i++) put(&r, fill, fl);
  put(&r, body + (align == '=' ? pre : 0), o.n - (align == '=' ? pre : 0));
  for (I i = 0; i < (align == '=' ? 0 : gap - left); i++) put(&r, fill, fl);
  return pys_str(r.p, r.n);
}

/* ---------- I/O and process ---------- */
/* Text files as CPython's open() makes them, over C stdio: its argument checks in its order,
   newline translation, and positions when a "+" file switches between reading and writing.
   Writes reach the OS when CPython's do: its TextIOWrapper keeps written text pending until
   8 KiB have gathered (or a write of 8 KiB or more comes), then hands it to a BufferedWriter
   of st_blksize bytes (buffering=, when above 1), which keeps a piece that fits below its
   size and writes anything bigger at once; buffering=1, and a terminal, flush every write that
   holds "\n" or "\r". Here the pending text has a buffer of its own and C stdio's buffer is
   the BufferedWriter's. sys.stdout is such a file too, unless it is a terminal, which keeps C
   stdio's line buffering. A file that becomes unreachable is closed by the collector (CPython
   closes it when its last reference goes), the compiler closes a file used in one expression,
   open(p).read(), right after that use, and the files still open at exit are closed in the
   order they were opened; when such an implicit close fails, the error is reported as
   CPython's finalizer reports it and the program goes on. sys.stdin, sys.stdout and
   sys.stderr are files too. */
typedef struct {
  FILE *f; Str *name, *mode, *enc;   /* enc: encoding= as given, NULL when not given */
  I rd, wr, closed, nl, last, std;   /* nl: newline None 0, "" 1, "\n" 2, "\r" 3, "\r\n" 4; last: 1 wrote, 2 read */
  I rstart, rcons;                   /* where the current run of reads began; raw bytes it consumed */
  I lat, emu, lb, pn, bn, bs, kept;  /* Latin-1; CPython's write layers emulated: line buffered, bytes pending
                                        (in pb) and buffered (in stdio's buffer, of bs bytes); errno of a failed
                                        write whose data CPython keeps (so writing it again fails again) */
  char *pb, *buf; dev_t dev; ino_t ino;   /* the two buffers (malloc'd); the file that was opened */
} File;
static File std_in, std_out, std_err;
static File **files;                   /* the open files, malloc'd: the collector does not see them */
static I cfiles;
static const char *errcls(int e) {     /* CPython's OSError subclass for an errno */
  return e == ENOENT ? "FileNotFoundError" : e == EEXIST ? "FileExistsError" : e == EISDIR ? "IsADirectoryError" :
    e == ENOTDIR ? "NotADirectoryError" : e == EACCES || e == EPERM ? "PermissionError" : e == EINTR ? "InterruptedError" :
    e == EPIPE ? "BrokenPipeError" : e == ECONNRESET ? "ConnectionResetError" : "OSError";
}
static _Noreturn void ioerr(int e) {   /* a failed write, flush or close raises, as in CPython */
  char b[160]; snprintf(b, sizeof b, "%s: [Errno %d] %s", errcls(e), e, strerror(e)); pys_fail(b);
}

/* Ctrl-C. CPython's handler only notes the signal; KeyboardInterrupt is raised between two
   bytecodes, and the program ends as for an uncaught exception, then by SIGINT. Here the handler
   ends the program at once (stdout and the open files flushed, KeyboardInterrupt printed), which
   is safe while no stdio call runs: no FILE is locked or half updated, and nothing allocates. If
   the I/O layer is inside one (io_busy), the handler only notes the signal and returns; without
   SA_RESTART a blocked read or write then returns early, and the layer ends the program through
   the ordinary KeyboardInterrupt exit when it leaves (io_out). */
static volatile sig_atomic_t io_busy;
static int sigint_on;
static void io_in(void) { io_busy++; atomic_signal_fence(memory_order_seq_cst); }
static void io_out(void) { atomic_signal_fence(memory_order_seq_cst); if (!--io_busy && io_intr) kbint_exit(); }
static void drain(File *f) { if (f->pn) fwrite(f->pb, 1, f->pn, f->f); fflush(f->f); }   /* all it holds, errors aside */
static void on_sigint(int s) {
  if (io_busy) { io_intr = 1; return; }
  static const char k[] = "KeyboardInterrupt\n";
  sigset_t m; sigemptyset(&m); sigaddset(&m, s);
  signal(s, SIG_DFL); sigprocmask(SIG_UNBLOCK, &m, 0);   /* another Ctrl-C kills at once */
  if (!std_out.closed) drain(&std_out);
  if (write(2, k, sizeof k - 1) < 0) {}
  for (I i = 0; i < nfiles; i++) if (files[i]->wr && !files[i]->closed) drain(files[i]);
  raise(s); _exit(130);
}
static void leaving(void) { if (sigint_on) signal(SIGINT, SIG_DFL); sigint_on = 0; }
static _Noreturn void die_sigint(void) {   /* CPython's exit_sigint: killed by SIGINT, or status 130 if it is blocked */
  signal(SIGINT, SIG_DFL); raise(SIGINT); exit(130);
}

/* the write layers (see above): pn bytes pending in the text layer, bn in the buffered layer */
static int osflush(File *f, int keep) {   /* stdio writes what it holds: 0, or the errno of a failure; stdio then
                                             drops the data, which CPython keeps when keep */
  if (!fflush(f->f) && !ferror(f->f)) return 0;
  int e = errno ? errno : EIO;
  __fpurge(f->f); clearerr(f->f);
  if (keep && !f->kept) f->kept = e;
  return e;
}
static int bput(File *f, const char *a, I na, const char *b, I nb) {   /* BufferedWriter.write() of a then b */
  I p = na + nb; int e;
  if (p <= f->bs - f->bn && p < f->bs) { fwrite(a, 1, na, f->f); fwrite(b, 1, nb, f->f); f->bn += p; return 0; }
  if (f->bn && (e = osflush(f, 1))) return e;   /* what it holds is written first (and kept if that fails), */
  fwrite(a, 1, na, f->f); fwrite(b, 1, nb, f->f);
  f->bn = p < f->bs ? p : 0;                   /* then a piece below its size is kept, a bigger one written */
  return f->bn ? 0 : osflush(f, 0);
}
static int tflush(File *f) {           /* TextIOWrapper.flush(): the pending text, then the buffered layer */
  I n = f->pn; int e;
  f->pn = 0;
  if ((e = bput(f, f->pb, n, "", 0)) || !f->bn) return e;
  f->bn = 0;
  return osflush(f, 1);
}
static int wput(File *f, const char *s, I n) {   /* TextIOWrapper.write() of n bytes: 0 or an errno */
  int e, lf = f->lb && (memchr(s, '\n', n) || memchr(s, '\r', n));
  I k = f->pn;
  if (k + n < 8192 && !lf) { memcpy(f->pb + k, s, n); f->pn += n; return 0; }
  f->pn = 0;                           /* 8 KiB pending, or a line: all of it goes on; a write */
  if (n >= 8192 && k && (e = bput(f, f->pb, k, "", 0))) return e;   /* of 8 KiB goes after the rest */
  if ((e = n >= 8192 && k ? bput(f, s, n, "", 0) : bput(f, f->pb, k, s, n)) || !lf || !f->bn) return e;
  f->bn = 0;
  return osflush(f, 1);
}
static int flush1(File *f) {           /* flush(): 0 or an errno */
  if (f->kept) { __fpurge(f->f); f->pn = f->bn = 0; return f->kept; }   /* CPython writes the kept data first, which fails again */
  return f->emu ? tflush(f) : osflush(f, 0);
}
static int shut(File *f) {             /* close(): a flush, then the file is closed even if it failed; 0 or an errno */
  int e = flush1(f);
  f->closed = 1; f->kept = 0;
  if (f->std) return e;                /* sys.stdout.close(): the stream stays open underneath */
  if (fclose(f->f) && !e) e = errno;
  free(f->pb); f->pb = f->buf = 0;
  return e;
}

/* an implicit close that failed: CPython's finalizer reports it and the program goes on */
static const char *defenc(void) {      /* the encoding CPython names for a file opened without encoding=: "utf-8" in
                                          its UTF-8 mode, which the C and POSIX locales turn on, else the locale's */
  static char e[40];
  if (!*e) {
    const char *l = setlocale(LC_CTYPE, "");
    snprintf(e, sizeof e, "%s", l && strcmp(l, "C") && strcmp(l, "POSIX") ? nl_langinfo(CODESET) : "utf-8");
    setlocale(LC_CTYPE, "C");
  }
  return e;
}
typedef struct { char b[256]; I n; } EBuf;   /* stderr text gathered on the stack: a report may come from inside a
                                                collection, where nothing may be allocated */
static void eput(EBuf *o, const char *s, I n) {
  for (I k; n > 0; s += k, n -= k) {
    if (o->n == (I)sizeof o->b) { fwrite(o->b, 1, o->n, stderr); o->n = 0; }
    k = (I)sizeof o->b - o->n < n ? (I)sizeof o->b - o->n : n;
    memcpy(o->b + o->n, s, k); o->n += k;
  }
}
static void erepr(EBuf *o, const char *k, const char *s, I n) {   /* k, then repr() of the string s[0, n) */
  char q = rquote(s, n), t[12];
  eput(o, k, strlen(k)); eput(o, &q, 1);
  for (I i = 0, m; i < n; i += m) eput(o, t, resc(t, s + i, n - i, q, &m));
  eput(o, &q, 1);
}
static void report(File *f, int e) {
  if (io_intr) return;                 /* the error is the EINTR of a Ctrl-C, which ends the program */
  EBuf o; char t[160]; const char *d = defenc();
  o.n = 0;
  erepr(&o, "Exception ignored in: <_io.TextIOWrapper name=", f->name->s, f->name->len);
  erepr(&o, " mode=", f->mode->s, f->mode->len);
  erepr(&o, " encoding=", f->enc ? f->enc->s : d, f->enc ? f->enc->len : (I)strlen(d));
  int n = snprintf(t, sizeof t, ">\n%s: [Errno %d] %s\n", errcls(e), e, strerror(e));
  eput(&o, t, n < (int)sizeof t ? n : (int)sizeof t - 1);
  fwrite(o.b, 1, o.n, stderr);
}

static void out_flush(void) {          /* CPython's flush_io() when the program's code ends, before any traceback:
                                          a failure is ignored, and fails again at exit if CPython kept the data */
  leaving();
  if (!std_out.closed) flush1(&std_out);
}
static _Noreturn void kbint_exit(void) {   /* a Ctrl-C noted during a stdio call: an uncaught KeyboardInterrupt */
  io_intr = 0;
  clearerr(stdout);                    /* the call it cut short failed with EINTR */
  for (I i = 0; i < nfiles; i++) if (!files[i]->closed) clearerr(files[i]->f);
  out_flush(); fputs("KeyboardInterrupt\n", stderr);
  kbint = 1; pys_finish(); exit(130);
}
void pys_finish(void) {                /* at exit, what CPython's shows of its end: stdout flushed after the code (see
                                          out_flush), the collector's report, stdout flushed in finalization (a
                                          failure is reported, status 120), the open files closed in the order they
                                          were opened (a failure is reported), and an uncaught KeyboardInterrupt's
                                          end by SIGINT */
  static int done;
  if (done++) return;
  out_flush();
  if (gc_stats) gc_report();
  int bad = 0, e;
  if (!std_out.closed && (e = flush1(&std_out))) {
    fprintf(stderr, "Exception ignored on flushing sys.stdout:\n%s: [Errno %d] %s\n", errcls(e), e, strerror(e));
    bad = 1;
  }
  for (I i = 0; i < nfiles; i++) if (!files[i]->closed && (e = shut(files[i]))) report(files[i], e);
  nfiles = 0;
  if (kbint) die_sigint();
  if (bad) { fflush(NULL); _exit(120); }
}
static int gc_marked(const void *p) {
  uintptr_t w = (uintptr_t)p; Seg **m, *s;
  if (w - gc_lo >= gc_hi - gc_lo || !(m = pmap[w >> 30]) || !(s = m[w >> 12 & 0x3ffff])) return 1;
  I i = s->large ? 0 : (I)((w - (uintptr_t)s->start) * s->inv >> 40);
  return s->mark[i >> 6] >> (i & 63) & 1;
}
static void files_sweep(void) {        /* after marking: close the open files nothing refers to */
  I j = 0;
  io_in();
  for (I i = 0; i < nfiles; i++) {
    File *f = files[i]; int e;
    if (f->closed) continue;
    if (!gc_marked(f)) { if ((e = shut(f))) report(f, e); continue; }
    files[j++] = f;
  }
  nfiles = j;
  io_out();
}
static _Noreturn void oserr(const char *path);
static _Noreturn void closed_err(void) { pys_fail("ValueError: I/O operation on closed file."); }
static void put1(File *f, const char *s, I n) {   /* write(): through CPython's layers, or C stdio's (stderr, a terminal) */
  if (f->closed) closed_err();
  int e = f->emu ? wput(f, s, n) : (fwrite(s, 1, n, f->f), ferror(f->f) ? osflush(f, 0) : 0);
  if (e) ioerr(e);
}
static void setbuf1(File *f, I bs) {   /* CPython's write layers: 8 KiB of pending text, then bs bytes buffered */
  if (!(f->pb = malloc(8192 + bs))) oom();
  f->buf = f->pb + 8192; f->bs = bs; f->emu = 1;
  setvbuf(f->f, f->buf, _IOFBF, bs);
}
__attribute__((minsize)) void pys_init(int argc, char **argv, char *sb, I **roots, I nroots) {   /* first call of @main */
  gc_init(sb, roots, nroots);
  args = pys_list_new(argc); for (int i = 0; i < argc; i++) pys_list_append(args, (I)cstr(argv[i]));
  char *a0 = getenv("PYSTACHY_ARGV0");  /* pystachy run: sys.argv[0] is the script, as in CPython */
  if (a0 && argc) { args->a[0] = (I)cstr(a0); unsetenv("PYSTACHY_ARGV0"); }
  std_in.f = stdin; std_in.rd = 1; std_in.nl = 2; std_in.std = 1;   /* CPython's stdin: newline="\n" */
  std_out.f = stdout; std_out.wr = 1; std_out.std = 1;
  std_err.f = stderr; std_err.wr = 1; std_err.std = 1;
  struct stat st;
  if (!isatty(1) && !fstat(1, &st)) setbuf1(&std_out, st.st_blksize > 1 ? st.st_blksize : 8192);
  signal(SIGPIPE, SIG_IGN);            /* as CPython: a closed pipe is an error, not a signal */
  struct sigaction sa;                 /* and Ctrl-C is KeyboardInterrupt, unless SIGINT is ignored */
  if (!sigaction(SIGINT, 0, &sa) && sa.sa_handler != SIG_IGN) {
    memset(&sa, 0, sizeof sa); sa.sa_handler = on_sigint; sigemptyset(&sa.sa_mask);
    sigint_on = !sigaction(SIGINT, &sa, 0);
  }
}
List *pys_argv(void) { return args; }
File *pys_std(I i) { return i == 0 ? &std_in : i == 1 ? &std_out : &std_err; }
void pys_write(Str *s, I fd) { io_in(); put1(fd == 2 ? &std_err : &std_out, s->s, s->len); io_out(); }
void pys_file_flush(File *f);
void pys_flush(void) { pys_file_flush(&std_out); }
Str *pys_input(Str *prompt) {          /* CPython: the prompt, if given, is written to sys.stdout, which is then
                                          flushed (a failure is ignored); then a line from sys.stdin */
  char *line = 0; size_t cap = 0;
  io_in();
  if (prompt) put1(&std_out, prompt->s, prompt->len);
  if (!std_out.closed && !std_out.kept) flush1(&std_out);
  if (std_in.closed) closed_err();
  if (feof(stdin)) clearerr(stdin);    /* CPython reads again after the end (a terminal goes on after Ctrl-D) */
  ssize_t n = getline(&line, &cap, stdin);
  io_out();
  if (n < 0) { free(line); pys_fail("EOFError: EOF when reading a line"); }
  if (n && line[n - 1] == '\n') n--;
  Str *s = pys_str(line, n); free(line); return s;
}
static int nul(Str *s) { return memchr(s->s, 0, s->len) != 0; }
static int codec(Str *e) {             /* encoding= as CPython's codec lookup finds it: 1 UTF-8, 2 Latin-1, 0 another.
                                          The name is normalized (lowercase; a run of characters other than ASCII
                                          letters, digits and "." is one "_" between them), then it must be an alias,
                                          or one with "." read as "_", or the codec's module name */
  static const char *alias[2] = {" utf8 u8 utf utf8_ucs2 utf8_ucs4 cp65001 ",
    " latin1 latin l1 iso8859_1 iso_8859_1 iso_8859_1_1987 iso_ir_100 iso8859 8859 cp819 ibm819 csisolatin1 "},
    *module[2] = {" utf_8 ", " latin_1 "};
  char b[48] = " "; int n = 1, punct = 0, dot = 0;
  for (I i = 0; i < e->len; i++) {
    unsigned char c = e->s[i];
    if (!isalnum(c) && c != '.') { punct = 1; continue; }
    if (n > 40) return 0;
    if (punct && n > 1) b[n++] = '_';
    punct = 0; dot |= c == '.'; b[n++] = (char)tolower(c);
  }
  b[n++] = ' '; b[n] = 0;
  if (dot) for (char *p = b; *p; p++) if (*p == '.') *p = '_';
  for (int k = 0; k < 2; k++) if (strstr(alias[k], b) || (!dot && !strcmp(b, module[k]))) return k + 1;
  return 0;
}
File *pys_open(Str *path, Str *mode, Str *enc, Str *nl, I buffering) {   /* CPython's checks, in its order */
  int x = 0, r = 0, w = 0, a = 0, plus = 0, t = 0, b = 0, lat = 1;
  if (nul(mode) || (enc && nul(enc)) || (nl && nul(nl))) pys_fail("ValueError: embedded null character");
  for (I i = 0; i < mode->len; i++) {
    char c = mode->s[i];
    int *p = c == 'x' ? &x : c == 'r' ? &r : c == 'w' ? &w : c == 'a' ? &a : c == '+' ? &plus : c == 't' ? &t : c == 'b' ? &b : 0;
    if (!p || *p) failf("ValueError: invalid mode: '%s'", mode->s);
    *p = 1;
  }
  if (t && b) pys_fail("ValueError: can't have text and binary mode at once");
  if (x + r + w + a > 1) pys_fail("ValueError: must have exactly one of create/read/write/append mode");
  if (b) pys_fail("NotImplementedError: binary mode is not supported (no bytes type)");
  if (nul(path)) pys_fail("ValueError: embedded null byte");
  if (!(x + r + w + a)) pys_fail("ValueError: Must have exactly one of create/read/write/append mode and at most one plus");
  io_in();
  struct stat st;
  if (nfiles && !gc_off && !stat(path->s, &st))   /* a writer to this file that nothing refers to any more has */
    for (I i = 0; i < nfiles; i++)               /* been closed by CPython: a collection closes it first */
      if (files[i]->wr && !files[i]->closed && files[i]->dev == st.st_dev && files[i]->ino == st.st_ino) { collect(); break; }
  char m[4] = {x || w ? 'w' : r ? 'r' : 'a', plus ? '+' : 0, 0, 0};
  if (x) m[plus ? 2 : 1] = 'x';        /* glibc: O_EXCL */
  FILE *f = fopen(path->s, m);
  if (!f && (errno == EMFILE || errno == ENFILE) && !gc_off) { collect(); f = fopen(path->s, m); }   /* unreachable files closed */
  if (!f) oserr(path->s);
  if (fstat(fileno(f), &st)) memset(&st, 0, sizeof st);
  else if (S_ISDIR(st.st_mode)) { fclose(f); errno = EISDIR; oserr(path->s); }
  if (!buffering) { fclose(f); pys_fail("ValueError: can't have unbuffered text I/O"); }   /* the file is created by now */
  I k = !nl ? 0 : !nl->len ? 1 : !strcmp(nl->s, "\n") ? 2 : !strcmp(nl->s, "\r") ? 3 : !strcmp(nl->s, "\r\n") ? 4 : -1;
  if (k < 0) { fclose(f); failf("ValueError: illegal newline value: %s", nl->s); }
  if (enc && !(lat = codec(enc))) {      /* checked once the file is open, as CPython does */
    fclose(f); failf("NotImplementedError: only UTF-8 and Latin-1 files are supported, not encoding '%s'", enc->s);
  }
  File *o = pys_alloc(sizeof(File));
  o->f = f; o->name = path; o->mode = mode; o->enc = enc; o->rd = r || plus; o->wr = !r || plus; o->nl = k;
  o->lat = lat == 2; o->dev = st.st_dev; o->ino = st.st_ino;
  if (o->wr) {                         /* buffering=1, or -1 on a terminal: line buffered */
    o->lb = buffering == 1 || (buffering < 0 && isatty(fileno(f)));
    setbuf1(o, buffering > 1 ? buffering : st.st_blksize > 1 ? st.st_blksize : 8192);
  }
  if (a) fseek(f, 0, SEEK_END);        /* CPython starts an append file at its end */
  o->rstart = a ? ftell(f) : 0;
  if (nfiles == cfiles && !(files = realloc(files, (cfiles = 2 * cfiles + 16) * sizeof *files))) oom();
  files[nfiles++] = o;
  io_out();
  return o;
}
static void use(File *f, int rd) {     /* check a read (rd) or write, and reposition between them */
  if (f->closed) closed_err();
  if (rd ? !f->rd : !f->wr) pys_fail(rd ? "io.UnsupportedOperation: not readable" : "io.UnsupportedOperation: not writable");
  if (rd && feof(f->f)) clearerr(f->f);   /* CPython reads again after the end: the file may have grown */
  if (f->std || f->last == (rd ? 2 : 1)) return;
  if (rd) {                            /* after writing: what was written reaches the file, and reads start there */
    int e = flush1(f);
    if (e) ioerr(e);
    f->rstart = ftell(f->f); f->rcons = 0;
  } else if (f->last == 2) {           /* after reading: CPython's text layer read ahead in 8 KiB chunks; with */
    I end = f->rstart + (f->rcons + 8191) / 8192 * 8192, size;   /* newline None or "", a chunk that ends in */
    char c;                            /* "\r" pulls in the next one, to see whether "\n" follows */
    if (f->nl < 2 && f->rcons && f->rcons % 8192 == 0 && pread(fileno(f->f), &c, 1, end - 1) == 1 && c == '\r') end += 8192;
    fseek(f->f, 0, SEEK_END); size = ftell(f->f);
    fseek(f->f, end < size ? end : size, SEEK_SET);
  }
  f->last = rd ? 2 : 1;
}
static int get(File *f) { int c = getc_unlocked(f->f); f->rcons += c != EOF; return c; }
static void unget(File *f, int c) { ungetc(c, f->f); f->rcons--; }
static int getnl(File *f, int c) {     /* newline=None reads "\r\n" and "\r" as "\n" */
  if (c == '\r' && !f->nl) { int d = get(f); if (d != '\n' && d != EOF) unget(f, d); c = '\n'; }
  return c;
}
static Str *read1(File *f, I n) {      /* n < 0: to the end; else n characters (in a Latin-1 file, n bytes) */
  use(f, 1); Buf b = {0};
  if (n < 0) {
    char t[1 << 16]; size_t k;
    while ((k = fread(t, 1, sizeof t, f->f)) > 0) { put(&b, t, k); f->rcons += k; }
    I j = 0;
    if (!f->nl) for (I i = 0; i < b.n; i++) { char c = b.p[i]; if (c == '\r') { c = '\n'; i += i + 1 < b.n && b.p[i + 1] == '\n'; } b.p[j++] = c; }
    if (!f->nl) b.n = j;
    return done(&b);
  }
  for (I k = 0;;) {
    int c = get(f);
    if (c == EOF) break;
    if ((f->lat || (c & 0xC0) != 0x80) && k++ == n) { unget(f, c); break; }   /* the next character starts */
    char ch = getnl(f, c); put(&b, &ch, 1);
  }
  return done(&b);
}
Str *pys_file_read(File *f, I n) { io_in(); Str *s = read1(f, n); io_out(); return s; }
Str *pys_file_readline(File *f) {      /* a line ends as newline= says: None "\n" after translation; "" any of
                                          "\n" "\r" "\r\n"; otherwise exactly that string */
  io_in(); use(f, 1); Buf b = {0}; int c;
  while ((c = get(f)) != EOF) {
    char ch = getnl(f, c); put(&b, &ch, 1);
    if (ch == '\n' && f->nl != 3 && f->nl != 4) break;
    if (ch == '\r' && f->nl == 3) break;
    if (ch == '\r' && (f->nl == 1 || f->nl == 4)) {
      int d = get(f);
      if (d == '\n') { put(&b, "\n", 1); break; }
      if (d != EOF) unget(f, d);
      if (f->nl == 1) break;
    }
  }
  io_out();
  return done(&b);
}
List *pys_file_readlines(File *f) {
  List *l = pys_list_new(0);
  for (Str *s; (s = pys_file_readline(f))->len;) pys_list_append(l, (I)s);
  return l;
}
I pys_file_write(File *f, Str *s) {   /* newline="\r" or "\r\n" writes "\n" as that */
  io_in(); use(f, 0);
  const char *p = s->s, *q; I n = s->len;
  if (f->nl >= 3 && memchr(p, '\n', n)) {
    Buf b = {0};
    for (I i = 0; i < n; i = q - p + 1) {
      if (!(q = memchr(p + i, '\n', n - i))) q = p + n;
      put(&b, p + i, q - p - i);
      if (q < p + n) put(&b, "\r\n", f->nl == 3 ? 1 : 2);
    }
    p = b.p; n = b.n;
  }
  put1(f, p, n);
  io_out();
  return s->len;
}
void pys_file_writelines(File *f, List *l) { for (I i = 0; i < l->len; i++) pys_file_write(f, (Str *)l->a[i]); }
void pys_file_flush(File *f) {
  if (f->closed) closed_err();
  io_in(); int e = flush1(f); io_out();
  if (e) ioerr(e);
}
void pys_file_close(File *f) {
  if (f->closed) return;
  io_in(); int e = shut(f); io_out();
  if (e) ioerr(e);
}
void pys_file_drop(File *f) {          /* the compiler's close of a file used in one expression: as CPython's finalizer */
  if (f->closed) return;
  io_in(); int e = shut(f); if (e) report(f, e); io_out();
}
I pys_file_closed(File *f) { return f->closed; }
Str *pys_file_name(File *f) { return f->name ? f->name : cstr(f == &std_in ? "<stdin>" : f == &std_out ? "<stdout>" : "<stderr>"); }
Str *pys_file_mode(File *f) { return f->mode ? f->mode : cstr(f == &std_in ? "r" : "w"); }
I pys_system(Str *c) {
  if (nul(c)) pys_fail("ValueError: embedded null byte");
  return system(c->s);                 /* like CPython, without flushing stdout first */
}
I pys_getpid(void) { return getpid(); }
static I recursion_limit = 1000;       /* sys.setrecursionlimit: only recorded, the native stack bounds recursion */
void pys_setrecursionlimit(I n) {
  if (n > INT32_MAX || n < INT32_MIN) pys_fail("OverflowError: Python int too large to convert to C int");
  if (n < 1) pys_fail("ValueError: recursion limit must be greater or equal than 1");
  recursion_limit = n;
}
I pys_getrecursionlimit(void) { return recursion_limit; }
Str *pys_platform(void) {              /* sys.platform */
#if defined(__linux__)
  return cstr("linux");
#elif defined(__APPLE__)
  return cstr("darwin");
#elif defined(__FreeBSD__)
  return cstr("freebsd");
#else
  return cstr("unknown");
#endif
}
I pys_exists(Str *p) { return !nul(p) && access(p->s, F_OK) == 0; }
Str *pys_getenv(Str *k, Str *dflt) { char *v = nul(k) ? 0 : getenv(k->s); return v ? cstr(v) : dflt; }

/* ---------- exceptions: a chain of handler records (setjmp/longjmp) ----------
   A try statement pushes a handler record, which lives in its function's frame, on the chain
   and calls _setjmp on it. A raise under a try (pys_fail, pys_raise, sys.exit, pys_throw)
   notes the exception, restores the runtime state the innermost record saved, runs the unwind
   actions registered since it was pushed, pops it and longjmps to it, where the landing reads
   the exception (pys_exc_cur); with an empty chain the actions run and the exception is
   reported as before, CPython's last traceback line and exit status. Code outside a try pays
   nothing, a try one push, _setjmp and pop. Compiled code allocates the record as alloca
   [512 x i8], align 16, and passes it to _setjmp as it is (jb comes first), declared and
   called returns_twice; locals stored under a try and read after a longjmp are volatile. A
   user exception object's first field points to its class's ExcClass, a constant compiled
   code emits per class. The exception being handled (a bare raise's, CPython's exc_info) is
   set by a handler when it starts and restored on every way out of it: a record saves it
   when pushed and a raise restores it. Not catchable: an allocation that fails (oom), a
   Ctrl-C (kbint_exit) and a stack overflow.
   What a longjmp out of the runtime would leave half done is restored from the record (the
   I/O layer's busy count, which defers a Ctrl-C, and the stack of objects whose generated
   __repr__ runs, which nests) or undone by an unwind action: a with statement's file is
   closed as its __exit__ would (a close that fails raises instead), and a list being sorted
   gets its items back (list.sort). The rest raises before it changes anything (list and
   dict operations; open() closes the file it opened first), builds new objects that become
   garbage (strings, containers, formatting) or never raises (the collector and its closing
   of unreachable files). */
typedef struct ExcClass {
  Str *kind;                           /* unique name, which pys_exc_in matches */
  Str *disp;                           /* name in an uncaught exception's line: "mod.Class", "Class" in __main__ */
  Str *(*str)(void *obj), *(*repr)(void *obj);
} ExcClass;
struct Exc {
  Str *kind;                           /* "KeyError", or the user class's ExcClass->kind */
  Str *msg;                            /* str(e) of a builtin exception; NULL for a user object */
  void *obj;                           /* the user exception object, or NULL */
  I code, has_code;                    /* SystemExit: its status (msg holds a non-int code's text) */
  Str *args;                           /* repr(e) is the class's name and (args); NULL: made from msg */
};
struct Handler {
  jmp_buf jb;                          /* first: _setjmp takes the record itself */
  Handler *prev;
  Exc *handled;                        /* when it was pushed: the exception being handled, */
  I unwind, nbusy, io;                 /* unwind actions registered, reprs running, io_busy */
};
_Static_assert(offsetof(Handler, jb) == 0 && sizeof(Handler) <= 512 && _Alignof(Handler) <= 16,
               "compiled code allocates a handler record as [512 x i8], align 16, and passes it to _setjmp");
#define XCLS(e) (*(ExcClass **)(e)->obj)
void pys_try_push(Handler *h) { h->prev = top; h->handled = xhandled; h->unwind = nunw; h->nbusy = nbusy; h->io = io_busy; top = h; }
void pys_try_pop(void) { top = top->prev; }
Exc *pys_exc_new(Str *kind, Str *msg, Str *args) { Exc *e = pys_alloc(sizeof(Exc)); e->kind = kind; e->msg = msg; e->args = args; return e; }
Exc *pys_exc_user(void *obj) { Exc *e = pys_alloc(sizeof(Exc)); e->kind = (*(ExcClass **)obj)->kind; e->obj = obj; return e; }
Exc *pys_exc_exit(I code, Str *str, Str *args) {   /* SystemExit with an int status; str(e), its args */
  Exc *e = pys_exc_new(cstr("SystemExit"), str, args); e->code = code; e->has_code = 1; return e;
}
static Exc *exc_exit(I c, Str *m) {   /* sys.exit(c), or sys.exit(m): message m, status 1 */
  return m ? pys_exc_new(cstr("SystemExit"), m, 0) : pys_exc_exit(c, pys_str_int(c), 0);
}
static Exc *exc_line(const char *m) {  /* pys_fail's "Kind: message"; the args of its tuple and errno forms */
  const char *c = strstr(m, ": "), *t, *q;
  Str *s = cstr(c ? c + 2 : ""), *a = 0;
  if (s->len > 1 && s->s[0] == '(' && s->s[s->len - 1] == ')') a = pys_str(s->s + 1, s->len - 2);   /* (34, '...') */
  else if (!strncmp(s->s, "[Errno ", 7) && (t = strstr(s->s, "] "))) {   /* an OSError's (errno, strerror) */
    Buf b = {0}; q = strstr(t + 2, ": ");
    put(&b, s->s + 7, t - s->s - 7); put(&b, ", ", 2); repr_str(&b, pys_str(t + 2, q ? q - t - 2 : s->s + s->len - t - 2));
    a = done(&b);
  }
  return pys_exc_new(pys_str(m, c ? c - m : (I)strlen(m)), s, a);
}
Str *pys_exc_str(Exc *e) { return e->obj ? XCLS(e)->str(e->obj) : e->msg; }
Str *pys_exc_repr(Exc *e) {            /* CPython's: the class's name without its module, then its args */
  if (e->obj) return XCLS(e)->repr(e->obj);
  Buf b = {0}; Str *k = e->kind, *m = e->msg; const char *dot = memrchr(k->s, '.', k->len);
  if (dot) put(&b, dot + 1, k->s + k->len - dot - 1); else put(&b, k->s, k->len);
  put(&b, "(", 1);
  if (e->args) put(&b, e->args->s, e->args->len);
  else if (e->has_code || !strcmp(k->s, "KeyError")) put(&b, m->s, m->len);   /* a KeyError's message is its key's repr */
  else if (m->len) repr_str(&b, m);
  put(&b, ")", 1); return done(&b);
}
I pys_exc_in(Exc *e, Str *names) {     /* e's kind is one of the names in "\1A\1B\1" */
  Str *k = e->kind;
  for (const char *p = names->s, *end = p + names->len; (p = memchr(p, 1, end - p)) && end - p > k->len + 1; p++)
    if (!memcmp(p + 1, k->s, k->len) && p[k->len + 1] == 1) return 1;
  return 0;
}
void *pys_exc_obj(Exc *e) { return e->obj; }
Exc *pys_exc_cur(void) { return xcur; }
Exc *pys_exc_handled(void) { return xhandled; }
void pys_exc_set_handled(Exc *e) { xhandled = e; }
static Str *safe_str(Exc *e) {         /* str(e) for the report: CPython's text if it raises */
  Handler h;
  pys_try_push(&h);
  if (_setjmp(h.jb)) return cstr("<exception str() failed>");
  Str *s = pys_exc_str(e);
  pys_try_pop();
  return s;
}
static _Noreturn void uncaught(Exc *e) {   /* as pys_raise, pys_exit and pys_exit_msg end the program */
  if (!e->obj && !strcmp(e->kind->s, "SystemExit")) {
    if (e->has_code) { pys_finish(); exit((int)e->code); }
    out_flush(); fwrite(e->msg->s, 1, e->msg->len, stderr); fputc('\n', stderr); pys_finish(); exit(1);
  }
  out_flush();
  Str *k = e->obj ? XCLS(e)->disp : e->kind, *m = e->obj ? safe_str(e) : e->msg;
  fwrite(k->s, 1, k->len, stderr);
  if (m->len) { fputs(": ", stderr); fwrite(m->s, 1, m->len, stderr); }
  fputc('\n', stderr);
  kbint = !e->obj && !strcmp(k->s, "KeyboardInterrupt");
  pys_finish();
  exit(1);
}
void pys_unwind_push(void (*fn)(void *), void *arg) {   /* run fn(arg) if a raise leaves this frame */
  if (nunw == cunw && !(unw = realloc(unw, (cunw = 2 * cunw + 16) * sizeof *unw))) oom();
  unw[nunw++] = (Unwind){fn, arg};
}
void pys_unwind_pop(void) { nunw--; }  /* the frame is left another way: forget the latest action */
static void close_with(void *f) { pys_file_close(f); }
void pys_unwind_file(File *f) { pys_unwind_push(close_with, f); }   /* with open(...) as f */
/* a raise on its way to the innermost record: the state the record saved is restored, then the
   actions registered since it was pushed run, the latest first, each popped before it runs (one
   that raises comes back here with its own exception) */
static Handler *settle(void) {
  Handler *h = top;
  if (h) {
    xhandled = h->handled; nbusy = h->nbusy; io_busy = h->io;
    atomic_signal_fence(memory_order_seq_cst);
    if (io_intr && !io_busy) kbint_exit();   /* a Ctrl-C the I/O layer deferred */
  }
  for (I d = h ? h->unwind : 0; nunw > d;) { Unwind u = unw[--nunw]; u.fn(u.arg); }
  return h;
}
_Noreturn void pys_throw(Exc *e) {
  Handler *h = settle();
  if (!h) uncaught(e);
  top = h->prev; xcur = e;
  longjmp(h->jb, 1);
}
/* a raise to a record in the caller's own frame: as pys_throw, but the caller branches to its landing */
void pys_throw_local(Exc *e) { settle(); top = top->prev; xcur = e; }
_Noreturn void pys_reraise(void) {     /* a bare raise */
  if (!xhandled) pys_raise(cstr("RuntimeError"), cstr("No active exception to reraise"));
  pys_throw(xhandled);
}

/* ---------- the time module: clocks and sleep ---------- */
static I clock_ns(clockid_t c) { struct timespec t; clock_gettime(c, &t); return (I)t.tv_sec * 1000000000 + t.tv_nsec; }
static double ns_secs(I ns) { return ns % 1000000000 == 0 ? (double)(ns / 1000000000) : (double)ns / 1e9; }   /* as CPython */
double pys_time(void) { return ns_secs(clock_ns(CLOCK_REALTIME)); }
I pys_time_ns(void) { return clock_ns(CLOCK_REALTIME); }
double pys_monotonic(void) { return ns_secs(clock_ns(CLOCK_MONOTONIC)); }
I pys_monotonic_ns(void) { return clock_ns(CLOCK_MONOTONIC); }
double pys_process_time(void) { return ns_secs(clock_ns(CLOCK_PROCESS_CPUTIME_ID)); }
I pys_process_time_ns(void) { return clock_ns(CLOCK_PROCESS_CPUTIME_ID); }
void pys_sleep(double s) {             /* time.sleep: resumes after a signal (PEP 475); Ctrl-C raises KeyboardInterrupt */
  if (s != s) pys_fail("ValueError: Invalid value NaN (not a number)");
  if (s < 0) pys_fail("ValueError: sleep length must be non-negative");
  if (s >= 9.2e9) pys_fail("OverflowError: timestamp too large to convert to C _PyTime_t");
  struct timespec t = {(time_t)s, (long)((s - (double)(time_t)s) * 1e9)}, r;
  if (t.tv_nsec >= 1000000000) { t.tv_sec++; t.tv_nsec -= 1000000000; }
  while (nanosleep(&t, &r) != 0 && errno == EINTR) { if (io_intr) kbint_exit(); t = r; }
}
void pys_sleep_int(I s) { pys_sleep((double)s); }

/* ---------- the errno module: the platform's error numbers ---------- */
static const struct { const char *name; int value; } errnos[] = {
#ifdef EPERM
  {"EPERM", EPERM},
#endif
#ifdef ENOENT
  {"ENOENT", ENOENT},
#endif
#ifdef ESRCH
  {"ESRCH", ESRCH},
#endif
#ifdef EINTR
  {"EINTR", EINTR},
#endif
#ifdef EIO
  {"EIO", EIO},
#endif
#ifdef ENXIO
  {"ENXIO", ENXIO},
#endif
#ifdef E2BIG
  {"E2BIG", E2BIG},
#endif
#ifdef ENOEXEC
  {"ENOEXEC", ENOEXEC},
#endif
#ifdef EBADF
  {"EBADF", EBADF},
#endif
#ifdef ECHILD
  {"ECHILD", ECHILD},
#endif
#ifdef EAGAIN
  {"EAGAIN", EAGAIN},
#endif
#ifdef ENOMEM
  {"ENOMEM", ENOMEM},
#endif
#ifdef EACCES
  {"EACCES", EACCES},
#endif
#ifdef EFAULT
  {"EFAULT", EFAULT},
#endif
#ifdef ENOTBLK
  {"ENOTBLK", ENOTBLK},
#endif
#ifdef EBUSY
  {"EBUSY", EBUSY},
#endif
#ifdef EEXIST
  {"EEXIST", EEXIST},
#endif
#ifdef EXDEV
  {"EXDEV", EXDEV},
#endif
#ifdef ENODEV
  {"ENODEV", ENODEV},
#endif
#ifdef ENOTDIR
  {"ENOTDIR", ENOTDIR},
#endif
#ifdef EISDIR
  {"EISDIR", EISDIR},
#endif
#ifdef EINVAL
  {"EINVAL", EINVAL},
#endif
#ifdef ENFILE
  {"ENFILE", ENFILE},
#endif
#ifdef EMFILE
  {"EMFILE", EMFILE},
#endif
#ifdef ENOTTY
  {"ENOTTY", ENOTTY},
#endif
#ifdef ETXTBSY
  {"ETXTBSY", ETXTBSY},
#endif
#ifdef EFBIG
  {"EFBIG", EFBIG},
#endif
#ifdef ENOSPC
  {"ENOSPC", ENOSPC},
#endif
#ifdef ESPIPE
  {"ESPIPE", ESPIPE},
#endif
#ifdef EROFS
  {"EROFS", EROFS},
#endif
#ifdef EMLINK
  {"EMLINK", EMLINK},
#endif
#ifdef EPIPE
  {"EPIPE", EPIPE},
#endif
#ifdef EDOM
  {"EDOM", EDOM},
#endif
#ifdef ERANGE
  {"ERANGE", ERANGE},
#endif
#ifdef EDEADLK
  {"EDEADLK", EDEADLK},
#endif
#ifdef ENAMETOOLONG
  {"ENAMETOOLONG", ENAMETOOLONG},
#endif
#ifdef ENOLCK
  {"ENOLCK", ENOLCK},
#endif
#ifdef ENOSYS
  {"ENOSYS", ENOSYS},
#endif
#ifdef ENOTEMPTY
  {"ENOTEMPTY", ENOTEMPTY},
#endif
#ifdef ELOOP
  {"ELOOP", ELOOP},
#endif
#ifdef EWOULDBLOCK
  {"EWOULDBLOCK", EWOULDBLOCK},
#endif
#ifdef ENOMSG
  {"ENOMSG", ENOMSG},
#endif
#ifdef EIDRM
  {"EIDRM", EIDRM},
#endif
#ifdef ENOSTR
  {"ENOSTR", ENOSTR},
#endif
#ifdef ENODATA
  {"ENODATA", ENODATA},
#endif
#ifdef ETIME
  {"ETIME", ETIME},
#endif
#ifdef ENOSR
  {"ENOSR", ENOSR},
#endif
#ifdef EREMOTE
  {"EREMOTE", EREMOTE},
#endif
#ifdef ENOLINK
  {"ENOLINK", ENOLINK},
#endif
#ifdef EPROTO
  {"EPROTO", EPROTO},
#endif
#ifdef EMULTIHOP
  {"EMULTIHOP", EMULTIHOP},
#endif
#ifdef EBADMSG
  {"EBADMSG", EBADMSG},
#endif
#ifdef EOVERFLOW
  {"EOVERFLOW", EOVERFLOW},
#endif
#ifdef EILSEQ
  {"EILSEQ", EILSEQ},
#endif
#ifdef EUSERS
  {"EUSERS", EUSERS},
#endif
#ifdef ENOTSOCK
  {"ENOTSOCK", ENOTSOCK},
#endif
#ifdef EDESTADDRREQ
  {"EDESTADDRREQ", EDESTADDRREQ},
#endif
#ifdef EMSGSIZE
  {"EMSGSIZE", EMSGSIZE},
#endif
#ifdef EPROTOTYPE
  {"EPROTOTYPE", EPROTOTYPE},
#endif
#ifdef ENOPROTOOPT
  {"ENOPROTOOPT", ENOPROTOOPT},
#endif
#ifdef EPROTONOSUPPORT
  {"EPROTONOSUPPORT", EPROTONOSUPPORT},
#endif
#ifdef ESOCKTNOSUPPORT
  {"ESOCKTNOSUPPORT", ESOCKTNOSUPPORT},
#endif
#ifdef EOPNOTSUPP
  {"EOPNOTSUPP", EOPNOTSUPP},
#endif
#ifdef ENOTSUP
  {"ENOTSUP", ENOTSUP},
#endif
#ifdef EPFNOSUPPORT
  {"EPFNOSUPPORT", EPFNOSUPPORT},
#endif
#ifdef EAFNOSUPPORT
  {"EAFNOSUPPORT", EAFNOSUPPORT},
#endif
#ifdef EADDRINUSE
  {"EADDRINUSE", EADDRINUSE},
#endif
#ifdef EADDRNOTAVAIL
  {"EADDRNOTAVAIL", EADDRNOTAVAIL},
#endif
#ifdef ENETDOWN
  {"ENETDOWN", ENETDOWN},
#endif
#ifdef ENETUNREACH
  {"ENETUNREACH", ENETUNREACH},
#endif
#ifdef ENETRESET
  {"ENETRESET", ENETRESET},
#endif
#ifdef ECONNABORTED
  {"ECONNABORTED", ECONNABORTED},
#endif
#ifdef ECONNRESET
  {"ECONNRESET", ECONNRESET},
#endif
#ifdef ENOBUFS
  {"ENOBUFS", ENOBUFS},
#endif
#ifdef EISCONN
  {"EISCONN", EISCONN},
#endif
#ifdef ENOTCONN
  {"ENOTCONN", ENOTCONN},
#endif
#ifdef ESHUTDOWN
  {"ESHUTDOWN", ESHUTDOWN},
#endif
#ifdef ETOOMANYREFS
  {"ETOOMANYREFS", ETOOMANYREFS},
#endif
#ifdef ETIMEDOUT
  {"ETIMEDOUT", ETIMEDOUT},
#endif
#ifdef ECONNREFUSED
  {"ECONNREFUSED", ECONNREFUSED},
#endif
#ifdef EHOSTDOWN
  {"EHOSTDOWN", EHOSTDOWN},
#endif
#ifdef EHOSTUNREACH
  {"EHOSTUNREACH", EHOSTUNREACH},
#endif
#ifdef EALREADY
  {"EALREADY", EALREADY},
#endif
#ifdef EINPROGRESS
  {"EINPROGRESS", EINPROGRESS},
#endif
#ifdef ESTALE
  {"ESTALE", ESTALE},
#endif
#ifdef EDQUOT
  {"EDQUOT", EDQUOT},
#endif
#ifdef ECANCELED
  {"ECANCELED", ECANCELED},
#endif
#ifdef EOWNERDEAD
  {"EOWNERDEAD", EOWNERDEAD},
#endif
#ifdef ENOTRECOVERABLE
  {"ENOTRECOVERABLE", ENOTRECOVERABLE},
#endif
};
I pys_errno(Str *name) {
  for (size_t i = 0; i < sizeof errnos / sizeof errnos[0]; i++) if (strcmp(errnos[i].name, name->s) == 0) return errnos[i].value;
  Buf b = {0}; put(&b, "AttributeError: module 'errno' has no attribute '", 49); put(&b, name->s, name->len); put(&b, "'", 2); pys_fail(b.p);
}

/* ---------- temporary directories: tempfile.mkdtemp, os.remove, os.rmdir ---------- */
static _Noreturn void oserr(const char *path) {         /* raise CPython's OSError subclass for errno */
  int e = errno; Buf b = {0}; char t[32];
  const char *k = errcls(e), *m = strerror(e);
  put(&b, k, strlen(k)); put(&b, t, snprintf(t, sizeof t, ": [Errno %d] ", e)); put(&b, m, strlen(m)); put(&b, ": ", 2);
  repr_str(&b, cstr(path)); put(&b, "", 1); pys_fail(b.p);
}
void pys_remove(Str *p) { if (nul(p)) pys_fail("ValueError: remove: embedded null character in path"); if (unlink(p->s)) oserr(p->s); }
void pys_rmdir(Str *p) { if (nul(p)) pys_fail("ValueError: rmdir: embedded null character in path"); if (rmdir(p->s)) oserr(p->s); }
typedef struct { Str **a; I n, cap; } Parts;            /* a stack of path components; NULL marks a resolved link */
static void parts_push(Parts *p, Str *s) {
  if (p->n == p->cap) { I c = p->cap * 2 + 16; Str **a = pys_alloc(c * sizeof(Str *)); if (p->n) memcpy(a, p->a, p->n * sizeof(Str *)); p->a = a; p->cap = c; }
  p->a[p->n++] = s;
}
static I parts_split(Parts *p, const char *s, I n) {    /* push s.split("/") reversed, so that it pops in order */
  I k = p->n;
  for (I i = n, j = n; i >= 0; i--) if (i == 0 || s[i - 1] == '/') { parts_push(p, pys_str(s + i, j - i)); j = i - 1; }
  return p->n - k;
}
Str *pys_realpath(Str *f) {    /* os.path.realpath(f): CPython 3.13's posixpath.realpath (strict=False), step for step */
  if (nul(f)) pys_fail("ValueError: lstat: embedded null character in path");
  Parts rest = {0}, seen = {0};                          /* seen: link path, then its resolved path (NULL: not yet) */
  I count = parts_split(&rest, f->s, f->len);
  Str *path;
  if (f->len && f->s[0] == '/') path = cstr("/");
  else {
    char *c = getcwd(NULL, 0);
    if (!c) {
      int e = errno; Buf b = {0}; char t[32]; const char *k = errcls(e), *m = strerror(e);
      put(&b, k, strlen(k)); put(&b, t, snprintf(t, sizeof t, ": [Errno %d] ", e)); put(&b, m, strlen(m)); put(&b, "", 1); pys_fail(b.p);
    }
    path = cstr(c); free(c);
  }
  while (count) {
    Str *name = rest.a[--rest.n];
    if (!name) {                                         /* a link's target is resolved */
      Str *l = rest.a[--rest.n];
      for (I i = 0; i < seen.n; i += 2) if (seen.a[i] == l) seen.a[i + 1] = path;
      continue;
    }
    count--;
    if (!name->len || (name->len == 1 && name->s[0] == '.')) continue;
    if (name->len == 2 && name->s[0] == '.' && name->s[1] == '.') {
      I i = path->len - 1;
      while (path->s[i] != '/') i--;
      path = pys_str(path->s, i ? i : 1);
      continue;
    }
    Buf b = {0}; put(&b, path->s, path->len); if (path->len > 1) put(&b, "/", 1); put(&b, name->s, name->len);
    Str *np = done(&b);
    struct stat st;
    if (lstat(np->s, &st) || !S_ISLNK(st.st_mode)) { path = np; continue; }   /* (errors are ignored) */
    I k = -1;
    for (I i = 0; i < seen.n; i += 2) if (seen.a[i]->len == np->len && !memcmp(seen.a[i]->s, np->s, np->len)) k = i;
    if (k >= 0) { path = seen.a[k + 1] ? seen.a[k + 1] : np; continue; }   /* (NULL: a loop, kept as it is) */
    Str *t = 0;
    for (I n = 256; !t; n *= 2) {
      char *buf = pys_alloc_atomic(n); ssize_t r = readlink(np->s, buf, n);
      if (r < 0) break;
      if (r < n) t = pys_str(buf, r);
    }
    if (!t) { path = np; continue; }
    if (t->len && t->s[0] == '/') path = cstr("/");
    parts_push(&seen, np); parts_push(&seen, 0);
    parts_push(&rest, np); parts_push(&rest, 0);
    count += parts_split(&rest, t->s, t->len);
  }
  return path;
}
static void abspath(Buf *r, const char *d) {            /* os.path.abspath + "/": no symlink resolution */
  char cwd[4096]; Buf b = {0};
  if (*d != '/' && getcwd(cwd, sizeof cwd)) { put(&b, cwd, strlen(cwd)); put(&b, "/", 1); }
  put(&b, d, strlen(d)); put(r, "/", 1);
  for (I i = 0, j; i < b.n; i = j + 1) {                /* one path component per round: drop "" and ".", pop on ".." */
    for (j = i; j < b.n && b.p[j] != '/'; j++) {}
    if (j - i == 2 && b.p[i] == '.' && b.p[i + 1] == '.') { if (r->n > 1) for (r->n--; r->p[r->n - 1] != '/'; r->n--) {} }
    else if (j > i && !(j - i == 1 && b.p[i] == '.')) { put(r, b.p + i, j - i); put(r, "/", 1); }
  }
}
Str *pys_mkdtemp(void) {     /* like CPython: first usable of $TMPDIR $TEMP $TMP /tmp /var/tmp /usr/tmp cwd, mode 0700 */
  static const char *env[] = {"TMPDIR", "TEMP", "TMP"}, *none = "FileNotFoundError: [Errno 2] No usable temporary directory found in [";
  const char *c[7]; int n = 0; char cwd[4096];
  for (int i = 0; i < 3; i++) { char *v = getenv(env[i]); if (v && *v) c[n++] = v; }
  c[n++] = "/tmp"; c[n++] = "/var/tmp"; c[n++] = "/usr/tmp"; c[n++] = getcwd(cwd, sizeof cwd) ? cwd : ".";
  for (int i = 0; i < n; i++) {
    Buf b = {0}; abspath(&b, c[i]); put(&b, "tmpXXXXXXXX", 12);
    for (int tries = 0; tries < 10000; tries++) {   /* CPython's names: "tmp" and 8 of [a-z0-9_] */
      unsigned char r[8]; char *x = b.p + b.n - 9;
      if (getentropy(r, 8)) for (int k = 0; k < 8; k++) r[k] = rand();
      for (int k = 0; k < 8; k++) x[k] = "abcdefghijklmnopqrstuvwxyz0123456789_"[r[k] % 37];
      if (!mkdir(b.p, 0700)) return cstr(b.p);
      if (errno != EEXIST) break;
    }
  }
  Buf b = {0}; put(&b, none, strlen(none));
  for (int i = 0; i < n; i++) { if (i) put(&b, ", ", 2); repr_str(&b, cstr(c[i])); }
  put(&b, "]", 2); pys_fail(b.p);
}

/* ---------- tables ---------- */
/* str.isprintable(), CPython's Py_UNICODE_ISPRINTABLE: false for the categories Cc Cf Cs Co Cn Zl
   Zp and Zs (but U+0020), which repr() escapes. The code points from U+0080 on where it changes,
   for Unicode 15.1 (unicodedata.unidata_version in CPython 3.13), as printed by
   python3 -c 'p = lambda c: 0x80 <= c < 0x110000 and not chr(c).isprintable(); print(", ".join(hex(c) for c in range(0x80, 0x110000) if p(c) != p(c - 1)))' */
static const int32_t pchange[] = {
  0x80, 0xa1, 0xad, 0xae, 0x378, 0x37a, 0x380, 0x384, 0x38b, 0x38c, 0x38d, 0x38e, 0x3a2, 0x3a3, 0x530, 0x531, 0x557,
  0x559, 0x58b, 0x58d, 0x590, 0x591, 0x5c8, 0x5d0, 0x5eb, 0x5ef, 0x5f5, 0x606, 0x61c, 0x61d, 0x6dd, 0x6de, 0x70e,
  0x710, 0x74b, 0x74d, 0x7b2, 0x7c0, 0x7fb, 0x7fd, 0x82e, 0x830, 0x83f, 0x840, 0x85c, 0x85e, 0x85f, 0x860, 0x86b,
  0x870, 0x88f, 0x898, 0x8e2, 0x8e3, 0x984, 0x985, 0x98d, 0x98f, 0x991, 0x993, 0x9a9, 0x9aa, 0x9b1, 0x9b2, 0x9b3,
  0x9b6, 0x9ba, 0x9bc, 0x9c5, 0x9c7, 0x9c9, 0x9cb, 0x9cf, 0x9d7, 0x9d8, 0x9dc, 0x9de, 0x9df, 0x9e4, 0x9e6, 0x9ff,
  0xa01, 0xa04, 0xa05, 0xa0b, 0xa0f, 0xa11, 0xa13, 0xa29, 0xa2a, 0xa31, 0xa32, 0xa34, 0xa35, 0xa37, 0xa38, 0xa3a,
  0xa3c, 0xa3d, 0xa3e, 0xa43, 0xa47, 0xa49, 0xa4b, 0xa4e, 0xa51, 0xa52, 0xa59, 0xa5d, 0xa5e, 0xa5f, 0xa66, 0xa77,
  0xa81, 0xa84, 0xa85, 0xa8e, 0xa8f, 0xa92, 0xa93, 0xaa9, 0xaaa, 0xab1, 0xab2, 0xab4, 0xab5, 0xaba, 0xabc, 0xac6,
  0xac7, 0xaca, 0xacb, 0xace, 0xad0, 0xad1, 0xae0, 0xae4, 0xae6, 0xaf2, 0xaf9, 0xb00, 0xb01, 0xb04, 0xb05, 0xb0d,
  0xb0f, 0xb11, 0xb13, 0xb29, 0xb2a, 0xb31, 0xb32, 0xb34, 0xb35, 0xb3a, 0xb3c, 0xb45, 0xb47, 0xb49, 0xb4b, 0xb4e,
  0xb55, 0xb58, 0xb5c, 0xb5e, 0xb5f, 0xb64, 0xb66, 0xb78, 0xb82, 0xb84, 0xb85, 0xb8b, 0xb8e, 0xb91, 0xb92, 0xb96,
  0xb99, 0xb9b, 0xb9c, 0xb9d, 0xb9e, 0xba0, 0xba3, 0xba5, 0xba8, 0xbab, 0xbae, 0xbba, 0xbbe, 0xbc3, 0xbc6, 0xbc9,
  0xbca, 0xbce, 0xbd0, 0xbd1, 0xbd7, 0xbd8, 0xbe6, 0xbfb, 0xc00, 0xc0d, 0xc0e, 0xc11, 0xc12, 0xc29, 0xc2a, 0xc3a,
  0xc3c, 0xc45, 0xc46, 0xc49, 0xc4a, 0xc4e, 0xc55, 0xc57, 0xc58, 0xc5b, 0xc5d, 0xc5e, 0xc60, 0xc64, 0xc66, 0xc70,
  0xc77, 0xc8d, 0xc8e, 0xc91, 0xc92, 0xca9, 0xcaa, 0xcb4, 0xcb5, 0xcba, 0xcbc, 0xcc5, 0xcc6, 0xcc9, 0xcca, 0xcce,
  0xcd5, 0xcd7, 0xcdd, 0xcdf, 0xce0, 0xce4, 0xce6, 0xcf0, 0xcf1, 0xcf4, 0xd00, 0xd0d, 0xd0e, 0xd11, 0xd12, 0xd45,
  0xd46, 0xd49, 0xd4a, 0xd50, 0xd54, 0xd64, 0xd66, 0xd80, 0xd81, 0xd84, 0xd85, 0xd97, 0xd9a, 0xdb2, 0xdb3, 0xdbc,
  0xdbd, 0xdbe, 0xdc0, 0xdc7, 0xdca, 0xdcb, 0xdcf, 0xdd5, 0xdd6, 0xdd7, 0xdd8, 0xde0, 0xde6, 0xdf0, 0xdf2, 0xdf5,
  0xe01, 0xe3b, 0xe3f, 0xe5c, 0xe81, 0xe83, 0xe84, 0xe85, 0xe86, 0xe8b, 0xe8c, 0xea4, 0xea5, 0xea6, 0xea7, 0xebe,
  0xec0, 0xec5, 0xec6, 0xec7, 0xec8, 0xecf, 0xed0, 0xeda, 0xedc, 0xee0, 0xf00, 0xf48, 0xf49, 0xf6d, 0xf71, 0xf98,
  0xf99, 0xfbd, 0xfbe, 0xfcd, 0xfce, 0xfdb, 0x1000, 0x10c6, 0x10c7, 0x10c8, 0x10cd, 0x10ce, 0x10d0, 0x1249, 0x124a,
  0x124e, 0x1250, 0x1257, 0x1258, 0x1259, 0x125a, 0x125e, 0x1260, 0x1289, 0x128a, 0x128e, 0x1290, 0x12b1, 0x12b2,
  0x12b6, 0x12b8, 0x12bf, 0x12c0, 0x12c1, 0x12c2, 0x12c6, 0x12c8, 0x12d7, 0x12d8, 0x1311, 0x1312, 0x1316, 0x1318,
  0x135b, 0x135d, 0x137d, 0x1380, 0x139a, 0x13a0, 0x13f6, 0x13f8, 0x13fe, 0x1400, 0x1680, 0x1681, 0x169d, 0x16a0,
  0x16f9, 0x1700, 0x1716, 0x171f, 0x1737, 0x1740, 0x1754, 0x1760, 0x176d, 0x176e, 0x1771, 0x1772, 0x1774, 0x1780,
  0x17de, 0x17e0, 0x17ea, 0x17f0, 0x17fa, 0x1800, 0x180e, 0x180f, 0x181a, 0x1820, 0x1879, 0x1880, 0x18ab, 0x18b0,
  0x18f6, 0x1900, 0x191f, 0x1920, 0x192c, 0x1930, 0x193c, 0x1940, 0x1941, 0x1944, 0x196e, 0x1970, 0x1975, 0x1980,
  0x19ac, 0x19b0, 0x19ca, 0x19d0, 0x19db, 0x19de, 0x1a1c, 0x1a1e, 0x1a5f, 0x1a60, 0x1a7d, 0x1a7f, 0x1a8a, 0x1a90,
  0x1a9a, 0x1aa0, 0x1aae, 0x1ab0, 0x1acf, 0x1b00, 0x1b4d, 0x1b50, 0x1b7f, 0x1b80, 0x1bf4, 0x1bfc, 0x1c38, 0x1c3b,
  0x1c4a, 0x1c4d, 0x1c89, 0x1c90, 0x1cbb, 0x1cbd, 0x1cc8, 0x1cd0, 0x1cfb, 0x1d00, 0x1f16, 0x1f18, 0x1f1e, 0x1f20,
  0x1f46, 0x1f48, 0x1f4e, 0x1f50, 0x1f58, 0x1f59, 0x1f5a, 0x1f5b, 0x1f5c, 0x1f5d, 0x1f5e, 0x1f5f, 0x1f7e, 0x1f80,
  0x1fb5, 0x1fb6, 0x1fc5, 0x1fc6, 0x1fd4, 0x1fd6, 0x1fdc, 0x1fdd, 0x1ff0, 0x1ff2, 0x1ff5, 0x1ff6, 0x1fff, 0x2010,
  0x2028, 0x2030, 0x205f, 0x2070, 0x2072, 0x2074, 0x208f, 0x2090, 0x209d, 0x20a0, 0x20c1, 0x20d0, 0x20f1, 0x2100,
  0x218c, 0x2190, 0x2427, 0x2440, 0x244b, 0x2460, 0x2b74, 0x2b76, 0x2b96, 0x2b97, 0x2cf4, 0x2cf9, 0x2d26, 0x2d27,
  0x2d28, 0x2d2d, 0x2d2e, 0x2d30, 0x2d68, 0x2d6f, 0x2d71, 0x2d7f, 0x2d97, 0x2da0, 0x2da7, 0x2da8, 0x2daf, 0x2db0,
  0x2db7, 0x2db8, 0x2dbf, 0x2dc0, 0x2dc7, 0x2dc8, 0x2dcf, 0x2dd0, 0x2dd7, 0x2dd8, 0x2ddf, 0x2de0, 0x2e5e, 0x2e80,
  0x2e9a, 0x2e9b, 0x2ef4, 0x2f00, 0x2fd6, 0x2ff0, 0x3000, 0x3001, 0x3040, 0x3041, 0x3097, 0x3099, 0x3100, 0x3105,
  0x3130, 0x3131, 0x318f, 0x3190, 0x31e4, 0x31ef, 0x321f, 0x3220, 0xa48d, 0xa490, 0xa4c7, 0xa4d0, 0xa62c, 0xa640,
  0xa6f8, 0xa700, 0xa7cb, 0xa7d0, 0xa7d2, 0xa7d3, 0xa7d4, 0xa7d5, 0xa7da, 0xa7f2, 0xa82d, 0xa830, 0xa83a, 0xa840,
  0xa878, 0xa880, 0xa8c6, 0xa8ce, 0xa8da, 0xa8e0, 0xa954, 0xa95f, 0xa97d, 0xa980, 0xa9ce, 0xa9cf, 0xa9da, 0xa9de,
  0xa9ff, 0xaa00, 0xaa37, 0xaa40, 0xaa4e, 0xaa50, 0xaa5a, 0xaa5c, 0xaac3, 0xaadb, 0xaaf7, 0xab01, 0xab07, 0xab09,
  0xab0f, 0xab11, 0xab17, 0xab20, 0xab27, 0xab28, 0xab2f, 0xab30, 0xab6c, 0xab70, 0xabee, 0xabf0, 0xabfa, 0xac00,
  0xd7a4, 0xd7b0, 0xd7c7, 0xd7cb, 0xd7fc, 0xf900, 0xfa6e, 0xfa70, 0xfada, 0xfb00, 0xfb07, 0xfb13, 0xfb18, 0xfb1d,
  0xfb37, 0xfb38, 0xfb3d, 0xfb3e, 0xfb3f, 0xfb40, 0xfb42, 0xfb43, 0xfb45, 0xfb46, 0xfbc3, 0xfbd3, 0xfd90, 0xfd92,
  0xfdc8, 0xfdcf, 0xfdd0, 0xfdf0, 0xfe1a, 0xfe20, 0xfe53, 0xfe54, 0xfe67, 0xfe68, 0xfe6c, 0xfe70, 0xfe75, 0xfe76,
  0xfefd, 0xff01, 0xffbf, 0xffc2, 0xffc8, 0xffca, 0xffd0, 0xffd2, 0xffd8, 0xffda, 0xffdd, 0xffe0, 0xffe7, 0xffe8,
  0xffef, 0xfffc, 0xfffe, 0x10000, 0x1000c, 0x1000d, 0x10027, 0x10028, 0x1003b, 0x1003c, 0x1003e, 0x1003f, 0x1004e,
  0x10050, 0x1005e, 0x10080, 0x100fb, 0x10100, 0x10103, 0x10107, 0x10134, 0x10137, 0x1018f, 0x10190, 0x1019d, 0x101a0,
  0x101a1, 0x101d0, 0x101fe, 0x10280, 0x1029d, 0x102a0, 0x102d1, 0x102e0, 0x102fc, 0x10300, 0x10324, 0x1032d, 0x1034b,
  0x10350, 0x1037b, 0x10380, 0x1039e, 0x1039f, 0x103c4, 0x103c8, 0x103d6, 0x10400, 0x1049e, 0x104a0, 0x104aa, 0x104b0,
  0x104d4, 0x104d8, 0x104fc, 0x10500, 0x10528, 0x10530, 0x10564, 0x1056f, 0x1057b, 0x1057c, 0x1058b, 0x1058c, 0x10593,
  0x10594, 0x10596, 0x10597, 0x105a2, 0x105a3, 0x105b2, 0x105b3, 0x105ba, 0x105bb, 0x105bd, 0x10600, 0x10737, 0x10740,
  0x10756, 0x10760, 0x10768, 0x10780, 0x10786, 0x10787, 0x107b1, 0x107b2, 0x107bb, 0x10800, 0x10806, 0x10808, 0x10809,
  0x1080a, 0x10836, 0x10837, 0x10839, 0x1083c, 0x1083d, 0x1083f, 0x10856, 0x10857, 0x1089f, 0x108a7, 0x108b0, 0x108e0,
  0x108f3, 0x108f4, 0x108f6, 0x108fb, 0x1091c, 0x1091f, 0x1093a, 0x1093f, 0x10940, 0x10980, 0x109b8, 0x109bc, 0x109d0,
  0x109d2, 0x10a04, 0x10a05, 0x10a07, 0x10a0c, 0x10a14, 0x10a15, 0x10a18, 0x10a19, 0x10a36, 0x10a38, 0x10a3b, 0x10a3f,
  0x10a49, 0x10a50, 0x10a59, 0x10a60, 0x10aa0, 0x10ac0, 0x10ae7, 0x10aeb, 0x10af7, 0x10b00, 0x10b36, 0x10b39, 0x10b56,
  0x10b58, 0x10b73, 0x10b78, 0x10b92, 0x10b99, 0x10b9d, 0x10ba9, 0x10bb0, 0x10c00, 0x10c49, 0x10c80, 0x10cb3, 0x10cc0,
  0x10cf3, 0x10cfa, 0x10d28, 0x10d30, 0x10d3a, 0x10e60, 0x10e7f, 0x10e80, 0x10eaa, 0x10eab, 0x10eae, 0x10eb0, 0x10eb2,
  0x10efd, 0x10f28, 0x10f30, 0x10f5a, 0x10f70, 0x10f8a, 0x10fb0, 0x10fcc, 0x10fe0, 0x10ff7, 0x11000, 0x1104e, 0x11052,
  0x11076, 0x1107f, 0x110bd, 0x110be, 0x110c3, 0x110d0, 0x110e9, 0x110f0, 0x110fa, 0x11100, 0x11135, 0x11136, 0x11148,
  0x11150, 0x11177, 0x11180, 0x111e0, 0x111e1, 0x111f5, 0x11200, 0x11212, 0x11213, 0x11242, 0x11280, 0x11287, 0x11288,
  0x11289, 0x1128a, 0x1128e, 0x1128f, 0x1129e, 0x1129f, 0x112aa, 0x112b0, 0x112eb, 0x112f0, 0x112fa, 0x11300, 0x11304,
  0x11305, 0x1130d, 0x1130f, 0x11311, 0x11313, 0x11329, 0x1132a, 0x11331, 0x11332, 0x11334, 0x11335, 0x1133a, 0x1133b,
  0x11345, 0x11347, 0x11349, 0x1134b, 0x1134e, 0x11350, 0x11351, 0x11357, 0x11358, 0x1135d, 0x11364, 0x11366, 0x1136d,
  0x11370, 0x11375, 0x11400, 0x1145c, 0x1145d, 0x11462, 0x11480, 0x114c8, 0x114d0, 0x114da, 0x11580, 0x115b6, 0x115b8,
  0x115de, 0x11600, 0x11645, 0x11650, 0x1165a, 0x11660, 0x1166d, 0x11680, 0x116ba, 0x116c0, 0x116ca, 0x11700, 0x1171b,
  0x1171d, 0x1172c, 0x11730, 0x11747, 0x11800, 0x1183c, 0x118a0, 0x118f3, 0x118ff, 0x11907, 0x11909, 0x1190a, 0x1190c,
  0x11914, 0x11915, 0x11917, 0x11918, 0x11936, 0x11937, 0x11939, 0x1193b, 0x11947, 0x11950, 0x1195a, 0x119a0, 0x119a8,
  0x119aa, 0x119d8, 0x119da, 0x119e5, 0x11a00, 0x11a48, 0x11a50, 0x11aa3, 0x11ab0, 0x11af9, 0x11b00, 0x11b0a, 0x11c00,
  0x11c09, 0x11c0a, 0x11c37, 0x11c38, 0x11c46, 0x11c50, 0x11c6d, 0x11c70, 0x11c90, 0x11c92, 0x11ca8, 0x11ca9, 0x11cb7,
  0x11d00, 0x11d07, 0x11d08, 0x11d0a, 0x11d0b, 0x11d37, 0x11d3a, 0x11d3b, 0x11d3c, 0x11d3e, 0x11d3f, 0x11d48, 0x11d50,
  0x11d5a, 0x11d60, 0x11d66, 0x11d67, 0x11d69, 0x11d6a, 0x11d8f, 0x11d90, 0x11d92, 0x11d93, 0x11d99, 0x11da0, 0x11daa,
  0x11ee0, 0x11ef9, 0x11f00, 0x11f11, 0x11f12, 0x11f3b, 0x11f3e, 0x11f5a, 0x11fb0, 0x11fb1, 0x11fc0, 0x11ff2, 0x11fff,
  0x1239a, 0x12400, 0x1246f, 0x12470, 0x12475, 0x12480, 0x12544, 0x12f90, 0x12ff3, 0x13000, 0x13430, 0x13440, 0x13456,
  0x14400, 0x14647, 0x16800, 0x16a39, 0x16a40, 0x16a5f, 0x16a60, 0x16a6a, 0x16a6e, 0x16abf, 0x16ac0, 0x16aca, 0x16ad0,
  0x16aee, 0x16af0, 0x16af6, 0x16b00, 0x16b46, 0x16b50, 0x16b5a, 0x16b5b, 0x16b62, 0x16b63, 0x16b78, 0x16b7d, 0x16b90,
  0x16e40, 0x16e9b, 0x16f00, 0x16f4b, 0x16f4f, 0x16f88, 0x16f8f, 0x16fa0, 0x16fe0, 0x16fe5, 0x16ff0, 0x16ff2, 0x17000,
  0x187f8, 0x18800, 0x18cd6, 0x18d00, 0x18d09, 0x1aff0, 0x1aff4, 0x1aff5, 0x1affc, 0x1affd, 0x1afff, 0x1b000, 0x1b123,
  0x1b132, 0x1b133, 0x1b150, 0x1b153, 0x1b155, 0x1b156, 0x1b164, 0x1b168, 0x1b170, 0x1b2fc, 0x1bc00, 0x1bc6b, 0x1bc70,
  0x1bc7d, 0x1bc80, 0x1bc89, 0x1bc90, 0x1bc9a, 0x1bc9c, 0x1bca0, 0x1cf00, 0x1cf2e, 0x1cf30, 0x1cf47, 0x1cf50, 0x1cfc4,
  0x1d000, 0x1d0f6, 0x1d100, 0x1d127, 0x1d129, 0x1d173, 0x1d17b, 0x1d1eb, 0x1d200, 0x1d246, 0x1d2c0, 0x1d2d4, 0x1d2e0,
  0x1d2f4, 0x1d300, 0x1d357, 0x1d360, 0x1d379, 0x1d400, 0x1d455, 0x1d456, 0x1d49d, 0x1d49e, 0x1d4a0, 0x1d4a2, 0x1d4a3,
  0x1d4a5, 0x1d4a7, 0x1d4a9, 0x1d4ad, 0x1d4ae, 0x1d4ba, 0x1d4bb, 0x1d4bc, 0x1d4bd, 0x1d4c4, 0x1d4c5, 0x1d506, 0x1d507,
  0x1d50b, 0x1d50d, 0x1d515, 0x1d516, 0x1d51d, 0x1d51e, 0x1d53a, 0x1d53b, 0x1d53f, 0x1d540, 0x1d545, 0x1d546, 0x1d547,
  0x1d54a, 0x1d551, 0x1d552, 0x1d6a6, 0x1d6a8, 0x1d7cc, 0x1d7ce, 0x1da8c, 0x1da9b, 0x1daa0, 0x1daa1, 0x1dab0, 0x1df00,
  0x1df1f, 0x1df25, 0x1df2b, 0x1e000, 0x1e007, 0x1e008, 0x1e019, 0x1e01b, 0x1e022, 0x1e023, 0x1e025, 0x1e026, 0x1e02b,
  0x1e030, 0x1e06e, 0x1e08f, 0x1e090, 0x1e100, 0x1e12d, 0x1e130, 0x1e13e, 0x1e140, 0x1e14a, 0x1e14e, 0x1e150, 0x1e290,
  0x1e2af, 0x1e2c0, 0x1e2fa, 0x1e2ff, 0x1e300, 0x1e4d0, 0x1e4fa, 0x1e7e0, 0x1e7e7, 0x1e7e8, 0x1e7ec, 0x1e7ed, 0x1e7ef,
  0x1e7f0, 0x1e7ff, 0x1e800, 0x1e8c5, 0x1e8c7, 0x1e8d7, 0x1e900, 0x1e94c, 0x1e950, 0x1e95a, 0x1e95e, 0x1e960, 0x1ec71,
  0x1ecb5, 0x1ed01, 0x1ed3e, 0x1ee00, 0x1ee04, 0x1ee05, 0x1ee20, 0x1ee21, 0x1ee23, 0x1ee24, 0x1ee25, 0x1ee27, 0x1ee28,
  0x1ee29, 0x1ee33, 0x1ee34, 0x1ee38, 0x1ee39, 0x1ee3a, 0x1ee3b, 0x1ee3c, 0x1ee42, 0x1ee43, 0x1ee47, 0x1ee48, 0x1ee49,
  0x1ee4a, 0x1ee4b, 0x1ee4c, 0x1ee4d, 0x1ee50, 0x1ee51, 0x1ee53, 0x1ee54, 0x1ee55, 0x1ee57, 0x1ee58, 0x1ee59, 0x1ee5a,
  0x1ee5b, 0x1ee5c, 0x1ee5d, 0x1ee5e, 0x1ee5f, 0x1ee60, 0x1ee61, 0x1ee63, 0x1ee64, 0x1ee65, 0x1ee67, 0x1ee6b, 0x1ee6c,
  0x1ee73, 0x1ee74, 0x1ee78, 0x1ee79, 0x1ee7d, 0x1ee7e, 0x1ee7f, 0x1ee80, 0x1ee8a, 0x1ee8b, 0x1ee9c, 0x1eea1, 0x1eea4,
  0x1eea5, 0x1eeaa, 0x1eeab, 0x1eebc, 0x1eef0, 0x1eef2, 0x1f000, 0x1f02c, 0x1f030, 0x1f094, 0x1f0a0, 0x1f0af, 0x1f0b1,
  0x1f0c0, 0x1f0c1, 0x1f0d0, 0x1f0d1, 0x1f0f6, 0x1f100, 0x1f1ae, 0x1f1e6, 0x1f203, 0x1f210, 0x1f23c, 0x1f240, 0x1f249,
  0x1f250, 0x1f252, 0x1f260, 0x1f266, 0x1f300, 0x1f6d8, 0x1f6dc, 0x1f6ed, 0x1f6f0, 0x1f6fd, 0x1f700, 0x1f777, 0x1f77b,
  0x1f7da, 0x1f7e0, 0x1f7ec, 0x1f7f0, 0x1f7f1, 0x1f800, 0x1f80c, 0x1f810, 0x1f848, 0x1f850, 0x1f85a, 0x1f860, 0x1f888,
  0x1f890, 0x1f8ae, 0x1f8b0, 0x1f8b2, 0x1f900, 0x1fa54, 0x1fa60, 0x1fa6e, 0x1fa70, 0x1fa7d, 0x1fa80, 0x1fa89, 0x1fa90,
  0x1fabe, 0x1fabf, 0x1fac6, 0x1face, 0x1fadc, 0x1fae0, 0x1fae9, 0x1faf0, 0x1faf9, 0x1fb00, 0x1fb93, 0x1fb94, 0x1fbcb,
  0x1fbf0, 0x1fbfa, 0x20000, 0x2a6e0, 0x2a700, 0x2b73a, 0x2b740, 0x2b81e, 0x2b820, 0x2cea2, 0x2ceb0, 0x2ebe1, 0x2ebf0,
  0x2ee5e, 0x2f800, 0x2fa1e, 0x30000, 0x3134b, 0x31350, 0x323b0, 0xe0100, 0xe01f0
};
static int printable(I c) {            /* c >= 0x80: printable unless an odd number of changes are <= c */
  I lo = 0, hi = sizeof pchange / sizeof *pchange;
  while (lo < hi) { I m = (lo + hi) / 2; if (pchange[m] <= c) lo = m + 1; else hi = m; }
  return !(lo & 1);
}
