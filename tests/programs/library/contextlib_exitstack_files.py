# contextlib.ExitStack entering files, generator context managers, closing() and nullcontext().
import os
import tempfile
from contextlib import contextmanager, closing, nullcontext
from contextlib import ExitStack


@contextmanager
def tag(log: list[str], name: str):
    log.append("<" + name + ">")
    try:
        yield name.upper()
    finally:
        log.append("</" + name + ">")


class Res:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def close(self) -> None:
        self.log.append("closed")


def main() -> None:
    d = tempfile.mkdtemp()
    names = [os.path.join(d, "a.txt"), os.path.join(d, "b.txt")]
    for n in names:
        with open(n, "w") as f:
            f.write("data " + os.path.basename(n) + "\n")
    log: list[str] = []
    with ExitStack() as stack:
        files = [stack.enter_context(open(fname)) for fname in names]
        up = stack.enter_context(tag(log, "t"))
        r = stack.enter_context(closing(Res(log)))
        stack.enter_context(nullcontext())
        for f in files:
            log.append(f.read().strip())
        log.append(up)
    print(log)
    print([f.closed for f in files])


main()
