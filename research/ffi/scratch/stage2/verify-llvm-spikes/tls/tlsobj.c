__thread long tv = 41;           /* initialised TLS: .tdata */
static __thread long cnt;        /* zero TLS: .tbss */
long get_tv(void) { return tv; }
long bump(void) { return ++cnt; }
void *addr_tv(void) { return &tv; }
