static __thread long depth;
static long plain;
long bump(void) { plain++; return ++depth * 1000 + plain; }
