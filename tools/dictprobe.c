/* Probe counts of the runtime's dict tables, for keys that defeat a weak hash or probe sequence
   (issue #4: keys i << 46 used to pile up in one cluster), with sequential keys as the control.
   It includes runtime.c with DICT_PROBE counting the index slots that lookups, insertions and
   rebuilds visit (normal builds define it as nothing), builds a dict of N keys of each pattern
   (N = 4000, 8000, 16000 and 30000 unless given), and reports the slots visited per operation:
     insert   per insertion, the rebuilds that growth makes included
     hit      per lookup of each key
     miss     per lookup of N keys that are absent
     deleted  per lookup of each key after every other one was deleted (the holes stay)
     longest  the most slots that one of those lookups visited
   It checks the values, the insertion order and the deletions on the way. The counts depend on
   nothing but the runtime, so they are the same on every machine, and the run fails if a pattern
   averages more than LIMIT slots per lookup: a hash that behaved randomly would average at most
   1.5 per miss and 2 per lookup after the deletions, at the fullest table (a third of the slots
   in use). The times (nanoseconds per insertion or hit, best of three) are for information only.
   usage: make dictprobe   (clang -O2 tools/dictprobe.c -o build/dictprobe -lm; build/dictprobe [N...]) */
#include <time.h>
static long long probes;
#define DICT_PROBE() (probes++)
#include "../runtime.c"

#define LIMIT 3.0
I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }   /* the programs' callbacks: no objects here */
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static const char *pats[] = {"i", "-i", "i << 46", "i << 32", "i * 1000", "(i // 128) << 32 | i % 128",
  "random", "f\"k{i}\"", "f\"{i:08}\"", "\"x\" * 64 + str(i)", "str(i) + \"x\" * 64", "letter case of i's bits"};
#define NPAT (I)(sizeof pats / sizeof *pats)
#define MAXN 65536                     /* 2N keys i << 46 fit in 63 bits */
static List *keys;                     /* the collector's roots */
static Dict *dict;
static I *roots[] = {(I *)&keys, (I *)&dict};
static long long longest;

#define X64 "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
static I key(I p, I i) {               /* key i of pattern p; the 2N keys of a pattern are distinct */
  char b[96]; uint64_t z;
  switch (p) {
  case 0: return i;
  case 1: return -i;
  case 2: return i << 46;
  case 3: return i << 32;
  case 4: return i * 1000;
  case 5: return (i / 128) << 32 | i % 128;
  case 6: z = (uint64_t)i * 0x9E3779B97F4A7C15ULL + 1;   /* SplitMix64: distinct for distinct i */
    z = (z ^ z >> 30) * 0xBF58476D1CE4E5B9ULL; z = (z ^ z >> 27) * 0x94D049BB133111EBULL; return (I)(z ^ z >> 31);
  case 7: return (I)pys_str(b, snprintf(b, sizeof b, "k%lld", (long long)i));
  case 8: return (I)pys_str(b, snprintf(b, sizeof b, "%08lld", (long long)i));
  case 9: return (I)pys_str(b, snprintf(b, sizeof b, "%s%lld", X64, (long long)i));
  case 10: return (I)pys_str(b, snprintf(b, sizeof b, "%lld%s", (long long)i, X64));
  default: for (int j = 0; j < 20; j++) b[j] = (char)('a' + j - (i >> j & 1) * 32);   /* "aBcD..." */
    return (I)pys_str(b, 20);
  }
}
static I lookup(I k, I dflt) {         /* d.get(k, dflt), noting the longest lookup */
  long long b = probes; I v = pys_dict_get(dict, k, dflt);
  if (probes - b > longest) longest = probes - b;
  return v;
}
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static _Noreturn void bad(I p, I n, const char *what) { fprintf(stderr, "dictprobe: %s, %lld keys: %s\n", pats[p], (long long)n, what); exit(1); }
static double run(I p, I n, long long c[4]) {  /* c: slots visited by insert, hit, miss, deleted */
  double t = 1e9;
  for (int r = 0; r < 3; r++) {
    dict = pys_dict_new(p >= 7, 0);
    probes = 0; double t0 = now();
    for (I i = 0; i < n; i++) pys_dict_set(dict, keys->a[i], i);
    c[0] = probes; probes = 0;
    for (I i = 0; i < n; i++) if (lookup(keys->a[i], -1) != i) bad(p, n, "wrong value");
    if (now() - t0 < t) t = now() - t0;
    c[1] = probes;
  }
  probes = 0;
  for (I i = n; i < 2 * n; i++) if (lookup(keys->a[i], -1) != -1) bad(p, n, "absent key found");
  c[2] = probes;
  for (I i = 0; i < n; i += 2) if (pys_dict_pop(dict, keys->a[i]) != i) bad(p, n, "wrong value popped");
  probes = 0;
  for (I i = 0; i < n; i++) if (lookup(keys->a[i], -1) != (i % 2 ? i : -1)) bad(p, n, "deleted key found, or kept key lost");
  c[3] = probes;
  I j = 1;                             /* the survivors, in insertion order */
  for (I e = pys_dict_next(dict, 0, n / 2, 0), k = 0; e >= 0; e = pys_dict_next(dict, e + 1, n / 2, ++k), j += 2)
    if (pys_dict_key(dict, e) != keys->a[j] || pys_dict_val(dict, e) != j) bad(p, n, "insertion order lost");
  if (j != n + 1) bad(p, n, "survivors lost");
  return t / (2 * n) * 1e9;
}
int main(int argc, char **argv) {
  gc_init(__builtin_frame_address(0), roots, 2);
  I ns[8] = {4000, 8000, 16000, 30000}, nn = 4, fails = 0;
  double worst = 0;
  if (argc > 1) for (nn = 0; nn + 1 < argc && nn < 8; nn++) ns[nn] = atoll(argv[nn + 1]) & ~(I)1;
  for (I k = 0; k < nn; k++) if (ns[k] < 2 || ns[k] > MAXN) { fprintf(stderr, "usage: dictprobe [N...]   (2 <= N <= %d)\n", MAXN); return 2; }
  for (int r = 0; r < 100; r++) {      /* the heap grows to its working size before the timings */
    dict = pys_dict_new(0, 0);
    for (I i = 0; i < 30000; i++) pys_dict_set(dict, i, i);
  }
  printf("%-28s %6s %7s %6s %6s %8s %8s %6s\n", "keys", "n", "insert", "hit", "miss", "deleted", "longest", "ns/op");
  for (I p = 0; p < NPAT; p++)
    for (I k = 0; k < nn; k++) {
      I n = ns[k]; long long c[4];
      keys = pys_list_new(2 * n);
      for (I i = 0; i < 2 * n; i++) keys->a[keys->len++] = key(p, i);
      longest = 0;
      double t = run(p, n, c);
      printf("%-28s %6lld %7.2f %6.2f %6.2f %8.2f %8lld %6.1f\n", pats[p], (long long)n, (double)c[0] / n,
             (double)c[1] / n, (double)c[2] / n, (double)c[3] / n, longest, t);
      for (int m = 1; m < 4; m++) {
        if ((double)c[m] / n > worst) worst = (double)c[m] / n;
        if ((double)c[m] / n > LIMIT) fails++;
      }
    }
  printf("worst average: %.2f slots per lookup (limit %.1f)\n", worst, LIMIT);
  if (fails) fprintf(stderr, "dictprobe: %lld averages above %.1f slots per lookup\n", (long long)fails, LIMIT);
  return fails != 0;
}
