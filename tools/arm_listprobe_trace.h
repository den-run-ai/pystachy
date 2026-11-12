/* Temporary diagnostic branch only. Included by a generated scratch runtime.c.
   These records are intentionally absent from the collector's root inventory.
   Addresses are complemented until dumping, including the stack bounds.
   No allocation or output occurs while marking. Instrumentation can change
   register allocation, so the unmodified probe is always run independently. */
typedef struct {
  uintptr_t segment, object, source_slot, source_value;
  I size, collection;
  int root, large;
} ArmDiagMark;
/* GC_NO_ROOT(arm_diag_marks): observations, never strong references. */
static ArmDiagMark arm_diag_marks[4096];
static unsigned arm_diag_count, arm_diag_overflow;
static int arm_diag_in_roots;
static uintptr_t arm_diag_stack_begin, arm_diag_stack_end;

static void arm_diag_record(Seg *s, uintptr_t i, const W *p, uintptr_t value) {
  if (arm_diag_count == sizeof arm_diag_marks / sizeof *arm_diag_marks) {
    arm_diag_overflow++;
    return;
  }
  ArmDiagMark *entry = &arm_diag_marks[arm_diag_count++];
  entry->segment = ~(uintptr_t)s;
  entry->object = ~((uintptr_t)s->start + i * s->size);
  entry->source_slot = ~(uintptr_t)p;
  entry->source_value = ~value;
  entry->size = s->size;
  entry->collection = gc_n;
  entry->root = arm_diag_in_roots;
  entry->large = s->large;
}

__attribute__((noinline)) static void arm_diag_dump(List *kept) {
  fprintf(stderr, "DIAG gc_live=%lld gc_n=%lld records=%u overflow=%u stack_begin=%p stack_end=%p\n",
          (long long)gc_live, (long long)gc_n, arm_diag_count, arm_diag_overflow,
          (void *)~arm_diag_stack_begin, (void *)~arm_diag_stack_end);
  for (Seg *s = bigs; s; s = s->next)
    fprintf(stderr, "DIAG surviving_big segment=%p start=%p size=%lld kind=%d\n",
            (void *)s, (void *)s->start, (long long)s->size, s->k);
  for (unsigned i = 0; i < arm_diag_count; i++) {
    ArmDiagMark *entry = &arm_diag_marks[i];
    fprintf(stderr, "DIAG first_mark collection=%lld origin=%s segment=%p object=%p size=%lld large=%d source_slot=%p source_value=%p\n",
            (long long)entry->collection, entry->root ? "root" : "heap",
            (void *)~entry->segment, (void *)~entry->object, (long long)entry->size,
            entry->large, (void *)~entry->source_slot, (void *)~entry->source_value);
  }
  fprintf(stderr, "DIAG retained_lists=%lld\n", (long long)kept->len);
  for (I i = 0; i < kept->len; i++) {
    List *list = (List *)kept->a[i];
    fprintf(stderr, "DIAG list index=%lld header=%p length=%lld capacity=%lld backing=%p\n",
            (long long)i, (void *)list, (long long)list->len,
            (long long)list->cap, (void *)list->a);
  }
}

