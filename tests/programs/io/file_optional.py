# TextIO | None: parameters, returns, fields, locals and list items that hold a file or None.
import os
import sys
import tempfile
from typing import TextIO


def read_all(text: str = "", fd: TextIO | None = None) -> str:
    if fd is not None and not fd.closed:
        text = fd.read()
        fd = None
    if fd:
        return "unreachable"
    return text


def pick(path: str, use: bool) -> TextIO | None:
    if use:
        return open(path)
    return None


class Holder:
    def __init__(self, fd: TextIO | None) -> None:
        self.fd = fd
        self.other: TextIO | None = None

    def first(self) -> str:
        if self.fd is None:
            return "<none>"
        fd = self.fd
        return fd.readline().strip()


def main() -> None:
    d = tempfile.mkdtemp()
    p = os.path.join(d, "a.txt")
    with open(p, "w") as f:
        f.write("line one\nline two\n")
    print(read_all("fallback"))
    with open(p) as f:
        print(read_all(fd=f).strip())
    g = pick(p, True)
    h = pick(p, False)
    print(g is None, h is None, g is not None, bool(h), bool(g))
    if g is not None:
        print(g.readline().strip())
        g.close()
    print(Holder(None).first(), Holder(None).other is None)
    with open(p) as f:
        print(Holder(f).first())
    out: TextIO | None = None
    if len(sys.argv) > 5:
        out = sys.stdout
    print(out is None)
    out = sys.stdout
    if out is not None:
        out.write("written\n")
    files: list[TextIO | None] = [None]
    print(len(files), files[0] is None)


main()
