/* Deterministic reachability oracle for both tracing orders. The model's edges
   live in malloc memory and are traversed independently of the collector. We
   seed explicit roots (without conservative stack noise), then use the actual
   scan/trace functions and compare every object's mark. No timing gate. */
#include "../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

enum { N = 6000, EDGES = 3, DEAD = N - 32 };
typedef struct { void *p; I bytes; int atomic, edge[EDGES]; } Model;
static Model *model;
static _Noreturn void bad(const char *message) {
  fprintf(stderr, "gcmarkprobe: %s\n", message); exit(1);
}

static void make_graph(void) {
  model = calloc(N, sizeof *model);
  if (!model) oom();
  /* A dense initial class spans several chunks. The rest exercise all small
     class sizes, atomic chunks and sliced large-object ranges. */
  for (int i = 0; i < N; i++) {
    I bytes = i < 4096 ? 24 : csize[i % (NK / 2)] - 1;
    if (bytes < 24) bytes = 24;
    if (i % 97 == 96) bytes = 24576;
    int atomic = i >= 4096 && i % 7 == 0;
    model[i].p = atomic ? pys_alloc_atomic(bytes) : pys_alloc(bytes);
    model[i].bytes = bytes; model[i].atomic = atomic;
    for (int j = 0; j < EDGES; j++) model[i].edge[j] = -1;
  }
  for (int i = 0; i < DEAD; i++) {
    /* Reverse chains repeatedly discover earlier bitmap words. Long jumps
       also revisit chunks already drained and form cross-chunk cycles. */
    model[i].edge[0] = i ? i - 1 : 4095;
    model[i].edge[1] = (i * 173 + 977) % DEAD;
    model[i].edge[2] = (i + 2047) % DEAD;
  }
  /* Dead objects hold a separate live-looking graph. A whole-chunk scan would
     wrongly mark it; atomic payloads are its only incoming references. */
  for (int i = DEAD; i < N; i++) model[i].edge[0] = DEAD + (i + 1) % (N - DEAD);
  for (int i = 4096; i < DEAD; i++) if (model[i].atomic) model[i].edge[0] = DEAD;
  for (int i = 0; i < N; i++) {
    W *p = model[i].p;
    for (int j = 0; j < EDGES; j++) if (model[i].edge[j] >= 0) {
      I at = j;
      if (model[i].bytes > SMALL && j == 2) at = model[i].bytes / (I)sizeof(W) - 1;
      p[at] = (W)model[model[i].edge[j]].p;
    }
  }
}

static void check_drained(void) {
  for (Seg *s = chunks; s; s = s->next) {
    if (s->used & 2) bad("chunk remained queued after tracing");
    if (gc_blocks && !(s->k & 1)) {
      if (pending(s) != s->mark + (CHUNK / s->size + 63) / 64)
        bad("reciprocal gave the wrong pending bitmap offset");
      if (pending(s)[0]) bad("pending word summary remained after tracing");
      for (I j = 0; j < (s->bump + 63) / 64; j++)
        if (pending(s)[j + 1]) bad("pending work remained after tracing");
    }
  }
  if (msp || gc_gray || gc_gray_tail) bad("tracer did not drain to a fixed point");
}

static void clear_marks(void) {
  check_drained();
  for (Seg *s = chunks; s; s = s->next) {
    memset(s->mark, 0, (s->bump + 63) / 64 * 8); s->nmark = 0;
  }
  for (Seg *s = bigs; s; s = s->next) { s->mark[0] = 0; s->nmark = 0; }
}

static void trace_model(int root, I offset, unsigned char *seen) {
  memset(seen, 0, N);
  int queue[N], head = 0, tail = 0;
  int count = root < 0 ? -root : 1;
  for (int i = 0; i < count; i++) {
    int k = root < 0 ? i : root;
    queue[tail++] = k; seen[k] = 1;
    W address = (W)((char *)model[k].p + offset);
    scan(&address, &address + 1);
  }
  while (head < tail) {
    Model *m = &model[queue[head++]];
    if (m->atomic) continue;
    for (int j = 0; j < EDGES; j++) {
      int k = m->edge[j];
      if (k >= 0 && !seen[k]) { seen[k] = 1; queue[tail++] = k; }
    }
  }
  trace();
  for (int i = 0; i < N; i++) if (!!gc_marked(model[i].p) != seen[i]) {
    fprintf(stderr, "gcmarkprobe: root=%d offset=%lld object=%d expected=%d actual=%d\n",
            root, (long long)offset, i, seen[i], !!gc_marked(model[i].p));
    bad("mark set differs from independent graph oracle");
  }
  check_drained();
}

static void check(int root, I offset) {
  unsigned char seen[N];
  trace_model(root, offset, seen);
  clear_marks();
}

/* The same pointer-sized bits have different ownership in these two union
   boxes. Only the scanned payload is an edge in this tiny independent graph.
   Explicit roots avoid accidental retention by the C stack, and an interior
   pointer to the payload must keep either box itself alive. */
static void union_boxes(void) {
  W *tail = pys_alloc(23), *live = pys_alloc(23), *dead = pys_alloc(23);
  live[0] = (W)tail;
  W *ref = pys_ubox(17, (I)live);
  W *scalar = pys_ubox_atomic(18, (I)dead);
  W roots[] = {(W)(ref + 1), (W)(scalar + 1)};
  scan(roots, roots + 2); trace();
  if (!gc_marked(ref) || !gc_marked(scalar) || !gc_marked(live) || !gc_marked(tail))
    bad("union box or its reference payload was not traced");
  if (gc_marked(dead)) bad("scalar union's pointer-looking bits retained an unrelated object");
  if (ref[0] != 17 || ref[1] != (W)live || scalar[0] != 18 || scalar[1] != (W)dead)
    bad("tracing changed an immutable union box");
  clear_marks();
  /* Optional reference conversion must retain its edge, and a promoting-int
     box must retain its Mpz pointer even when ordinary integer boxes are atomic. */
  W *optional = pys_ubox_opt(19, live, 0);
  Mpz *wide = pys_mpz_from_str(cstr("1180591620717411303424"), 10);
  W *big = pys_big_box(0, wide);
  W more[] = {(W)optional, (W)big};
  scan(more, more + 2); trace();
  if (!gc_marked(optional) || !gc_marked(live) || !gc_marked(tail) ||
      !gc_marked(big) || !gc_marked(wide))
    bad("optional union or promoting-int box lost its reference payload");
  if (gc_marked(ref) || gc_marked(scalar) || gc_marked(dead))
    bad("unreachable union box or payload was marked");
  clear_marks(); sweep();
}

/* Tiny slots have the most bitmap words. A reverse chain spans whole chunks
   and their highest usable summary indices, using only the first pointer word. */
static void small_boundaries(void) {
  for (int k = 0; k < NK / 2; k++) {
    uint64_t inv = ((1ULL << 40) + csize[k] - 1) / csize[k];
    if ((CHUNK * inv >> 40) != (uint64_t)(CHUNK / csize[k]) ||
        (CHUNK / csize[k] + 63) / 64 > 64) bad("pending offset/capacity arithmetic");
  }
  for (I bytes = 15; bytes <= 23; bytes += 8) {
    W **nodes = calloc(5000, sizeof *nodes);
    if (!nodes) oom();
    for (int i = 0; i < 5000; i++) {
      nodes[i] = pys_alloc(bytes);
      nodes[i][0] = i ? (W)nodes[i - 1] : 0;
    }
    W root = (W)((char *)nodes[4999] + bytes);
    scan(&root, &root + 1); trace();
    for (int i = 0; i < 5000; i++)
      if (!gc_marked(nodes[i]) || nodes[i][0] != (i ? (W)nodes[i - 1] : 0))
        bad("tiny-slot chain lost an object or edge");
    clear_marks(); sweep(); free(nodes);
  }
}

enum { PART = 4096, FRESH = PART / 2 };

static void check_survivors(void) {
  for (int i = 0; i < PART; i += 2) {
    W *p = model[i].p;
    if (p[0] != (W)model[(i + 2) % PART].p || p[1] || p[2])
      bad("partial sweep or refill changed a live graph field");
    if (model[i].bytes > SMALL && p[model[i].bytes / (I)sizeof(W) - 1])
      bad("partial sweep or refill changed a live large object's tail");
  }
}

static void mark_survivors(void **fresh, int count) {
  W root = (W)model[PART - 2].p;
  scan(&root, &root + 1); trace();
  check_drained();
  for (int i = 0; i < PART; i += 2)
    if (!gc_marked(model[i].p)) bad("partial-sweep survivor lost after refill");
  for (int i = 0; i < count; i++)
    if (gc_marked(fresh[i])) bad("unreachable replacement marked after refill");
}

/* Keep every other object of the dense class in a cycle. Unlike the complete
   teardown below, these sweeps retain chunks with holes and reuse their free
   lists after tracing borrowed Seg.avail. The malloc-backed model/fresh arrays
   remain outside the explicitly seeded root set. */
static void partial_refill(void) {
  unsigned char seen[N];
  for (int i = 0; i < N; i++) {
    W *p = model[i].p;
    for (int j = 0; j < EDGES; j++) {
      model[i].edge[j] = -1;
      I at = model[i].bytes > SMALL && j == 2 ? model[i].bytes / (I)sizeof(W) - 1 : j;
      p[at] = 0;
    }
    if (i < PART && !(i & 1)) {
      model[i].edge[0] = (i + 2) % PART;
      p[0] = (W)model[model[i].edge[0]].p;
    }
  }
  trace_model(PART - 2, 0, seen);
  for (int i = 0; i < N; i++)
    if (seen[i] != (i < PART && !(i & 1))) bad("partial-sweep model has an unexpected survivor");
  sweep();
  check_survivors();
  void **fresh = calloc(FRESH, sizeof *fresh);
  if (!fresh) oom();
  for (int round = 0; round < 2; round++) {
    int reused = 0;
    for (int k = 0; k < FRESH; k++) {
      I bytes = model[2 * k + 1].bytes;
      unsigned char *p = pys_alloc(bytes);
      fresh[k] = p;
      for (I j = 0; j < bytes + 1; j++) if (p[j]) bad("refilled object was not zeroed");
      uintptr_t a = (uintptr_t)p;
      for (int i = 0; i < PART; i++) {
        uintptr_t b = (uintptr_t)model[i].p;
        if (seen[i] && a < b + model[i].bytes + 1 && b < a + bytes + 1)
          bad("refill overlapped a live object");
        if (!seen[i] && a == b) reused++;
      }
      memset(p, 0xa5, bytes);         /* the next refill must clear reused storage */
    }
    if (!reused) bad("partial sweep failed to reuse any dead slot");
    check_survivors();
    mark_survivors(fresh, FRESH);
    sweep();
    check_survivors();
    /* With no allocations or deaths in surviving chunks, sweep skips rebuild;
       it must still reconstruct availability links that tracing borrowed. */
    mark_survivors(NULL, 0);
    sweep();
    check_survivors();
  }
  free(fresh);
}

int main(void) {
  gc_init(__builtin_frame_address(0), NULL, 0);
  /* Construction must not collect: malloc's model table is intentionally not
     a root, and these checks control exactly which object starts tracing. */
  gc_off = 1; gc_stress = 0;
  union_boxes();
  small_boundaries();
  for (int cycle = 0; cycle < 2; cycle++) {
    make_graph();
    check(-64, 0);                   /* a full pending word (including shift-by-64 boundary) */
    check(63, 0);                    /* the highest bit alone at discovery */
    check(4095, 0);
    check(4095, 13);                  /* unaligned interior pointer */
    check(4095, model[4095].bytes);  /* requested-size end pointer uses the slack */
    check(96, model[96].bytes);      /* large object's end pointer and late-slice edge */
    check(DEAD, 0);                  /* change roots, reuse the queues and bitmaps */
    check(4102, 0);                  /* atomic object must not trace its payload */
    partial_refill();
    free(model); model = NULL;
    sweep();                        /* zero marks free everything; repeat on recycled pages */
  }
  puts("gcmarkprobe: union ownership, exact reachability, cycles, backward edges, large slices, interior/slack roots, queue reuse and partial-sweep refill passed");
  return 0;
}
