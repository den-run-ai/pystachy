# pystachy: dynamic-any
"""Optional socket/readiness prototype; see README.md for the bounded contract.

The C bridge borrows inputs only during a call. Receive allocations are copied
and freed here; selectors retain Python keys, never managed pointers in C.
Use explicit close() or a context manager for every owned socket/selector.
"""

import errno
import math
import time
from dataclasses import dataclass
from typing import Any

from ffi import bytes_at, c_int, c_int64, c_void_p, extern


@extern("libpystachy_netio.so")
def nio_strerror(code: c_int) -> str: ...


@extern("libpystachy_netio.so")
def nio_socket() -> c_int: ...


@extern("libpystachy_netio.so")
def nio_socketpair(out: list[c_int64]) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_bind(fd: c_int, host: str, port: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_listen(fd: c_int, backlog: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_accept(fd: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_connect_ex(fd: c_int, host: str, port: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_setblocking(fd: c_int, flag: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_getblocking(fd: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_sockname(fd: c_int, peer: c_int, out: list[c_int64]) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_shutdown(fd: c_int, how: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_close(fd: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_option(fd: c_int, level: c_int, option: c_int, value: c_int, setting: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_constant(code: c_int) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_send(fd: c_int, data: bytes, size: c_int64) -> c_int64: ...


@extern("libpystachy_netio.so")
def nio_recv(fd: c_int, size: c_int64, out: list[c_int64]) -> c_int64: ...


@extern("libpystachy_netio.so")
def nio_read(fd: c_int, size: c_int64, out: list[c_int64]) -> c_int64: ...


@extern("libpystachy_netio.so")
def nio_free(pointer: c_void_p) -> None: ...


@extern("libpystachy_netio.so")
def nio_selector_create() -> c_int: ...


@extern("libpystachy_netio.so")
def nio_selector_ctl(selector: c_int, op: c_int, fd: c_int, events: c_int,
                     old_events: c_int, token: c_int64) -> c_int: ...


@extern("libpystachy_netio.so")
def nio_selector_wait(selector: c_int, maxevents: c_int, timeout_ms: c_int,
                      out: list[c_int64]) -> c_int: ...


AF_UNIX = 1
AF_INET = 2
SOCK_STREAM = 1
EVENT_READ = 1
EVENT_WRITE = 2
SOL_SOCKET = nio_constant(1)
SO_REUSEADDR = nio_constant(2)
SO_ERROR = nio_constant(3)
SO_SNDBUF = nio_constant(4)
SO_RCVBUF = nio_constant(5)
SHUT_RD = nio_constant(6)
SHUT_WR = nio_constant(7)
SHUT_RDWR = nio_constant(8)
MAX_RECEIVE = 16777216
MAX_REGISTRATIONS = 4096


def _checked(result: int) -> int:
    if result < 0:
        code = -result
        raise OSError(code, nio_strerror(code))
    return result


def _address(address: tuple[str, int]) -> tuple[str, int]:
    host, port = address
    if port < 0 or port > 65535:
        raise OverflowError("port must be 0-65535")
    if host == "":
        return "0.0.0.0", port
    parts = host.split(".")
    if len(parts) != 4:
        raise NotImplementedError("netio supports numeric IPv4 addresses only")
    for part in parts:
        if not part or len(part) > 3:
            raise NotImplementedError("netio supports numeric IPv4 addresses only")
        for digit in part:
            if digit < "0" or digit > "9":
                raise NotImplementedError("netio supports numeric IPv4 addresses only")
        if int(part) > 255 or (len(part) > 1 and part[0] == "0"):
            raise NotImplementedError("netio supports canonical numeric IPv4 addresses only")
    return host, port


def set_blocking(fd: int, blocking: bool) -> None:
    """The supported integer-descriptor operation of os.set_blocking()."""
    _checked(nio_setblocking(fd, int(blocking)))


def close_fd(fd: int) -> None:
    """Close a caller-owned descriptor once, as os.close() does."""
    _checked(nio_close(fd))


def read(fd: int, size: int) -> bytes:
    """Read up to MAX_RECEIVE bytes, as os.read(); the caller owns fd."""
    if size < 0 or size > MAX_RECEIVE:
        raise ValueError("netio read size must be between 0 and 16777216")
    out: list[c_int64] = [0]
    count = nio_read(fd, size, out)
    while count == -errno.EINTR:
        count = nio_read(fd, size, out)
    _checked(count)
    try:
        return bytes_at(out[0], count)
    finally:
        nio_free(out[0])


class Socket:
    """Owned stream socket; create with socket()/socketpair(), close explicitly."""

    def __init__(self, fd: int) -> None:
        self._fd = fd
        self._blocking = True

    def fileno(self) -> int:
        return self._fd

    def close(self) -> None:
        fd = self._fd
        self._fd = -1
        if fd >= 0:
            _checked(nio_close(fd))

    def __enter__(self) -> "Socket":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def setblocking(self, flag: bool) -> None:
        set_blocking(self._fd, flag)
        self._blocking = flag

    def getblocking(self) -> bool:
        return self._blocking

    def gettimeout(self) -> float | None:
        if self.getblocking():
            return None
        return 0.0

    def settimeout(self, value: float | None) -> None:
        if value is None:
            self.setblocking(True)
        elif value == 0:
            self.setblocking(False)
        elif value < 0:
            raise ValueError("Timeout value out of range")
        else:
            raise NotImplementedError("netio uses selector deadlines; socket timeouts support only None/0")

    def bind(self, address: tuple[str, int]) -> None:
        host, port = _address(address)
        _checked(nio_bind(self._fd, host, port))

    def listen(self, backlog: int = 128) -> None:
        _checked(nio_listen(self._fd, backlog))

    def accept(self) -> tuple["Socket", tuple[str, int]]:
        fd = nio_accept(self._fd)
        while fd == -errno.EINTR:
            fd = nio_accept(self._fd)
        accepted = _own(_checked(fd))
        try:
            return accepted, accepted.getpeername()
        except BaseException:
            accepted.close()
            raise

    def connect_ex(self, address: tuple[str, int]) -> int:
        host, port = _address(address)
        result = nio_connect_ex(self._fd, host, port)
        return -result

    def connect(self, address: tuple[str, int]) -> None:
        _checked(-self.connect_ex(address))

    def send(self, data: bytes) -> int:
        count = nio_send(self._fd, data, len(data))
        while count == -errno.EINTR:
            count = nio_send(self._fd, data, len(data))
        return _checked(count)

    def recv(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("negative buffersize in recv")
        if size > MAX_RECEIVE:
            raise ValueError("netio receive size exceeds 16777216")
        out: list[c_int64] = [0]
        count = nio_recv(self._fd, size, out)
        while count == -errno.EINTR:
            count = nio_recv(self._fd, size, out)
        _checked(count)
        try:
            return bytes_at(out[0], count)
        finally:
            nio_free(out[0])

    def _name(self, peer: bool) -> tuple[str, int]:
        out: list[c_int64] = [0, 0]
        _checked(nio_sockname(self._fd, int(peer), out))
        ip = out[0]
        return (str((ip >> 24) & 255) + "." + str((ip >> 16) & 255) + "."
                + str((ip >> 8) & 255) + "." + str(ip & 255), out[1])

    def getsockname(self) -> tuple[str, int]:
        return self._name(False)

    def getpeername(self) -> tuple[str, int]:
        return self._name(True)

    def setsockopt(self, level: int, option: int, value: int) -> None:
        _option(level, option)
        _checked(nio_option(self._fd, level, option, value, 1))

    def getsockopt(self, level: int, option: int) -> int:
        _option(level, option)
        return _checked(nio_option(self._fd, level, option, 0, 0))

    def shutdown(self, how: int) -> None:
        _checked(nio_shutdown(self._fd, how))


def _option(level: int, option: int) -> None:
    if level != SOL_SOCKET or option not in (SO_REUSEADDR, SO_ERROR, SO_SNDBUF, SO_RCVBUF):
        raise NotImplementedError("netio supports SOL_SOCKET REUSEADDR/ERROR/SNDBUF/RCVBUF only")


def _own(fd: int) -> Socket:
    try:
        return Socket(fd)
    except BaseException:
        nio_close(fd)
        raise


def socket(family: int = AF_INET, type: int = SOCK_STREAM, proto: int = 0) -> Socket:
    if family != AF_INET or type != SOCK_STREAM or proto != 0:
        raise NotImplementedError("netio socket() supports AF_INET/SOCK_STREAM/proto=0")
    return _own(_checked(nio_socket()))


def socketpair(family: int = AF_UNIX, type: int = SOCK_STREAM, proto: int = 0) -> tuple[Socket, Socket]:
    if family != AF_UNIX or type != SOCK_STREAM or proto != 0:
        raise NotImplementedError("netio socketpair() supports AF_UNIX/SOCK_STREAM/proto=0")
    out: list[c_int64] = [-1, -1]
    _checked(nio_socketpair(out))
    try:
        return Socket(out[0]), Socket(out[1])
    except BaseException:
        nio_close(out[0])
        nio_close(out[1])
        raise


@dataclass(frozen=True)
class SelectorKey:
    fileobj: Any
    fd: int
    events: int
    data: int | None


def _fileno(fileobj: Any) -> int:
    if isinstance(fileobj, int):
        fd: int = fileobj
    else:
        fd = fileobj.fileno()
    if fd < 0:
        raise ValueError("Invalid file descriptor: " + str(fd))
    return fd


def _events(events: int) -> None:
    if events == 0 or (events & ~3) != 0:
        raise ValueError("Invalid events: " + str(events))


class DefaultSelector:
    """Level-triggered epoll/kqueue with integer metadata and bounded capacity."""

    def __init__(self) -> None:
        self._keys: dict[int, SelectorKey] = {}
        self._tokens: dict[int, int] = {}
        self._by_token: dict[int, SelectorKey] = {}
        self._next_token = 1
        self._selector = _checked(nio_selector_create())

    def _open(self) -> None:
        if self._selector < 0:
            raise ValueError("I/O operation on closed selector")

    def register(self, fileobj: Any, events: int, data: int | None = None) -> SelectorKey:
        self._open()
        _events(events)
        fd = _fileno(fileobj)
        if fd in self._keys:
            raise KeyError(str(fd) + " is already registered")
        if len(self._keys) >= MAX_REGISTRATIONS:
            raise ValueError("netio selector capacity exceeded")
        if self._next_token == 9223372036854775807:
            raise OverflowError("netio registration token space exhausted")
        token = self._next_token
        self._next_token += 1
        key = SelectorKey(fileobj, fd, events, data)
        # Allocate the managed bookkeeping before changing the kernel interest set.
        try:
            self._keys[fd] = key
            self._tokens[fd] = token
            self._by_token[token] = key
            _checked(nio_selector_ctl(self._selector, 1, fd, events, 0, token))
        except BaseException:
            self._keys.pop(fd, None)
            self._tokens.pop(fd, None)
            self._by_token.pop(token, None)
            raise
        return key

    def get_key(self, fileobj: Any) -> SelectorKey:
        self._open()
        try:
            fd = _fileno(fileobj)
        except ValueError:
            for key in self._keys.values():
                if key.fileobj is fileobj:
                    return key
            raise
        if fd not in self._keys:
            raise KeyError(str(fd) + " is not registered")
        return self._keys[fd]

    def modify(self, fileobj: Any, events: int, data: int | None = None) -> SelectorKey:
        self._open()
        _events(events)
        old = self.get_key(fileobj)
        key = SelectorKey(old.fileobj, old.fd, events, data)
        token = self._tokens[old.fd]
        if events != old.events:
            try:
                _checked(nio_selector_ctl(self._selector, 2, old.fd, events, old.events, token))
            except OSError:
                # kqueue can have restored the old filters after a failed update.
                nio_selector_ctl(self._selector, 3, old.fd, 0, old.events, token)
                del self._keys[old.fd]
                del self._tokens[old.fd]
                del self._by_token[token]
                raise
        self._keys[old.fd] = key
        self._by_token[token] = key
        return key

    def unregister(self, fileobj: Any) -> SelectorKey:
        key = self.get_key(fileobj)
        token = self._tokens[key.fd]
        # Like selectors, remove bookkeeping even if a closed/reused fd makes
        # the kernel deletion fail. The selector never owns registered fds.
        nio_selector_ctl(self._selector, 3, key.fd, 0, key.events, token)
        del self._keys[key.fd]
        del self._tokens[key.fd]
        del self._by_token[token]
        return key

    def select(self, timeout: float | None = None) -> list[tuple[SelectorKey, int]]:
        self._open()
        deadline = 0.0
        if timeout is not None:
            if math.isnan(timeout):
                raise ValueError("Invalid value NaN (not a number)")
            if math.isinf(timeout):
                raise OverflowError("timeout is too large")
            deadline = time.monotonic() + max(timeout, 0.0)
        # kqueue returns separate records for read and write on the same fd.
        count = min(max(2 * len(self._keys), 1), MAX_REGISTRATIONS)
        out: list[c_int64] = [0] * (2 * count)
        while True:
            # Bounded native waits let the owner regain control; EINTR uses the same deadline.
            milliseconds = 1000
            if timeout is not None:
                remaining = max(deadline - time.monotonic(), 0.0)
                milliseconds = int(math.ceil(min(remaining, 1.0) * 1000.0))
            ready = nio_selector_wait(self._selector, count, milliseconds, out)
            if ready < 0 and -ready != errno.EINTR:
                _checked(ready)
            masks: dict[int, int] = {}
            for i in range(max(ready, 0)):
                token = out[2 * i]
                if token in self._by_token:
                    key = self._by_token[token]
                    mask = out[2 * i + 1] & key.events
                    if mask:
                        masks[token] = masks.get(token, 0) | mask
            result: list[tuple[SelectorKey, int]] = []
            for token, mask in masks.items():
                result.append((self._by_token[token], mask))
            if result or (timeout is not None and time.monotonic() >= deadline):
                return result

    def close(self) -> None:
        descriptor = self._selector
        self._selector = -1
        self._keys.clear()
        self._tokens.clear()
        self._by_token.clear()
        if descriptor >= 0:
            _checked(nio_close(descriptor))

    def __enter__(self) -> "DefaultSelector":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
