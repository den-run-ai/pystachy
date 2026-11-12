"""Host adapters for the native AskMe port: paths, files, processes and HTTP.

``askme.py`` reaches the operating system through ``pathlib``, ``subprocess``,
``hashlib``, ``shutil`` and ``requests``. A Pystachy executable has none of
those, so this module provides the same operations from the small surface every
runtime shares: ``os``, ``os.path``, ``open()`` and ``os.system()``.

Processes run through POSIX ``sh`` with their output captured in a private
scratch directory, on every runtime alike. HTTP is sent in-process by
``native_http`` and falls back to ``curl`` behind a proxy or where the stream
libraries are missing.
This is not a sandbox: commands run with the launching user's permissions.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

from native_http import HttpClient, HttpReply

PROCESS_TERMINATION_GRACE = "0.2"  # seconds between TERM and KILL on timeout


# --- pure POSIX paths ------------------------------------------------------
#
# These follow pathlib.PurePosixPath: empty and "." segments disappear, ".."
# is kept, and exactly two leading slashes are a distinct root.


def path_root(path: str) -> str:
    if path.startswith("//") and not path.startswith("///"):
        return "//"
    if path.startswith("/"):
        return "/"
    return ""


def path_parts(path: str) -> list[str]:
    """Segments after the root, as ``PurePosixPath(path).parts`` keeps them."""
    return [part for part in path.split("/") if part and part != "."]


def _path_build(root: str, parts: list[str]) -> str:
    text = root + "/".join(parts)
    return text if text else "."


def path_str(path: str) -> str:
    """``str(PurePosixPath(path))``."""
    return _path_build(path_root(path), path_parts(path))


def path_is_absolute(path: str) -> bool:
    return path.startswith("/")


def path_name(path: str) -> str:
    """``PurePosixPath(path).name``: the final segment, or ``""``."""
    parts = path_parts(path)
    return parts[-1] if parts else ""


def path_parent(path: str) -> str:
    """``str(PurePosixPath(path).parent)``."""
    parts = path_parts(path)
    if not parts:
        return path_str(path)
    return _path_build(path_root(path), parts[:-1])


def path_join(base: str, other: str) -> str:
    """``str(PurePosixPath(base) / other)``."""
    if path_is_absolute(other):
        return path_str(other)
    return _path_build(path_root(base), path_parts(base) + path_parts(other))


def path_depth(path: str) -> int:
    """``len(PurePosixPath(path).parts)``."""
    return len(path_parts(path)) + (1 if path_root(path) else 0)


def path_relative_to(path: str, base: str) -> str | None:
    """``str(PurePosixPath(path).relative_to(base))``, or None when not below it."""
    parts = path_parts(path)
    base_parts = path_parts(base)
    if path_root(path) != path_root(base) or len(base_parts) > len(parts):
        return None
    if parts[: len(base_parts)] != base_parts:
        return None
    return _path_build("", parts[len(base_parts) :])


def path_resolve(path: str) -> str:
    """``str(Path(path).resolve(strict=False))``."""
    return path_str(os.path.realpath(path))


# --- files -----------------------------------------------------------------


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as stream:
        return stream.read()


def byte_length(data: bytes) -> int:
    """``len(data)`` as a plain ``int`` result.

    Pystachy's IR check does not yet accept a bytes length stored directly
    as a JSON value; it accepts the result of a call.
    """
    return len(data)


def _universal_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: str) -> str:
    """``Path(path).read_text()`` for UTF-8: strict decoding, newlines translated."""
    return _universal_newlines(read_bytes(path).decode("utf-8"))


def read_text_replace(path: str) -> str:
    """``Path(path).read_text(errors="replace")`` for UTF-8."""
    return _universal_newlines(read_bytes(path).decode("utf-8", "replace"))


def write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(content)


def append_text(path: str, content: str) -> None:
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(content)


def list_dir(path: str) -> tuple[list[str], list[str], bool]:
    """One ``os.walk`` level: (directories, other entries, readable)."""
    dirs: list[str] = []
    files: list[str] = []
    try:
        names = os.listdir(path)
    except OSError:
        return dirs, files, False
    for name in names:
        if os.path.isdir(os.path.join(path, name)):
            dirs.append(name)
        else:
            files.append(name)
    return dirs, files, True


def make_workspace() -> str:
    """A fresh private directory named like ``tempfile.mkdtemp(prefix="askme_")``."""
    created = tempfile.mkdtemp()
    name = os.path.basename(created)
    suffix = name[3:] if name.startswith("tmp") else name
    renamed = os.path.join(os.path.dirname(created), "askme_" + suffix)
    try:
        os.rename(created, renamed)
    except OSError:
        return created
    return renamed


def remove_tree(path: str) -> None:
    shutil.rmtree(path, True)


# --- SHA-256 ---------------------------------------------------------------

_SHA256_K = [
    0x428A2F98,
    0x71374491,
    0xB5C0FBCF,
    0xE9B5DBA5,
    0x3956C25B,
    0x59F111F1,
    0x923F82A4,
    0xAB1C5ED5,
    0xD807AA98,
    0x12835B01,
    0x243185BE,
    0x550C7DC3,
    0x72BE5D74,
    0x80DEB1FE,
    0x9BDC06A7,
    0xC19BF174,
    0xE49B69C1,
    0xEFBE4786,
    0x0FC19DC6,
    0x240CA1CC,
    0x2DE92C6F,
    0x4A7484AA,
    0x5CB0A9DC,
    0x76F988DA,
    0x983E5152,
    0xA831C66D,
    0xB00327C8,
    0xBF597FC7,
    0xC6E00BF3,
    0xD5A79147,
    0x06CA6351,
    0x14292967,
    0x27B70A85,
    0x2E1B2138,
    0x4D2C6DFC,
    0x53380D13,
    0x650A7354,
    0x766A0ABB,
    0x81C2C92E,
    0x92722C85,
    0xA2BFE8A1,
    0xA81A664B,
    0xC24B8B70,
    0xC76C51A3,
    0xD192E819,
    0xD6990624,
    0xF40E3585,
    0x106AA070,
    0x19A4C116,
    0x1E376C08,
    0x2748774C,
    0x34B0BCB5,
    0x391C0CB3,
    0x4ED8AA4A,
    0x5B9CCA4F,
    0x682E6FF3,
    0x748F82EE,
    0x78A5636F,
    0x84C87814,
    0x8CC70208,
    0x90BEFFFA,
    0xA4506CEB,
    0xBEF9A3F7,
    0xC67178F2,
]

_MASK32 = 0xFFFFFFFF


def _rotr(value: int, count: int) -> int:
    return ((value >> count) | (value << (32 - count))) & _MASK32


def sha256_pure(data: bytes) -> str:
    """Hex SHA-256 in 64-bit integer arithmetic, for runtimes without hashlib."""
    state = [
        0x6A09E667,
        0xBB67AE85,
        0x3C6EF372,
        0xA54FF53A,
        0x510E527F,
        0x9B05688C,
        0x1F83D9AB,
        0x5BE0CD19,
    ]
    bit_length = len(data) * 8
    tail = [0x80]
    while (len(data) + len(tail)) % 64 != 56:
        tail.append(0)
    for shift in (56, 48, 40, 32, 24, 16, 8, 0):
        tail.append((bit_length >> shift) & 0xFF)
    message = data + bytes(tail)
    words = [0] * 64
    for offset in range(0, len(message), 64):
        for i in range(16):
            j = offset + i * 4
            words[i] = (
                (message[j] << 24) | (message[j + 1] << 16) | (message[j + 2] << 8) | message[j + 3]
            )
        for i in range(16, 64):
            w15 = words[i - 15]
            w2 = words[i - 2]
            s0 = _rotr(w15, 7) ^ _rotr(w15, 18) ^ (w15 >> 3)
            s1 = _rotr(w2, 17) ^ _rotr(w2, 19) ^ (w2 >> 10)
            words[i] = (words[i - 16] + s0 + words[i - 7] + s1) & _MASK32
        a = state[0]
        b = state[1]
        c = state[2]
        d = state[3]
        e = state[4]
        f = state[5]
        g = state[6]
        h = state[7]
        for i in range(64):
            big1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
            choose = (e & f) ^ ((e ^ _MASK32) & g)
            temp1 = (h + big1 + choose + _SHA256_K[i] + words[i]) & _MASK32
            big0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
            majority = (a & b) ^ (a & c) ^ (b & c)
            temp2 = (big0 + majority) & _MASK32
            h = g
            g = f
            f = e
            e = (d + temp1) & _MASK32
            d = c
            c = b
            b = a
            a = (temp1 + temp2) & _MASK32
        state[0] = (state[0] + a) & _MASK32
        state[1] = (state[1] + b) & _MASK32
        state[2] = (state[2] + c) & _MASK32
        state[3] = (state[3] + d) & _MASK32
        state[4] = (state[4] + e) & _MASK32
        state[5] = (state[5] + f) & _MASK32
        state[6] = (state[6] + g) & _MASK32
        state[7] = (state[7] + h) & _MASK32
    return "".join([f"{value:08x}" for value in state])


def sha256_hex(data: bytes) -> str:
    """``hashlib.sha256(data).hexdigest()``; Pystachy uses the pure fallback."""
    if sys.implementation.name != "pystachy":
        import hashlib

        return hashlib.sha256(data).hexdigest()
    return sha256_pure(data)


# --- shell -----------------------------------------------------------------


def shell_quote(text: str) -> str:
    """One POSIX shell word. NUL cannot appear in a command line."""
    if "\x00" in text:
        raise ValueError("embedded null byte")
    return "'" + text.replace("'", "'\\''") + "'"


def shell_exit_code(status: int) -> int:
    """Exit code from an ``os.system`` wait status (128+N for signal N)."""
    if status & 0x7F == 0:
        return (status >> 8) & 0xFF
    return 128 + (status & 0x7F)


def run_command(script: str) -> int:
    """Run ``sh -c script`` and return its exit code.

    ``os.system`` is the one process primitive every supported runtime has.
    """
    return shell_exit_code(os.system(script))  # ty: ignore[deprecated]


def find_on_path(name: str) -> str:
    """First regular file called ``name`` on PATH, or ``""``."""
    for directory in os.environ.get("PATH", "").split(":"):
        candidate = os.path.join(directory if directory else ".", name)
        if os.path.isfile(candidate):
            return candidate
    return ""


def utc_clock(now: float) -> str:
    """``HH:MM:SS`` in UTC for a console line."""
    seconds = int(now) % 86400
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


class CapturedProcess:
    """Result of one captured command; ``timed_out`` replaces TimeoutExpired."""

    def __init__(self, returncode: int, stdout: str, stderr: str, timed_out: bool) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out


class HostProbe:
    def __init__(self, system: str, machine: str, found: list[str]) -> None:
        self.system = system
        self.machine = machine
        self.found = found


class Host:
    """Owns the private scratch directory behind every external command."""

    def __init__(self) -> None:
        self._scratch = ""
        self._sequence = 0
        self._timeout_tool = ""
        self._timeout_checked = False
        self._signal_reset = ""
        self._signal_checked = False
        self.http = HttpClient()

    def scratch(self) -> str:
        if not self._scratch:
            self._scratch = tempfile.mkdtemp()
        return self._scratch

    def cleanup(self) -> None:
        self.http.close()
        if self._scratch:
            remove_tree(self._scratch)
            self._scratch = ""

    def _file(self, label: str) -> str:
        self._sequence += 1
        return os.path.join(self.scratch(), f"{label}-{self._sequence}")

    def timeout_tool(self) -> str:
        """GNU/BusyBox ``timeout`` (``gtimeout`` on macOS), or ``""`` for the sh watchdog."""
        if not self._timeout_checked:
            self._timeout_checked = True
            override = os.environ.get("ASKME_NATIVE_TIMEOUT_TOOL", "")
            if override == "none":
                self._timeout_tool = ""
            elif override:
                self._timeout_tool = override
            else:
                self._timeout_tool = find_on_path("timeout") or find_on_path("gtimeout")
        return self._timeout_tool

    def signal_reset(self) -> str:
        """A command prefix that restores default signal actions, or ``""``.

        Every runtime here ignores SIGPIPE and ``os.system`` passes that on, so
        ``producer | head`` would report "Broken pipe" where ``askme.py``'s
        ``subprocess`` child stops quietly. The wrapper's background job also
        starts with SIGINT and SIGQUIT ignored. A shell cannot undo an
        inherited ignore; GNU ``env`` or ``perl`` can.
        """
        if not self._signal_checked:
            self._signal_checked = True
            override = os.environ.get("ASKME_NATIVE_SIGNAL_RESET", "")
            if override == "none":
                self._signal_reset = ""
            elif run_command("env --default-signal=PIPE,INT,QUIT true 2>/dev/null") == 0:
                self._signal_reset = "env --default-signal=PIPE,INT,QUIT "
            elif find_on_path("perl"):
                self._signal_reset = (
                    "perl -e '$SIG{PIPE}=$SIG{INT}=$SIG{QUIT}=\"DEFAULT\";exec @ARGV;exit 127' "
                )
        return self._signal_reset

    def run_shell(self, command: str, timeout: int, cwd: str) -> CapturedProcess:
        """Run ``/bin/sh -c command`` in ``cwd`` with captured output and a deadline.

        With ``timeout`` the command gets its own process group; at the
        deadline the group receives TERM and, after a short grace period, KILL.
        The KILL reaches the group even when the command's shell has already
        exited, so a descendant that ignores TERM cannot keep changing the
        workspace. Descendants that leave the group can outlive it, as with
        ``askme.py``'s session-based cleanup. The sh fallback signals the
        command's shell only.
        """
        out_path = self._file("stdout")
        err_path = self._file("stderr")
        prefix = (
            "exec > "
            + shell_quote(out_path)
            + " 2> "
            + shell_quote(err_path)
            + "; cd -- "
            + shell_quote(cwd)
            + " || exit 1; "
        )
        tool = self.timeout_tool()
        reset = self.signal_reset()
        if tool:
            # timeout leads a new process group and signals it, but sends its
            # KILL only while its own child lives. The wrapper finishes the
            # job: after a timeout it kills whatever is left of the group.
            script = (
                prefix
                + reset
                + shell_quote(tool)
                + " -k "
                + PROCESS_TERMINATION_GRACE
                + " "
                + str(timeout)
                + " /bin/sh -c "
                + shell_quote(command)
                + " <&0 & group=$!; wait $group; status=$?; "
                + "case $status in 124|137) if kill -s 0 -- -$group 2>/dev/null; then sleep "
                + PROCESS_TERMINATION_GRACE
                + "; kill -s KILL -- -$group 2>/dev/null; fi;; esac; exit $status"
            )
        else:
            # No timeout utility: a plain sh watchdog signals the command's own
            # shell. Without job control it cannot signal the whole group.
            script = (
                prefix
                + reset
                + "/bin/sh -c "
                + shell_quote(command)
                + " & child=$!; ( sleep "
                + str(timeout)
                + "; kill -TERM $child 2>/dev/null; sleep "
                + PROCESS_TERMINATION_GRACE
                + "; kill -KILL $child 2>/dev/null ) >/dev/null 2>&1 & watch=$!; "
                + "wait $child; status=$?; kill -TERM $watch 2>/dev/null; exit $status"
            )
        started = time.monotonic()
        code = run_command(script)
        elapsed = time.monotonic() - started
        timed_out = elapsed >= timeout and code in (124, 137, 143)
        stdout = ""
        stderr = ""
        if not timed_out:
            stdout = _read_captured(out_path)
            stderr = _read_captured(err_path)
        _remove_quietly(out_path)
        _remove_quietly(err_path)
        return CapturedProcess(code, stdout, stderr, timed_out)

    def http_post(self, url: str, body: str, headers: list[str], timeout: int) -> HttpReply:
        """POST ``body`` in-process, or with curl where that cannot serve the request.

        The in-process client keeps each origin's connection open. curl remains
        for proxies and for machines without the stream libraries; its headers
        travel in a private file, never argv.
        """
        if not (url.startswith("http://") or url.startswith("https://")):
            return HttpReply(0, "", f"Invalid URL {url!r}: only http:// and https:// are supported")
        for header in headers:
            if "\r" in header or "\n" in header or "\x00" in header:
                return HttpReply(0, "", "invalid header value")
        direct = self.http.post(url, body, headers, timeout)
        if direct is not None:
            return direct
        request_path = self._file("request")
        header_path = self._file("headers")
        reply_path = self._file("reply")
        status_path = self._file("status")
        error_path = self._file("curl-error")
        write_text(request_path, body)
        write_text(header_path, "".join([header + "\n" for header in headers]))
        try:
            command = (
                "curl --silent --show-error --max-time "
                + str(timeout)
                + " --request POST --header "
                + shell_quote("@" + header_path)
                + " --data-binary "
                + shell_quote("@" + request_path)
                + " --output "
                + shell_quote(reply_path)
                + " --write-out '%{http_code}' "
                + shell_quote(url)
                + " > "
                + shell_quote(status_path)
                + " 2> "
                + shell_quote(error_path)
            )
            code = run_command(command)
            if code != 0:
                detail = _read_captured(error_path).strip()
                return HttpReply(
                    0, "", f"curl exit {code}: {detail}" if detail else f"curl exit {code}"
                )
            status_text = _read_captured(status_path).strip()
            if not status_text.isdigit():
                return HttpReply(0, "", "curl reported no HTTP status")
            text = _read_captured(reply_path) if os.path.exists(reply_path) else ""
            return HttpReply(int(status_text), text, "")
        finally:
            _remove_quietly(header_path)
            _remove_quietly(request_path)
            _remove_quietly(reply_path)
            _remove_quietly(status_path)
            _remove_quietly(error_path)

    def probe(self, names: list[str]) -> HostProbe:
        """Platform identity plus which of ``names`` are commands, in one ``sh``."""
        out_path = self._file("probe")
        checks = ""
        for name in names:
            checks += (
                " command -v "
                + shell_quote(name)
                + " >/dev/null 2>&1 && echo "
                + shell_quote(name)
                + ";"
            )
        run_command(
            "{ uname -s; uname -m;" + checks + " } > " + shell_quote(out_path) + " 2>/dev/null"
        )
        lines: list[str] = []
        if os.path.exists(out_path):
            lines = _read_captured(out_path).split("\n")
            _remove_quietly(out_path)
        system = lines[0] if len(lines) > 0 and lines[0] else sys.platform
        machine = lines[1] if len(lines) > 1 else ""
        found = [line for line in lines[2:] if line]
        return HostProbe(system, machine, found)


def _read_captured(path: str) -> str:
    try:
        return read_bytes(path).decode("utf-8", "replace")
    except OSError:
        return ""


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
