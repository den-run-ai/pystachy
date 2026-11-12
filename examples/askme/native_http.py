"""HTTP/1.1 POST over kept connections, in the process, on every runtime.

One protocol implementation serves all runtimes; only the byte stream beneath
it differs. A Pystachy build uses libc sockets and OpenSSL through its FFI
(``native_ffi_net``), the interpreters use ``socket`` and ``ssl``
(``native_std_net``). Both verify TLS certificates and host names.

``HttpClient.post`` returns ``None`` when a request is not its to send: the
stream layer is missing on this machine, or the environment names a proxy.
The caller then uses ``curl``, which handles both.
"""

import os
import sys

MAX_HEADER_BYTES = 65536
MAX_CHUNK_LINE = 256
MODES = ["auto", "inprocess", "curl"]
PROXY_NAMES = ["all_proxy", "ALL_PROXY"]
OWN_HEADERS = ["host", "content-length", "transfer-encoding"]
DEFAULT_HEADERS = [
    "User-Agent: askme-native",
    "Accept: */*",
    "Accept-Encoding: identity",
    "Connection: keep-alive",
]


# The stream libraries load at the first request, not at startup. Pystachy
# compiles a function's import only of a module that module-level code also
# imports; this one is that import, and lets a run load them up front.
if sys.implementation.name == "pystachy":
    if os.environ.get("ASKME_NATIVE_PRELOAD", "") == "1":
        import native_ffi_net  # noqa: F401


class HttpReply:
    """One HTTP exchange: a status and body, or a transport ``error``."""

    def __init__(self, status: int, text: str, error: str) -> None:
        self.status = status
        self.text = text
        self.error = error


class ParsedUrl:
    def __init__(self, tls: bool, host: str, port: int, target: str, authority: str) -> None:
        self.tls = tls
        self.host = host
        self.port = port
        self.target = target
        self.authority = authority


def parse_url(url: str) -> ParsedUrl | None:
    """Split an ``http``/``https`` URL; ``None`` for one this client does not send."""
    tls = url.startswith("https://")
    if not tls and not url.startswith("http://"):
        return None
    rest = url[8:] if tls else url[7:]
    rest = rest.split("#", 1)[0]
    cut = len(rest)
    for mark in ["/", "?"]:
        found = rest.find(mark)
        if 0 <= found < cut:
            cut = found
    authority = rest[:cut]
    target = rest[cut:]
    if not target.startswith("/"):
        target = "/" + target
    if not authority or "@" in authority:
        return None
    for character in authority + target:
        if character <= " " or character == "\x7f":
            return None
    host = authority
    port_text = ""
    if authority.startswith("["):
        end = authority.find("]")
        if end < 0:
            return None
        host = authority[1:end]
        tail = authority[end + 1 :]
        if tail:
            if not tail.startswith(":"):
                return None
            port_text = tail[1:]
    elif ":" in authority:
        host, port_text = authority.rsplit(":", 1)
    port = 443 if tls else 80
    if port_text:
        if not port_text.isdigit() or len(port_text) > 5:
            return None
        port = int(port_text)
    if not host or port < 1 or port > 65535:
        return None
    return ParsedUrl(tls, host, port, target, authority)


def proxied(tls: bool, host: str) -> bool:
    """Whether the environment routes this host through a proxy."""
    names = (["https_proxy", "HTTPS_PROXY"] if tls else ["http_proxy", "HTTP_PROXY"]) + PROXY_NAMES
    configured = False
    for name in names:
        if os.environ.get(name, ""):
            configured = True
    if not configured:
        return False
    rules = os.environ.get("no_proxy", "") or os.environ.get("NO_PROXY", "")
    lowered = host.lower()
    for raw in rules.split(","):
        rule = raw.strip().lower()
        if rule == "*":
            return False
        while rule.startswith("."):
            rule = rule[1:]
        if rule and (lowered == rule or lowered.endswith("." + rule)):
            return False
    return True


def _stream_problem(tls: bool) -> str:
    """Why this machine cannot open such a stream in-process, or ``""``."""
    if sys.implementation.name == "pystachy":
        try:
            import native_ffi_net
        except OSError as load_error:
            return str(load_error)
        return native_ffi_net.tls_problem() if tls else ""
    else:
        import native_std_net

        return native_std_net.tls_problem() if tls else ""


def _open(tls: bool, host: str, port: int, timeout: int) -> int:
    if sys.implementation.name == "pystachy":
        import native_ffi_net

        return native_ffi_net.open_stream(tls, host, port, timeout)
    else:
        import native_std_net

        return native_std_net.open_stream(tls, host, port, timeout)


def _send(handle: int, data: bytes) -> None:
    if sys.implementation.name == "pystachy":
        import native_ffi_net

        native_ffi_net.stream_send(handle, data)
    else:
        import native_std_net

        native_std_net.stream_send(handle, data)


def _recv(handle: int) -> bytes:
    if sys.implementation.name == "pystachy":
        import native_ffi_net

        return native_ffi_net.stream_recv(handle)
    else:
        import native_std_net

        return native_std_net.stream_recv(handle)


def _idle(handle: int) -> bool:
    if sys.implementation.name == "pystachy":
        import native_ffi_net

        return native_ffi_net.stream_idle(handle)
    else:
        import native_std_net

        return native_std_net.stream_idle(handle)


def _close(handle: int) -> None:
    if sys.implementation.name == "pystachy":
        import native_ffi_net

        native_ffi_net.stream_close(handle)
    else:
        import native_std_net

        native_std_net.stream_close(handle)


class _Reader:
    """Buffered reads from one stream."""

    def __init__(self, handle: int) -> None:
        self.handle = handle
        self.data = b""
        self.closed = False
        self.started = False  # whether any byte of a reply has arrived

    def receive(self) -> bytes:
        chunk = _recv(self.handle)
        if chunk:
            self.started = True
        else:
            self.closed = True
        return chunk

    def more(self) -> bool:
        if self.closed:
            return False
        chunk = self.receive()
        if not chunk:
            return False
        self.data += chunk
        return True

    def line(self, limit: int) -> bytes | None:
        """The next line without its CRLF; ``None`` at a close or past ``limit`` bytes."""
        while True:
            end = self.data.find(b"\n")
            if end >= 0:
                line = self.data[:end]
                self.data = self.data[end + 1 :]
                return line[:-1] if line.endswith(b"\r") else line
            if len(self.data) > limit or not self.more():
                return None

    def exact(self, size: int) -> bytes | None:
        """Exactly ``size`` bytes; ``None`` if the stream closes first."""
        parts: list[bytes] = [self.data]
        have = len(self.data)
        self.data = b""
        while have < size:
            if self.closed:
                return None
            chunk = self.receive()
            if not chunk:
                return None
            parts.append(chunk)
            have += len(chunk)
        joined = b"".join(parts)
        self.data = joined[size:]
        return joined[:size]

    def rest(self) -> bytes:
        parts: list[bytes] = [self.data]
        self.data = b""
        while not self.closed:
            chunk = self.receive()
            if chunk:
                parts.append(chunk)
        return b"".join(parts)


def _number(text: bytes, base: int) -> int:
    """A non-negative integer of at most 15 digits, or -1."""
    digits = b"0123456789abcdef"[:base]
    lowered = text.lower()
    if not lowered or len(lowered) > 15:
        return -1
    value = 0
    for byte in lowered:
        digit = digits.find(bytes([byte]))
        if digit < 0:
            return -1
        value = value * base + digit
    return value


def _read_chunked(reader: _Reader) -> bytes:
    parts: list[bytes] = []
    while True:
        line = reader.line(MAX_CHUNK_LINE)
        if line is None:
            raise OSError("connection closed inside a chunked response")
        size = _number(line.split(b";", 1)[0].strip(), 16)
        if size < 0:
            raise OSError("malformed chunk size in the response")
        if size == 0:
            break
        data = reader.exact(size)
        if data is None:
            raise OSError("connection closed inside a chunked response")
        parts.append(data)
        ending = reader.line(2)
        if ending is None or ending:
            raise OSError("malformed chunk ending in the response")
    while True:
        trailer = reader.line(MAX_HEADER_BYTES)
        if trailer is None:
            raise OSError("connection closed inside a chunked response")
        if not trailer:
            return b"".join(parts)


class _Response:
    def __init__(self, status: int, body: bytes, reusable: bool) -> None:
        self.status = status
        self.body = body
        self.reusable = reusable


def read_response(reader: _Reader) -> _Response:
    """One response, skipping interim 1xx replies. Raises ``OSError`` on a broken one."""
    while True:
        status_line = reader.line(MAX_HEADER_BYTES)
        if status_line is None:
            raise OSError("connection closed before a response arrived")
        parts = status_line.split(b" ", 2)
        if len(parts) < 2 or not parts[0].startswith(b"HTTP/1.") or len(parts[1]) != 3:
            raise OSError("malformed HTTP status line")
        status = _number(parts[1], 10)
        if status < 100:
            raise OSError("malformed HTTP status line")
        close = parts[0] != b"HTTP/1.1"
        length = -1
        chunked = False
        seen = len(status_line)
        while True:
            line = reader.line(MAX_HEADER_BYTES)
            if line is None:
                raise OSError("connection closed inside the response headers")
            if not line:
                break
            seen += len(line)
            if seen > MAX_HEADER_BYTES:
                raise OSError("response headers are too large")
            colon = line.find(b":")
            if colon < 0:
                continue
            name = line[:colon].strip().lower()
            value = line[colon + 1 :].strip()
            if name == b"content-length":
                declared = _number(value, 10)
                if declared < 0 or (length >= 0 and declared != length):
                    raise OSError("malformed Content-Length in the response")
                length = declared
            elif name == b"transfer-encoding":
                chunked = b"chunked" in value.lower()
            elif name == b"connection":
                lowered = value.lower()
                if b"close" in lowered:
                    close = True
                elif b"keep-alive" in lowered:
                    close = False
        if status >= 200 or status == 101:
            break
    if status == 204 or status == 304:
        body = b""
    elif chunked:
        body = _read_chunked(reader)
    elif length >= 0:
        counted = reader.exact(length)
        if counted is None:
            raise OSError("connection closed before the response body was complete")
        body = counted
    else:
        body = reader.rest()
        close = True
    return _Response(status, body, not close and not reader.closed and not reader.data)


def build_request(url: ParsedUrl, body: bytes, headers: list[str]) -> bytes:
    lines = ["POST " + url.target + " HTTP/1.1", "Host: " + url.authority]
    given = [header.split(":", 1)[0].strip().lower() for header in headers]
    for default in DEFAULT_HEADERS:
        if default.split(":", 1)[0].lower() not in given:
            lines.append(default)
    for index in range(len(headers)):
        if given[index] not in OWN_HEADERS:
            lines.append(headers[index])
    lines.append("Content-Length: " + str(len(body)))
    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8") + body


class HttpClient:
    """Sends POST requests and keeps each origin's connection for the next one."""

    def __init__(self) -> None:
        self.mode: str = os.environ.get("ASKME_NATIVE_HTTP", "").strip().lower() or "auto"
        self.streams: dict[str, int] = {}
        self.problems: dict[str, str] = {}

    def mode_problem(self) -> str:
        if self.mode in MODES:
            return ""
        return "ASKME_NATIVE_HTTP must be auto, inprocess or curl"

    def _problem(self, tls: bool) -> str:
        key = "https" if tls else "http"
        if key not in self.problems:
            self.problems[key] = _stream_problem(tls)
        return self.problems[key]

    def post(self, url: str, body: str, headers: list[str], timeout: int) -> HttpReply | None:
        """The reply, or ``None`` where ``curl`` must send this request."""
        if self.mode == "curl":
            return None
        parsed = parse_url(url)
        if parsed is None:
            return None
        problem = self._problem(parsed.tls)
        if self.mode != "inprocess" and (problem or proxied(parsed.tls, parsed.host)):
            return None
        if problem:
            return HttpReply(0, "", "in-process HTTP is unavailable: " + problem)
        request = build_request(parsed, body.encode("utf-8"), headers)
        key = ("https://" if parsed.tls else "http://") + parsed.authority + "#" + str(timeout)
        try:
            handle = self.streams.pop(key, 0)
            if handle != 0 and not _idle(handle):
                _close(handle)
                handle = 0
            kept = handle != 0
            while True:
                if handle == 0:
                    handle = _open(parsed.tls, parsed.host, parsed.port, timeout)
                reader = _Reader(handle)
                try:
                    _send(handle, request)
                    response = read_response(reader)
                    break
                except OSError as exchange_error:
                    _close(handle)
                    handle = 0
                    # A server may close a kept connection just as the request
                    # leaves. Nothing of a reply arrived, so it goes out once
                    # more on a new connection; a timeout is never repeated.
                    if not kept or reader.started or str(exchange_error).endswith("timed out"):
                        raise
                    kept = False
            if response.reusable:
                self.streams[key] = handle
            else:
                _close(handle)
        except OSError as transport_error:
            return HttpReply(0, "", str(transport_error))
        return HttpReply(response.status, response.body.decode("utf-8", "replace"), "")

    def close(self) -> None:
        for key in list(self.streams):
            _close(self.streams.pop(key))
