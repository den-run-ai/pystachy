# pystachy: dynamic-any
"""The same bounded, binary-safe scenarios run against stdlib and the C bridge."""

import errno
import os
import sys
import time

import netio


def wait_one(selector: netio.DefaultSelector, data: int, events: int) -> None:
    ready = selector.select(2.0)
    assert len(ready) == 1, "expected exactly one ready registration"
    key, mask = ready[0]
    assert key.data == data
    assert mask & events == events
    assert mask & ~key.events == 0


def lifecycle(repeat: int) -> None:
    directory = "/proc/self/fd" if sys.platform == "linux" else "/dev/fd"
    before = len(os.listdir(directory))
    for _ in range(repeat):
        left, right = netio.socketpair()
        with left:
            with right:
                with netio.DefaultSelector() as selector:
                    assert left.getblocking()
                    assert left.gettimeout() is None
                    left.settimeout(0.0)
                    assert not left.getblocking()
                    assert left.gettimeout() == 0.0
                    left.settimeout(None)
                    assert left.getblocking()
                    selector.register(left, netio.EVENT_READ, 7)
                    assert right.send(b"a") == 1
                    wait_one(selector, 7, netio.EVENT_READ)
                    assert left.recv(1) == b"a"
                    selector.unregister(left)
        assert left.fileno() == -1
        assert right.fileno() == -1
        left.close()
        right.close()
        selector.close()
    assert len(os.listdir(directory)) == before, "explicit close leaked descriptors"


def binary(repeat: int) -> None:
    payload = b"\x00hello\xff\x80\x00world\r\n\x00"
    for _ in range(repeat):
        left, right = netio.socketpair()
        try:
            assert left.recv(0) == b""
            assert left.send(b"") == 0
            assert left.send(payload) == len(payload)
            received = b""
            while len(received) < len(payload):
                received += right.recv(3)
            assert received == payload
            left.shutdown(netio.SHUT_WR)
            assert right.recv(8) == b""
            assert right.send(b"reply\x00") == 6
            assert left.recv(6) == b"reply\x00"
            right.shutdown(netio.SHUT_WR)
            assert left.recv(1) == b""
        finally:
            left.close()
            right.close()


def selector_keys(repeat: int) -> None:
    for _ in range(repeat):
        left, right = netio.socketpair()
        selector = netio.DefaultSelector()
        try:
            left.setblocking(False)
            key = selector.register(left, netio.EVENT_READ, 11)
            assert key.fileobj is left
            assert key.fd == left.fileno()
            assert key.events == netio.EVENT_READ
            assert key.data == 11
            assert selector.get_key(left.fileno()) == key
            try:
                selector.register(left.fileno(), netio.EVENT_WRITE)
                raise AssertionError("duplicate registration accepted")
            except KeyError:
                pass
            for events in [0, -1, 4]:
                try:
                    selector.register(right, events)
                    raise AssertionError("invalid event mask accepted")
                except ValueError:
                    pass
            assert selector.get_key(left) == key
            replacement = selector.modify(left, netio.EVENT_WRITE, 12)
            assert replacement.fileobj is left
            assert replacement.events == netio.EVENT_WRITE
            assert key.events == netio.EVENT_READ
            wait_one(selector, 12, netio.EVENT_WRITE)
            selector.modify(left, netio.EVENT_READ, 13)
            assert selector.select(0.0) == []
            assert right.send(b"r") == 1
            wait_one(selector, 13, netio.EVENT_READ)
            assert left.recv(1) == b"r"
            removed = selector.unregister(left.fileno())
            assert removed.data == 13
            for missing in [left.fileno(), right.fileno()]:
                try:
                    selector.get_key(missing)
                    raise AssertionError("unregistered descriptor found")
                except KeyError:
                    pass
                try:
                    selector.unregister(missing)
                    raise AssertionError("unregistered descriptor removed")
                except KeyError:
                    pass
            try:
                selector.register(-1, netio.EVENT_READ)
                raise AssertionError("invalid descriptor accepted")
            except ValueError:
                pass
            selector.register(left.fileno(), netio.EVENT_WRITE)
            key2, mask = selector.select(2.0)[0]
            assert key2.fileobj == left.fileno()
            assert key2.data is None
            assert mask == netio.EVENT_WRITE
            selector.unregister(left.fileno())
            selector.register(left, netio.EVENT_READ, 14)
            old_fd = left.fileno()
            left.close()
            assert selector.get_key(left).fd == old_fd
            assert selector.unregister(left).fd == old_fd
            selector.register(right, netio.EVENT_READ, 20)
            right_fd = right.fileno()
            right.close()
            try:
                selector.modify(right_fd, netio.EVENT_WRITE)
                raise AssertionError("closed descriptor modified")
            except OSError:
                pass
            try:
                selector.get_key(right_fd)
                raise AssertionError("failed modification retained its registration")
            except KeyError:
                pass
        finally:
            selector.close()
            left.close()
            right.close()


def readiness(repeat: int) -> None:
    for _ in range(repeat):
        first, peer1 = netio.socketpair()
        second, peer2 = netio.socketpair()
        selector = netio.DefaultSelector()
        try:
            selector.register(first, netio.EVENT_READ, 1)
            selector.register(second, netio.EVENT_READ, 2)
            assert peer2.send(b"b") == 1
            wait_one(selector, 2, netio.EVENT_READ)
            assert peer1.send(b"a") == 1
            seen = 0
            for key, mask in selector.select(2.0):
                assert mask == netio.EVENT_READ
                if key.data == 1:
                    seen |= 1
                elif key.data == 2:
                    seen |= 2
                else:
                    raise AssertionError("unexpected readiness key")
            assert seen == 3
            assert first.recv(1) == b"a"
            assert second.recv(1) == b"b"
            assert selector.select(-1.0) == []
        finally:
            selector.close()
            first.close()
            second.close()
            peer1.close()
            peer2.close()


def backpressure(repeat: int) -> None:
    for _ in range(repeat):
        left, right = netio.socketpair()
        selector = netio.DefaultSelector()
        try:
            left.setsockopt(netio.SOL_SOCKET, netio.SO_SNDBUF, 4096)
            assert left.getsockopt(netio.SOL_SOCKET, netio.SO_SNDBUF) > 0
            left.setblocking(False)
            right.setblocking(False)
            try:
                right.recv(1)
                raise AssertionError("empty nonblocking socket did not block")
            except BlockingIOError:
                pass
            total = 0
            blocked = False
            partial = False
            payload = b"x" * 65536
            while total < 8388608:
                try:
                    count = left.send(payload)
                    assert 0 < count <= len(payload)
                    if count < len(payload):
                        partial = True
                    total += count
                except BlockingIOError:
                    blocked = True
                    break
            assert blocked and total > 0, "send queue did not exert backpressure"
            assert partial, "fixture did not exercise partial writes"
            selector.register(left, netio.EVENT_WRITE, 1)
            assert selector.select(0.0) == []
            selector.register(right, netio.EVENT_READ, 2)
            wait_one(selector, 2, netio.EVENT_READ)
            received = 0
            while received < total:
                chunk = right.recv(min(65536, total - received))
                assert chunk and chunk == b"x" * len(chunk)
                received += len(chunk)
            selector.unregister(right)
            wait_one(selector, 1, netio.EVENT_WRITE)
            try:
                right.recv(1)
                raise AssertionError("drained socket did not block")
            except BlockingIOError:
                pass
            left.shutdown(netio.SHUT_WR)
            assert right.recv(1) == b""
        finally:
            selector.close()
            left.close()
            right.close()


def tcp(repeat: int) -> None:
    for _ in range(repeat):
        listener = netio.socket()
        client = netio.socket()
        selector = netio.DefaultSelector()
        try:
            listener.setsockopt(netio.SOL_SOCKET, netio.SO_REUSEADDR, 1)
            assert listener.getsockopt(netio.SOL_SOCKET, netio.SO_REUSEADDR) == 1
            listener.bind(("127.0.0.1", 0))
            address = listener.getsockname()
            assert address[0] == "127.0.0.1" and address[1] > 0
            listener.listen()
            listener.setblocking(False)
            client.setblocking(False)
            result = client.connect_ex(address)
            assert result in [0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY]
            selector.register(client, netio.EVENT_WRITE, 1)
            wait_one(selector, 1, netio.EVENT_WRITE)
            assert client.getsockopt(netio.SOL_SOCKET, netio.SO_ERROR) == 0
            selector.unregister(client)
            selector.register(listener, netio.EVENT_READ, 2)
            wait_one(selector, 2, netio.EVENT_READ)
            accepted, peer = listener.accept()
            try:
                assert accepted.getblocking()
                assert peer == client.getsockname()
                assert accepted.getsockname() == address
                assert client.getpeername() == address
                assert client.send(b"tcp\x00") == 4
                assert accepted.recv(4) == b"tcp\x00"
                accepted.shutdown(netio.SHUT_WR)
                selector.unregister(listener)
                selector.register(client, netio.EVENT_READ, 3)
                wait_one(selector, 3, netio.EVENT_READ)
                assert client.recv(1) == b""
            finally:
                accepted.close()
        finally:
            selector.close()
            client.close()
            listener.close()


def blocking_connect(repeat: int) -> None:
    for _ in range(repeat):
        listener = netio.socket()
        client = netio.socket()
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            client.connect(listener.getsockname())
            accepted, peer = listener.accept()
            try:
                assert peer == client.getsockname()
                assert accepted.send(b"ok") == 2
                assert client.recv(2) == b"ok"
            finally:
                accepted.close()
        finally:
            client.close()
            listener.close()


def refused(repeat: int) -> None:
    # Keep the local port reserved without listening, so another process cannot take it.
    for _ in range(repeat):
        reservation = netio.socket()
        client = netio.socket()
        selector = netio.DefaultSelector()
        try:
            reservation.bind(("127.0.0.1", 0))
            client.setblocking(False)
            result = client.connect_ex(reservation.getsockname())
            if result == errno.ECONNREFUSED:
                pass
            else:
                assert result in [errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY]
                selector.register(client, netio.EVENT_WRITE, 1)
                wait_one(selector, 1, netio.EVENT_WRITE)
                assert client.getsockopt(netio.SOL_SOCKET, netio.SO_ERROR) == errno.ECONNREFUSED
        finally:
            selector.close()
            client.close()
            reservation.close()


def timeouts(repeat: int) -> None:
    with netio.DefaultSelector() as selector:
        for _ in range(repeat):
            assert selector.select(0.0) == []
            assert selector.select(-0.5) == []
        start = time.monotonic()
        assert selector.select(0.015) == []
        assert time.monotonic() - start >= 0.014, "finite timeout returned early"
    left, right = netio.socketpair()
    try:
        with netio.DefaultSelector() as selector2:
            selector2.register(left, netio.EVENT_READ, 4)
            assert right.send(b"x") == 1
            wait_one(selector2, 4, netio.EVENT_READ)
            # None is safe here: the socket is already ready before entering the wait.
            ready = selector2.select(None)
            assert len(ready) == 1 and ready[0][0].data == 4
            assert left.recv(1) == b"x"
    finally:
        left.close()
        right.close()


def fd_reuse(repeat: int) -> None:
    with netio.DefaultSelector() as selector:
        for _ in range(repeat):
            first, peer = netio.socketpair()
            old = first.fileno()
            selector.register(first, netio.EVENT_READ, 1)
            first.close()
            peer.close()
            replacement, other = netio.socketpair()
            try:
                assert replacement.fileno() == old, "fixture did not reuse the descriptor"
                assert selector.unregister(old).data == 1
                selector.register(replacement, netio.EVENT_READ, 2)
                assert selector.select(0.0) == []
                assert other.send(b"new") == 3
                wait_one(selector, 2, netio.EVENT_READ)
                assert replacement.recv(3) == b"new"
                selector.unregister(replacement)
            finally:
                replacement.close()
                other.close()


def closed_errors(repeat: int) -> None:
    for _ in range(repeat):
        left, right = netio.socketpair()
        try:
            right.close()
            try:
                left.send(b"closed")
                raise AssertionError("closed peer accepted bytes")
            except BrokenPipeError:
                pass
            left.close()
            assert left.recv(0) == b""
            try:
                left.recv(1)
                raise AssertionError("closed descriptor received bytes")
            except OSError:
                pass
            try:
                left.setblocking(False)
                raise AssertionError("closed descriptor changed flags")
            except OSError:
                pass
            try:
                netio.read(-1, 0)
                raise AssertionError("os.read accepted an invalid descriptor")
            except OSError:
                pass
        finally:
            left.close()
            right.close()


def inherited_pipe(fd: int) -> None:
    assert fd > 1024, "high descriptor fixture is below FD_SETSIZE"
    try:
        netio.set_blocking(fd, False)
        with netio.DefaultSelector() as selector:
            key = selector.register(fd, netio.EVENT_READ, 99)
            assert key.fd == fd and key.fileobj == fd
            wait_one(selector, 99, netio.EVENT_READ)
            assert netio.read(fd, 2) == b"hi"
            assert netio.read(fd, 8) == b"\x00\xff\n"
            assert netio.read(fd, 1) == b""
            assert selector.unregister(fd).data == 99
    finally:
        netio.close_fd(fd)


def main() -> None:
    case = sys.argv[1]
    repeat = int(sys.argv[2])
    assert repeat > 0
    if case == "lifecycle":
        lifecycle(repeat)
    elif case == "binary":
        binary(repeat)
    elif case == "selector_keys":
        selector_keys(repeat)
    elif case == "readiness":
        readiness(repeat)
    elif case == "backpressure":
        backpressure(repeat)
    elif case == "tcp":
        tcp(repeat)
    elif case == "blocking_connect":
        blocking_connect(repeat)
    elif case == "refused":
        refused(repeat)
    elif case == "timeouts":
        timeouts(repeat)
    elif case == "fd_reuse":
        fd_reuse(repeat)
    elif case == "closed_errors":
        closed_errors(repeat)
    elif case == "inherited_pipe":
        inherited_pipe(int(sys.argv[3]))
    else:
        raise ValueError("unknown probe scenario")
    print(case, repeat, "ok")


if __name__ == "__main__":
    main()
