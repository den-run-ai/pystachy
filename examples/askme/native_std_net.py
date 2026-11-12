"""Blocking TCP streams for the interpreters: the standard ``socket`` and ``ssl``.

The counterpart of ``native_ffi_net`` under CPython, PyPy and mypyc, with the
same five functions, so ``native_http`` runs one protocol implementation on
every runtime. A stream is a small integer.
"""

import os
import select
import socket
import ssl

RECEIVE_BYTES = 65536

_STREAMS: dict[int, socket.socket] = {}
_NEXT: list[int] = [1]
_CONTEXTS: list[ssl.SSLContext] = []


def _context() -> ssl.SSLContext:
    if not _CONTEXTS:
        context = ssl.create_default_context()
        bundle = os.environ.get("CURL_CA_BUNDLE", "") or os.environ.get("REQUESTS_CA_BUNDLE", "")
        if bundle:
            context.load_verify_locations(cafile=bundle)
        _CONTEXTS.append(context)
    return _CONTEXTS[0]


def tls_problem() -> str:
    """Why HTTPS cannot be served in-process here, or ``""``."""
    try:
        _context()
    except (OSError, ValueError) as error:
        return str(error)
    return ""


def _detail(error: OSError) -> str:
    """The system's message alone, as the compiled build reports it."""
    return error.strerror if error.strerror else str(error)


def open_stream(tls: bool, host: str, port: int, timeout: int) -> int:
    limit = float(timeout) if timeout > 0 else None
    target = "connect to " + host + ":" + str(port)
    try:
        stream = socket.create_connection((host, port), limit)
    except socket.timeout:
        raise OSError(target + ": timed out") from None
    except socket.gaierror as resolve_error:
        raise OSError("cannot resolve " + host + ": " + _detail(resolve_error)) from None
    except OSError as connect_error:
        raise OSError(target + ": " + _detail(connect_error)) from None
    try:
        stream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if tls:
            stream = _context().wrap_socket(stream, server_hostname=host)
    except socket.timeout:
        stream.close()
        raise OSError("TLS handshake with " + host + ": timed out") from None
    except (OSError, ValueError) as error:
        stream.close()
        raise OSError("TLS handshake with " + host + ": " + str(error)) from None
    handle = _NEXT[0]
    _NEXT[0] = handle + 1
    _STREAMS[handle] = stream
    return handle


def _acknowledge_at_once(stream: socket.socket) -> None:
    # A server that writes headers and body separately waits for the first
    # segment's acknowledgement; on a kept connection the kernel would delay
    # it by 40 ms. Linux only, and not sticky: set before each reply.
    if hasattr(socket, "TCP_QUICKACK"):
        try:
            stream.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        except OSError:
            pass


def stream_send(handle: int, data: bytes) -> None:
    _acknowledge_at_once(_STREAMS[handle])
    try:
        _STREAMS[handle].sendall(data)
    except socket.timeout:
        raise OSError("send: timed out") from None
    except OSError as send_error:
        raise OSError("send: " + _detail(send_error)) from None


def stream_recv(handle: int) -> bytes:
    """Up to one buffer of bytes; ``b""`` once the peer has closed."""
    try:
        received = _STREAMS[handle].recv(RECEIVE_BYTES)
        _acknowledge_at_once(_STREAMS[handle])
        return received
    except socket.timeout:
        raise OSError("receive: timed out") from None
    except OSError as receive_error:
        raise OSError("receive: " + _detail(receive_error)) from None


def stream_idle(handle: int) -> bool:
    """Whether nothing has arrived: a close or stray bytes make a kept stream unusable."""
    stream = _STREAMS[handle]
    if isinstance(stream, ssl.SSLSocket) and stream.pending() > 0:
        return False
    readable, _, _ = select.select([stream], [], [], 0)
    return not readable


def stream_close(handle: int) -> None:
    stream = _STREAMS.pop(handle, None)
    if stream is None:
        return
    try:
        stream.close()
    except OSError:
        pass
