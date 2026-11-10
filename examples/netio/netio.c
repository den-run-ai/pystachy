/* Optional native I/O bridge. It owns no managed Python objects and retains no
   argument buffers. Socket descriptors belong to the Python wrapper; readiness
   registrations belong to the kernel. Receive buffers have explicit ownership. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "netio.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <netinet/in.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#if defined(__linux__)
#include <sys/epoll.h>
#elif defined(__APPLE__)
#include <sys/event.h>
#include <sys/time.h>
#else
#error "The netio prototype supports Linux epoll and macOS kqueue only"
#endif

_Static_assert(sizeof(void *) == sizeof(int64_t), "netio requires 64-bit pointers");

static int cloexec(int fd) {
  int flags = fcntl(fd, F_GETFD);
  if (flags < 0) return -errno;
  return fcntl(fd, F_SETFD, flags | FD_CLOEXEC) < 0 ? -errno : 0;
}

static int socket_setup(int fd) {
  int error = cloexec(fd);
#if defined(__APPLE__)
  if (!error) {
    int enabled = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled)) < 0)
      error = -errno;
  }
#endif
  return error;
}

static int address(const char *host, int port, struct sockaddr_in *out) {
  if (!host || port < 0 || port > 65535) return -EINVAL;
  memset(out, 0, sizeof(*out));
  out->sin_family = AF_INET;
  out->sin_port = htons((uint16_t)port);
#if defined(__APPLE__)
  out->sin_len = sizeof(*out);
#endif
  /* Numeric addresses only: no resolver, worker pool or borrowed callback. */
  return inet_pton(AF_INET, host, &out->sin_addr) == 1 ? 0 : -EINVAL;
}

int nio_socket(void) {
#if defined(__linux__)
  int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
#else
  int fd = socket(AF_INET, SOCK_STREAM, 0);
#endif
  if (fd < 0) return -errno;
  int error = socket_setup(fd);
  if (error) { close(fd); return error; }
  return fd;
}

int nio_socketpair(int64_t *out) {
  if (!out) return -EINVAL;
  out[0] = out[1] = -1;
  int pair[2];
#if defined(__linux__)
  int result = socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, pair);
#else
  int result = socketpair(AF_UNIX, SOCK_STREAM, 0, pair);
#endif
  if (result < 0) return -errno;
  int error = socket_setup(pair[0]);
  if (!error) error = socket_setup(pair[1]);
  if (error) { close(pair[0]); close(pair[1]); return error; }
  out[0] = pair[0];
  out[1] = pair[1];
  return 0;
}

int nio_bind(int fd, const char *host, int port) {
  struct sockaddr_in value;
  int error = address(host, port, &value);
  if (error) return error;
  return bind(fd, (struct sockaddr *)&value, sizeof(value)) < 0 ? -errno : 0;
}

int nio_listen(int fd, int backlog) {
  /* socket.listen() clamps a negative backlog to zero. */
  return listen(fd, backlog < 0 ? 0 : backlog) < 0 ? -errno : 0;
}

int nio_accept(int fd) {
#if defined(__linux__)
  int accepted = accept4(fd, NULL, NULL, SOCK_CLOEXEC);
#else
  int accepted = accept(fd, NULL, NULL);
#endif
  if (accepted < 0) return -errno;
  int error = socket_setup(accepted);
  if (error) { close(accepted); return error; }
  return accepted;
}

int nio_connect_ex(int fd, const char *host, int port) {
  struct sockaddr_in value;
  int error = address(host, port, &value);
  if (error) return error;
  return connect(fd, (struct sockaddr *)&value, sizeof(value)) < 0 ? -errno : 0;
}

int nio_setblocking(int fd, int flag) {
  int flags = fcntl(fd, F_GETFL);
  if (flags < 0) return -errno;
  flags = flag ? flags & ~O_NONBLOCK : flags | O_NONBLOCK;
  return fcntl(fd, F_SETFL, flags) < 0 ? -errno : 0;
}

int nio_getblocking(int fd) {
  int flags = fcntl(fd, F_GETFL);
  return flags < 0 ? -errno : !(flags & O_NONBLOCK);
}

int nio_sockname(int fd, int peer, int64_t *out) {
  if (!out || (peer != 0 && peer != 1)) return -EINVAL;
  struct sockaddr_in value;
  socklen_t length = sizeof(value);
  memset(&value, 0, sizeof(value));
  int result = peer ? getpeername(fd, (struct sockaddr *)&value, &length)
                    : getsockname(fd, (struct sockaddr *)&value, &length);
  if (result < 0) return -errno;
  if (value.sin_family != AF_INET || length < sizeof(value)) return -EAFNOSUPPORT;
  out[0] = ntohl(value.sin_addr.s_addr);
  out[1] = ntohs(value.sin_port);
  return 0;
}

int nio_shutdown(int fd, int how) {
  return shutdown(fd, how) < 0 ? -errno : 0;
}

int nio_close(int fd) {
  /* A failed close must not be retried: the descriptor may already be reused. */
  return close(fd) < 0 ? -errno : 0;
}

int nio_option(int fd, int level, int option, int value, int set) {
  if (set != 0 && set != 1) return -EINVAL;
  /* These integer options have nonnegative results, so a negative return can
     unambiguously carry errno. Other options need their own typed contract. */
  if (level != SOL_SOCKET || (option != SO_REUSEADDR && option != SO_ERROR
      && option != SO_SNDBUF && option != SO_RCVBUF)) return -EOPNOTSUPP;
  if (set)
    return setsockopt(fd, level, option, &value, sizeof(value)) < 0 ? -errno : 0;
  socklen_t length = sizeof(value);
  if (getsockopt(fd, level, option, &value, &length) < 0) return -errno;
  return length == sizeof(value) ? value : -EINVAL;
}

int nio_constant(int code) {
  switch (code) {
  case 1: return SOL_SOCKET;
  case 2: return SO_REUSEADDR;
  case 3: return SO_ERROR;
  case 4: return SO_SNDBUF;
  case 5: return SO_RCVBUF;
  case 6: return SHUT_RD;
  case 7: return SHUT_WR;
  case 8: return SHUT_RDWR;
  default: return -EINVAL;
  }
}

const char *nio_strerror(int code) { return strerror(code); }

int64_t nio_send(int fd, const char *data, int64_t length) {
  if (length < 0 || (!data && length)) return -EINVAL;
  if ((uint64_t)length > (uint64_t)SSIZE_MAX) return -EOVERFLOW;
#if defined(__linux__)
  ssize_t sent = send(fd, data, (size_t)length, MSG_NOSIGNAL);
#else
  /* Every socket made by this bridge has SO_NOSIGPIPE on macOS. */
  ssize_t sent = send(fd, data, (size_t)length, 0);
#endif
  return sent < 0 ? -errno : (int64_t)sent;
}

static int64_t receive(int fd, int64_t limit, int64_t *out, int socket_read) {
  if (!out) return -EINVAL;
  *out = 0;
  if (limit < 0 || limit > NIO_MAX_READ_BYTES) return -EINVAL;
  /* CPython socket.recv(0) succeeds even on a closed socket. os.read(fd, 0)
     still enters the OS, which validates fd. Neither should wait for data. */
  if (!limit && socket_read) return 0;
  char *buffer = limit ? malloc((size_t)limit) : NULL;
  if (limit && !buffer) return -ENOMEM;
  ssize_t count = socket_read ? recv(fd, buffer, (size_t)limit, 0)
                              : read(fd, buffer, (size_t)limit);
  if (count <= 0) {
    int error = count < 0 ? errno : 0;
    free(buffer);
    return -error;
  }
  *out = (int64_t)(uintptr_t)buffer;
  return (int64_t)count;
}

int64_t nio_recv(int fd, int64_t limit, int64_t *out) {
  return receive(fd, limit, out, 1);
}

int64_t nio_read(int fd, int64_t limit, int64_t *out) {
  return receive(fd, limit, out, 0);
}

void nio_free(void *buffer) { free(buffer); }

int nio_selector_create(void) {
#if defined(__linux__)
  int fd = epoll_create1(EPOLL_CLOEXEC);
  return fd < 0 ? -errno : fd;
#else
  int fd = kqueue();
  if (fd < 0) return -errno;
  int error = cloexec(fd);
  if (error) { close(fd); return error; }
  return fd;
#endif
}

#if defined(__APPLE__)
static int kqueue_change(int selector, int fd, int bit, int add, int64_t token) {
  struct kevent event;
  EV_SET(&event, (uintptr_t)fd, bit == 1 ? EVFILT_READ : EVFILT_WRITE,
         add ? EV_ADD | EV_ENABLE : EV_DELETE, 0, 0, (void *)(uintptr_t)token);
  if (kevent(selector, &event, 1, NULL, 0, NULL) == 0) return 0;
  int error = errno;
  /* Closing an fd removes its kqueue registrations automatically. */
  return !add && error == ENOENT ? 0 : -error;
}
#endif

int nio_selector_ctl(int selector, int op, int fd, int events,
                     int old_events, int64_t token) {
  if (op < 1 || op > 3 || fd < 0 || token <= 0 || events < 0 || (events & ~3)
      || old_events < 0 || (old_events & ~3)) return -EINVAL;
  if ((op != 3 && !events) || (op == 1 && old_events)
      || (op != 1 && !old_events)) return -EINVAL;
#if defined(__linux__)
  struct epoll_event event;
  memset(&event, 0, sizeof(event));
  if (events & 1) event.events |= EPOLLIN;
  if (events & 2) event.events |= EPOLLOUT;
  event.data.u64 = (uint64_t)token;
  int action = op == 1 ? EPOLL_CTL_ADD : op == 2 ? EPOLL_CTL_MOD : EPOLL_CTL_DEL;
  return epoll_ctl(selector, action, fd, &event) < 0 ? -errno : 0;
#else
  int desired = op == 3 ? 0 : events;
  int changed = 0;
  /* The wrapper retains tokens across modify. Restore the previous mask if
     either filter change fails, including partial registration failures. */
  for (int bit = 1; bit <= 2; bit <<= 1) {
    if (!((desired | old_events) & bit)) continue;
    int error = kqueue_change(selector, fd, bit, !!(desired & bit), token);
    if (error) {
      for (int undo = 1; undo <= 2; undo <<= 1) {
        if (!(changed & undo)) continue;
        int rollback = kqueue_change(selector, fd, undo, !!(old_events & undo), token);
        if (rollback) return -EIO;
      }
      return error;
    }
    changed |= bit;
  }
  return 0;
#endif
}

int nio_selector_wait(int selector, int maxevents, int timeout_ms, int64_t *out) {
  if (!out || maxevents < 1 || maxevents > NIO_MAX_EVENTS
      || timeout_ms < 0 || timeout_ms > NIO_MAX_WAIT_MS) return -EINVAL;
#if defined(__linux__)
  struct epoll_event *ready = malloc((size_t)maxevents * sizeof(*ready));
  if (!ready) return -ENOMEM;
  int count = epoll_wait(selector, ready, maxevents, timeout_ms);
  if (count < 0) {
    int error = errno;
    free(ready);
    return -error;
  }
  for (int i = 0; i < count; i++) {
    uint32_t events = ready[i].events;
    int mask = 0;
    if (events & (EPOLLIN | EPOLLPRI)) mask |= 1;
    if (events & EPOLLOUT) mask |= 2;
    if (events & (EPOLLERR | EPOLLHUP)) mask |= 3;
    out[2 * i] = (int64_t)ready[i].data.u64;
    out[2 * i + 1] = mask;
  }
#else
  struct kevent *ready = malloc((size_t)maxevents * sizeof(*ready));
  if (!ready) return -ENOMEM;
  struct timespec timeout = {timeout_ms / 1000, (timeout_ms % 1000) * 1000000L};
  int count = kevent(selector, NULL, 0, ready, maxevents, &timeout);
  if (count < 0) {
    int error = errno;
    free(ready);
    return -error;
  }
  for (int i = 0; i < count; i++) {
    out[2 * i] = (int64_t)(uintptr_t)ready[i].udata;
    out[2 * i + 1] = ready[i].filter == EVFILT_READ ? 1 : 2;
  }
#endif
  free(ready);
  return count;
}
