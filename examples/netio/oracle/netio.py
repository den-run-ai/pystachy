"""Independent CPython oracle: aliases of unmodified standard-library APIs."""

from os import close as close_fd, read, set_blocking
from selectors import EVENT_READ, EVENT_WRITE, DefaultSelector, SelectorKey
from socket import (
    AF_INET, AF_UNIX, SHUT_RD, SHUT_RDWR, SHUT_WR, SOCK_STREAM, SOL_SOCKET,
    SO_ERROR, SO_RCVBUF, SO_REUSEADDR, SO_SNDBUF, socket, socketpair,
)

Socket = socket

__all__ = [
    "AF_INET", "AF_UNIX", "SHUT_RD", "SHUT_RDWR", "SHUT_WR", "SOCK_STREAM", "SOL_SOCKET",
    "SO_ERROR", "SO_RCVBUF", "SO_REUSEADDR", "SO_SNDBUF", "EVENT_READ", "EVENT_WRITE",
    "DefaultSelector", "SelectorKey", "Socket", "socket", "socketpair", "read", "set_blocking", "close_fd",
]
