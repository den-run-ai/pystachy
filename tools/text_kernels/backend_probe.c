/* Report the adapter backend inside the native or instrumented process. */
#include <stdio.h>

extern const char *pystachy_stringzilla_backend(void);

int main(void) {
    return puts(pystachy_stringzilla_backend()) < 0;
}
