/* Bounded byte scanning: an independent scalar oracle, every byte/alignment/tail,
   general delimiter predicates, exact guard-page bounds and deterministic bulk-work
   counts. Include the real runtime and link runtime.py's IR, as unicodeprobe does.
   Usage: make bytescanprobe. Timings are not pass/fail criteria. */
static long long scan_words, scan_bytes, scan_bulk;
#define BYTESCAN_WORD() (scan_words++)
#define BYTESCAN_BYTE() (scan_bytes++)
#define BYTESCAN_BULK() (scan_bulk++)
#include "../runtime.c"
#include <sys/wait.h>

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static Str *current;
static I *roots[] = {(I *)&current};
static long long checks;
static _Noreturn void bad(const char *what) { fprintf(stderr, "bytescanprobe: %s\n", what); exit(1); }
static I scalar(const char *p, I start, I end, unsigned first, unsigned second, unsigned below) {
  for (I i = start; i < end; i++) {
    unsigned c = (unsigned char)p[i];
    if (c == first || c == second || c < below) return i;
  }
  return end;
}
static void check(const char *p, I start, I end, unsigned first, unsigned second, unsigned below) {
  I expected = scalar(p, start, end, first, second, below);
  I actual = byte_scan(p, start, end, first, second, below);
  checks++;
  if (actual != expected) {
    fprintf(stderr, "bytescanprobe: [%lld,%lld), delimiters %u/%u, below %u: got %lld, expected %lld\n",
            (long long)start, (long long)end, first, second, below, (long long)actual, (long long)expected);
    exit(1);
  }
}
static void bytes_and_alignments(void) {
  char storage[32 + 64];
  /* Both ordinary ASCII and high bytes surround each possible byte at every
     offset. Cross-word borrowing must not hide a hit or invent an earlier one. */
  for (unsigned fill = 0; fill < 2; fill++) {
    memset(storage, fill ? 0xA5 : 'x', sizeof storage);
    for (I alignment = 0; alignment < 32; alignment++) {
      char *p = storage + alignment;
      for (unsigned c = 0; c < 256; c++) {
        for (I at = 0; at < 64; at++) {
          p[at] = (char)c;
          check(p, 0, 64, 34, 92, 32);
          p[at] = fill ? (char)0xA5 : 'x';
        }
      }
    }
  }
  /* Every short length and scalar tail, with a stop at every position or EOF. */
  for (I alignment = 0; alignment < 32; alignment++) {
    char *p = storage + alignment;
    for (I n = 0; n <= 64; n++) {
      memset(p, 0xFF, (size_t)n);
      check(p, 0, n, 34, 92, 32);
      for (I at = 0; at < n; at++) {
        p[at] = at % 3 == 0 ? 34 : at % 3 == 1 ? 92 : 0;
        check(p, 0, n, 34, 92, 32);
        p[at] = (char)0xFF;
      }
    }
  }
}
static void long_spans(void) {
  char storage[32 + 512];
  for (I alignment = 0; alignment < 32; alignment++) {
    char *p = storage + alignment;
    memset(p, 0xA5, 512);
    for (unsigned c = 0; c < 256; c++) for (I at = 0; at < 512; at++) {
      p[at] = (char)c;
      check(p, 0, 512, 34, 92, 32);
      p[at] = (char)0xA5;
    }
  }
}
static void predicates(void) {
  char text[96];
  /* All thresholds, including the non-SWAR 129..256 range, against every byte.
     Delimiters differ from the tested byte and the 0xFF ordinary prefix. */
  for (unsigned below = 0; below <= 256; below++) {
    for (unsigned c = 0; c < 256; c++) {
      memset(text, 0xFF, sizeof text);
      text[47] = (char)c;
      check(text, 0, sizeof text, (c + 1) % 255, (c + 2) % 255, below);
    }
  }
  /* Every delimiter is selectable, in either slot and with equal delimiters. */
  for (unsigned c = 0; c < 256; c++) {
    unsigned other = c ^ 255, fill = (c + 1) & 255;
    if (fill == other) fill = (fill + 1) & 255;
    memset(text, (int)fill, sizeof text);
    for (I at = 0; at < (I)sizeof text; at++) {
      text[at] = (char)c;
      check(text, 0, sizeof text, c, other, 0);
      check(text, 0, sizeof text, other, c, 0);
      check(text, 0, sizeof text, c, c, 0);
      text[at] = (char)fill;
    }
  }
  /* Distinct terminator classes compete within and across words. Byte 1 after
     byte 0 specifically exercises the neighboring lane's subtraction borrow. */
  for (I a = 0; a < 64; a++) for (I b = a + 1; b < 65; b++) {
    for (unsigned kind = 0; kind < 3; kind++) {
      memset(text, 0xA5, sizeof text);
      text[a] = kind == 0 ? 34 : kind == 1 ? 92 : 0;
      text[b] = kind == 0 ? 92 : kind == 1 ? 0 : 1;
      check(text, 0, sizeof text, 34, 92, 32);
      check(text, a + 1, sizeof text, 34, 92, 32);
    }
  }
  uint32_t random = UINT32_C(0x8625A17);
  for (I trial = 0; trial < 4096; trial++) {
    for (I i = 0; i < (I)sizeof text; i++) {
      random ^= random << 13; random ^= random >> 17; random ^= random << 5;
      text[i] = (char)(random >> 24);
    }
    I start = random % 33, end = start + (random >> 8) % (sizeof text - start + 1);
    check(text, start, end, random & 255, (random >> 8) & 255, trial % 3 ? 32 : 0);
  }
}
static void wrapper(void) {
  char text[96];
  for (I i = 0; i < (I)sizeof text; i++) text[i] = (char)((i * 73 + 17) & 255);
  current = pys_str(text, sizeof text);
  current->dict_hash = 12345;
  current->chars1 = 19;  /* The scanner must not inspect or change a text cache. */
  for (I end = 0; end <= current->len; end++) for (I start = 0; start <= end; start++) {
    I expected = scalar(text, start, end, 34, 92, 32);
    if (pys_bytes_scan(current, start, end, 34, 92, 32) != expected) bad("public wrapper offset");
    checks++;
  }
  if (current->len != sizeof text || current->dict_hash != 12345 || current->chars1 != 19 ||
      memcmp(current->s, text, sizeof text)) bad("scanner changed its input or metadata");
}
static void error(I start, I end, I first, I second, I below, const char *kind) {
  int fds[2];
  if (pipe(fds)) bad("error pipe");
  pid_t child = fork();
  if (child < 0) bad("error fork");
  if (!child) {
    close(fds[0]);
    if (dup2(fds[1], STDERR_FILENO) < 0) _exit(2);
    close(fds[1]);
    std_out.closed = std_err.closed = 1;
    pys_bytes_scan(current, start, end, first, second, below);
    _exit(3);
  }
  close(fds[1]);
  char text[256]; size_t n = 0;
  while (n < sizeof text - 1) {
    ssize_t got = read(fds[0], text + n, sizeof text - 1 - n);
    if (got < 0 && errno == EINTR) continue;
    if (got < 0) bad("error read");
    if (!got) break;
    n += (size_t)got;
  }
  close(fds[0]); text[n] = 0;
  int status;
  if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) != 1 ||
      strncmp(text, kind, strlen(kind))) bad("invalid argument did not raise expected exception");
  checks++;
}
static void errors(void) {
  current = cstr("abcdefgh");
  const I ranges[][2] = {{-1, 8}, {0, -1}, {0, 9}, {9, 9}, {5, 4}, {INT64_MIN, 8}, {0, INT64_MAX}};
  for (I i = 0; i < (I)(sizeof ranges / sizeof *ranges); i++)
    error(ranges[i][0], ranges[i][1], 34, 92, 32, "IndexError:");
  const I predicates[][3] = {{-1, 92, 32}, {256, 92, 32}, {INT64_MIN, 92, 32},
    {INT64_MAX, 92, 32}, {34, -1, 32}, {34, 256, 32}, {34, 92, -1}, {34, 92, 257}};
  for (I i = 0; i < (I)(sizeof predicates / sizeof *predicates); i++)
    error(0, 8, predicates[i][0], predicates[i][1], predicates[i][2], "ValueError:");
}
static void guarded(void) {
  long page = sysconf(_SC_PAGESIZE);
  if (page < 256) bad("page size");
  char *mapping = mmap(NULL, (size_t)page * 3, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (mapping == MAP_FAILED || mprotect(mapping + page, (size_t)page, PROT_READ | PROT_WRITE)) bad("guard mapping");
  char *right = mapping + 2 * page;
  /* Right guard catches reads of even one byte beyond end, including empty input.
     Varying length moves the first address through every word alignment. */
  for (I n = 0; n <= 512; n++) {
    char *p = right - n;
    memset(p, 0xA5, (size_t)n);
    check(p, 0, n, 34, 92, 32);
    for (I start = 0; start <= n; start++) check(p, start, n, 34, 92, 32);
    for (I at = 0; at < n; at++) {
      p[at] = at & 1 ? 34 : 92;
      check(p, 0, n, 34, 92, 32);
      p[at] = (char)0xA5;
    }
  }
  /* Left guard catches loads rounded below the first readable byte. */
  char *left = mapping + page;
  memset(left, 0xFF, 512);
  for (I n = 0; n <= 512; n++) {
    check(left, 0, n, 0, 1, 128);
    check(left, 0, n, 34, 92, 32);
  }
  if (munmap(mapping, (size_t)page * 3)) bad("guard unmap");
}
static void bulk_work(void) {
  char text[16384]; memset(text, 0xA5, sizeof text);
  for (I n = 4096; n <= (I)sizeof text; n *= 2) {
    current = pys_str(text, n);
    I tick = gc_tick;
    scan_words = scan_bytes = scan_bulk = 0;
    if (pys_bytes_scan(current, 0, n, 34, 92, 32) != n) bad("long ordinary span result");
    /* A removed bulk path still passes the scalar oracle; these counts reject it.
       Permit a small prefix/tail rather than depending on one exact loop shape. */
#ifdef PYSTACHY_STRINGZILLA
    if (scan_bulk != 1 || scan_words || scan_bytes) bad("StringZilla path was not called");
#else
    if (scan_words < n / 16 || scan_words > n / 4 || scan_bytes > 64) bad("long span did not skip words");
#endif
    if (gc_tick != tick) bad("scanner allocates");
    printf("bytescanprobe: %lld bytes, %lld word probes, %lld scalar probes, %lld external calls\n", (long long)n, scan_words, scan_bytes, scan_bulk);
  }
}
int main(void) {
  gc_init(__builtin_frame_address(0), roots, 1);
  bytes_and_alignments(); long_spans(); predicates(); wrapper(); errors(); guarded(); bulk_work();
  printf("bytescanprobe: %lld scalar-oracle/bounds checks, guard pages and bulk-work bounds passed\n", checks);
  return 0;
}
