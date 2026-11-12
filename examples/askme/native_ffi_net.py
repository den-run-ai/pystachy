"""Blocking TCP streams for the compiled build: libc sockets through Pystachy's FFI.

Only a Pystachy build imports this module, and only when a request is first
sent: importing it loads ``libc.so.6``. The struct layouts and constants are
those of 64-bit little-endian Linux with glibc; elsewhere the import fails
with ``OSError`` and the caller keeps its ``curl`` transport.

A stream is a small integer. ``native_http`` owns the protocol; TLS comes from
``native_ffi_tls`` on first use, so plain HTTP needs no OpenSSL.
"""

import os

from ffi import (  # type: ignore
    bytes_at,
    c_int,
    c_int64,
    c_size_t,
    c_ssize_t,
    c_uint,
    c_uint64,
    c_void_p,
    extern,
)

# OpenSSL loads with the first https:// stream (see native_http on this import).
if os.environ.get("ASKME_NATIVE_PRELOAD", "") == "1":
    import native_ffi_tls  # noqa: F401

AF_UNSPEC = 0
SOCK_STREAM = 1
SOCK_CLOEXEC = 0x80000
SOL_SOCKET = 1
SO_RCVTIMEO = 20
SO_SNDTIMEO = 21
IPPROTO_TCP = 6
TCP_NODELAY = 1
TCP_QUICKACK = 12
MSG_NOSIGNAL = 0x4000
POLLIN = 1
EINTR = 4
EAGAIN = 11
EINPROGRESS = 115
ADDRINFO_SIZE = 48
RECEIVE_BYTES = 65536


@extern("libc.so.6", "socket")
def c_socket(domain: c_int, kind: c_int, protocol: c_int) -> c_int: ...


@extern("libc.so.6", "connect")
def c_connect(fd: c_int, address: bytes, size: c_uint) -> c_int: ...


@extern("libc.so.6", "close")
def c_close(fd: c_int) -> c_int: ...


@extern("libc.so.6", "send")
def c_send(fd: c_int, data: bytes, size: c_size_t, flags: c_int) -> c_ssize_t: ...


@extern("libc.so.6", "recv")
def c_recv(fd: c_int, buffer: c_void_p, size: c_size_t, flags: c_int) -> c_ssize_t: ...


@extern("libc.so.6", "poll")
def c_poll(fds: list[c_int64], count: c_uint64, timeout_ms: c_int) -> c_int: ...


@extern("libc.so.6", "setsockopt")
def c_setsockopt(fd: c_int, level: c_int, name: c_int, value: bytes, size: c_uint) -> c_int: ...


@extern("libc.so.6", "getaddrinfo")
def c_getaddrinfo(node: str, service: str, hints: bytes, out: list[c_int64]) -> c_int: ...


@extern("libc.so.6", "freeaddrinfo")
def c_freeaddrinfo(found: c_void_p) -> None: ...


@extern("libc.so.6", "gai_strerror")
def c_gai_strerror(code: c_int) -> str: ...  # ty: ignore[empty-body]


@extern("libc.so.6", "strerror")
def c_strerror(code: c_int) -> str: ...  # ty: ignore[empty-body]


@extern("libc.so.6", "__errno_location")
def c_errno_location() -> c_void_p: ...


@extern("libc.so.6", "malloc")
def c_malloc(size: c_size_t) -> c_void_p: ...


@extern("libc.so.6", "free")
def c_free(pointer: c_void_p) -> None: ...


class Stream:
    """One open connection: its descriptor, receive buffer and TLS session."""

    def __init__(self, fd: int, buffer: int, session: int) -> None:
        self.fd = fd
        self.buffer = buffer
        self.session = session  # an SSL *, or 0 for plain TCP


_STREAMS: dict[int, Stream] = {}
_NEXT: list[int] = [1]


def _unsigned(data: bytes, offset: int, size: int) -> int:
    value = 0
    for index in range(size):
        value |= data[offset + index] << (8 * index)
    return value


def _packed(value: int, size: int) -> bytes:
    return bytes([(value >> (8 * index)) & 255 for index in range(size)])


def errno() -> int:
    return _unsigned(bytes_at(c_errno_location(), 4), 0, 4)


def _failure(action: str) -> OSError:
    code = errno()
    if code == EAGAIN or code == EINPROGRESS:
        return OSError(action + ": timed out")
    return OSError(action + ": " + c_strerror(code))


def _addresses(host: str, port: int) -> list[tuple[int, bytes]]:
    """(family, sockaddr) for each address of ``host``, in resolver order."""
    hints = _packed(0, 4) + _packed(AF_UNSPEC, 4) + _packed(SOCK_STREAM, 4) + bytes(36)
    out: list[int] = [0]
    code = c_getaddrinfo(host, str(port), hints, out)
    if code != 0:
        raise OSError("cannot resolve " + host + ": " + c_gai_strerror(code))
    found: list[tuple[int, bytes]] = []
    entry = out[0]
    while entry != 0:
        record = bytes_at(entry, ADDRINFO_SIZE)
        family = _unsigned(record, 4, 4)
        size = _unsigned(record, 16, 4)
        address = _unsigned(record, 24, 8)
        if address != 0 and size > 0:
            found.append((family, bytes_at(address, size)))
        entry = _unsigned(record, 40, 8)
    c_freeaddrinfo(out[0])
    if not found:
        raise OSError("cannot resolve " + host + ": no address")
    return found


def _connect(host: str, port: int, timeout: int) -> int:
    seconds = _packed(timeout if timeout > 0 else 0, 8) + _packed(0, 8)
    problem = "no address"
    for family, address in _addresses(host, port):
        fd = c_socket(family, SOCK_STREAM | SOCK_CLOEXEC, 0)
        if fd < 0:
            problem = str(_failure("socket"))
            continue
        # The kernel bounds connect(), send() and recv(): no descriptor flag
        # changes, and a TLS read inside OpenSSL is bounded as well.
        c_setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, seconds, 16)
        c_setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, seconds, 16)
        c_setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, _packed(1, 4), 4)
        while True:
            if c_connect(fd, address, len(address)) == 0:
                return fd
            if errno() != EINTR:
                break
        problem = str(_failure("connect to " + host + ":" + str(port)))
        c_close(fd)
    raise OSError(problem)


def tls_problem() -> str:
    """Why HTTPS cannot be served in-process here, or ``""``."""
    try:
        import native_ffi_tls
    except OSError as error:
        return str(error)
    return native_ffi_tls.problem()


def open_stream(tls: bool, host: str, port: int, timeout: int) -> int:
    fd = _connect(host, port, timeout)
    session = 0
    if tls:
        import native_ffi_tls

        try:
            session = native_ffi_tls.handshake(fd, host)
        except OSError:
            c_close(fd)
            raise
    handle = _NEXT[0]
    _NEXT[0] = handle + 1
    _STREAMS[handle] = Stream(fd, c_malloc(RECEIVE_BYTES), session)
    return handle


def _acknowledge_at_once(fd: int) -> None:
    # A server that writes headers and body separately waits for the first
    # segment's acknowledgement; on a kept connection the kernel would delay
    # it by 40 ms. The option is not sticky, so it is set before each reply.
    c_setsockopt(fd, IPPROTO_TCP, TCP_QUICKACK, _packed(1, 4), 4)


def stream_send(handle: int, data: bytes) -> None:
    stream = _STREAMS[handle]
    _acknowledge_at_once(stream.fd)
    if stream.session != 0:
        import native_ffi_tls

        native_ffi_tls.send_all(stream.session, data)
        return
    sent = 0
    while sent < len(data):
        count = c_send(stream.fd, data[sent:], len(data) - sent, MSG_NOSIGNAL)
        if count > 0:
            sent += count
        elif errno() != EINTR:
            raise _failure("send")


def stream_recv(handle: int) -> bytes:
    """Up to one buffer of bytes; ``b""`` once the peer has closed."""
    stream = _STREAMS[handle]
    if stream.session != 0:
        import native_ffi_tls

        received = native_ffi_tls.receive(stream.session, stream.buffer, RECEIVE_BYTES)
        _acknowledge_at_once(stream.fd)
        return received
    while True:
        count = c_recv(stream.fd, stream.buffer, RECEIVE_BYTES, 0)
        if count >= 0:
            _acknowledge_at_once(stream.fd)
            return bytes_at(stream.buffer, count)
        if errno() != EINTR:
            raise _failure("receive")


def stream_idle(handle: int) -> bool:
    """Whether nothing has arrived: a close or stray bytes make a kept stream unusable."""
    stream = _STREAMS[handle]
    if stream.session != 0:
        import native_ffi_tls

        if native_ffi_tls.pending(stream.session) > 0:
            return False
    # struct pollfd { int fd; short events; short revents; } in one 64-bit word
    fds: list[int] = [stream.fd | (POLLIN << 32)]
    return c_poll(fds, 1, 0) == 0


def stream_close(handle: int) -> None:
    stream = _STREAMS.pop(handle, None)
    if stream is None:
        return
    if stream.session != 0:
        import native_ffi_tls

        native_ffi_tls.close(stream.session)
    c_close(stream.fd)
    c_free(stream.buffer)
