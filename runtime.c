/* Pystachy runtime: memory, strings, lists, dicts, formatting, printing and I/O.
   `pystachy build` links it into every program as LLVM bitcode, so LLVM inlines these
   helpers across the program boundary (whole-program optimization); `pystachy run`
   links a precompiled object instead, since the JIT tier does not inline.
   Value model: every container slot is 8 bytes (int, float bits, bool, or pointer). */
#define _GNU_SOURCE
#include <ctype.h>
#include <errno.h>
#include <stdarg.h>
#include <math.h>
#include <signal.h>
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

static _Noreturn void oom(void) { fflush(stdout); fputs("MemoryError\n", stderr); exit(1); }
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
   CPython reports it, with status 120 */
static int out_errno;
static void out_flush(void) { if (fflush(stdout) && !out_errno) out_errno = errno; }
void pys_finish(void);                 /* every way out of the program runs it (lli skips atexit handlers) */
_Noreturn void pys_fail(const char *m) { out_flush(); fprintf(stderr, "%s\n", m); pys_finish(); exit(1); }
_Noreturn void pys_raise(Str *kind, Str *msg) {     /* raise kind(msg): CPython's last traceback line */
  out_flush();
  fwrite(kind->s, 1, kind->len, stderr);
  if (msg->len) { fputs(": ", stderr); fwrite(msg->s, 1, msg->len, stderr); }
  fputc('\n', stderr);
  pys_finish();
  if (!strcmp(kind->s, "KeyboardInterrupt")) { fflush(NULL); signal(SIGINT, SIG_DFL); raise(SIGINT); }   /* status 130 */
  exit(1);
}
void pys_exit(I c) { pys_finish(); exit((int)c); }
_Noreturn void pys_exit_msg(Str *msg) {          /* sys.exit(msg): msg to stderr, status 1 */
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
I pys_ord(Str *s) {                    /* a byte, or one UTF-8 encoded character */
  unsigned char c = s->len ? s->s[0] : 0; I n = c >= 0xF0 ? 4 : c >= 0xE0 ? 3 : c >= 0xC2 ? 2 : 1, cp = c & (0x7F >> n);
  if (s->len == n && n > 1) {
    for (I k = 1; k < n; k++) { if ((s->s[k] & 0xC0) != 0x80) { cp = -1; break; } cp = cp << 6 | (s->s[k] & 0x3F); }
    if (cp >= (n == 2 ? 0x80 : n == 3 ? 0x800 : 0x10000) && cp <= 0x10FFFF) return cp;
  }
  if (s->len != 1) {
    char b[96]; snprintf(b, 96, "TypeError: ord() expected a character, but string of length %lld found", (long long)s->len); pys_fail(b);
  }
  return (unsigned char)s->s[0];
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
static Str *pad(Str *s, I w, int left) {
  if (s->len >= w) return s;
  Str *r = pys_alloc_atomic(sizeof(Str) + w + 1); r->len = w; memset(r->s, ' ', w);
  memcpy(r->s + (left ? 0 : w - s->len), s->s, s->len); return r;
}
Str *pys_str_ljust(Str *s, I w) { return pad(s, w, 1); }
Str *pys_str_rjust(Str *s, I w) { return pad(s, w, 0); }
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
I pys_f2i(double d);
static _Noreturn void badlit(const char *what, I base, Str *s) {
  Buf b = {0}; char t[64];
  put(&b, what, strlen(what));
  if (base >= 0) put(&b, t, snprintf(t, 64, " with base %lld", (long long)base));
  put(&b, ": ", 2); repr_str(&b, s); put(&b, "", 1); pys_fail(b.p);
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
I pys_int_str(Str *s, I base) {
  if (base != 0 && (base < 2 || base > 36)) pys_fail("ValueError: int() base must be >= 2 and <= 36, or 0");
  Str *t = asciinum(s);
  const char *p = t->s, *e = t->s + t->len; I b0 = base;
  while (p < e && aws(*p)) p++;
  while (e > p && aws(e[-1])) e--;
  int neg = 0;
  if (p < e && (*p == '+' || *p == '-')) neg = *p++ == '-';
  if (e - p >= 2 && p[0] == '0') {
    int pb = (p[1] | 32) == 'x' ? 16 : (p[1] | 32) == 'o' ? 8 : (p[1] | 32) == 'b' ? 2 : 0;
    if (pb && (base == 0 || base == pb)) { base = pb; p += 2; if (p < e && *p == '_') p++; }
  }
  if (base == 0) {                             /* decimal: no leading zeros unless the value is 0 */
    base = 10;
    if (p < e && *p == '0') for (const char *q = p; q < e; q++) if (*q != '0' && *q != '_') badlit("ValueError: invalid literal for int()", b0, s);
  }
  uint64_t u = 0, lim = neg ? (uint64_t)1 << 63 : ((uint64_t)1 << 63) - 1; int any = 0, ovf = 0;
  for (; p < e; p++) {
    if (*p == '_' && any && p + 1 < e && p[1] != '_') continue;
    int dv = digitv(*p);
    if (dv >= base) badlit("ValueError: invalid literal for int()", b0, s);
    if (u > (lim - dv) / base) ovf = 1; else u = u * base + dv;
    any = 1;
  }
  if (!any) badlit("ValueError: invalid literal for int()", b0, s);
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
I pys_powmod(I a, I b, I m) {                 /* pow(a, b, m): 128-bit remainders and products cannot overflow */
  if (!m) pys_fail("ValueError: pow() 3rd argument cannot be 0");
  if (b < 0) pys_fail("ValueError: pow() 2nd argument cannot be negative when 3rd argument specified");
  __int128 r = 1 % m, x = (__int128)a % m;    /* INT64_MIN % -1 traps in 64 bits */
  for (; b; b >>= 1) { if (b & 1) r = r * x % m; x = x * x % m; }
  I v = (I)r;
  return v && (v < 0) != (m < 0) ? v + m : v;   /* the result has the sign of m, as in Python */
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
  if (a == 0 && b < 0) pys_fail("ZeroDivisionError: 0.0 cannot be raised to a negative power");
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
  const char *f = "<__main__.%s object at %p>"; int n = snprintf(0, 0, f, cls->s, p);
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
static void repr_str(Buf *b, Str *s) {
  char q = memchr(s->s, '\'', s->len) && !memchr(s->s, '"', s->len) ? '"' : '\'', t[8];
  put(b, &q, 1);
  for (I i = 0; i < s->len; i++) {
    unsigned char c = s->s[i];
    if (c == q || c == '\\') { t[0] = '\\'; t[1] = c; put(b, t, 2); }
    else if (c == '\n') put(b, "\\n", 2);
    else if (c == '\r') put(b, "\\r", 2);
    else if (c == '\t') put(b, "\\t", 2);
    else if (c < 32 || c == 127) put(b, t, snprintf(t, 8, "\\x%02x", c));
    else put(b, (char *)&c, 1);
  }
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
static _Noreturn void failf(const char *f, ...);
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
I pys_list_pop(List *l, I i) {
  if (!l->len) pys_fail("IndexError: pop from empty list");
  i = idx(i, l->len, "IndexError: pop index out of range");
  I v = l->a[i]; memmove(l->a + i, l->a + i + 1, (l->len - i - 1) * 8); l->len--; return v;
}
void pys_list_del(List *l, I i) { i = idx(i, l->len, "IndexError: list assignment index out of range"); memmove(l->a + i, l->a + i + 1, (l->len - i - 1) * 8); l->len--; }
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
void pys_list_clear(List *l) { l->len = 0; }
List *pys_list_add(List *a, List *b) { List *r = pys_list_new(a->len + b->len); pys_list_extend(r, a); pys_list_extend(r, b); return r; }
void pys_list_imul(List *l, I n) {               /* xs *= n, in place */
  I m = l->len;
  if (n <= 0 || !m) { l->len = 0; return; }
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
/* list.sort is CPython 3.13's timsort (Objects/listobject.c, designed in listsort.txt), ported
   function by function so that it makes exactly CPython's sequence of `<` comparisons, which is
   observable (where NaNs end up, what an __lt__ with side effects sees): each ISLT(x, y) there is
   one LT(x, y) here, in the same order. Natural runs, extended to minrun items by binary insertion,
   are merged as the powersort policy decides; a merge copies the shorter run to a buffer and
   gallops while one side keeps winning. No key=; CPython's type-specialized compares make the same
   comparisons as opv. As in CPython (ob_item NULL, allocated -1), the list looks empty while it is
   sorted, and growing it from __lt__ makes the sort fail afterwards. Items can exist only in the
   merge buffer when a comparison runs the collector: the buffer is scanned memory, and it and the
   item array stay in volatile fields of the MergeState (MS) on the stack. Speed: the common item
   types compare inline, and binary insertion and the one-at-a-time merging of ints and floats use
   selects, as random data makes their branches unpredictable (merging strings or objects keeps
   the branches, which let the CPU fetch their data early). */
#define MIN_GALLOP 7
typedef struct { I s, n; int power; } Run;          /* a pending run: start, length, powersort power */
typedef struct {
  const char *d; int kind; I cls;                   /* element descriptor; its kind (below) and class id */
  I *volatile a, *volatile t;                       /* item array and merge buffer: roots for the collector */
  I n, nt, min_gallop; int np; Run p[64];           /* items; buffer size; the stack of pending runs */
} MS;
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
static void merge_lo(MS *ms, I *a, I na, I *b, I nb) {   /* na <= nb: a goes to the buffer, merge from the left */
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
      if (LT(*pb, *pa)) { *d++ = *pb++; bc++; ac = 0; if (--nb == 0 || bc >= mg) break; }
      else { *d++ = *pa++; ac++; bc = 0; if (--na == 1 || ac >= mg) break; }
    }
    if (!nb) goto done;
    if (na == 1) goto copyb;
    mg++;
    do {                                            /* galloping */
      mg -= mg > 1; ms->min_gallop = mg;
      ac = k = gallop(ms, *pb, pa, na, 0, 1);
      if (k) { memcpy(d, pa, k * 8); d += k; pa += k; na -= k; if (na == 1) goto copyb; if (!na) goto done; }
      *d++ = *pb++;
      if (--nb == 0) goto done;
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
static void merge_hi(MS *ms, I *a, I na, I *b, I nb) {   /* na > nb: b goes to the buffer, merge from the right */
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
      if (LT(pb[-1], pa[-1])) { *--d = *--pa; ac++; bc = 0; if (--na == 0 || ac >= mg) break; }
      else { *--d = *--pb; bc++; ac = 0; if (--nb == 1 || bc >= mg) break; }
    }
    if (!na) goto done;
    if (nb == 1) goto copya;
    mg++;
    do {
      mg -= mg > 1; ms->min_gallop = mg;
      ac = k = na - gallop(ms, pb[-1], a, na, na - 1, 1);
      if (k) { d -= k; pa -= k; memmove(d, pa, k * 8); if ((na -= k) == 0) goto done; }
      *--d = *--pb;
      if (--nb == 1) goto copya;
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
static void merge_at(MS *ms, int i) {               /* merge pending runs i and i+1 */
  Run *p = ms->p;
  I *a = ms->a + p[i].s, na = p[i].n, *b = a + na, nb = p[i + 1].n, k;
  p[i].n = na + nb;
  if (i == ms->np - 3) p[i + 1] = p[i + 2];
  ms->np--;
  k = gallop(ms, *b, a, na, 0, 1);                  /* a[:k] and then b[nb:] are in place already */
  a += k;
  if (!(na -= k) || !(nb = gallop(ms, a[na - 1], b, nb, nb - 1, 0))) return;
  if (na <= nb) merge_lo(ms, a, na, b, nb); else merge_hi(ms, a, na, b, nb);
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
void pys_list_sort_r(List *l, Str *d, I reverse) {
  I n = l->len, cap = l->cap, *a = l->a, m = n, r = 0, c = *d->s;
  MS ms = {.d = d->s, .kind = c == 'i' || c == 'b' ? INT : c == 'f' ? FLOAT : c == 's' ? STR : c == 'O' ? OBJ : 0,
           .cls = c == 'O' ? ocls(d->s + 1) : 0, .a = a, .n = n, .min_gallop = MIN_GALLOP};
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
  if (l->a != sorting) pys_fail("ValueError: list modified during sort");
  l->len = n; l->cap = cap; l->a = a;
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
      if (maxsplit-- == 0) { I j = n; while (j > i && ws(s->s[j - 1])) j--; pys_list_append(l, (I)pys_str(s->s + i, j - i)); return l; }
      I j = i; while (j < n && !ws(s->s[j])) j++;
      pys_list_append(l, (I)pys_str(s->s + i, j - i)); i = j;
    }
  }
  if (!sep->len) pys_fail("ValueError: empty separator");
  for (I j; maxsplit-- != 0 && (j = find(s, sep, i)) >= 0; i = j + sep->len) pys_list_append(l, (I)pys_str(s->s + i, j - i));
  pys_list_append(l, (I)pys_str(s->s + i, n - i));
  return l;
}

/* ---------- dicts: CPython's compact ordered layout ---------- */
/* Entries (keys, vals, hs) are kept in insertion order. A deleted entry stays in place as a
   hole with hash 0 until the table is rebuilt, so deletion is O(1) and a loop's position
   stays valid. idx is open addressing over 2*size slots holding entry + 1 (0 empty, -1
   deleted). The sizes are CPython 3.13's, because they decide what a loop that changes its
   dict sees: size is a power of two >= 8 (0 before the first insertion and after clear()),
   at most size*2/3 entries are used, and inserting into a full table rebuilds it without
   holes at the size for len*3. */
static uint64_t hsh(Dict *d, I k) {
  uint64_t h;
  if (d->kind) {
    Str *s = (Str *)k; h = 1469598103934665603ULL;
    for (I i = 0; i < s->len; i++) h = (h ^ (unsigned char)s->s[i]) * 1099511628211ULL;
  } else h = (uint64_t)k * 0x9E3779B97F4A7C15ULL;
  h ^= h >> 29;
  return h ? h : 1;                                  /* 0 marks a hole */
}
static I keysize(I n) { I s = 8; while (s < n) s *= 2; return s; }   /* calculate_log2_keysize */
static I dfind(Dict *d, I k, uint64_t h, I *free) {    /* k's idx slot or -1; *free: where to insert k */
  I m = d->size * 2 - 1, f = -1;
  if (!d->size) return -1;
  for (I i = h & m;; i = (i + 1) & m) {
    int32_t e = d->idx[i];
    if (!e) { if (free) *free = f < 0 ? i : f; return -1; }
    if (e < 0) { if (f < 0) f = i; }
    else if (d->hs[e - 1] == h && (d->keys[e - 1] == k || (d->kind && pys_str_eq((Str *)d->keys[e - 1], (Str *)k)))) return i;
  }
}
static void build(Dict *d, Dict *src, I size) {      /* d := src's items in a table of this size, holes dropped */
  I u = size * 2 / 3, *k = pys_alloc(u * 8), *v = pys_alloc(u * 8), n = 0, m = size * 2 - 1;
  uint64_t *hs = pys_alloc_atomic(u * 8); int32_t *ix = pys_alloc_atomic(size * 8);
  for (I e = 0; e < src->n; e++) {
    if (!src->hs[e]) continue;
    I i = src->hs[e] & m;
    while (ix[i]) i = (i + 1) & m;
    k[n] = src->keys[e]; v[n] = src->vals[e]; hs[n] = src->hs[e]; ix[i] = (int32_t)++n;
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
   used = len when the loop started, count = items produced so far */
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
I pys_dict_prev(Dict *d, I e, I used) {
  changed(d, used);
  if (e >= d->n) e = d->n - 1;
  while (e >= 0 && !d->hs[e]) e--;
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
Dict *pys_dict_copy(Dict *d) {                        /* dict.copy(): clone a table with few holes, else rebuild */
  Dict *r = pys_dict_new(d->kind, 0);
  if (!d->len) return r;
  if (d->len < d->n * 2 / 3) { build(r, d, keysize((d->len * 3 + 1) / 2)); return r; }
  I u = d->size * 2 / 3;                              /* the clone keeps the holes, as CPython's does */
  r->keys = pys_alloc(u * 8); r->vals = pys_alloc(u * 8); r->hs = pys_alloc_atomic(u * 8); r->idx = pys_alloc_atomic(d->size * 8);
  memcpy(r->keys, d->keys, d->n * 8); memcpy(r->vals, d->vals, d->n * 8); memcpy(r->hs, d->hs, d->n * 8);
  memcpy(r->idx, d->idx, d->size * 8); r->len = d->len; r->n = d->n; r->size = d->size;
  return r;
}

/* ---------- formatting: f"{x:spec}" ---------- */
/* CPython's format-spec mini-language for int (and bool), float and str:
   [[fill]align][sign][z][#][0][width][grouping][.precision][type]. Widths count code points;
   other types accept only an empty spec, which the compiler turns into str(). */
static _Noreturn void failf(const char *f, ...) {
  char b[512]; va_list a; va_start(a, f); vsnprintf(b, sizeof b, f, a); va_end(a); pys_fail(b);
}
static I ulen(const char *p, I n) { I k = 0; for (I i = 0; i < n; i++) k += ((unsigned char)p[i] & 0xC0) != 0x80; return k; }
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
/* Text files as CPython's open() makes them, over C stdio: its modes and errors, newline
   translation, and positions when a "+" file switches between reading and writing. A
   file that becomes unreachable is closed by the collector (CPython closes it when its last
   reference goes); the compiler closes a file used in one expression, open(p).read(),
   right after that use. sys.stdin, sys.stdout and sys.stderr are files too. */
typedef struct {
  FILE *f; Str *name, *mode;
  I rd, wr, closed, nl, last, std;   /* nl: newline None 0, "" 1, "\n" 2, "\r" 3, "\r\n" 4; last: 1 wrote, 2 read */
  I rstart, rcons;                   /* where the current run of reads began; raw bytes it consumed */
} File;
static File std_in, std_out, std_err;
static const char *errcls(int e) {     /* CPython's OSError subclass for an errno */
  return e == ENOENT ? "FileNotFoundError" : e == EEXIST ? "FileExistsError" : e == EISDIR ? "IsADirectoryError" :
    e == ENOTDIR ? "NotADirectoryError" : e == EACCES || e == EPERM ? "PermissionError" : e == EINTR ? "InterruptedError" :
    e == EPIPE ? "BrokenPipeError" : e == ECONNRESET ? "ConnectionResetError" : "OSError";
}
static void wcheck(File *f) {          /* a write that failed raises, as in CPython; its data is dropped */
  if (!ferror(f->f)) return;
  int e = errno; char b[160];
  __fpurge(f->f); clearerr(f->f);
  snprintf(b, sizeof b, "%s: [Errno %d] %s", errcls(e), e, strerror(e)); pys_fail(b);
}
void pys_finish(void) {                /* at exit: the collector's report; a failed flush of stdout is
                                          reported as CPython does, status 120 */
  static int done;
  if (done++) return;
  if (gc_stats) gc_report();
  if (!fflush(stdout) && !ferror(stdout) && !out_errno) return;
  int e = out_errno ? out_errno : errno;
  __fpurge(stdout); clearerr(stdout);
  fprintf(stderr, "Exception ignored on flushing sys.stdout:\n%s: [Errno %d] %s\n", errcls(e), e, strerror(e));
  fflush(NULL); _exit(120);
}
static File **files;                   /* the open files, malloc'd: the collector does not see them */
static I cfiles;
static int gc_marked(const void *p) {
  uintptr_t w = (uintptr_t)p; Seg **m, *s;
  if (w - gc_lo >= gc_hi - gc_lo || !(m = pmap[w >> 30]) || !(s = m[w >> 12 & 0x3ffff])) return 1;
  I i = s->large ? 0 : (I)((w - (uintptr_t)s->start) * s->inv >> 40);
  return s->mark[i >> 6] >> (i & 63) & 1;
}
static void files_sweep(void) {        /* after marking: close the open files nothing refers to */
  I j = 0;
  for (I i = 0; i < nfiles; i++) {
    File *f = files[i];
    if (f->closed) continue;
    if (!gc_marked(f)) { fclose(f->f); f->closed = 1; continue; }
    files[j++] = f;
  }
  nfiles = j;
}
static _Noreturn void oserr(const char *path);
static _Noreturn void closed_err(void) { pys_fail("ValueError: I/O operation on closed file."); }
__attribute__((minsize)) void pys_init(int argc, char **argv, char *sb, I **roots, I nroots) {   /* first call of @main */
  gc_init(sb, roots, nroots);
  args = pys_list_new(argc); for (int i = 0; i < argc; i++) pys_list_append(args, (I)cstr(argv[i]));
  char *a0 = getenv("PYSTACHY_ARGV0");  /* pystachy run: sys.argv[0] is the script, as in CPython */
  if (a0 && argc) { args->a[0] = (I)cstr(a0); unsetenv("PYSTACHY_ARGV0"); }
  std_in.f = stdin; std_in.rd = 1; std_in.nl = 2; std_in.std = 1;   /* CPython's stdin: newline="\n" */
  std_out.f = stdout; std_out.wr = 1; std_out.std = 1;
  std_err.f = stderr; std_err.wr = 1; std_err.std = 1;
  signal(SIGPIPE, SIG_IGN);            /* as CPython: a closed pipe is an error, not a signal */
}
List *pys_argv(void) { return args; }
File *pys_std(I i) { return i == 0 ? &std_in : i == 1 ? &std_out : &std_err; }
void pys_write(Str *s, I fd) { File *f = fd == 2 ? &std_err : &std_out; if (f->closed) closed_err(); fwrite(s->s, 1, s->len, f->f); wcheck(f); }
void pys_flush(void) { fflush(stdout); }
Str *pys_input(Str *prompt) {
  char *line = 0; size_t cap = 0;
  pys_write(prompt, 1); fflush(stdout);
  if (std_in.closed) closed_err();
  ssize_t n = getline(&line, &cap, stdin);
  if (n < 0) pys_fail("EOFError: EOF when reading a line");
  if (n && line[n - 1] == '\n') n--;
  Str *s = pys_str(line, n); free(line); return s;
}
static int nul(Str *s) { return memchr(s->s, 0, s->len) != 0; }
File *pys_open(Str *path, Str *mode, Str *enc, Str *nl, I buffering) {
  int x = 0, r = 0, w = 0, a = 0, plus = 0, t = 0, b = 0;   /* CPython's checks, in its order */
  for (I i = 0; i < mode->len; i++) {
    char c = mode->s[i];
    int *p = c == 'x' ? &x : c == 'r' ? &r : c == 'w' ? &w : c == 'a' ? &a : c == '+' ? &plus : c == 't' ? &t : c == 'b' ? &b : 0;
    if (!p || *p) failf("ValueError: invalid mode: '%s'", mode->s);
    *p = 1;
  }
  if (t && b) pys_fail("ValueError: can't have text and binary mode at once");
  if (x + r + w + a > 1) pys_fail("ValueError: must have exactly one of create/read/write/append mode");
  if (b) pys_fail("NotImplementedError: binary mode is not supported (no bytes type)");
  if (!buffering) pys_fail("ValueError: can't have unbuffered text I/O");
  if (nul(path)) pys_fail("ValueError: embedded null byte");
  if (!(x + r + w + a)) pys_fail("ValueError: Must have exactly one of create/read/write/append mode and at most one plus");
  for (I i = 0; i < nfiles && !gc_off; i++)   /* a writer to this path that nothing refers to any more has */
    if (files[i]->wr && !files[i]->closed && pys_str_eq(files[i]->name, path)) { collect(); break; }   /* been closed in CPython */
  char m[4] = {x || w ? 'w' : r ? 'r' : 'a', plus ? '+' : 0, 0, 0};
  if (x) m[plus ? 2 : 1] = 'x';        /* glibc: O_EXCL */
  FILE *f = fopen(path->s, m);
  if (!f && (errno == EMFILE || errno == ENFILE) && !gc_off) { collect(); f = fopen(path->s, m); }   /* unreachable files closed */
  if (!f) oserr(path->s);
  struct stat st;
  if (!fstat(fileno(f), &st) && S_ISDIR(st.st_mode)) { fclose(f); errno = EISDIR; oserr(path->s); }
  if (a) fseek(f, 0, SEEK_END);        /* CPython starts an append file at its end */
  if (enc) {                           /* checked once the file is open, as CPython does */
    static const char *ok = " utf8 u8 utf latin1 latin l1 iso88591 iso8859 8859 cp819 ibm819 csisolatin1 iso885911987 isoir100 ";
    char e[24] = " "; I n = 1;
    for (I i = 0; i < enc->len && n < 22; i++) if (enc->s[i] != '-' && enc->s[i] != '_') e[n++] = tolower((unsigned char)enc->s[i]);
    e[n++] = ' '; e[n] = 0;
    if (enc->len > 20 || nul(enc) || !strstr(ok, e)) {
      fclose(f); failf("NotImplementedError: only UTF-8 and Latin-1 files are supported, not encoding '%s'", enc->s);
    }
  }
  I k = !nl ? 0 : !nl->len ? 1 : !strcmp(nl->s, "\n") ? 2 : !strcmp(nl->s, "\r") ? 3 : !strcmp(nl->s, "\r\n") ? 4 : -1;
  if (k < 0 || (nl && nul(nl))) { fclose(f); failf("ValueError: illegal newline value: %s", nl->s); }
  File *o = pys_alloc(sizeof(File));
  o->f = f; o->name = path; o->mode = mode; o->rd = r || plus; o->wr = !r || plus; o->nl = k;
  o->rstart = a ? ftell(f) : 0;
  if (nfiles == cfiles && !(files = realloc(files, (cfiles = 2 * cfiles + 16) * sizeof *files))) oom();
  files[nfiles++] = o;
  return o;
}
static void use(File *f, int rd) {     /* check a read (rd) or write, and reposition between them */
  if (f->closed) closed_err();
  if (rd ? !f->rd : !f->wr) pys_fail(rd ? "io.UnsupportedOperation: not readable" : "io.UnsupportedOperation: not writable");
  if (f->std || f->last == (rd ? 2 : 1)) return;
  if (rd) {                            /* after writing: read from where the writes ended */
    fflush(f->f); f->rstart = ftell(f->f); f->rcons = 0;
  } else if (f->last == 2) {           /* after reading: CPython's text layer read ahead in 8 KiB chunks */
    I end = f->rstart + (f->rcons + 8191) / 8192 * 8192, size;
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
Str *pys_file_read(File *f, I n) {     /* n < 0: to the end; else n characters */
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
    if ((c & 0xC0) != 0x80 && n >= 0 && k++ == n) { unget(f, c); break; }   /* the next character starts */
    char ch = getnl(f, c); put(&b, &ch, 1);
  }
  return done(&b);
}
Str *pys_file_readline(File *f) {      /* a line ends as newline= says: None "\n" after translation; "" any of
                                          "\n" "\r" "\r\n"; otherwise exactly that string */
  use(f, 1); Buf b = {0}; int c;
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
  return done(&b);
}
List *pys_file_readlines(File *f) {
  List *l = pys_list_new(0);
  for (Str *s; (s = pys_file_readline(f))->len;) pys_list_append(l, (I)s);
  return l;
}
I pys_file_write(File *f, Str *s) {   /* newline="\r" or "\r\n" writes "\n" as that */
  use(f, 0);
  if (f->nl < 3) fwrite(s->s, 1, s->len, f->f);
  else for (I i = 0; i < s->len; i++) if (s->s[i] != '\n') putc(s->s[i], f->f); else fputs(f->nl == 3 ? "\r" : "\r\n", f->f);
  wcheck(f);
  return s->len;
}
void pys_file_writelines(File *f, List *l) { for (I i = 0; i < l->len; i++) pys_file_write(f, (Str *)l->a[i]); }
void pys_file_flush(File *f) { if (f->closed) closed_err(); fflush(f->f); wcheck(f); }
void pys_file_close(File *f) {
  if (f->closed) return;
  f->closed = 1;
  if (f->std) { fflush(f->f); return; }   /* sys.stdout.close(): the stream stays open underneath */
  if (fclose(f->f)) { char b[160]; snprintf(b, sizeof b, "OSError: [Errno %d] %s", errno, strerror(errno)); pys_fail(b); }
}
I pys_file_closed(File *f) { return f->closed; }
Str *pys_file_name(File *f) { return f->name ? f->name : cstr(f == &std_in ? "<stdin>" : f == &std_out ? "<stdout>" : "<stderr>"); }
Str *pys_file_mode(File *f) { return f->mode ? f->mode : cstr(f == &std_in ? "r" : "w"); }
I pys_system(Str *c) {
  if (nul(c)) pys_fail("ValueError: embedded null byte");
  return system(c->s);                 /* like CPython, without flushing stdout first */
}
I pys_getpid(void) { return getpid(); }
I pys_exists(Str *p) { return !nul(p) && access(p->s, F_OK) == 0; }
Str *pys_getenv(Str *k, Str *dflt) { char *v = nul(k) ? 0 : getenv(k->s); return v ? cstr(v) : dflt; }

/* ---------- temporary directories: tempfile.mkdtemp, os.remove, os.rmdir ---------- */
static _Noreturn void oserr(const char *path) {         /* raise CPython's OSError subclass for errno */
  int e = errno; Buf b = {0}; char t[32];
  const char *k = errcls(e), *m = strerror(e);
  put(&b, k, strlen(k)); put(&b, t, snprintf(t, sizeof t, ": [Errno %d] ", e)); put(&b, m, strlen(m)); put(&b, ": ", 2);
  repr_str(&b, cstr(path)); put(&b, "", 1); pys_fail(b.p);
}
void pys_remove(Str *p) { if (nul(p)) pys_fail("ValueError: remove: embedded null character in path"); if (unlink(p->s)) oserr(p->s); }
void pys_rmdir(Str *p) { if (nul(p)) pys_fail("ValueError: rmdir: embedded null character in path"); if (rmdir(p->s)) oserr(p->s); }
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
