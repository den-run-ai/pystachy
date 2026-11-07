#ifndef PYSTACHY_EXAMPLE_NETIO_H
#define PYSTACHY_EXAMPLE_NETIO_H

#include <stdint.h>

/* Internal scalar ABI for the opt-in netio example, not a runtime ABI.
   Calls borrow their arguments only until return. Unless specified otherwise,
   failures return -errno captured before cleanup; success is nonnegative. */
#define NIO_MAX_READ_BYTES (16 * 1024 * 1024)
#define NIO_MAX_EVENTS 4096
#define NIO_MAX_WAIT_MS 1000

int nio_socket(void);
int nio_socketpair(int64_t *out); /* two owned descriptors on success */
int nio_bind(int fd, const char *host, int port);
int nio_listen(int fd, int backlog);
int nio_accept(int fd);
int nio_connect_ex(int fd, const char *host, int port); /* 0 or -errno */
int nio_setblocking(int fd, int flag);
int nio_getblocking(int fd);
int nio_sockname(int fd, int peer, int64_t *out); /* host-order IPv4, port */
int nio_shutdown(int fd, int how);
int nio_close(int fd); /* do not retry close after EINTR */
int nio_option(int fd, int level, int option, int value, int set);
int nio_constant(int code); /* 1..8: SOL_SOCKET, REUSEADDR, ERROR, SNDBUF,
                              RCVBUF, SHUT_RD, SHUT_WR, SHUT_RDWR */
const char *nio_strerror(int code); /* copied by the binding before another call */
int64_t nio_send(int fd, const char *data, int64_t length);
int64_t nio_recv(int fd, int64_t limit, int64_t *out);
int64_t nio_read(int fd, int64_t limit, int64_t *out);
/* recv/read put a malloc-owned buffer in out[0], or zero for empty/error.
   The caller copies the returned byte count and frees the buffer in finally. */
void nio_free(void *buffer);

int nio_selector_create(void); /* close with nio_close */
/* op: 1 add, 2 modify, 3 delete. Events: read=1, write=2.
   old_events describes the existing registration (zero for add). The token
   must stay unchanged on modify and change on unregister/re-register. */
int nio_selector_ctl(int selector, int op, int fd, int events,
                     int old_events, int64_t token);
/* out has 2*maxevents int64 slots: (token, event mask) pairs. kqueue may return
   separate read/write records for one token; the binding combines them.
   timeout_ms must be 0..NIO_MAX_WAIT_MS. The binding owns monotonic deadlines
   and retries EINTR. No descriptor or caller buffer is retained by this shim. */
int nio_selector_wait(int selector, int maxevents, int timeout_ms, int64_t *out);

#endif
