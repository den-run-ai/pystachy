#include <stdio.h>
_Thread_local int tv = 41;
int get_tv(void) { printf("tv=%d at %p\n", tv, (void*)&tv); return ++tv; }
