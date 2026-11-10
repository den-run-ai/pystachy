/* Standalone ownership/ABI checks; also run with address/undefined sanitizers.
   No Python interpreter, network service or managed object layout is needed. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "netio.h"

#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static void ownership_cycles(void) {
  for (int iteration = 0; iteration < 300; iteration++) {
    int64_t pair[2], pointer, events[8];
    assert(nio_socketpair(pair) == 0);
    int selector = nio_selector_create();
    assert(selector >= 0);
    assert(nio_setblocking((int)pair[0], 0) == 0);
    assert(nio_option((int)pair[0], SOL_SOCKET, SO_ERROR, 0, 0) == 0);
    assert(nio_option((int)pair[0], SOL_SOCKET, SO_KEEPALIVE, 0, 0) == -EOPNOTSUPP);
    assert(nio_recv((int)pair[0], 1, &pointer) == -EAGAIN && pointer == 0);
    assert(nio_recv((int)pair[0], -1, &pointer) == -EINVAL && pointer == 0);
    assert(nio_recv((int)pair[0], NIO_MAX_READ_BYTES + 1, &pointer) == -EINVAL && pointer == 0);
    assert(nio_recv(-1, 0, &pointer) == 0 && pointer == 0);
    assert(nio_read(-1, 0, &pointer) == -EBADF && pointer == 0);
    assert(nio_selector_ctl(selector, 1, (int)pair[0], 1, 0, 7) == 0);
    assert(nio_selector_wait(selector, 4, 0, events) == 0);
    assert(nio_send((int)pair[1], "a\0b", 3) == 3);
    assert(nio_selector_wait(selector, 4, 0, events) == 1);
    assert(events[0] == 7 && events[1] == 1);
    assert(nio_recv((int)pair[0], 8, &pointer) == 3);
    int64_t owned = pointer;
    /* A later failed receive cannot invalidate the caller's earlier buffer. */
    assert(nio_recv((int)pair[0], 1, &pointer) == -EAGAIN && pointer == 0);
    assert(memcmp((void *)(uintptr_t)owned, "a\0b", 3) == 0);
    nio_free((void *)(uintptr_t)owned);
    assert(nio_selector_ctl(selector, 2, (int)pair[0], 2, 1, 7) == 0);
    assert(nio_selector_wait(selector, 4, 0, events) == 1);
    assert(events[0] == 7 && events[1] == 2);
    assert(nio_selector_ctl(selector, 3, (int)pair[0], 0, 2, 7) == 0);
    assert(nio_selector_wait(selector, 4, 0, events) == 0);
    assert(nio_selector_wait(selector, 0, 0, events) == -EINVAL);
    assert(nio_selector_wait(selector, NIO_MAX_EVENTS + 1, 0, events) == -EINVAL);
    assert(nio_selector_wait(selector, 1, -1, events) == -EINVAL);
    assert(nio_selector_wait(selector, 1, NIO_MAX_WAIT_MS + 1, events) == -EINVAL);
    assert(nio_shutdown((int)pair[1], SHUT_WR) == 0);
    assert(nio_recv((int)pair[0], 8, &pointer) == 0 && pointer == 0);
    assert(nio_close((int)pair[0]) == 0);
    /* With SIGPIPE's default disposition, this must return EPIPE, not kill us. */
    assert(nio_send((int)pair[1], "x", 1) == -EPIPE);
    assert(nio_close((int)pair[1]) == 0);
    assert(nio_close(selector) == 0);
  }
}

static void inherited_pipe(void) {
  int pipefd[2];
  assert(pipe(pipefd) == 0);
  int high = fcntl(pipefd[0], F_DUPFD_CLOEXEC, 1300);
  if (high < 0) {
    /* A platform's low descriptor limit need not prevent the other checks. */
    assert(errno == EINVAL || errno == EMFILE);
    fputs("high descriptor check skipped: descriptor limit below 1301\n", stderr);
    high = pipefd[0];
  }
  int selector = nio_selector_create();
  assert(selector >= 0);
  int64_t ready[2], pointer;
  assert(nio_selector_ctl(selector, 1, high, 1, 0, 99) == 0);
  assert(write(pipefd[1], "binary\0pipe", 11) == 11);
  assert(nio_selector_wait(selector, 1, 0, ready) == 1);
  assert(ready[0] == 99 && ready[1] == 1);
  assert(nio_read(high, 30, &pointer) == 11);
  assert(memcmp((void *)(uintptr_t)pointer, "binary\0pipe", 11) == 0);
  nio_free((void *)(uintptr_t)pointer);
  assert(nio_selector_ctl(selector, 3, high, 0, 1, 99) == 0);
  if (high != pipefd[0]) assert(nio_close(high) == 0);
  assert(nio_close(selector) == 0);
  assert(close(pipefd[0]) == 0);
  assert(close(pipefd[1]) == 0);
}

int main(void) {
  assert(signal(SIGPIPE, SIG_DFL) != SIG_ERR);
  ownership_cycles();
  inherited_pipe();
  puts("netio ownership: 300 cycles, SIGPIPE, pipe readiness and bounds pass");
  return 0;
}
