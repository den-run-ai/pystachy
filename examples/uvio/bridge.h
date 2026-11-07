#ifndef PYSTACHY_UVIO_BRIDGE_H
#define PYSTACHY_UVIO_BRIDGE_H
#include <stdint.h>

void *uvio_create(int64_t capacity, int64_t byte_limit);
int64_t uvio_submit(void *loop, const char *address, int64_t port,
                    const char *input, uint64_t input_size, int64_t timeout_ms);
int uvio_step(void *loop, int block);
int uvio_peek(void *loop, int64_t *info, uint64_t length);
int uvio_release(void *loop, int64_t id);
int uvio_cancel(void *loop, int64_t id);
int uvio_close(void *loop);
const char *uvio_error_name(int status);
const char *uvio_version(void);
#endif
