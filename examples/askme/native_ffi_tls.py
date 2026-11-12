"""TLS client sessions for the compiled build: OpenSSL 3 through Pystachy's FFI.

Imported by ``native_ffi_net`` when the first ``https://`` request is sent;
importing it loads ``libssl.so.3``, and where that fails the caller keeps its
``curl`` transport. Sessions verify the peer's certificate chain and host name
against the system trust store, as ``requests`` and ``curl`` do by default.
There is no switch that turns verification off.

Trust comes from OpenSSL's default paths (``SSL_CERT_FILE`` and
``SSL_CERT_DIR`` included) plus the bundle named by ``CURL_CA_BUNDLE`` or
``REQUESTS_CA_BUNDLE`` when one is set.
"""

import os

from ffi import (  # type: ignore
    bytes_at,
    c_int,
    c_int64,
    c_size_t,
    c_uint64,
    c_void_p,
    extern,
)

SSL_VERIFY_PEER = 1
SSL_CTRL_SET_TLSEXT_HOSTNAME = 55
SSL_CTRL_SET_MIN_PROTO_VERSION = 123
TLS1_2_VERSION = 0x0303
SSL_ERROR_SSL = 1
SSL_ERROR_WANT_READ = 2
SSL_ERROR_WANT_WRITE = 3
SSL_ERROR_SYSCALL = 5
SSL_ERROR_ZERO_RETURN = 6
SIGPIPE = 13
SIG_IGN = 1
SIG_ERR = -1
ERROR_TEXT_BYTES = 256


@extern("libssl.so.3")
def TLS_client_method() -> c_void_p: ...


@extern("libssl.so.3")
def SSL_CTX_new(method: c_void_p) -> c_void_p: ...


@extern("libssl.so.3")
def SSL_CTX_set_default_verify_paths(context: c_void_p) -> c_int: ...


@extern("libssl.so.3")
def SSL_CTX_load_verify_locations(
    context: c_void_p, file: bytes | None, directory: bytes | None
) -> c_int: ...


@extern("libssl.so.3")
def SSL_CTX_set_verify(context: c_void_p, mode: c_int, callback: c_void_p) -> None: ...


@extern("libssl.so.3")
def SSL_CTX_ctrl(
    context: c_void_p, command: c_int, number: c_int64, pointer: c_void_p
) -> c_int64: ...


@extern("libssl.so.3")
def SSL_new(context: c_void_p) -> c_void_p: ...


@extern("libssl.so.3")
def SSL_free(session: c_void_p) -> None: ...


@extern("libssl.so.3")
def SSL_set_fd(session: c_void_p, fd: c_int) -> c_int: ...


@extern("libssl.so.3")
def SSL_ctrl(session: c_void_p, command: c_int, number: c_int64, text: bytes) -> c_int64: ...


@extern("libssl.so.3")
def SSL_set1_host(session: c_void_p, name: str) -> c_int: ...


@extern("libssl.so.3")
def SSL_connect(session: c_void_p) -> c_int: ...


@extern("libssl.so.3")
def SSL_get_error(session: c_void_p, result: c_int) -> c_int: ...


@extern("libssl.so.3")
def SSL_get_verify_result(session: c_void_p) -> c_int64: ...


@extern("libssl.so.3")
def SSL_write(session: c_void_p, data: bytes, size: c_int) -> c_int: ...


@extern("libssl.so.3")
def SSL_read(session: c_void_p, buffer: c_void_p, size: c_int) -> c_int: ...


@extern("libssl.so.3")
def SSL_pending(session: c_void_p) -> c_int: ...


@extern("libssl.so.3")
def SSL_shutdown(session: c_void_p) -> c_int: ...


@extern("libssl.so.3")
def X509_verify_cert_error_string(code: c_int64) -> str: ...  # ty: ignore[empty-body]


@extern("libssl.so.3")
def ERR_get_error() -> c_uint64: ...


@extern("libssl.so.3")
def ERR_clear_error() -> None: ...


@extern("libssl.so.3")
def ERR_error_string_n(code: c_uint64, buffer: c_void_p, size: c_size_t) -> None: ...


@extern("libc.so.6", "signal")
def c_signal(number: c_int, handler: c_void_p) -> c_void_p: ...


@extern("libc.so.6", "malloc")
def c_malloc(size: c_size_t) -> c_void_p: ...


@extern("libc.so.6", "free")
def c_free(pointer: c_void_p) -> None: ...


_CONTEXT: list[int] = [0]
_PROBLEM: list[str] = [""]


def _error_text() -> str:
    """The oldest queued OpenSSL error, emptied from the queue."""
    code = ERR_get_error()
    if code == 0:
        return ""
    buffer = c_malloc(ERROR_TEXT_BYTES)
    ERR_error_string_n(code, buffer, ERROR_TEXT_BYTES)
    text = bytes_at(buffer, -1).decode("utf-8", "replace")
    c_free(buffer)
    ERR_clear_error()
    return text


def _context() -> int:
    if _CONTEXT[0] != 0 or _PROBLEM[0]:
        return _CONTEXT[0]
    context = SSL_CTX_new(TLS_client_method())
    if context == 0:
        _PROBLEM[0] = "OpenSSL context: " + _error_text()
        return 0
    SSL_CTX_ctrl(context, SSL_CTRL_SET_MIN_PROTO_VERSION, TLS1_2_VERSION, 0)
    SSL_CTX_set_verify(context, SSL_VERIFY_PEER, 0)
    SSL_CTX_set_default_verify_paths(context)
    bundle = os.environ.get("CURL_CA_BUNDLE", "") or os.environ.get("REQUESTS_CA_BUNDLE", "")
    if bundle and SSL_CTX_load_verify_locations(context, bundle.encode() + b"\x00", None) != 1:
        _PROBLEM[0] = "cannot load CA bundle " + bundle + ": " + _error_text()
        return 0
    ERR_clear_error()
    _CONTEXT[0] = context
    return context


def problem() -> str:
    """Why no session can be made here, or ``""``."""
    _context()
    return _PROBLEM[0]


def _is_address(host: str) -> bool:
    if ":" in host:
        return True
    parts = host.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
    return True


def _ignore_pipe() -> int:
    # OpenSSL writes with write(2): a peer that has gone would raise SIGPIPE.
    return c_signal(SIGPIPE, SIG_IGN)


def _restore_pipe(previous: int) -> None:
    if previous != SIG_ERR:
        c_signal(SIGPIPE, previous)


def _failure(session: int, result: int, action: str) -> OSError:
    kind = SSL_get_error(session, result)
    if kind == SSL_ERROR_WANT_READ or kind == SSL_ERROR_WANT_WRITE:
        ERR_clear_error()
        return OSError(action + ": timed out")
    detail = _error_text()
    if not detail:
        detail = "connection closed" if kind == SSL_ERROR_SYSCALL else "TLS error " + str(kind)
    return OSError(action + ": " + detail)


def handshake(fd: int, host: str) -> int:
    """A verified session over connected socket ``fd``; ``OSError`` otherwise."""
    context = _context()
    if context == 0:
        raise OSError(_PROBLEM[0])
    session = SSL_new(context)
    if session == 0:
        raise OSError("TLS session: " + _error_text())
    ready = SSL_set_fd(session, fd) == 1 and SSL_set1_host(session, host) == 1
    if ready and not _is_address(host):
        ready = SSL_ctrl(session, SSL_CTRL_SET_TLSEXT_HOSTNAME, 0, host.encode() + b"\x00") == 1
    if not ready:
        detail = _error_text()
        SSL_free(session)
        raise OSError("TLS session: " + detail)
    previous = _ignore_pipe()
    result = SSL_connect(session)
    _restore_pipe(previous)
    if result != 1:
        verdict = SSL_get_verify_result(session)
        error = _failure(session, result, "TLS handshake with " + host)
        if verdict != 0:
            error = OSError(
                "TLS handshake with "
                + host
                + ": certificate verify failed: "
                + X509_verify_cert_error_string(verdict)
            )
        ERR_clear_error()
        SSL_free(session)
        raise error
    return session


def send_all(session: int, data: bytes) -> None:
    previous = _ignore_pipe()
    sent = 0
    while sent < len(data):
        count = SSL_write(session, data[sent:], len(data) - sent)
        if count <= 0:
            error = _failure(session, count, "send")
            _restore_pipe(previous)
            raise error
        sent += count
    _restore_pipe(previous)


def receive(session: int, buffer: int, size: int) -> bytes:
    """Up to ``size`` bytes; ``b""`` when the peer closed, with or without close_notify."""
    count = SSL_read(session, buffer, size)
    if count > 0:
        return bytes_at(buffer, count)
    kind = SSL_get_error(session, count)
    if kind == SSL_ERROR_WANT_READ or kind == SSL_ERROR_WANT_WRITE:
        ERR_clear_error()
        raise OSError("receive: timed out")
    if kind == SSL_ERROR_ZERO_RETURN:
        return b""
    # A close without close_notify also ends the stream, as Python's ssl treats
    # it: the HTTP layer checks a body against its declared length.
    detail = _error_text()
    if not detail or "unexpected eof" in detail:
        return b""
    raise OSError("receive: " + detail)


def pending(session: int) -> int:
    return SSL_pending(session)


def close(session: int) -> None:
    previous = _ignore_pipe()
    SSL_shutdown(session)
    _restore_pipe(previous)
    ERR_clear_error()
    SSL_free(session)
