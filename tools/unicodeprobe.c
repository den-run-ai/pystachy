/* Deterministic checks for the public str code-point cache and byte cursors (#120).
   Read cache fields before len(): repeated appends must keep a populated cache, so
   len-after-append cannot become a quadratic scan. Raw-byte joins exercise the
   continuation-byte invalidation rule. The real collector runs normally and under
   PYSTACHY_GC_STRESS=1. Like dictprobe, link with runtime.py's generated IR.
   usage: make unicodeprobe */
static long long text_steps;
#define TEXT_PROBE() (text_steps++)
#include "../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static Str *current;
static List *held;
static I *roots[] = {(I *)&current, (I *)&held};
static _Noreturn void bad(const char *what) { fprintf(stderr, "unicodeprobe: %s\n", what); exit(1); }
static Str *hold(Str *s) { pys_list_append(held, (I)s); return s; }
static void cached(Str *s, I n, const char *what) {
  if (s->chars1 != n + 1 || pys_text_len(s) != n) bad(what);
}
static void cache(void) {
  char text[4096]; memset(text, 'a', sizeof text);
  current = pys_str(text, sizeof text);
  if (current->chars1 || pys_text_len(current) != sizeof text) bad("lazy ASCII length");
  for (I i = 0; i < 1000; i++) cached(current, sizeof text, "repeated ASCII length");
  current = cstr("");
  Str *a = hold(pys_text_chr('a')), *accent = hold(pys_text_chr(0xE9));
  for (I i = 0; i < 8192; i++) {
    current = pys_str_iadd(current, a, i != 0);
    cached(current, i + 1, "ASCII len after owned append rescans");
  }
  Str *snapshot = hold(current);
  current = pys_str_iadd(current, accent, 0);
  cached(snapshot, 8192, "append modifies aliased string cache");
  for (I i = 0; i < 1024; i++) {
    cached(current, 8193 + i, "Unicode len after owned append rescans");
    current = pys_str_iadd(current, accent, 1);
  }
  cached(current, 9217, "last Unicode append");
  if (current->len != 10242) bad("logical cache replaced the byte length");
  Str *sum = hold(pys_str_add(a, accent));
  cached(sum, 2, "cached add");
  cached(hold(pys_str_mul(sum, 5)), 10, "cached repeat");
  cached(hold(pys_str_cat(3, a, accent, sum, a, a, a, a, a)), 4, "cached concatenation");
  Str *unknown = hold(cstr("\xC3\xA9"));
  if (unknown->chars1) bad("uncached multibyte input");
  current = pys_str_iadd(current, unknown, 1);
  if (current->chars1 || pys_text_len(current) != 9218) bad("uncached suffix invalidation");
  collect();
  cached(current, 9218, "cache lost across collection");
  cached(snapshot, 8192, "aliased string lost across collection");
}
static void seams(void) {
  /* Each raw fragment decodes separately as one-byte fallbacks. Joining them
     creates a valid UTF-8 character, so their cached counts must not be added. */
  Str *lead = hold(pys_str("\xC3", 1)), *tail = hold(pys_str("\xA9", 1));
  cached(lead, 1, "raw leading byte"); cached(tail, 1, "raw continuation byte");
  current = pys_str_add(lead, tail);
  if (current->chars1 || pys_text_len(current) != 1) bad("add caches invalid raw seam");
  current = pys_str_iadd(lead, tail, 0);
  if (current->chars1 || pys_text_len(current) != 1) bad("append caches invalid raw seam");
  Str *left = hold(pys_str("\xF0\x9F", 2)), *right = hold(pys_str("\xA6\x8A", 2));
  if (pys_text_len(left) != 2 || pys_text_len(right) != 2) bad("raw fallback length");
  current = pys_str_cat(3, left, cstr(""), right, left, left, left, left, left);
  if (current->chars1 || pys_text_len(current) != 1 || pys_ord(current) != 0x1F98A) bad("concat caches invalid raw seam");
  Str *raw = hold(pys_str("\x80\xC2", 2));
  if (pys_text_len(raw) != 2) bad("raw repeat input");
  current = pys_str_mul(raw, 2);
  if (current->chars1 || pys_text_len(current) != 3) bad("repeat caches invalid raw seam");
  /* A continuation byte after a complete ASCII character stays a raw byte. */
  current = pys_str_add(hold(cstr("a")), tail);
  if (pys_text_len(current) != 2) bad("conservative raw seam invalidation");
}
static void slice_seams(void) {
  current = cstr("abcdef");
  current = pys_text_slice_step(current, NONE, NONE, 2);
  cached(current, 3, "ASCII stepped slice lost its known count");
  current = cstr("a\xC3\xA9\xE4\xB8\xAD\xF0\x9F\xA6\x8A");
  current = pys_text_slice_step(current, NONE, NONE, 2);
  cached(current, 2, "Unicode stepped slice lost its known count");
  /* Selecting isolated malformed bytes can assemble valid UTF-8. The selected
     item count is then not the decoded result length, in either slice path. */
  const char *raw[] = {"\xC3x\xA9x", "\xA9x\xC3", "\xC3\xA9x\xF0x\x9Fx\xA6x\x8Ax",
                      "\x8Ax\xA6x\x9Fx\xF0x\xC3\xA9"};
  for (I i = 0; i < 4; i++) {
    current = cstr(raw[i]);
    current = pys_text_slice_step(current, NONE, NONE, i & 1 ? -2 : 2);
    I expected = i < 2 ? 1 : 2;
    if (pys_text_len(current) != expected) bad("stepped slice caches a raw seam count");
    if (pys_ord(pys_text_get(current, 0)) != 0xE9) bad("stepped slice first decoded character");
    if (i >= 2 && pys_ord(pys_text_get(current, 1)) != 0x1F98A) bad("stepped slice joined UTF-8 character");
    cached(current, expected, "stepped slice cached result count");
  }
}
static void cursors(void) {
  const char text[] = "A\0\xC3\xA9\xE4\xB8\xAD\xF0\x9F\xA6\x8A\xED\xA0\x80Z";
  I at[] = {0, 1, 2, 4, 7, 11, 14, 15};
  I cp[] = {'A', 0, 0xE9, 0x4E2D, 0x1F98A, 0xD800, 'Z'};
  current = pys_str(text, sizeof text - 1);
  if (pys_text_len(current) != 7 || current->len != 15) bad("mixed code-point length");
  List *chars = pys_text_list(current);
  if (chars->len != 7) bad("code-point list length");
  for (I i = 0; i < 7; i++) {
    if (pys_ord(pys_text_at(current, at[i])) != cp[i] || pys_text_next(current, at[i]) != at[i + 1]) bad("forward byte cursor");
    if (pys_text_prev(current, at[i + 1]) != at[i]) bad("reverse byte cursor");
    if (pys_ord((Str *)chars->a[i]) != cp[i] || pys_ord(pys_text_get(current, i - 7)) != cp[i]) bad("list/indexed character");
  }
  if (pys_text_prev(current, 0) != -1 || pys_text_prev(cstr(""), 0) != -1) bad("reverse exhaustion sentinel");
  Str *reversed = hold(pys_text_slice_step(current, NONE, NONE, -1));
  cached(reversed, 7, "reverse slice cache");
  for (I i = 0; i < 7; i++) if (pys_ord(pys_text_get(reversed, i)) != cp[6 - i]) bad("reverse slice splits a code point");
  if (pys_bytes_get(current, 2) != 0xC3 || pys_ord(pys_str_get(current, 2)) != 0xC3 || pys_str_list(current)->len != 15)
    bad("byte/runtime operations changed semantics");
  collect();
  cached(current, 7, "cursor source lost across collection");
}
static void locality(void) {
  /* A mostly ASCII source file with one Unicode literal must not make repeated
     lexer-style src[i]/src[i+1] scan the whole prefix. Count actual mapping steps,
     including actual text_get calls, rather than putting timings in the gate. */
  const I n = 32768;
  Str *x = hold(pys_text_chr('x')), *accent = hold(pys_text_chr(0xE9));
  current = pys_str_add(pys_str_mul(x, n), accent);
  text_steps = 0;
  for (I i = 0; i < n; i++) {
    if (pys_ord(pys_text_get(current, i)) != 'x' ||
        pys_ord(pys_text_get(current, i + 1)) != (i + 1 == n ? 0xE9 : 'x')) bad("nearby indexed characters");
  }
  if (text_steps > 3 * n) bad("nearby get rescans prefixes");
  text_steps = 0;
  for (I i = n; i-- > 0;) if (pys_ord(pys_text_get(current, i)) != 'x') bad("backwards indexed characters");
  if (text_steps > 2 * n) bad("backwards get rescans prefixes");
  text_steps = 0;
  for (I i = 0; i < n; i++) if (pys_text_find(current, x, i, INT64_MAX) != i) bad("nearby bounded find");
  if (text_steps > 2 * n) bad("search default endpoint evicts interior hint");
  collect();
  for (I i = 0; i < 64; i++) if (text_hints[i].s) bad("GC kept a weak position hint");
  if (pys_ord(pys_text_get(current, n)) != 0xE9) bad("index after clearing weak hints");
  /* Force an in-place append with room already allocated. The suffix completes
     an invalid raw sequence, changing the mapping before the previous end. */
  current = pys_alloc_atomic(sizeof(Str) + 32);
  current->len = 5; memcpy(current->s, "\xC3\xA9x\xF0\x9F", 5);
  if (pys_text_len(current) != 4 || text_offset(current, 3) != 4) bad("raw append hint setup");
  Str *tail = hold(pys_str("\xA6\x8A", 2));
  text_offset(current, 3);   /* hold() may have collected under stress */
  Str *before = current;
  current = pys_str_iadd(current, tail, 1);
  if (current != before || text_hint_slot(current)->s == current) bad("owned append retained a position hint");
  if (pys_text_len(current) != 3 || pys_ord(pys_text_get(current, 2)) != 0x1F98A) bad("raw append changed cached segmentation");
}
int main(void) {
  gc_init(__builtin_frame_address(0), roots, 2);
  held = pys_list_new(32);
  cache(); seams(); slice_seams(); cursors(); locality();
  if (gc_stress && gc_n <= 3) bad("GC stress did not add allocation-triggered collections");
  puts("unicodeprobe: length/position caches, linear nearby indexing/search, raw seam invalidation, cursors and GC passed");
  return 0;
}
