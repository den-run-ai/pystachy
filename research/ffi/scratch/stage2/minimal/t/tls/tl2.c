static __thread long depth;
long bump(void) { return ++depth; }
long other(void) { return 7; }
