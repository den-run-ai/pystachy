# ast_serialize's bytes read back with librt.internal, mypy's cache codec (both lib/ here, the
# Rust and C extensions in CPython): a walk over the tags of the serialized tree and imports of
# parse() and parse_type_string(), counting each node tag and summing the ints and string lengths
# the reader decodes.
from ast_serialize import parse, parse_type_string
from librt.internal import ReadBuffer, read_float, read_int, read_str, read_tag

SOURCE = """import os, sys as system
from collections.abc import Callable
x: dict[str, list[int]] = {'a': [1, 2, 3]}  # type: ignore
def f[T](a: T, *args: int, k: 'str | None' = None, **kw) -> T:
    '''Return a.'''
    if sys.version_info >= (3, 12) and a:
        return [i * 2 for i in range(10) if i % 3][0]
    elif not kw:
        raise ValueError(f'bad {a!r:>{k}} {x=}')
    for i, (j, *k) in enumerate(args):
        while i < 3.5e2:
            i += 1j.imag or 0x1F
    with open(a) as fh, lock:
        del fh
    try:
        yield from g(*args, **kw)
    except* (TypeError, KeyError) as e:
        pass
    finally:
        lambda q=1: q
    match a:
        case [1, *rest] | {'k': rest}: pass
        case Point(x=0) as p if p: pass
    return a
@decorator(1)
class C(Base, metaclass=Meta):
    attr = b'\\x00bytes'
    async def m(self) -> None:
        async for z in self:
            await z
"""


def walk(data: bytes, counts: dict[int, int]) -> tuple[int, int, int]:
    # (tags read, sum of the ints, total length of the strings)
    buf = ReadBuffer(data)
    ntags = 0
    total = 0
    strlen = 0
    while True:
        try:
            tag = read_tag(buf)
        except ValueError:
            break
        ntags += 1
        if tag == 3:
            total += read_int(buf)
        elif tag == 4:
            strlen += len(read_str(buf))
        elif tag == 6:
            total += int(read_float(buf) * 100)
        elif tag == 20 or tag == 30:
            total += read_int(buf)
        elif tag == 21:
            for _ in range(read_int(buf)):
                total += read_int(buf)
        elif tag == 152:
            for _ in range(4):
                total += read_int(buf)
        elif tag > 6:
            counts[tag] = counts.get(tag, 0) + 1
    return ntags, total, strlen


for cv in (0, 5, 7):
    r = parse("reader.py", SOURCE, False, (3, 13), "linux", None, None, cv)
    counts: dict[int, int] = {}
    print(cv, walk(r[0], counts), walk(r[3], counts))
    print("  ", sorted(counts.items()))
counts = {}
for text in ["List[int]", "Dict[str, 'Foo'] | None", "Callable[[Arg(int, 'x')], None]", "1 + 2"]:
    print(repr(text), walk(parse_type_string(text, (1, 0, 1, len(text)), 5), counts))
print("  ", sorted(counts.items()))
